# -*- coding: utf-8 -*-
"""Boletos para shows en ROSSO (primero: Carla Gibert, 25-nov-2026).

Catálogo: boletos.json (público, lo lee también build.py). El trato con cada artista (fijo,
porcentaje, comisión acordada) vive en boletos_tratos.json, que NO va al repo público.

Compra: la página del show pide una Checkout Session (/boletos/checkout). Primero se crea la
sesión en Stripe y luego, en una sola escritura, el apartado de lugares; si ya no hay lugar se
expira la sesión antes de que el cliente la vea. El pago se registra por el webhook o, si el
webhook se atrasa, por la página de gracias, que le pregunta a Stripe (/boletos/estado). Los dos
caminos usan la misma función idempotente (la llave es el id de la sesión de Stripe).

Libro de cupo: un JSON por sesión del show en un bucket propio (BOLETOS_BUCKET, con versiones y
sin regla de borrado). Cada cambio es leer -> aplicar -> escribir con if_generation_match, que es
lo único atómico entre las dos instancias de Cloud Run. La hoja de Google es sólo un espejo.

Los apartados duran 20 min. Al vencer no se sueltan a ciegas: se expira la sesión en Stripe y se
decide con lo que Stripe conteste (expirada: se suelta; pagada: se registra la compra).

Puerta (/boletos/puerta/*): lista, entradas, ventas en puerta, cortesías, anular, mover de
sesión, soltar apartados, pausa, cupo y avisos a Telegram. PIN de puerta (PUERTA_PIN) o el de
barra (CANJE_PIN), con el mismo freno de intentos del resto del API.
"""
import csv
import datetime as dt
import hmac
import io
import json
import os
import random
import re
import secrets
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

import requests

import freno as freno_mod
import regalo as regalo_mod

AQUI = Path(__file__).parent
CATALOGO = AQUI / "boletos.json"
TRATOS = AQUI / "boletos_tratos.json"

STRIPE_KEY = os.environ.get("STRIPE_KEY", "")
# Versión fija: con la de 2026-09-30.endive ya no existe payment_method_types en Checkout y sin
# fijarla cada llamada usaría la versión que tenga la cuenta.
STRIPE_VERSION = os.environ.get("STRIPE_VERSION", "2026-09-30.endive")
BUCKET = os.environ.get("BOLETOS_BUCKET", "")
LOCAL = os.environ.get("BOLETOS_LOCAL", "")          # carpeta para pruebas en la compu; nunca en Cloud Run
EN_CLOUD_RUN = bool(os.environ.get("K_SERVICE"))
SHEET_ID = os.environ.get("BOLETOS_SHEET_ID", "")
PUERTA_PIN = os.environ.get("PUERTA_PIN", "")
if PUERTA_PIN and (len(PUERTA_PIN) < 6 or not PUERTA_PIN.isdigit()):
    print("PUERTA_PIN ignorado: tiene que ser de 6 dígitos o más")
    PUERTA_PIN = ""
SITIO = os.environ.get("SITIO", "https://rossospeakeasy.com")

PREFIJO = "boletos/"
APARTADO_MIN = 20          # lo que se le guarda el lugar a quien está pagando
STRIPE_EXPIRA_MIN = 31     # Stripe no deja menos de 30 min; el servidor la expira antes (a los 20)
OLVIDAR_APARTADO_H = 6     # un apartado que Stripe nunca resuelve se suelta (y se avisa) a las 6 h
AFORO_MAX = 50             # tarifario.AFORO_TOTAL: el cupo de una sesión nunca pasa de aquí
IVA = 0.16
OPS_GUARDADAS = 300
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O/1/I: se dicta en la puerta
RESERVADOS = {"gracias", "puerta", "show", "estado", "checkout", "cancelar", "liquidacion", "lista-telegram", "huerfana"}
METODOS_PUERTA = {"efectivo", "clip", "transferencia"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

# comisión de Stripe MX publicada (tarjeta nacional), sólo para informar a Pablo
STRIPE_PCT, STRIPE_FIJO = 0.036, 3.0


class Ocupado(Exception):
    """No se pudo escribir el libro después de varios intentos: hay mucha demanda en este momento."""


class SinAlmacen(Exception):
    """No hay dónde guardar el libro de cupo (falta BOLETOS_BUCKET)."""


# Errores pasajeros: se reintenta (el webhook responde 500 y Stripe vuelve a mandar; las rutas, 503).
# RetryError (cuando la librería de GCS agota sus reintentos) es GoogleAPIError, no GoogleAPICallError.
try:
    from google.api_core import exceptions as _gexc
    from google.auth import exceptions as _aexc
    TRANSITORIOS = (Ocupado, SinAlmacen, _gexc.GoogleAPIError, _aexc.GoogleAuthError, requests.RequestException,
                    ConnectionError, TimeoutError)
except ImportError:   # pragma: no cover
    TRANSITORIOS = (Ocupado, SinAlmacen, requests.RequestException, ConnectionError, TimeoutError)


# ------------------------------------------------------------------ catálogo
def _hora_ok(h):
    return bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(h or "")))


def _cargar_catalogo():
    datos = json.loads(CATALOGO.read_text(encoding="utf-8"))
    shows = {}
    for s in datos.get("shows", []):
        slug = s["slug"]
        if not re.fullmatch(r"[a-z0-9-]{2,40}", slug) or slug in RESERVADOS or slug in shows:
            raise ValueError(f"boletos.json: slug inválido o repetido: {slug!r}")
        if s.get("visible", "no") not in ("no", "oculto", "si"):
            raise ValueError(f"boletos.json: visible de {slug} debe ser no, oculto o si")
        dt.date.fromisoformat(s["fecha"])
        if s.get("venta_abre") and dt.datetime.fromisoformat(s["venta_abre"]).tzinfo is not None:
            raise ValueError(f"boletos.json: venta_abre de {slug} va sin zona horaria, en hora de la CDMX (ej. 2026-10-28T12:00)")
        if int(s["precio"]) <= 0 or not 1 <= int(s["max_por_compra"]) <= 10:
            raise ValueError(f"boletos.json: precio o max_por_compra inválido en {slug}")
        ids = set()
        for x in s["sesiones"]:
            if not re.fullmatch(r"[a-z0-9]{1,8}", x["id"]) or x["id"] in ids:
                raise ValueError(f"boletos.json: id de sesión inválido o repetido en {slug}: {x['id']!r}")
            if not _hora_ok(x["hora"]) or not _hora_ok(x.get("puertas", x["hora"])):
                raise ValueError(f"boletos.json: hora inválida en {slug}/{x['id']}")
            if not 1 <= int(x["cupo"]) <= AFORO_MAX:
                raise ValueError(f"boletos.json: cupo fuera de rango en {slug}/{x['id']}")
            ids.add(x["id"])
        shows[slug] = s
    return shows


SHOWS = _cargar_catalogo()


def _sesion_cfg(show, sid):
    return next((x for x in show["sesiones"] if x["id"] == sid), None)


def _trato(slug):
    """El trato con la artista. Si no está el archivo privado, la liquidación lo dice."""
    try:
        return (json.loads(TRATOS.read_text(encoding="utf-8")) or {}).get(slug)
    except FileNotFoundError:
        return None


def configurado():
    return bool(STRIPE_KEY) and (bool(BUCKET) or (bool(LOCAL) and not EN_CLOUD_RUN))


# ------------------------------------------------------------------ tiempo
def _ahora():
    return time.time()


def _ahora_local():
    """Hora de la CDMX: el contenedor corre con TZ=America/Mexico_City."""
    return dt.datetime.now().replace(microsecond=0)


def _inicio(show, ses):
    f = dt.date.fromisoformat(show["fecha"])
    h, m = (int(x) for x in ses["hora"].split(":"))
    if h < 12:   # una sesión a las 00:30 es de la madrugada siguiente
        f += dt.timedelta(days=1)
    return dt.datetime(f.year, f.month, f.day, h, m)


def _cierre_en_linea(show, ses):
    return _inicio(show, ses) - dt.timedelta(minutes=int(show.get("cierra_min_antes", 0)))


def _fin(show, ses):
    return _inicio(show, ses) + dt.timedelta(minutes=int(show.get("duracion_min", 60)))


# ------------------------------------------------------------------ libro de cupo (GCS con compare-and-swap)
_hilo = threading.local()


def _cliente():
    c = getattr(_hilo, "cliente", None)
    if c is None:
        from google.cloud import storage
        c = _hilo.cliente = storage.Client()
    return c


def _reintento():
    """Los reintentos propios de la librería de GCS duran hasta 120 s; aquí, a lo más 4 s por llamada,
    para que el plazo de _mutar sea real y un hilo no se quede colgado."""
    from google.cloud.storage.retry import DEFAULT_RETRY
    acotar = getattr(DEFAULT_RETRY, "with_timeout", None) or DEFAULT_RETRY.with_deadline
    return acotar(4.0)


class _GCS:
    @staticmethod
    def leer(nombre):
        """(datos, generación) de la MISMA versión del objeto; (None, 0) si no existe."""
        from google.api_core import exceptions as gexc
        bucket = _cliente().bucket(BUCKET)
        for _ in range(4):
            blob = bucket.get_blob(nombre, timeout=5, retry=_reintento())
            if blob is None:
                return None, 0
            try:
                # el blob trae su generación: se descarga exactamente esa versión
                return json.loads(blob.download_as_bytes(timeout=5, retry=_reintento())), int(blob.generation)
            except gexc.NotFound:
                continue      # la reemplazaron entre la lectura y la descarga: otra vuelta
        raise Ocupado("el libro cambió demasiadas veces seguidas")

    @staticmethod
    def escribir(nombre, datos, gen):
        """True si se escribió; False si alguien más escribió antes (412)."""
        from google.api_core import exceptions as gexc
        blob = _cliente().bucket(BUCKET).blob(nombre)
        try:
            blob.upload_from_string(json.dumps(datos, ensure_ascii=False, separators=(",", ":")),
                                    content_type="application/json", if_generation_match=gen, timeout=5,
                                    retry=_reintento())
            return True
        except (gexc.PreconditionFailed, gexc.NotFound):
            return False


class _Local:
    """Mismo contrato que _GCS sobre archivos, para probar en la compu (BOLETOS_LOCAL=carpeta)."""
    _lock = threading.Lock()

    @staticmethod
    def _ruta(nombre):
        return Path(LOCAL) / nombre.replace("/", "__")

    @classmethod
    def leer(cls, nombre):
        with cls._lock:
            p = cls._ruta(nombre)
            if not p.exists():
                return None, 0
            d = json.loads(p.read_text(encoding="utf-8"))
            return d["datos"], d["gen"]

    @classmethod
    def escribir(cls, nombre, datos, gen):
        with cls._lock:
            p = cls._ruta(nombre)
            actual = json.loads(p.read_text(encoding="utf-8"))["gen"] if p.exists() else 0
            if actual != gen:
                return False
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"gen": actual + 1, "datos": datos}, ensure_ascii=False), encoding="utf-8")
            return True


def _almacen():
    if BUCKET:
        return _GCS
    if LOCAL and not EN_CLOUD_RUN:
        return _Local
    raise SinAlmacen("falta BOLETOS_BUCKET")


def _nombre(slug, sid):
    return f"{PREFIJO}{slug}/{sid}.json"


def _vacio():
    return {"apartados": {}, "compras": {}, "ops": {}}


def _leer(slug, sid):
    datos, _ = _almacen().leer(_nombre(slug, sid))
    return _completar(datos)


def _completar(d):
    d = d or _vacio()
    for k in ("apartados", "compras", "ops"):
        d.setdefault(k, {})
    return d


def _mutar(nombre, fn, plazo=8.0):
    """Aplica fn(datos) -> (cambió, resultado) y lo escribe sólo si nadie escribió en medio.
    fn no debe tener efectos fuera de `datos`: puede correr varias veces."""
    almacen = _almacen()
    fin = time.monotonic() + plazo
    n = 0
    while True:
        datos, gen = almacen.leer(nombre)
        datos = _completar(datos)
        cambio, resultado = fn(datos)
        if not cambio or almacen.escribir(nombre, datos, gen):
            return resultado
        n += 1
        if time.monotonic() >= fin:
            raise Ocupado(f"{nombre}: {n} choques seguidos")
        time.sleep(random.uniform(0, min(1.0, 0.05 * 2 ** n)))   # retroceso con jitter completo


def _mutar_sesion(slug, sid, fn):
    return _mutar(_nombre(slug, sid), fn)


def _control(slug):
    datos, _ = _almacen().leer(f"{PREFIJO}{slug}/control.json")
    d = datos or {}
    d.setdefault("pausada", False)
    d.setdefault("ajustes", {})
    d["ajustes"].setdefault("cupo", {})
    return d


def _mutar_control(slug, fn):
    def envuelta(d):
        d.setdefault("pausada", False)
        d.setdefault("ajustes", {})
        d["ajustes"].setdefault("cupo", {})
        return fn(d)
    return _mutar(f"{PREFIJO}{slug}/control.json", envuelta)


def _op_hecha(led, op, tok=None):
    """El resultado de una operación que ya se aplicó (reintento por mala señal), marcado como
    repetida. Si la aplicó esta misma solicitud (la escritura entró pero se perdió la respuesta y
    _mutar volvió a correr), `tok` coincide y no cuenta como repetida: hay que avisar igual."""
    e = led["ops"].get(op) if op else None
    if not e:
        return None
    r = e.get("r")
    return dict(r, repetida=tok is None or e.get("tok") != tok) if isinstance(r, dict) else r


def _anotar_op(led, op, resultado, tok=None):
    if not op:
        return
    led["ops"][op] = {"t": int(_ahora()), "r": resultado, "tok": tok}
    if len(led["ops"]) > OPS_GUARDADAS:
        for k in sorted(led["ops"], key=lambda k: led["ops"][k]["t"])[:len(led["ops"]) - OPS_GUARDADAS]:
            del led["ops"][k]


# ------------------------------------------------------------------ cuentas
def _vivas(led):
    return [c for c in led["compras"].values() if c.get("estado", "ok") == "ok"]


def _cupo(show, ses, control):
    return int(control["ajustes"]["cupo"].get(ses["id"], ses["cupo"]))


def _cuentas(led, cupo):
    vivas = _vivas(led)
    vendidos = sum(int(c["cantidad"]) for c in vivas)
    en_pago = sum(int(a["cantidad"]) for a in led["apartados"].values())
    entraron = sum(int(c.get("entraron", 0)) for c in vivas)
    return {"cupo": cupo, "vendidos": vendidos, "en_pago": en_pago, "entraron": entraron,
            "quedan": cupo - vendidos - en_pago}


def _estado_venta(show, ses, control, cuentas, ahora_local=None):
    """abierta | por_abrir | pausada | cerrada_en_linea | pasada | agotada | en_pago"""
    ahora_local = ahora_local or _ahora_local()
    if show.get("venta_abre") and ahora_local < dt.datetime.fromisoformat(show["venta_abre"]):
        return "por_abrir"
    if ahora_local >= _fin(show, ses):
        return "pasada"
    if control.get("pausada"):
        return "pausada"
    if ahora_local >= _cierre_en_linea(show, ses):
        return "cerrada_en_linea"
    if cuentas["quedan"] <= 0:
        return "en_pago" if cuentas["en_pago"] > 0 and cuentas["vendidos"] < cuentas["cupo"] else "agotada"
    return "abierta"


def _codigo_nuevo(slug):
    """XXX-XXX único en todo el show (compras y apartados de todas las sesiones)."""
    usados = set()
    for x in SHOWS[slug]["sesiones"]:
        led = _leer(slug, x["id"])
        usados |= {c.get("codigo") for c in led["compras"].values()}
        usados |= {a.get("codigo") for a in led["apartados"].values()}
    while True:
        cuerpo = "".join(secrets.choice(ALFABETO) for _ in range(6))
        codigo = f"{cuerpo[:3]}-{cuerpo[3:]}"
        if codigo not in usados:
            return codigo


# ------------------------------------------------------------------ limpieza de lo que manda el cliente
def limpiar_nombre(s, n=60):
    s = unicodedata.normalize("NFC", str(s or ""))
    s = "".join(ch for ch in s if ch.isprintable() and ch not in "<>\"'`=")
    return re.sub(r"\s+", " ", s).strip()[:n]


def limpiar_email(s):
    s = str(s or "").strip().lower()[:120]
    return s if EMAIL_RE.match(s) else ""


def limpiar_whatsapp(s):
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) == 10:
        d = "52" + d
    return d if 10 <= len(d) <= 15 else ""


def _tg(s):
    """Escapa texto del cliente para el HTML de Telegram (comillas incluidas)."""
    return (str(s if s is not None else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _sin_acentos(s):
    return "".join(ch for ch in unicodedata.normalize("NFKD", str(s or "")) if not unicodedata.combining(ch)).lower()


def _mascara_email(e):
    if "@" not in (e or ""):
        return ""
    u, d = e.split("@", 1)
    return (u[:1] + "•••@" + d) if u else ""


def _llave_ip(xff, remota):
    """Para el tope de apartados: la IP del cliente, con IPv6 agrupada por /56 (una casa)."""
    import ipaddress
    k = freno_mod.clave_ip(xff, remota)
    if "/" in k:
        try:
            return str(ipaddress.ip_network(k, strict=False).supernet(new_prefix=56))
        except ValueError:
            pass
    return k


def _pesos(n):
    return "${:,.0f}".format(round(float(n or 0)))


def _pesos2(n):
    return "${:,.2f}".format(float(n or 0))


# ------------------------------------------------------------------ Stripe (sin SDK, versión fija)
def _stripe(metodo, ruta, datos=None, idem=None):
    h = {"Stripe-Version": STRIPE_VERSION}
    if idem:
        h["Idempotency-Key"] = idem
    r = requests.request(metodo, "https://api.stripe.com/v1/" + ruta, data=datos, auth=(STRIPE_KEY, ""),
                         headers=h, timeout=20)
    try:
        j = r.json()
    except ValueError:
        j = {}
    return r.status_code, j


def _fecha_corta(show, idioma):
    d = dt.date.fromisoformat(show["fecha"])
    if idioma == "en":
        return d.strftime("%a %b ") + str(d.day)
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    return f"{dias[d.weekday()]} {d.day} {meses[d.month - 1]}"


def _crear_sesion_stripe(show, ses, hold_id, codigo, cantidad, nombre, email, whatsapp, idioma, canal):
    en = idioma == "en"
    pre = "/en" if en else ""
    etiqueta = ses.get(idioma) or ses.get("es") or ses["hora"]
    item = (f"{show['artista']} · {_fecha_corta(show, idioma)} · {etiqueta} · "
            f"{'Code' if en else 'Código'} {codigo}")
    datos = {
        "mode": "payment",
        "locale": "en" if en else "es-419",
        # sólo tarjeta (incluye Apple Pay / Google Pay): un pago diferido como OXXO dejaría el lugar en el aire
        "allowed_payment_method_types[0]": "card",
        "success_url": f"{SITIO}{pre}/boletos/gracias/?b={show['slug']}&f={ses['id']}&s={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{SITIO}{pre}/boletos/{show['slug']}/?cancelado={hold_id}&f={ses['id']}",
        "client_reference_id": hold_id,
        "customer_email": email,
        "line_items[0][quantity]": str(cantidad),
        "line_items[0][price_data][currency]": "mxn",
        "line_items[0][price_data][unit_amount]": str(int(show["precio"]) * 100),
        "line_items[0][price_data][product_data][name]": item[:250],
        "line_items[0][price_data][product_data][description]":
            ("Puebla 329, Roma Norte, CDMX · " + (f"doors {ses.get('puertas', '')}" if en else f"puertas {ses.get('puertas', '')}")),
        "payment_intent_data[description]": item[:250],
        "payment_intent_data[receipt_email]": email,
        "payment_intent_data[metadata][tipo]": "boleto",
        "payment_intent_data[metadata][show]": show["slug"],
        "payment_intent_data[metadata][codigo]": codigo,
        "metadata[tipo]": "boleto",
        "metadata[show]": show["slug"],
        "metadata[sesion]": ses["id"],
        "metadata[hold]": hold_id,
        "metadata[codigo]": codigo,
        "metadata[cantidad]": str(cantidad),
        "metadata[nombre]": nombre[:60],
        "metadata[whatsapp]": whatsapp[:15],
        "metadata[idioma]": idioma,
        "metadata[canal]": canal[:24],
        "custom_text[submit][message]": (
            f"Your code {codigo} shows up on screen and on the receipt. At the door we ask for your name and code."
            if en else f"Tu código {codigo} aparece en pantalla y en el recibo. En la puerta te pedimos tu nombre y tu código."),
        # al final, justo antes de mandar: Stripe exige al menos 30 min desde que la recibe
        "expires_at": str(int(time.time()) + STRIPE_EXPIRA_MIN * 60),
    }
    codigo_http, j = _stripe("POST", "checkout/sessions", datos, idem=f"boleto-{hold_id}")
    if codigo_http != 200 or not j.get("id"):
        raise RuntimeError(f"stripe {codigo_http}: {json.dumps(j.get('error', j), ensure_ascii=False)[:300]}")
    return j


def _expirar_y_consultar(cs):
    """Intenta expirar la sesión y regresa la sesión como la ve Stripe ahora (o None si no se pudo
    saber). Se decide con el status, nunca con el texto del error del expire."""
    try:
        _stripe("POST", f"checkout/sessions/{cs}/expire")
        c, j = _stripe("GET", f"checkout/sessions/{cs}")
        return j if c == 200 else None
    except requests.RequestException as e:
        print("stripe consulta fallo:", e)
        return None


def _consultar(cs):
    try:
        c, j = _stripe("GET", f"checkout/sessions/{cs}")
        return j if c == 200 else None
    except requests.RequestException as e:
        print("stripe consulta fallo:", e)
        return None


def _pagada(s):
    return bool(s) and s.get("status") == "complete" and s.get("payment_status") == "paid" \
        and (s.get("metadata") or {}).get("tipo") == "boleto"


def desdoblar_thin(evento):
    """Eventos "thin" (v1.checkout.session.*): traen sólo la referencia; se pide la sesión a Stripe.
    Regresa (tipo sin el prefijo v1., sesión). Si la sesión no se pudo leer regresa
    ("checkout.session.…", None) y el webhook debe responder error para que Stripe reintente."""
    tipo = evento.get("type", "")
    rel = evento.get("related_object") or {}
    if tipo.startswith("v1.checkout.session.") and str(rel.get("id", "")).startswith("cs_") and STRIPE_KEY:
        return tipo[3:], _consultar(rel["id"])
    print("stripe: evento que no se procesa:", tipo)
    return tipo, None


# ------------------------------------------------------------------ registrar pagos (webhook, gracias, reconciliación)
def _aplicar_pago(led, s, cupo, via, tok=None):
    """Función pura sobre el libro de la sesión: registra la compra si no existe. `tok` identifica
    la solicitud: si la compra ya está pero la escribió esta misma solicitud, sigue siendo nueva."""
    cs = s["id"]
    if cs in led["compras"]:
        c = led["compras"][cs]
        return False, (c, tok is not None and c.get("tok") == tok, False)
    md = s.get("metadata") or {}
    apartado = led["apartados"].pop(md.get("hold", ""), None)
    codigo = md.get("codigo") or (apartado or {}).get("codigo") or ""
    if not codigo or any(c.get("codigo") == codigo for c in led["compras"].values()):
        codigo = codigo + "-" + cs[-4:].upper()   # no debería pasar; mejor un código largo que dos iguales
    cd = s.get("customer_details") or {}
    try:
        cantidad = int(md.get("cantidad") or (apartado or {}).get("cantidad") or 0)
    except ValueError:
        cantidad = 0
    if cantidad <= 0:
        raise ValueError("sesión pagada sin cantidad en metadata")
    compra = {
        "codigo": codigo, "cantidad": cantidad, "entraron": 0,
        "nombre": limpiar_nombre(md.get("nombre") or cd.get("name")),
        "email": limpiar_email(cd.get("email") or s.get("customer_email")),
        "whatsapp": limpiar_whatsapp(md.get("whatsapp")),
        "canal": "web", "metodo": "stripe", "origen": limpiar_nombre(md.get("canal"), 24),
        "bruto": round(int(s.get("amount_total") or 0) / 100, 2),
        "cs": cs, "pi": s.get("payment_intent") or "", "idioma": md.get("idioma", "es"),
        "creado": _ahora_local().isoformat(), "estado": "ok", "via": via, "avisado": False,
        "avisando": int(_ahora()), "tok": tok, "sin_apartado": apartado is None,
    }
    led["compras"][cs] = compra
    sobreventa = _cuentas(led, cupo)["quedan"] < 0
    return True, (compra, True, sobreventa)


def _registrar(s, via):
    """Registra una sesión de Stripe ya pagada. Idempotente. Avisa por Telegram la primera vez."""
    md = s.get("metadata") or {}
    show = SHOWS.get(md.get("show", ""))
    ses = _sesion_cfg(show, md.get("sesion", "")) if show else None
    if not ses:
        _huerfana(s, "el show o la sesión ya no están en boletos.json")
        return None
    cupo = _cupo(show, ses, _control(show["slug"]))
    tok = secrets.token_hex(6)
    compra, nuevo, sobreventa = _mutar_sesion(show["slug"], ses["id"], lambda led: _aplicar_pago(led, s, cupo, via, tok))
    if nuevo or (not compra.get("avisado") and _reclamar_aviso(show["slug"], ses["id"], s["id"])):
        _avisar_compra(show, ses, compra, sobreventa, via)
    return compra


def _reclamar_aviso(slug, sid, clave):
    """Una compra registrada otra vez (webhook y página de gracias casi a la vez) sólo vuelve a
    avisar si nadie la está avisando ya, o si quien la avisaba lleva más de 5 minutos sin terminar."""
    ahora = int(_ahora())

    def fn(led):
        c = led["compras"].get(clave)
        if not c or c.get("avisado") or ahora - int(c.get("avisando", 0)) < 300:
            return False, False
        c["avisando"] = ahora
        return True, True
    return _mutar_sesion(slug, sid, fn)


def webhook(tipo, s):
    """Eventos de Stripe con metadata.tipo == boleto. Errores pasajeros (GCS, red) suben y el
    webhook responde 500 para que Stripe reintente; cualquier otro error se guarda como huérfana
    y se avisa, para no quedar en reintentos 3 días."""
    try:
        if tipo in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            if s.get("payment_status") == "paid":
                _registrar(s, "webhook")
        elif tipo == "checkout.session.expired":
            _soltar_por_cs(s)
    except TRANSITORIOS:
        raise
    except Exception as e:   # noqa: BLE001 — un pago no se puede perder en silencio
        print("boletos webhook error:", repr(e))
        _huerfana(s, f"{type(e).__name__}: {e}")


def _soltar_por_cs(s):
    md = s.get("metadata") or {}
    show = SHOWS.get(md.get("show", ""))
    if not show or not _sesion_cfg(show, md.get("sesion", "")):
        return

    def fn(led):
        a = led["apartados"].get(md.get("hold", ""))
        if a and a.get("cs") == s.get("id"):
            del led["apartados"][md["hold"]]
            return True, True
        return False, False
    _mutar_sesion(show["slug"], md["sesion"], fn)


def _huerfana(s, motivo):
    """Un pago de boleto que no se pudo registrar: se guarda aparte y se avisa a Pablo."""
    md = s.get("metadata") or {}
    tok = secrets.token_hex(6)
    registro = {"cs": s.get("id"), "pi": s.get("payment_intent"), "monto": (s.get("amount_total") or 0) / 100,
                "email": (s.get("customer_details") or {}).get("email"), "metadata": md, "motivo": motivo,
                "cuando": _ahora_local().isoformat(), "sesion_stripe": s, "tok": tok}
    try:
        def fn(d):
            d.setdefault("huerfanas", {})
            ya = d["huerfanas"].get(registro["cs"])
            if ya:
                return False, ya.get("tok") == tok   # si la escribió esta misma solicitud, se avisa
            d["huerfanas"][registro["cs"]] = registro
            return True, True
        nueva = _mutar(f"{PREFIJO}huerfanas.json", fn)
    except Exception as e:   # noqa: BLE001
        print("no se pudo guardar la huérfana:", e, {k: v for k, v in registro.items() if k != "sesion_stripe"})
        nueva = True
    if nueva:
        _aviso(f"⚠️ <b>Pago de boleto SIN registrar</b>\n{_pesos(registro['monto'])} · {_tg(registro['email'])} · "
               f"{_tg(md.get('nombre'))}\nShow {_tg(md.get('show'))} · sesión {_tg(md.get('sesion'))} · "
               f"{_tg(md.get('cantidad'))} boleto(s) · código {_tg(md.get('codigo'))}\nMotivo: {_tg(motivo)}\n"
               f"Stripe: <code>{_tg(registro['cs'])}</code>.\nNo lo metas como venta en puerta: saldría con otro código y "
               f"otra comisión. Pídele a Claude que lo registre (POST /boletos/huerfana) o reembólsalo en Stripe.")


# ------------------------------------------------------------------ apartados vencidos
def _reconciliar(show, ses):
    """Resuelve los apartados vencidos preguntándole a Stripe. Fuera de la función pura: llama a Stripe."""
    led = _leer(show["slug"], ses["id"])
    ahora = _ahora()
    viejos = {h: a for h, a in led["apartados"].items() if float(a.get("expira", 0)) <= ahora}
    if not viejos:
        return
    decision = {}
    for h, a in viejos.items():
        s = _expirar_y_consultar(a["cs"]) if a.get("cs") else {"status": "expired"}
        if s is None:
            if ahora - float(a.get("expira", 0)) > OLVIDAR_APARTADO_H * 3600:
                decision[h] = ("olvidar", None)
            continue
        if _pagada(s):
            decision[h] = ("pagada", s)
        elif s.get("status") == "expired":
            decision[h] = ("soltar", None)
    if not decision:
        return
    cupo = _cupo(show, ses, _control(show["slug"]))
    pagadas = []
    tok = secrets.token_hex(6)

    def fn(led):
        del pagadas[:]        # la función puede correr más de una vez (choques al escribir)
        cambio = False
        for h, (que, s) in decision.items():
            if h not in led["apartados"]:
                c = led["compras"].get((s or {}).get("id", ""))
                if que == "pagada" and c and c.get("tok") == tok:   # la escribió esta solicitud y se perdió la respuesta
                    pagadas.append((c, True, False))
                continue
            if que == "pagada":
                c, (compra, nuevo, sobre) = _aplicar_pago(led, s, cupo, "reconciliacion", tok)
                led["apartados"].pop(h, None)
                cambio = True
                pagadas.append((compra, nuevo, sobre))
            else:
                del led["apartados"][h]
                cambio = True
        return cambio, None
    _mutar_sesion(show["slug"], ses["id"], fn)
    for compra, nuevo, sobre in pagadas:
        if nuevo or (not compra.get("avisado") and _reclamar_aviso(show["slug"], ses["id"], compra["cs"])):
            _avisar_compra(show, ses, compra, sobre, "reconciliacion")
    olvidados = [h for h, (que, _) in decision.items() if que == "olvidar"]
    if olvidados:
        _aviso(f"⚠️ Boletos {_tg(show['artista'])} {_tg(ses.get('es'))}: solté {len(olvidados)} apartado(s) que Stripe no "
               f"resolvió en {OLVIDAR_APARTADO_H} h. Revisa en Stripe que no haya pagos sin boleto.")


_ultima_reconciliacion = {}


def _reconciliar_de_vez_en_cuando(show, ses, cada=60):
    k = (show["slug"], ses["id"])
    if _ahora() - _ultima_reconciliacion.get(k, 0) < cada:
        return
    _ultima_reconciliacion[k] = _ahora()
    try:
        _reconciliar(show, ses)
    except Exception as e:   # noqa: BLE001 — leer la disponibilidad no debe tronar por esto
        print("reconciliar fallo:", e)


# ------------------------------------------------------------------ avisos (Telegram y hoja)
_telegram = None
_avisos_apartados = {}


def _aviso(texto, **kw):
    if _telegram is None:
        print("TELEGRAM (sin montar):", texto[:300])
        return False
    try:
        return bool(_telegram(texto, **kw))
    except Exception as e:   # noqa: BLE001
        print("telegram fallo:", e)
        return False


def _resumen_show(show, control=None):
    control = control or _control(show["slug"])
    partes = []
    for x in show["sesiones"]:
        c = _cuentas(_leer(show["slug"], x["id"]), _cupo(show, x, control))
        partes.append(f"{x.get('es', x['hora'])}: {c['vendidos']}/{c['cupo']}")
    return " · ".join(partes)


def _avisar_compra(show, ses, compra, sobreventa, via):
    try:
        resumen = _resumen_show(show)
    except Exception:   # noqa: BLE001
        resumen = ""
    banderas = []
    if sobreventa:
        banderas.append("⚠️ <b>SOBREVENTA</b>: la sesión quedó arriba del cupo")
    if compra.get("sin_apartado"):
        banderas.append("⚠️ el pago llegó después de que se soltó su apartado")
    if via != "webhook":
        banderas.append(f"⚠️ registrada por {via}, no por el webhook: revisa el webhook en Stripe")
    try:
        if _ahora_local() >= _inicio(show, ses):
            banderas.append("⚠️ pagada después de empezar la sesión")
    except Exception:   # noqa: BLE001
        pass
    texto = (f"🎟 <b>{compra['cantidad']} boleto{'s' if compra['cantidad'] != 1 else ''} · {_tg(show['artista'])} "
             f"{_tg(ses.get('es', ses['hora']))}</b>\n{_tg(compra['nombre'])} · {_tg(compra['email'])}"
             + (f" · {_tg(compra['whatsapp'])}" if compra.get("whatsapp") else "")
             + f"\nCódigo <code>{_tg(compra['codigo'])}</code> · {_pesos(compra['bruto'])}"
             + (f"\n{_tg(resumen)}" if resumen else "")
             + ("\n" + "\n".join(banderas) if banderas else ""))
    ok_tg = _aviso(texto)
    ok_hoja = _hoja(show, ses, compra, "venta web")
    if ok_tg:
        def fn(led):
            c = led["compras"].get(compra["cs"])
            if not c or c.get("avisado"):
                return False, None
            c["avisado"] = True
            c["en_hoja"] = bool(ok_hoja)
            return True, None
        try:
            _mutar_sesion(show["slug"], ses["id"], fn)
        except Exception as e:   # noqa: BLE001
            print("no se pudo marcar avisado:", e)


_hoja_sesion = None
_hoja_lista = False
COLS_HOJA = ["fecha_hora", "show", "sesion", "codigo", "nombre", "email", "whatsapp", "cantidad", "bruto",
             "canal", "metodo", "movimiento", "referencia"]


def _hoja(show, ses, compra, movimiento):
    """Espejo en la hoja de Google (BOLETOS_SHEET_ID). Nunca es la verdad; si falla, sólo se loguea."""
    global _hoja_sesion, _hoja_lista
    if not SHEET_ID:
        return False
    try:
        if _hoja_sesion is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
            _hoja_sesion = AuthorizedSession(creds)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/"
        if not _hoja_lista:
            r = _hoja_sesion.get(url + "A1:M1", timeout=8)
            r.raise_for_status()
            if not r.json().get("values"):
                _hoja_sesion.put(url + "A1:M1?valueInputOption=RAW", json={"values": [COLS_HOJA]}, timeout=8).raise_for_status()
            _hoja_lista = True
        fila = [_ahora_local().isoformat(sep=" "), show["slug"], ses.get("es", ses["hora"]), compra.get("codigo", ""),
                compra.get("a_nombre_de") or compra.get("nombre", ""), compra.get("email", ""), compra.get("whatsapp", ""),
                compra.get("cantidad", 0), compra.get("bruto", 0), compra.get("canal", ""), compra.get("metodo", ""),
                movimiento, compra.get("cs") or compra.get("op", "")]
        r = _hoja_sesion.post(url + "A1:M1:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
                              json={"values": [fila]}, timeout=8)
        r.raise_for_status()
        return True
    except Exception as e:   # noqa: BLE001
        print("hoja de boletos fallo:", e)
        return False


# ------------------------------------------------------------------ datos públicos
def _publico_show(show, control=None):
    control = control or _control(show["slug"])
    sesiones = []
    for x in show["sesiones"]:
        _reconciliar_de_vez_en_cuando(show, x)
        c = _cuentas(_leer(show["slug"], x["id"]), _cupo(show, x, control))
        sesiones.append({"id": x["id"], "es": x.get("es"), "en": x.get("en"), "hora": x["hora"],
                         "puertas": x.get("puertas"), "cupo": c["cupo"], "quedan": max(0, c["quedan"]),
                         "en_pago": c["en_pago"], "estado": _estado_venta(show, x, control, c),
                         "cierra": _cierre_en_linea(show, x).isoformat()})
    return {"slug": show["slug"], "artista": show["artista"], "fecha": show["fecha"], "precio": int(show["precio"]),
            "max": int(show["max_por_compra"]), "venta_abre": show.get("venta_abre"), "sesiones": sesiones}


def _publico_compra(show, ses, c):
    return {"codigo": c["codigo"], "nombre": c.get("a_nombre_de") or c["nombre"], "cantidad": c["cantidad"],
            "show": show["slug"], "artista": show["artista"], "fecha": show["fecha"],
            "sesion": {"id": ses["id"], "es": ses.get("es"), "en": ses.get("en"), "hora": ses["hora"],
                       "puertas": ses.get("puertas")}, "estado": c.get("estado", "ok")}


# ------------------------------------------------------------------ liquidación
def liquidacion(slug):
    show = SHOWS[slug]
    trato = _trato(slug) or {}
    pct_web = float(trato.get("comision_web", 0.05))
    pct_clip = float(trato.get("comision_clip", 0.0225 * 1.16))
    filas, tot = [], {"bruto": 0.0, "comision": 0.0, "neto": 0.0, "stripe_estimada": 0.0, "boletos": 0,
                      "cortesias": 0, "efectivo": 0.0, "clip": 0.0, "transferencia": 0.0, "web": 0.0,
                      "anuladas": 0, "entraron": 0}
    for x in show["sesiones"]:
        led = _leer(slug, x["id"])
        for c in sorted(led["compras"].values(), key=lambda c: c.get("creado", "")):
            estado = c.get("estado", "ok")
            if estado == "anulada":
                tot["anuladas"] += 1
            if estado != "ok":
                continue
            bruto = float(c.get("bruto", 0)) if c["canal"] != "cortesia" else 0.0
            if c["metodo"] == "stripe":
                comision = bruto * pct_web
                stripe_est = (bruto * STRIPE_PCT + STRIPE_FIJO) * (1 + IVA)
                tot["web"] += bruto
            elif c["metodo"] == "clip":
                comision, stripe_est = bruto * pct_clip, 0.0
                tot["clip"] += bruto
            else:
                comision, stripe_est = 0.0, 0.0
                if c["metodo"] in ("efectivo", "transferencia"):
                    tot[c["metodo"]] += bruto
            neto = (bruto - comision) / (1 + IVA)
            tot["bruto"] += bruto
            tot["comision"] += comision
            tot["neto"] += neto
            tot["stripe_estimada"] += stripe_est
            tot["entraron"] += int(c.get("entraron", 0))
            if c["canal"] == "cortesia":
                tot["cortesias"] += int(c["cantidad"])
            else:
                tot["boletos"] += int(c["cantidad"])
            filas.append({"sesion": x.get("es", x["hora"]), "hora_compra": c.get("creado", ""), "codigo": c["codigo"],
                          "nombre": c.get("a_nombre_de") or c["nombre"], "canal": c["canal"], "metodo": c["metodo"],
                          "cantidad": c["cantidad"], "entraron": c.get("entraron", 0), "bruto": round(bruto, 2),
                          "comision": round(comision, 2), "iva": round((bruto - comision) - neto, 2),
                          "neto": round(neto, 2), "referencia_stripe": c.get("pi") or c.get("cs") or "",
                          "pidio_cortesia": c.get("pidio", "")})
    res = {"show": slug, "artista": show["artista"], "fecha": show["fecha"], "filas": filas,
           "totales": {k: round(v, 2) if isinstance(v, float) else v for k, v in tot.items()}, "trato": None}
    if trato:
        fijo = float(trato.get("fijo", 0))
        pct = float(trato.get("porcentaje", 0))
        res["trato"] = {"fijo": fijo, "porcentaje": pct, "comision_web": pct_web, "comision_clip": pct_clip,
                        "parte_variable": round(tot["neto"] * pct, 2), "pago_artista": round(fijo + tot["neto"] * pct, 2),
                        "queda_rosso_taquilla": round(tot["neto"] * (1 - pct) - fijo, 2)}
    return res


def _texto_liquidacion(liq):
    t = liq["totales"]
    lin = [f"🧾 <b>Liquidación · {_tg(liq['artista'])} · {liq['fecha']}</b>",
           f"Boletos pagados: {t['boletos']} · cortesías: {t['cortesias']} · entraron: {t['entraron']}"
           + (f" · anuladas: {t['anuladas']}" if t["anuladas"] else ""),
           f"Bruto (IVA incluido): {_pesos2(t['bruto'])}",
           f"  web {_pesos2(t['web'])} · clip {_pesos2(t['clip'])} · efectivo {_pesos2(t['efectivo'])} · transferencia {_pesos2(t['transferencia'])}",
           f"Comisión acordada: {_pesos2(t['comision'])} (Stripe real estimada: {_pesos2(t['stripe_estimada'])})",
           f"Neto sin IVA: <b>{_pesos2(t['neto'])}</b>"]
    if liq["trato"]:
        tr = liq["trato"]
        lin += [f"Artista: {_pesos2(tr['fijo'])} fijo + {tr['porcentaje'] * 100:.0f}% del neto ({_pesos2(tr['parte_variable'])}) = "
                f"<b>{_pesos2(tr['pago_artista'])}</b> bruto, antes de la retención de ISR",
                f"A ROSSO de la taquilla (neto − artista): {_pesos2(tr['queda_rosso_taquilla'])}"]
    else:
        lin.append("⚠️ Falta el trato del show en api/boletos_tratos.json: no calculé el pago a la artista.")
    lin.append(f"Efectivo esperado en caja de puerta: {_pesos2(t['efectivo'])}. "
               "Si reembolsaste algo en Stripe y no lo anulaste en la puerta, todavía cuenta aquí.")
    return "\n".join(lin)


def _csv_liquidacion(liq):
    buf = io.StringIO()
    cols = ["sesion", "hora_compra", "codigo", "nombre", "canal", "metodo", "cantidad", "entraron", "bruto",
            "comision", "iva", "neto", "referencia_stripe", "pidio_cortesia"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for f in liq["filas"]:
        # ningún texto puede arrancar como fórmula de Excel (nombre, de parte de quién, etc.)
        w.writerow({k: ("'" + v) if isinstance(v, str) and v[:1] in "=+-@\t\r" else v for k, v in f.items()})
    return buf.getvalue()


def _textos_lista(show):
    control = _control(show["slug"])
    out = []
    for x in show["sesiones"]:
        led = _leer(show["slug"], x["id"])
        c = _cuentas(led, _cupo(show, x, control))
        filas = sorted(_vivas(led), key=lambda k: _sin_acentos(k.get("a_nombre_de") or k["nombre"]))
        cab = (f"🚪 <b>Lista {_tg(show['artista'])} · {_tg(x.get('es', x['hora']))}</b> (puertas {_tg(x.get('puertas', ''))})\n"
               f"{c['vendidos']} de {c['cupo']} · en pago {c['en_pago']}\n")
        cuerpo = "\n".join(f"<code>{_tg(k['codigo'])}</code> {_tg(k.get('a_nombre_de') or k['nombre'])} · {k['cantidad']}"
                           + ("" if k["canal"] == "web" else f" ({_tg(k['canal'] if k['canal'] == 'cortesia' else k['metodo'])})")
                           for k in filas) or "(nadie todavía)"
        texto = cab + cuerpo
        while len(texto) > 3900:   # Telegram corta en 4096
            corte = texto.rfind("\n", 0, 3900)
            out.append(texto[:corte])
            texto = "(sigue)\n" + texto[corte + 1:]
        out.append(texto)
    return out


# ------------------------------------------------------------------ rutas
def montar(app, telegram, freno, origenes, refresh_key):
    """Registra las rutas /boletos/* en la app de Flask."""
    from flask import jsonify, request
    global _telegram
    _telegram = telegram
    _cache = {}
    if EN_CLOUD_RUN and STRIPE_KEY and not BUCKET:
        _aviso("⚠️ Boletos: el API tiene Stripe pero le falta BOLETOS_BUCKET; la venta y la puerta responden 503. "
               "Ponla con --update-env-vars (nunca --set-env-vars).")

    def error(msg, status=400, **extra):
        return jsonify(error=msg, **extra), status

    def entrada_json():
        """POST de navegador: sólo JSON y sólo desde el sitio (así otro sitio no puede mandar
        formularios a nombre de sus visitantes)."""
        if not request.is_json:
            return None, error("formato inválido", 415)
        if request.headers.get("Origin", "") not in origenes:
            return None, error("origen no permitido", 403)
        return request.get_json(silent=True) or {}, None

    def no_listo():
        if not configurado():
            return error("la venta de boletos todavía no está activa", 503, codigo="inactivo")
        return None

    def show_de(d, publico=True):
        show = SHOWS.get(str(d.get("show") or ""))
        if not show or (publico and show.get("visible", "no") == "no"):
            return None, None
        return show, _sesion_cfg(show, str(d.get("sesion") or ""))

    def pin_puerta(pin, ruta):
        """Como revisar_pin de app.py, pero también acepta el PIN de puerta. Mismo freno por IP.
        Sólo el PIN de BARRA borra los fallos de la IP: si el de puerta los borrara, quien sólo tiene
        el de puerta podría adivinar el de barra sin límite (9 intentos, PIN de puerta, repetir)."""
        ip = freno_mod.clave_ip(request.headers.get("X-Forwarded-For"), request.remote_addr)
        espera = freno.espera(ip)
        if not espera:
            p = str(pin or "")
            if regalo_mod.pin_correcto(p):
                freno.acierto(ip)
                return None
            if PUERTA_PIN and hmac.compare_digest(p.encode(), PUERTA_PIN.encode()):
                return None
            if not p.strip() or not freno.fallo(ip, ruta):
                return error("PIN incorrecto", 403)
            espera = freno.espera(ip)
        resp = jsonify(error=f"Demasiados intentos con PIN equivocado. Espera {-(-espera // 60)} min y vuelve a intentar.")
        resp.headers["Retry-After"] = str(espera)
        return resp, 429

    def fallas(fn):
        """Errores de almacén o de red -> 503 con mensaje claro, sin tumbar la ruta."""
        def envuelta(*a, **kw):
            try:
                return fn(*a, **kw)
            except SinAlmacen:
                return error("la venta de boletos todavía no está activa", 503, codigo="inactivo")
            except TRANSITORIOS as e:
                print("boletos: error pasajero:", repr(e))
                return error("hay mucha gente comprando en este momento; inténtalo en unos segundos", 503, codigo="ocupado")
        envuelta.__name__ = fn.__name__
        return envuelta

    # ---------------- público
    @app.get("/boletos/show/<slug>")
    @fallas
    def boletos_show(slug):
        show = SHOWS.get(slug)
        if not show or show.get("visible", "no") == "no":
            return error("ese show no existe", 404)
        if not configurado():
            return jsonify(activo=False, slug=slug)
        c = _cache.get(slug)
        if c and _ahora() - c[0] < 3:
            return jsonify(c[1])
        datos = dict(_publico_show(show), activo=True)
        _cache[slug] = (_ahora(), datos)
        return jsonify(datos)

    @app.post("/boletos/checkout")
    @fallas
    def boletos_checkout():
        d, err = entrada_json()
        if err:
            return err
        if d.get("empresa_web"):
            return error("no se pudo iniciar el pago", 400, codigo="error")   # miel para bots
        err = no_listo()
        if err:
            return err
        show, ses = show_de(d)
        if not show:
            return error("ese show no existe", 404, codigo="show")
        if not ses:
            return error("elige la sesión", 400, codigo="sesion")
        try:
            cantidad = int(d.get("cantidad") or 0)
        except (TypeError, ValueError):
            cantidad = 0
        if not 1 <= cantidad <= int(show["max_por_compra"]):
            return error(f"puedes comprar de 1 a {show['max_por_compra']} boletos por compra", 400, codigo="cantidad",
                         max=int(show["max_por_compra"]))
        nombre = limpiar_nombre(d.get("nombre"))
        email = limpiar_email(d.get("email"))
        whatsapp = limpiar_whatsapp(d.get("whatsapp"))
        idioma = "en" if d.get("idioma") == "en" else "es"
        canal = re.sub(r"[^a-z0-9_-]", "", str(d.get("canal") or "directo").lower())[:24] or "directo"
        if len(nombre) < 2:
            return error("nos falta tu nombre (es el que buscamos en la puerta)", 400, codigo="nombre")
        if not email:
            return error("revisa el correo", 400, codigo="correo")
        control = _control(show["slug"])
        _reconciliar(show, ses)
        led = _leer(show["slug"], ses["id"])
        cupo = _cupo(show, ses, control)
        c = _cuentas(led, cupo)
        estado = _estado_venta(show, ses, control, c)
        mensajes = {"por_abrir": "la venta todavía no abre", "pausada": "la venta está en pausa; escríbenos por WhatsApp",
                    "cerrada_en_linea": "la venta en línea de esta sesión ya cerró; pregunta en la puerta",
                    "pasada": "esta sesión ya pasó", "agotada": "esta sesión está agotada"}
        if estado in mensajes:
            return error(mensajes[estado], 409, estado=estado, codigo=estado)
        ahora = _ahora()
        llave = _llave_ip(request.headers.get("X-Forwarded-For"), request.remote_addr)
        tope_llave = 2 * int(show["max_por_compra"])
        # doble clic / volver a intentar: el mismo correo DESDE LA MISMA CONEXIÓN con un apartado vivo.
        # (Por correo solo no: cualquiera que lo sepa recibiría la liga de pago de otra persona.)
        mio = next(((h, a) for h, a in led["apartados"].items() if a.get("email") == email and a.get("llave") == llave), None)
        if mio and mio[1].get("cantidad") == cantidad and mio[1].get("url") and float(mio[1]["expira"]) > ahora + 60:
            return jsonify(ok=True, url=mio[1]["url"])
        if mio:   # cambió de opinión: se suelta el anterior (sólo si Stripe confirma que expiró)
            s_ant = _expirar_y_consultar(mio[1]["cs"]) if mio[1].get("cs") else {"status": "expired"}
            if s_ant and s_ant.get("status") == "expired":
                _soltar_por_cs({"id": mio[1].get("cs"), "metadata": {"show": show["slug"], "sesion": ses["id"], "hold": mio[0]}})
                led = _leer(show["slug"], ses["id"])
                c = _cuentas(led, cupo)
        # revisión previa (barata); la que cuenta va otra vez dentro de la escritura atómica
        de_llave = sum(int(a["cantidad"]) for a in led["apartados"].values() if a.get("llave") == llave)
        if de_llave + cantidad > tope_llave:
            return error("ya hay otros pagos en curso desde tu conexión; termínalos o espera unos minutos", 429, codigo="tope")
        if cantidad > c["quedan"]:
            if c["quedan"] <= 0:
                return error("ahorita no quedan lugares en esta sesión" + (
                    "; hay pagos en curso, vuelve a intentar en 20 minutos" if c["en_pago"] else ""), 409,
                    estado="en_pago" if c["en_pago"] else "agotada", codigo="en_pago" if c["en_pago"] else "agotada")
            return error(f"sólo quedan {c['quedan']} lugares en esta sesión", 409, quedan=c["quedan"], codigo="quedan")

        hold = secrets.token_urlsafe(16)
        codigo = _codigo_nuevo(show["slug"])
        try:
            s = _crear_sesion_stripe(show, ses, hold, codigo, cantidad, nombre, email, whatsapp, idioma, canal)
        except Exception as e:   # noqa: BLE001
            print("stripe checkout boletos fallo:", e)
            return error("no se pudo iniciar el pago; inténtalo de nuevo", 502, codigo="stripe")

        apartado = {"cantidad": cantidad, "email": email, "llave": llave, "codigo": codigo, "cs": s["id"],
                    "url": s["url"], "creado": int(ahora), "expira": int(ahora + APARTADO_MIN * 60)}

        def apartar(led):
            """Todos los topes se cuentan aquí, con el libro de ESTE intento."""
            if hold in led["apartados"]:          # la escritura sí entró aunque se perdió la respuesta
                return False, ("ok", None)
            otro = next((a for h, a in led["apartados"].items()
                         if a.get("email") == email and a.get("llave") == llave and a.get("cantidad") == cantidad
                         and a.get("url") and float(a.get("expira", 0)) > ahora + 60), None)
            if otro:                              # dos clics casi al mismo tiempo: gana el primero
                return False, ("ya", otro["url"])
            if sum(int(a["cantidad"]) for a in led["apartados"].values() if a.get("llave") == llave) + cantidad > tope_llave:
                return False, ("tope", None)
            if cantidad > _cuentas(led, cupo)["quedan"]:
                return False, ("sin_lugar", None)
            led["apartados"][hold] = apartado
            return True, ("ok", None)
        try:
            r, url_otro = _mutar_sesion(show["slug"], ses["id"], apartar)
        except Exception:
            _expirar_y_consultar(s["id"])         # nadie vio esa liga: que no se pueda pagar
            raise
        if r != "ok":
            _expirar_y_consultar(s["id"])
            if r == "ya":
                return jsonify(ok=True, url=url_otro)
            if r == "tope":
                return error("ya hay otros pagos en curso desde tu conexión; termínalos o espera unos minutos", 429, codigo="tope")
            return error("se acaban de apartar los últimos lugares; intenta con menos boletos o en unos minutos", 409, codigo="carrera")
        _vigilar_apartados(show, ses)
        return jsonify(ok=True, url=s["url"])

    def _vigilar_apartados(show, ses):
        """Aviso si los pagos en curso se comen la mitad de lo que queda (posible acaparamiento)."""
        try:
            led = _leer(show["slug"], ses["id"])
            c = _cuentas(led, _cupo(show, ses, _control(show["slug"])))
            libres = c["cupo"] - c["vendidos"]
            k = (show["slug"], ses["id"])
            if len(led["apartados"]) >= 4 and c["en_pago"] * 2 >= libres and _ahora() - _avisos_apartados.get(k, 0) > 1800:
                _avisos_apartados[k] = _ahora()
                _aviso(f"👀 Boletos {_tg(show['artista'])} {_tg(ses.get('es'))}: {c['en_pago']} lugares en pago "
                       f"({len(led['apartados'])} apartados) de {libres} libres. Si no es normal, suéltalos desde la puerta.")
        except Exception as e:   # noqa: BLE001
            print("vigilar apartados fallo:", e)

    @app.post("/boletos/cancelar")
    @fallas
    def boletos_cancelar():
        d, err = entrada_json()
        if err:
            return err
        err = no_listo()
        if err:
            return err
        show, ses = show_de(d)
        if not show or not ses:
            return error("ese show no existe", 404)
        hold = str(d.get("hold") or "")[:40]
        a = _leer(show["slug"], ses["id"])["apartados"].get(hold)
        if not a:
            return jsonify(ok=True, soltado=False)
        s = _expirar_y_consultar(a["cs"]) if a.get("cs") else {"status": "expired"}
        if s is None:
            return error("no pudimos confirmar con Stripe; tus lugares se liberan solos en unos minutos", 502)
        if _pagada(s):
            compra = _registrar(s, "cancelar")
            return jsonify(ok=True, pagado=True, compra=_publico_compra(show, ses, compra) if compra else None)
        if s.get("status") == "expired":
            _soltar_por_cs({"id": a.get("cs"), "metadata": {"show": show["slug"], "sesion": ses["id"], "hold": hold}})
            _cache.pop(show["slug"], None)
            return jsonify(ok=True, soltado=True)
        return error("tu pago sigue abierto en Stripe; se libera solo en unos minutos", 409)

    @app.get("/boletos/estado")
    @fallas
    def boletos_estado():
        show = SHOWS.get(request.args.get("b", ""))
        ses = _sesion_cfg(show, request.args.get("f", "")) if show else None
        cs = re.sub(r"[^A-Za-z0-9_]", "", request.args.get("s", ""))[:120]
        if not show or not ses or not cs.startswith("cs_"):
            return error("liga inválida", 400)
        led = _leer(show["slug"], ses["id"])
        c = led["compras"].get(cs)
        if c and c.get("estado") == "movida" and _sesion_cfg(show, c.get("movida_a", "")):
            # la pasaron de sesión en la puerta: se enseña la copia viva, con su sesión nueva
            destino = _sesion_cfg(show, c["movida_a"])
            copias = [k for k in _leer(show["slug"], destino["id"])["compras"].values() if k["codigo"] == c["codigo"]]
            nueva = next((k for k in copias if k.get("estado", "ok") == "ok"), None) or next(
                (k for k in copias if k.get("estado") == "anulada"), None)
            if nueva:
                return jsonify(listo=True, compra=_publico_compra(show, destino, nueva))
        if c:
            return jsonify(listo=True, compra=_publico_compra(show, ses, c))
        # el webhook se atrasa: cada tantos sondeos la página pide que se le pregunte a Stripe
        if request.args.get("v") == "1" and configurado() and any(a.get("cs") == cs for a in led["apartados"].values()):
            s = _consultar(cs)
            if _pagada(s) and (s.get("metadata") or {}).get("show") == show["slug"]:
                compra = _registrar(s, "pagina de gracias")
                if compra:
                    return jsonify(listo=True, compra=_publico_compra(show, ses, compra))
        return jsonify(listo=False)

    # ---------------- puerta (PIN)
    def puerta(fn):
        """Ruta de puerta: JSON del sitio, PIN, show existente (aunque no sea visible)."""
        def envuelta():
            d, err = entrada_json()
            if err:
                return err
            err = pin_puerta(d.get("pin"), "boletos/" + fn.__name__)
            if err:
                return err
            show = SHOWS.get(str(d.get("show") or ""))
            if not show:
                return error("ese show no existe", 404)
            if not configurado():
                return error("los boletos todavía no están activos", 503)
            return fn(d, show)
        envuelta.__name__ = "puerta_" + fn.__name__
        return fallas(envuelta)

    def _sesion_o_error(d, show, campo="sesion"):
        ses = _sesion_cfg(show, str(d.get(campo) or ""))
        return ses

    def _op(d):
        return re.sub(r"[^A-Za-z0-9_-]", "", str(d.get("op") or ""))[:64]

    def _lista(show):
        control = _control(show["slug"])
        sesiones = []
        for x in show["sesiones"]:
            _reconciliar(show, x)
            led = _leer(show["slug"], x["id"])
            c = _cuentas(led, _cupo(show, x, control))
            compras = [{"codigo": k["codigo"], "nombre": k["nombre"], "a_nombre_de": k.get("a_nombre_de", ""),
                        "email": _mascara_email(k.get("email")), "wa": (k.get("whatsapp") or "")[-4:],
                        "cantidad": k["cantidad"], "entraron": k.get("entraron", 0), "canal": k["canal"],
                        "metodo": k["metodo"], "estado": k.get("estado", "ok"), "creado": k.get("creado", "")}
                       for k in sorted(led["compras"].values(), key=lambda k: _sin_acentos(k.get("a_nombre_de") or k["nombre"]))
                       if k.get("estado", "ok") in ("ok", "anulada")]
            apartados = [{"cantidad": a["cantidad"], "vence": dt.datetime.fromtimestamp(float(a["expira"])).strftime("%H:%M")}
                         for a in led["apartados"].values()]
            sesiones.append(dict(c, id=x["id"], etiqueta=x.get("es", x["hora"]), puertas=x.get("puertas"),
                                 estado=_estado_venta(show, x, control, c), compras=compras, apartados=apartados,
                                 inicio=_inicio(show, x).isoformat()))
        cortesias = sum(int(k["cantidad"]) for x in show["sesiones"] for k in _vivas(_leer(show["slug"], x["id"]))
                        if k["canal"] == "cortesia")
        return {"show": show["slug"], "artista": show["artista"], "fecha": show["fecha"], "precio": int(show["precio"]),
                "pausada": control["pausada"], "cortesias": cortesias,
                "cortesias_max": int(control["ajustes"].get("cortesias_max", show.get("cortesias_max", 0))),
                "sesiones": sesiones, "hora": _ahora_local().strftime("%H:%M")}

    @app.post("/boletos/puerta/lista")
    @puerta
    def lista(d, show):
        return jsonify(ok=True, **_lista(show))

    @app.post("/boletos/puerta/entrada")
    @puerta
    def entrada(d, show):
        ses = _sesion_o_error(d, show)
        n = d.get("n")
        if not ses or n not in (1, -1):
            return error("datos incompletos", 400)
        codigo, op, tok = str(d.get("codigo") or "").upper()[:20], _op(d), secrets.token_hex(6)

        def fn(led):
            hecho = _op_hecha(led, op, tok)
            if hecho:
                return False, hecho
            k = next((k for k in led["compras"].values() if k["codigo"] == codigo and k.get("estado", "ok") == "ok"), None)
            if not k:
                return False, {"error": "ese código no está en esta sesión"}
            k["entraron"] = max(0, min(int(k["cantidad"]), int(k.get("entraron", 0)) + n))
            r = {"codigo": codigo, "entraron": k["entraron"], "cantidad": k["cantidad"]}
            _anotar_op(led, op, r, tok)
            return True, r
        r = _mutar_sesion(show["slug"], ses["id"], fn)
        if "error" in r:
            return error(r["error"], 404)
        return jsonify(ok=True, **r)

    @app.post("/boletos/puerta/venta")
    @puerta
    def venta(d, show):
        ses = _sesion_o_error(d, show)
        tipo = d.get("tipo")
        metodo = "cortesia" if tipo == "cortesia" else d.get("metodo")
        try:
            cantidad = int(d.get("cantidad") or 0)
        except (TypeError, ValueError):
            cantidad = 0
        op = _op(d)
        if not ses or tipo not in ("puerta", "cortesia") or (tipo == "puerta" and metodo not in METODOS_PUERTA) \
                or not 1 <= cantidad <= 10 or not op:
            return error("revisa sesión, cantidad y método", 400)
        nombre = limpiar_nombre(d.get("nombre")) or ("Cortesía" if tipo == "cortesia" else "Venta en puerta")
        pidio = limpiar_nombre(d.get("pidio"), 30)
        tok = secrets.token_hex(6)
        control = _control(show["slug"])
        cupo = _cupo(show, ses, control)
        hecha = _op_hecha(_leer(show["slug"], ses["id"]), op)
        if hecha:   # reintento por mala señal de algo que ya entró: antes que cualquier tope
            return jsonify(ok=True, codigo=hecha["codigo"])
        if tipo == "cortesia":
            ya = sum(int(k["cantidad"]) for x in show["sesiones"] for k in _vivas(_leer(show["slug"], x["id"]))
                     if k["canal"] == "cortesia")
            tope = int(control["ajustes"].get("cortesias_max", show.get("cortesias_max", 0)))
            if ya + cantidad > tope:
                return error(f"ya van {ya} cortesías de {tope}; súbele al tope desde aquí si Pablo lo autoriza", 409)

        def fn(led):
            hecho = _op_hecha(led, op, tok)
            if hecho:
                return False, hecho
            c = _cuentas(led, cupo)
            if cantidad > c["quedan"]:
                return False, {"error": f"sólo quedan {max(0, c['quedan'])} lugares" + (
                    f" ({c['en_pago']} en pago en línea: puedes soltarlos)" if c["en_pago"] else "")}
            usados = {k["codigo"] for k in led["compras"].values()} | {a.get("codigo") for a in led["apartados"].values()}
            while True:
                cuerpo = "".join(secrets.choice(ALFABETO) for _ in range(6))
                codigo = f"{cuerpo[:3]}-{cuerpo[3:]}"
                if codigo not in usados:
                    break
            compra = {"codigo": codigo, "cantidad": cantidad, "entraron": cantidad if d.get("entran") else 0,
                      "nombre": nombre, "email": "", "whatsapp": "", "canal": tipo, "metodo": metodo,
                      "bruto": 0 if tipo == "cortesia" else int(show["precio"]) * cantidad, "op": op,
                      "creado": _ahora_local().isoformat(), "estado": "ok", "pidio": pidio}
            led["compras"]["p-" + op] = compra
            r = {"codigo": codigo, "compra": compra}
            _anotar_op(led, op, r, tok)
            return True, r
        r = _mutar_sesion(show["slug"], ses["id"], fn)
        if "error" in r:
            return error(r["error"], 409)
        k = r["compra"]
        if not r.get("repetida"):
            _aviso(f"🚪 {'Cortesía' if tipo == 'cortesia' else 'Venta en puerta'} · {_tg(show['artista'])} {_tg(ses.get('es'))}: "
                   f"{cantidad} · {_tg(k['nombre'])}" + (f" · {_tg(metodo)} {_pesos(k['bruto'])}" if tipo == "puerta" else "")
                   + (f" · la pidió {_tg(pidio)}" if pidio else ""))
            _hoja(show, ses, k, "cortesía" if tipo == "cortesia" else "venta en puerta")
        return jsonify(ok=True, codigo=r["codigo"])

    @app.post("/boletos/puerta/anular")
    @puerta
    def anular(d, show):
        ses = _sesion_o_error(d, show)
        codigo, op, tok = str(d.get("codigo") or "").upper()[:20], _op(d), secrets.token_hex(6)
        motivo = limpiar_nombre(d.get("motivo"), 80)
        if not ses or not codigo:
            return error("datos incompletos", 400)

        def fn(led):
            hecho = _op_hecha(led, op, tok)
            if hecho:
                return False, hecho
            k = next((k for k in led["compras"].values() if k["codigo"] == codigo and k.get("estado", "ok") == "ok"), None)
            if not k:
                return False, {"error": "ese código no está activo en esta sesión"}
            k["estado"] = "anulada"
            k["motivo"] = motivo
            k["anulada"] = _ahora_local().isoformat()
            r = {"codigo": codigo, "compra": dict(k)}
            _anotar_op(led, op, r, tok)
            return True, r
        r = _mutar_sesion(show["slug"], ses["id"], fn)
        if "error" in r:
            return error(r["error"], 404)
        if r.get("repetida"):
            return jsonify(ok=True)
        k = r["compra"]
        _aviso(f"✖️ Anulado {_tg(codigo)} · {_tg(show['artista'])} {_tg(ses.get('es'))}: {k['cantidad']} · {_tg(k['nombre'])}"
               + (f" · {_tg(motivo)}" if motivo else "")
               + ("\nEs una compra web: si no la has reembolsado en Stripe, hazlo allá." if k["canal"] == "web" else ""))
        _hoja(show, ses, k, "anulada")
        return jsonify(ok=True)

    @app.post("/boletos/puerta/mover")
    @puerta
    def mover(d, show):
        ses = _sesion_o_error(d, show)
        destino = _sesion_o_error(d, show, "destino")
        codigo = str(d.get("codigo") or "").upper()[:20]
        if not ses or not destino or ses["id"] == destino["id"] or not codigo:
            return error("datos incompletos", 400)
        origen = next(((llave, k) for llave, k in _leer(show["slug"], ses["id"])["compras"].items()
                       if k["codigo"] == codigo and k.get("estado", "ok") == "ok"), None)
        if not origen:
            return error("ese código no está activo en esta sesión", 404)
        llave_origen, k = origen
        cupo_dest = _cupo(show, destino, _control(show["slug"]))
        llave_copia = "m-" + llave_origen   # la misma compra siempre da la misma copia: reintentar no duplica

        def poner(led):
            if any(x["codigo"] == codigo and x.get("estado", "ok") == "ok" for x in led["compras"].values()):
                return False, {}              # ya está en el destino (un intento anterior): sólo falta quitarla del origen
            if int(k["cantidad"]) > _cuentas(led, cupo_dest)["quedan"]:
                return False, {"error": "no hay lugar en la otra sesión"}
            led["compras"][llave_copia] = dict(k, entraron=0, movida_de=ses["id"], creado=_ahora_local().isoformat())
            return True, {}
        r = _mutar_sesion(show["slug"], destino["id"], poner)
        if "error" in r:
            return error(r["error"], 409)

        def quitar(led):
            kk = led["compras"].get(llave_origen)
            if not kk or kk.get("estado", "ok") != "ok":
                return False, False
            kk["estado"] = "movida"
            kk["movida_a"] = destino["id"]
            return True, True
        try:
            quitado = _mutar_sesion(show["slug"], ses["id"], quitar)
        except TRANSITORIOS:
            return error("quedó en las dos sesiones por un error de conexión: vuelve a tocar «Pasar a» para terminar", 503)
        if quitado:
            _aviso(f"↔️ {_tg(codigo)} ({_tg(k['nombre'])}, {k['cantidad']}) pasó de {_tg(ses.get('es'))} a {_tg(destino.get('es'))}")
        return jsonify(ok=True)

    @app.post("/boletos/puerta/nombre")
    @puerta
    def a_nombre_de(d, show):
        ses = _sesion_o_error(d, show)
        codigo = str(d.get("codigo") or "").upper()[:20]
        nombre = limpiar_nombre(d.get("nombre"))
        if not ses or not codigo:
            return error("datos incompletos", 400)

        def fn(led):
            k = next((k for k in led["compras"].values() if k["codigo"] == codigo and k.get("estado", "ok") == "ok"), None)
            if not k:
                return False, {"error": "ese código no está activo en esta sesión"}
            if k.get("a_nombre_de", "") == nombre:
                return False, {}
            k["a_nombre_de"] = nombre
            return True, {}
        r = _mutar_sesion(show["slug"], ses["id"], fn)
        if "error" in r:
            return error(r["error"], 404)
        return jsonify(ok=True)

    @app.post("/boletos/puerta/soltar")
    @puerta
    def soltar(d, show):
        """Suelta los apartados de pagos en línea de una sesión (sólo los que Stripe confirma expirados)."""
        ses = _sesion_o_error(d, show)
        if not ses:
            return error("elige la sesión", 400)
        led = _leer(show["slug"], ses["id"])
        sueltos, pagados, abiertos = 0, 0, 0
        for h, a in list(led["apartados"].items()):
            s = _expirar_y_consultar(a["cs"]) if a.get("cs") else {"status": "expired"}
            if s is None:
                abiertos += 1
            elif _pagada(s):
                _registrar(s, "puerta (soltar)")
                pagados += 1
            elif s.get("status") == "expired":
                _soltar_por_cs({"id": a.get("cs"), "metadata": {"show": show["slug"], "sesion": ses["id"], "hold": h}})
                sueltos += 1
            else:
                abiertos += 1
        _cache.pop(show["slug"], None)
        return jsonify(ok=True, sueltos=sueltos, pagados=pagados, abiertos=abiertos)

    @app.post("/boletos/puerta/pausa")
    @puerta
    def pausa(d, show):
        pausada = bool(d.get("pausada"))

        def fn(c):
            if c["pausada"] == pausada:
                return False, None
            c["pausada"] = pausada
            return True, None
        _mutar_control(show["slug"], fn)
        _cache.pop(show["slug"], None)
        _aviso(f"{'⏸ Pausé' if pausada else '▶️ Reanudé'} la venta en línea de {_tg(show['artista'])} (desde la puerta)")
        return jsonify(ok=True, pausada=pausada)

    @app.post("/boletos/puerta/cupo")
    @puerta
    def cupo(d, show):
        ses = _sesion_o_error(d, show)
        try:
            n = int(d.get("cupo"))
        except (TypeError, ValueError):
            n = 0
        campo = d.get("campo", "cupo")
        if campo == "cortesias_max":
            if not 0 <= n <= 20:
                return error("tope de cortesías fuera de rango", 400)
        elif not ses or not 1 <= n <= AFORO_MAX:
            return error(f"el cupo va de 1 a {AFORO_MAX}", 400)
        antes = {}

        def fn(c):
            if campo == "cortesias_max":
                antes["v"] = c["ajustes"].get("cortesias_max", show.get("cortesias_max", 0))
                c["ajustes"]["cortesias_max"] = n
            else:
                antes["v"] = c["ajustes"]["cupo"].get(ses["id"], ses["cupo"])
                c["ajustes"]["cupo"][ses["id"]] = n
            return True, None
        _mutar_control(show["slug"], fn)
        _cache.pop(show["slug"], None)
        que = "tope de cortesías" if campo == "cortesias_max" else f"cupo {ses.get('es')}"
        _aviso(f"✏️ {_tg(show['artista'])}: {_tg(que)} {antes.get('v')} → {n} (desde la puerta)")
        return jsonify(ok=True)

    @app.post("/boletos/puerta/telegram")
    @puerta
    def a_telegram(d, show):
        que = d.get("que")
        if que == "lista":
            ok = all([_aviso(t) for t in _textos_lista(show)])
        elif que == "liquidacion":
            liq = liquidacion(show["slug"])
            ruta = os.path.join(tempfile.gettempdir(), f"liquidacion-{show['slug']}.csv")
            with open(ruta, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write(_csv_liquidacion(liq))
            ok = _aviso(_texto_liquidacion(liq), archivo=ruta, nombre_archivo=f"liquidacion-{show['slug']}.csv")
            try:
                _almacen().escribir(f"{PREFIJO}{show['slug']}/liquidacion-{_ahora_local():%Y%m%d-%H%M%S}.json", liq, 0)
            except Exception as e:   # noqa: BLE001
                print("no se guardó copia de la liquidación:", e)
        else:
            return error("¿lista o liquidación?", 400)
        return jsonify(ok=True, enviado=ok) if ok else error("Telegram no respondió; inténtalo otra vez", 502)

    # ---------------- operación (X-Refresh-Key: Cloud Scheduler o Claude)
    def llave_ok():
        return bool(refresh_key) and hmac.compare_digest(request.headers.get("X-Refresh-Key", "").encode(), refresh_key.encode())

    @app.post("/boletos/lista-telegram")
    @fallas
    def lista_telegram():
        if not llave_ok():
            return error("no autorizado", 401)
        show = SHOWS.get((request.get_json(silent=True) or {}).get("show") or request.args.get("show", ""))
        if not show:
            return error("ese show no existe", 404)
        for t in _textos_lista(show):
            _aviso(t)
        return jsonify(ok=True)

    @app.get("/boletos/liquidacion")
    @fallas
    def liquidacion_json():
        if not llave_ok():
            return error("no autorizado", 401)
        show = SHOWS.get(request.args.get("show", ""))
        if not show:
            return error("ese show no existe", 404)
        return jsonify(liquidacion(show["slug"]))

    @app.post("/boletos/huerfana")
    @fallas
    def registrar_huerfana():
        """Registra un pago huérfano con su mismo código y su misma comisión. Body: {cs, show, sesion}
        (show y sesión a los que va, por si el catálogo cambió)."""
        if not llave_ok():
            return error("no autorizado", 401)
        d = request.get_json(silent=True) or {}
        show = SHOWS.get(str(d.get("show") or ""))
        ses = _sesion_cfg(show, str(d.get("sesion") or "")) if show else None
        datos, _ = _almacen().leer(f"{PREFIJO}huerfanas.json")
        h = ((datos or {}).get("huerfanas") or {}).get(str(d.get("cs") or ""))
        if not show or not ses or not h or not h.get("sesion_stripe"):
            return error("no encontré esa huérfana, o el show o la sesión", 404)
        s = dict(h["sesion_stripe"])
        s["metadata"] = dict(s.get("metadata") or {}, show=show["slug"], sesion=ses["id"])
        compra = _registrar(s, "huerfana")
        return jsonify(ok=bool(compra), compra=_publico_compra(show, ses, compra) if compra else None)
