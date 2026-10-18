# -*- coding: utf-8 -*-
"""API de rossospeakeasy.com (Cloud Run, servicio rosso-web-api).

GET  /carta            carta viva (JSON) leida del bucket; se regenera con /carta/refresh
POST /carta/refresh    recalcula la carta desde Wansoft (Cloud Scheduler, header X-Refresh-Key)
POST /eventos          solicitud de grupo o evento desde el sitio -> borrador de cotizacion
                       (docx en membrete) + aviso a Pablo por Telegram + copia en el bucket
GET  /health
"""
import datetime as dt
import json
import os
import re
import secrets
import sys
import threading
import time

import requests
from flask import Flask, jsonify, request, make_response

import agenda as agenda_mod
import carta as carta_mod
import metricas as metricas_mod
import regalo as regalo_mod
import clientes as clientes_mod
import descripciones as descripciones_mod
import vinilos as vinilos_mod
import sello as sello_mod
import marcador as marcador_mod
import freno as freno_mod
import cotizador
import pdf_cotizacion
import correo as correo_mod
import tarifario as tf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = Flask(__name__)

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN_ROSSO", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID_ROSSO", "")
WS_SUB = os.environ.get("WANSOFT_SUB", "")
WS_PWD = os.environ.get("WANSOFT_PWD", "")
BUCKET = os.environ.get("BUCKET", "")
PREFIJO = "rosso-web/"
REFRESH_KEY = os.environ.get("REFRESH_KEY", "")
ORIGENES = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "https://rossospeakeasy.com,http://rossospeakeasy.com,https://www.rossospeakeasy.com,"
    "http://www.rossospeakeasy.com,https://pablosels.github.io,http://localhost:8765"
).split(",") if o.strip()]
WHATSAPP = "5664357899"

_cache = {"carta": None, "t": 0}
_lock = threading.Lock()


# ------------------------------------------------------------------ utilidades
def _bucket():
    from google.cloud import storage
    return storage.Client().bucket(BUCKET)


def guardar(nombre, datos, content_type="application/json"):
    if not BUCKET:
        return
    blob = _bucket().blob(PREFIJO + nombre)
    if isinstance(datos, (dict, list)):
        datos = json.dumps(datos, ensure_ascii=False, indent=1)
    blob.upload_from_string(datos, content_type=content_type)


def leer(nombre):
    if not BUCKET:
        return None
    blob = _bucket().blob(PREFIJO + nombre)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


def cors(resp):
    origen = request.headers.get("Origin", "")
    if origen in ORIGENES:
        resp.headers["Access-Control-Allow-Origin"] = origen
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


@app.after_request
def _after(resp):
    return cors(resp)


@app.route("/<path:_p>", methods=["OPTIONS"])
@app.route("/", methods=["OPTIONS"])
def _options(_p=""):
    return make_response("", 204)


def telegram(texto, archivo=None, nombre_archivo=None):
    if not (TG_TOKEN and TG_CHAT):
        print("telegram: sin credenciales, mensaje:", texto[:200])
        return
    base = f"https://api.telegram.org/bot{TG_TOKEN}"
    r = requests.post(f"{base}/sendMessage", timeout=20,
                      data={"chat_id": TG_CHAT, "text": texto, "parse_mode": "HTML",
                            "disable_web_page_preview": True})
    if archivo:
        with open(archivo, "rb") as fh:
            requests.post(f"{base}/sendDocument", timeout=60,
                          data={"chat_id": TG_CHAT},
                          files={"document": (nombre_archivo or os.path.basename(archivo), fh)})
    return r.ok


def dinero(n):
    return "${:,.0f}".format(round(float(n)))


# ------------------------------------------------------------------ PIN de barra con freno de intentos
freno_pin = freno_mod.Freno(avisar=lambda texto: telegram(texto))


def revisar_pin(pin, ruta):
    """None si el PIN de barra es bueno; si no, la respuesta de error (403, o 429 si esa IP ya
    se equivocó demasiadas veces). Ver freno.py: el freno vive en memoria y es parcial."""
    ip = freno_mod.clave_ip(request.headers.get("X-Forwarded-For"), request.remote_addr)
    espera = freno_pin.espera(ip)
    if not espera:
        if regalo_mod.pin_correcto(pin):
            freno_pin.acierto(ip)
            return None
        # un PIN vacío nunca atina: no cuenta como intento
        if not str(pin or "").strip() or not freno_pin.fallo(ip, ruta):
            return jsonify(error="PIN incorrecto"), 403
        espera = freno_pin.espera(ip)   # este fallo fue el que la bloqueó
    resp = jsonify(error=f"Demasiados intentos con PIN equivocado. Espera {-(-espera // 60)} min y vuelve a intentar.")
    resp.headers["Retry-After"] = str(espera)
    return resp, 429


# ------------------------------------------------------------------ carta
@app.get("/health")
def health():
    return jsonify(ok=True, hora=dt.datetime.now().isoformat(timespec="seconds"))


@app.get("/carta")
def get_carta():
    with _lock:
        if _cache["carta"] and time.time() - _cache["t"] < 600:
            datos = _cache["carta"]
        else:
            datos = leer("carta.json")
            if datos:
                _cache.update(carta=datos, t=time.time())
    if not datos:
        return jsonify(error="carta no generada todavía"), 503
    resp = jsonify(descripciones_mod.aplicar(datos))
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


@app.post("/carta/refresh")
def refresh_carta():
    if not REFRESH_KEY or request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    if not (WS_SUB and WS_PWD):
        return jsonify(error="sin credenciales de Wansoft"), 500
    datos = carta_mod.armar_carta(WS_SUB, WS_PWD)
    n = sum(len(s["items"]) + sum(len(x["items"]) for x in s["subsecciones"])
            for s in datos["secciones"])
    guardar("carta.json", datos)
    with _lock:
        _cache.update(carta=datos, t=time.time())
    return jsonify(ok=True, productos=n, ventana=datos["ventana"])


# ------------------------------------------------------------------ agenda de DJs
_agenda_cache = {"datos": None, "t": 0}


@app.get("/agenda")
def get_agenda():
    with _lock:
        if _agenda_cache["datos"] is not None and time.time() - _agenda_cache["t"] < 300:
            datos = _agenda_cache["datos"]
        else:
            try:
                datos = agenda_mod.proximas(dias=21)
            except Exception as e:
                print("agenda fallo:", e)
                datos = _agenda_cache["datos"] or []
            _agenda_cache.update(datos=datos, t=time.time())
    resp = jsonify({"hoy": dt.date.today().isoformat(), "noches": datos})
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.post("/agenda/recordatorio")
def recordatorio_agenda():
    """Cloud Scheduler, lunes y martes 10:00: avisa por Telegram qué noches de la semana faltan."""
    if not REFRESH_KEY or request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    try:
        faltan = agenda_mod.semana_faltante()
    except Exception as e:
        telegram(f"⚠️ No pude leer la hoja Agenda ROSSO: {e}")
        return jsonify(error=str(e)), 500
    liga = f"https://docs.google.com/spreadsheets/d/{agenda_mod.SHEET_ID}/edit"
    if faltan:
        texto = ("🎧 <b>Agenda de la semana</b>\nFaltan los DJs de: <b>" + ", ".join(faltan) + "</b>.\n"
                 f"Llena la hoja y el sitio se actualiza solo en 5 minutos:\n{liga}")
    else:
        texto = f"🎧 <b>Agenda de la semana</b>: completa. Ya está en rossospeakeasy.com/noches/\n{liga}"
    try:
        pendientes = agenda_mod.pagos_pendientes()
    except Exception:
        pendientes = []
    try:
        if vinilos_mod.SHEET_ID and vinilos_mod.falta_domingo():
            texto += (f"\n\n💿 <b>Vinilo del domingo</b>: falta capturar el disco del {vinilos_mod.proximo_domingo().strftime('%d/%m')}."
                      f"\nHoja: https://docs.google.com/spreadsheets/d/{vinilos_mod.SHEET_ID}/edit")
    except Exception as e:
        print("vinilo recordatorio fallo:", e)
    mensajes_dj = []
    try:
        semana = [n for n in agenda_mod.proximas(dias=6)]
        if semana:
            texto += "\n\n📣 Abajo va un mensaje por DJ, listo para reenviar tal cual (que lo suban a su historia el día que tocan)."
            for n in semana:
                mensajes_dj.append(
                    f"Hola {n['dj']}, te dejo tu página en ROSSO para el {n['fecha_larga']}:\n"
                    f"https://rossospeakeasy.com/dj/?n={n['slug']}&de=dj\n\n"
                    "1. Ábrela en tu cel y toca “Imagen para tu historia”.\n"
                    "2. Al subirla a Instagram, agrega el sticker “Enlace” y pega esa misma liga.\n"
                    "3. Ponle “Reservar” al sticker.\n\n"
                    "Sin el sticker la gente no puede entrar a reservar. ¡Gracias!")
    except Exception as e:
        print("mensajes dj fallo:", e)
    if pendientes:
        total = sum(p["_pago"] for p in pendientes)
        texto += ("\n\n💸 <b>Pagos a DJs pendientes</b> (" + dinero(total) + "):\n"
                  + "\n".join(f"· {p['dj']} — {p['fecha_larga']} — {dinero(p['_pago'])}" for p in pendientes)
                  + "\nMarca SI en la columna <i>pagado</i> cuando los liquides.")
    telegram(texto)
    for m in mensajes_dj:
        telegram(m)
    with _lock:
        _agenda_cache.update(datos=None, t=0)
    return jsonify(ok=True, faltan=faltan, mensajes_dj=len(mensajes_dj))


# ------------------------------------------------------------------ mantenimiento de hojas
@app.post("/hojas/arreglar")
def hojas_arreglar():
    """Pone locale es_MX en Agenda y Vinilos y reescribe la columna fecha de la agenda con las
    fechas corregidas por el parser, como texto ISO. Idempotente."""
    if not REFRESH_KEY or request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
    ses = AuthorizedSession(creds)
    out = {}
    for sid in (agenda_mod.SHEET_ID, vinilos_mod.SHEET_ID):
        if not sid:
            continue
        r = ses.post(f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate", timeout=20,
                     json={"requests": [{"updateSpreadsheetProperties": {"properties": {"locale": "es_MX", "timeZone": "America/Mexico_City"}, "fields": "locale,timeZone"}}]})
        out[sid[:8]] = r.status_code
    # fechas de la agenda
    r = ses.get(f"https://sheets.googleapis.com/v4/spreadsheets/{agenda_mod.SHEET_ID}/values/A1:C400", timeout=20)
    vals = r.json().get("values", [])
    hoy = dt.date.today()
    filas, cambios = [], []
    for i, f in enumerate(vals[1:], start=2):
        txt = f[0] if f else ""
        fecha = agenda_mod._fecha(txt, hoy) if txt else None
        nuevo = fecha.isoformat() if fecha else txt
        filas.append([nuevo])
        if nuevo != txt:
            cambios.append(f"{txt} -> {nuevo} ({f[2] if len(f) > 2 else ''})")
    if filas:
        r = ses.put(f"https://sheets.googleapis.com/v4/spreadsheets/{agenda_mod.SHEET_ID}/values/A2:A{len(filas) + 1}?valueInputOption=RAW",
                    json={"values": filas}, timeout=20)
        out["fechas"] = r.status_code
    with _lock:
        _agenda_cache.update(datos=None, t=0)
    _djs_cache.update(datos=None, t=0)
    return jsonify(ok=True, resultado=out, cambios=cambios)


@app.post("/correo/prueba")
def correo_prueba():
    """Diagnóstico: entra a Gmail por IMAP, ubica Borradores y deja un borrador de prueba. Nunca devuelve secretos."""
    if not REFRESH_KEY or request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    import imaplib
    info = {"configurado": correo_mod.configurado(), "usuario": correo_mod.USUARIO, "clave_len": len(correo_mod.CLAVE)}
    if not correo_mod.configurado():
        return jsonify(info)
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        info["login"] = imap.login(correo_mod.USUARIO, correo_mod.CLAVE)[0]
        info["carpeta"] = correo_mod._carpeta_borradores(imap)
        ok, datos = imap.append(f'"{info["carpeta"]}"', "\Draft", imaplib.Time2Internaldate(time.time()),
                                correo_mod.armar(correo_mod.USUARIO, "Prueba de borrador ROSSO", "Si ves esto, la API ya deja borradores.").as_bytes())
        info["append"] = [ok, str(datos)[:200]]
        imap.logout()
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"[:300]
    return jsonify(info)


# ------------------------------------------------------------------ marcador de DJs (venta real por noche)
@app.post("/marcador")
def marcador_djs():
    """Cloud Scheduler, lunes: venta de cada noche con DJ contra lo normal de ese día. ?silencio=1 no manda Telegram."""
    if not REFRESH_KEY or request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    if not (WS_SUB and WS_PWD):
        return jsonify(error="sin credenciales de Wansoft"), 500
    dias = max(3, min(45, int(request.args.get("dias", 8))))
    filas = marcador_mod.marcador(WS_SUB, WS_PWD, leer, guardar, dias=dias)
    texto = marcador_mod.texto(filas)
    if not request.args.get("silencio"):
        telegram(texto)
    return jsonify(ok=True, noches=filas, texto=texto)


# ------------------------------------------------------------------ perfiles de DJs
_djs_cache = {"t": 0, "datos": None}


@app.get("/djs")
def get_djs():
    if _djs_cache["datos"] is None or time.time() - _djs_cache["t"] > 300:
        try:
            _djs_cache.update(datos=agenda_mod.djs(), t=time.time())
        except Exception as e:
            print("djs fallo:", e)
            _djs_cache.update(datos=_djs_cache["datos"] or [], t=time.time())
    resp = jsonify({"djs": _djs_cache["datos"]})
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.get("/dj/<k>")
def get_dj(k):
    k = re.sub(r"[^a-z0-9-]", "", k.lower())[:60]
    try:
        d = agenda_mod.dj(k)
    except Exception as e:
        print("dj fallo:", e)
        d = None
    if not d:
        return jsonify(error="no encontramos a ese selector"), 404
    resp = jsonify(d)
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


# ------------------------------------------------------------------ Sello ROSSO (lealtad por visitas)
@app.get("/sello/buscar")
def sello_buscar():
    error = revisar_pin(request.headers.get("X-Pin"), "sello/buscar")
    if error:
        return error
    q = regalo_mod.limpiar_texto(request.args.get("q"), 40)
    if len(q) < 3:
        return jsonify(error="escribe al menos 3 caracteres"), 400
    try:
        return jsonify(clientes=sello_mod.buscar(q), premio_cada=sello_mod.PREMIO_CADA)
    except Exception as e:
        print("sello buscar fallo:", e)
        return jsonify(error="no se pudo consultar; inténtalo otra vez"), 502


@app.post("/sello/registrar")
def sello_registrar():
    d = request.get_json(silent=True, force=True) or {}
    error = revisar_pin(d.get("pin"), "sello/registrar")
    if error:
        return error
    try:
        r = sello_mod.registrar(d.get("whatsapp"), regalo_mod.limpiar_texto(d.get("quien"), 40))
    except LookupError as e:
        return jsonify(error=str(e)), 404
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        print("sello registrar fallo:", e)
        return jsonify(error="no se pudo registrar; inténtalo otra vez"), 502
    if r["premio"]:
        try:
            telegram(f"🏅 <b>Sello ROSSO</b>: {r['nombre']} llegó a su visita {r['visitas']}. Toca cóctel de la casa.")
        except Exception:
            pass
    return jsonify(ok=True, **r)


# ------------------------------------------------------------------ vinilo del domingo
@app.get("/vinilo")
def get_vinilo():
    try:
        datos = vinilos_mod.actual()
    except Exception as e:
        print("vinilo fallo:", e)
        datos = {"domingo": vinilos_mod.proximo_domingo().isoformat(), "vinilo": None, "anteriores": []}
    resp = jsonify(datos)
    resp.headers["Cache-Control"] = "public, max-age=600"
    return resp


# ------------------------------------------------------------------ métricas de origen
@app.post("/clic")
def clic():
    """El sitio manda un beacon por visita y por clic importante. Sin datos personales."""
    d = request.get_json(silent=True, force=True) or {}   # el beacon llega como text/plain
    fila = metricas_mod.limpiar(d)
    if not fila:
        return jsonify(ok=False), 400
    try:
        metricas_mod.anotar(fila)
    except Exception as e:
        print("metricas fallo:", e)
    return jsonify(ok=True)


@app.post("/metricas/resumen")
def metricas_resumen():
    """Cloud Scheduler, lunes 9:30: resumen de la semana por canal al Telegram de Rosso."""
    if not REFRESH_KEY or request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    try:
        metricas_mod.vaciar()
        texto = metricas_mod.texto_resumen(7)
    except Exception as e:
        return jsonify(error=str(e)), 500
    telegram(texto)
    return jsonify(ok=True)


@app.get("/metricas")
def metricas_json():
    if not REFRESH_KEY or request.args.get("k") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 401
    metricas_mod.vaciar()
    return jsonify(metricas_mod.resumen(int(request.args.get("dias", 7))))


# ------------------------------------------------------------------ tarjetas de regalo
@app.get("/regalo/config")
def regalo_config():
    return jsonify(activo=regalo_mod.configurado(), montos=list(regalo_mod.MONTOS), vigencia_dias=regalo_mod.VIGENCIA_DIAS)


@app.post("/regalo/checkout")
def regalo_checkout():
    if not regalo_mod.configurado():
        return jsonify(error="las tarjetas de regalo todavía no están activas"), 503
    d = request.get_json(silent=True, force=True) or {}
    try:
        monto = int(d.get("monto") or 0)
    except (TypeError, ValueError):
        monto = 0
    if monto not in regalo_mod.MONTOS:
        return jsonify(error="elige un monto válido"), 400
    email = regalo_mod.limpiar_texto(d.get("email"), 120)
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify(error="revisa el correo"), 400
    try:
        sid, url = regalo_mod.crear_sesion(monto, regalo_mod.limpiar_texto(d.get("de"), 80),
                                           regalo_mod.limpiar_texto(d.get("para"), 80),
                                           regalo_mod.limpiar_texto(d.get("mensaje"), 200), email,
                                           regalo_mod.limpiar_texto(d.get("canal"), 24) or "directo")
    except Exception as e:
        print("stripe checkout fallo:", e)
        return jsonify(error="no se pudo iniciar el pago; inténtalo de nuevo"), 502
    return jsonify(ok=True, url=url, sesion=sid)


@app.post("/stripe/webhook")
def stripe_webhook():
    if not regalo_mod.configurado():
        return jsonify(error="no configurado"), 503
    payload = request.get_data()
    if not regalo_mod.verificar_firma(payload, request.headers.get("Stripe-Signature", "")):
        return jsonify(error="firma inválida"), 400
    evento = json.loads(payload)
    if evento.get("type") == "checkout.session.completed":
        ses = evento["data"]["object"]
        if (ses.get("metadata") or {}).get("tipo") == "regalo":
            d = regalo_mod.registrar_pago(ses)
            if d:
                try:
                    telegram(f"🎁 <b>Tarjeta de regalo vendida</b>: {dinero(d['monto'])}\n"
                             f"Código <code>{d['codigo']}</code> · de {d['comprador'] or '—'} para {d['para'] or '—'}"
                             + (f" · {d['email']}" if d['email'] else "")
                             + f"\nVence {d['vence']}. Hoja: https://docs.google.com/spreadsheets/d/{regalo_mod.SHEET_ID}/edit")
                except Exception as e:
                    print("telegram fallo:", e)
    return jsonify(ok=True)


@app.get("/regalo/estado")
def regalo_estado():
    sid = re.sub(r"[^A-Za-z0-9_]", "", request.args.get("s", ""))[:80]
    if not sid.startswith("cs_"):
        return jsonify(error="sesión inválida"), 400
    fila, d = regalo_mod.buscar(sesion=sid)
    if not d:
        return jsonify(listo=False)
    return jsonify(listo=True, tarjeta=regalo_mod.publica(d))


@app.get("/regalo/saldo")
def regalo_saldo():
    codigo = re.sub(r"[^A-Za-z0-9-]", "", request.args.get("c", "")).upper()[:16]
    fila, d = regalo_mod.buscar(codigo=codigo)
    if not d:
        return jsonify(error="ese código no existe"), 404
    return jsonify(tarjeta=regalo_mod.publica(d))


@app.post("/regalo/canjear")
def regalo_canjear():
    d = request.get_json(silent=True, force=True) or {}
    error = revisar_pin(d.get("pin"), "regalo/canjear")
    if error:
        return error
    try:
        t = regalo_mod.canjear(regalo_mod.limpiar_texto(d.get("codigo"), 16), d.get("monto"), str(d.get("pin", "")))
    except PermissionError as e:
        return jsonify(error=str(e)), 403
    except LookupError as e:
        return jsonify(error=str(e)), 404
    except (ValueError, TypeError) as e:
        return jsonify(error=str(e)), 400
    try:
        telegram(f"🎁 Canje: <code>{t['codigo']}</code> −{dinero(int(d.get('monto') or 0))} · saldo {dinero(t['saldo'])} ({t['estado']})")
    except Exception:
        pass
    return jsonify(ok=True, tarjeta=t)


# ------------------------------------------------------------------ club ROSSO (clientes y cumpleaños)
@app.post("/clientes")
def clientes_alta():
    d = request.get_json(silent=True, force=True) or {}
    if d.get("empresa_web"):
        return jsonify(ok=True, nuevo=False)   # miel para bots
    nombre = regalo_mod.limpiar_texto(d.get("nombre"), 80)
    whatsapp = clientes_mod.limpiar_whatsapp(d.get("whatsapp"))
    email = regalo_mod.limpiar_texto(d.get("email"), 120).lower()
    cumple = clientes_mod.limpiar_cumple(d.get("cumple"))
    if not nombre or not whatsapp:
        return jsonify(error="nos faltan tu nombre y tu WhatsApp"), 400
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return jsonify(error="revisa el correo"), 400
    if d.get("cumple") and not cumple:
        return jsonify(error="escribe tu cumpleaños como día/mes, por ejemplo 14/02"), 400
    if not d.get("acepto"):
        return jsonify(error="necesitamos que aceptes el aviso de privacidad"), 400
    try:
        r = clientes_mod.alta(nombre, whatsapp, email, cumple, regalo_mod.limpiar_texto(d.get("canal"), 24))
    except Exception as e:
        print("alta cliente fallo:", e)
        return jsonify(error="no se pudo guardar; inténtalo otra vez"), 502
    if r["nuevo"]:
        try:
            telegram(f"👋 <b>Nuevo en Club ROSSO</b>: {nombre}" + (f" · cumple {cumple}" if cumple else "") + f" · <a href=\"https://wa.me/{whatsapp}\">WhatsApp</a>")
        except Exception as e:
            print("telegram fallo:", e)
    return jsonify(ok=True, nuevo=r["nuevo"])


@app.post("/clientes/cumples")
def clientes_cumples():
    if request.headers.get("X-Refresh-Key") != REFRESH_KEY:
        return jsonify(error="no autorizado"), 403
    texto = clientes_mod.texto_cumples()
    try:
        if sello_mod.SHEET_ID:
            r = sello_mod.resumen_semana()
            texto += f"\n\n🏅 Sello ROSSO, 7 días: {r['visitas']} visitas de {r['personas']} personas · {r['premios']} cócteles de premio."
    except Exception as e:
        print("sello resumen fallo:", e)
    telegram(texto)
    return jsonify(ok=True)


# ------------------------------------------------------------------ locación para producciones
TIPOS_PRODUCCION = {"foto": "Fotografía", "video": "Video / comercial", "cine": "Cine / serie", "redes": "Contenido para redes",
                    "podcast": "Podcast / grabación", "otro": "Otro"}
NECESIDADES = {"barra": "Barra con bartender", "audio": "Audio y cabina de DJ", "cocina": "Cocina de Pavorosso",
               "vestidor": "Espacio de vestidor / maquillaje", "carga": "Carga y descarga por la calle"}


def armar_cotizacion_locacion(sol, fecha, horas, crew, nec, renta, abierto):
    """Cotización de locación: renta del lugar por horas + IVA; extras listados como aparte."""
    dia = tf.fecha_larga(fecha, "es")
    iva = round(renta * 0.16)
    total = renta + iva
    if horas >= 12 and not abierto:
        concepto = "Jornada completa de 12 horas, lunes"
    elif horas >= 8:
        concepto = f"Jornada de 8 horas" + (f" + {horas - 8} hora{'s' if horas - 8 > 1 else ''} extra" if horas > 8 else "")
    else:
        concepto = f"{max(3, horas)} horas de locación" + (" (mínimo 3)" if horas < 3 else "")
    extras = [NECESIDADES[n] for n in nec]
    tipo = TIPOS_PRODUCCION.get(sol["tipo"], "Producción")
    return {
        "archivo": f"ROSSO_Locacion_{fecha.isoformat()}_{re.sub(r'[^A-Za-z0-9]+', '-', sol['nombre'])[:30]}.pdf",
        "idioma": "es",
        "kicker": "Cotización de locación",
        "titulo": (sol["proyecto"] or tipo) + " en ROSSO",
        "subtitulo": f"{dia} · llamado {sol['hora']} · {horas} h · equipo de {crew}",
        "cliente": sol["nombre"] + (f" · {sol['proyecto']}" if sol["proyecto"] else ""),
        "fecha": dia, "horario": f"Desde las {sol['hora']}", "duracion": f"{horas} horas",
        "invitados": f"{crew} personas entre equipo y talento", "modalidad": f"Locación · {tipo}",
        "intro": ("Gracias por pensar en ROSSO como set. Somos un speakeasy de 40 m² en Puebla 329, Roma Norte: "
                  "barra completa con bancas alrededor, cabina de DJ de frente a la entrada y techo de círculos de luz, disponible en las horas en que "
                  "el bar está cerrado. Aquí va la propuesta para tu fecha; cualquier detalle lo ajustamos por WhatsApp."),
        "bloques": [
            {"tipo": "tabla", "titulo": "La locación",
             "nota": "Renta solo del lugar: acceso, luz de sala y energía. " + ("Ese día abrimos al público; la producción debe terminar antes de las 4:00 pm (domingo 2:00 pm)." if abierto else "Lunes: el espacio es tuyo el día completo."),
             "filas": [[concepto, dinero(renta), True], ["IVA 16%", dinero(iva), False]],
             "total": dinero(total) + " MXN", "etiqueta_total": "TOTAL"},
            {"tipo": "vinetas", "titulo": "Se cotiza aparte, según lo que necesiten",
             "items": (extras or ["Barra con bartender", "Audio y cabina de DJ", "Cocina de Pavorosso", "Personal de apoyo"])
                      + ["Cualquier otro requerimiento de producción que nos cuentes por WhatsApp."]},
            {"tipo": "vinetas", "titulo": "Condiciones",
             "items": ["Apartado del 50% para bloquear la fecha; el resto el día del llamado.",
                       "Carga y descarga por la calle; el acceso es por la cocina de Pavorosso.",
                       "Aforo máximo de 50 personas entre equipo y talento.",
                       "Precios en pesos mexicanos. Vigencia de 10 días naturales."]},
        ],
        "cierre": f"ROSSO · WhatsApp +52 {WHATSAPP} · hola@rossospeakeasy.com · @rosso.speakeasy",
    }


def _borrador_locacion(sol, fecha, folio, ruta_pdf):
    if not correo_mod.configurado():
        return f"\n\n✉️ El cliente dejó correo: {sol['email']} (los borradores automáticos se activan con GMAIL_APP_PASSWORD)."
    if not ruta_pdf:
        return ""
    try:
        ok = correo_mod.crear_borrador(sol["email"], f"Cotización de locación ROSSO · {tf.fecha_larga(fecha, 'es')}",
                                       correo_mod.texto_locacion(dict(sol, fecha_larga=tf.fecha_larga(fecha, 'es')), folio),
                                       ruta_pdf, os.path.basename(ruta_pdf))
        return f"\n\n✉️ Borrador listo en tu Gmail (Borradores) para {sol['email']}, desde hola@." if ok else "\n\n✉️ No se pudo dejar el borrador en Gmail."
    except Exception as e:
        print("borrador gmail fallo:", e)
        return "\n\n✉️ No se pudo dejar el borrador en Gmail."


@app.post("/produccion")
def produccion():
    d = request.get_json(silent=True) or request.form.to_dict() or {}
    if _limpio(d.get("empresa_web")):
        return jsonify(ok=True)
    try:
        fecha = dt.date.fromisoformat(_limpio(d.get("fecha"), 10))
        horas = max(1, min(14, int(d.get("horas") or 4)))
        crew = max(1, min(80, int(d.get("crew") or 0)))
    except (ValueError, TypeError):
        return jsonify(error="revisa la fecha, las horas o el tamaño del equipo"), 400
    nombre = _limpio(d.get("nombre"), 80)
    whatsapp = re.sub(r"[^0-9+]", "", str(d.get("whatsapp") or ""))[:16]
    if not nombre or len(whatsapp) < 10:
        return jsonify(error="faltan nombre o WhatsApp"), 400
    if fecha < dt.date.today():
        return jsonify(error="la fecha ya pasó"), 400
    nec = d.get("necesidades") or []
    if isinstance(nec, str):
        nec = [nec]
    nec = [n for n in nec if n in NECESIDADES]
    tipo = _limpio(d.get("tipo"), 12)
    sol = {
        "recibida": dt.datetime.now().isoformat(timespec="seconds"),
        "nombre": nombre, "whatsapp": whatsapp, "email": _limpio(d.get("email"), 120),
        "proyecto": _limpio(d.get("proyecto"), 120), "tipo": tipo if tipo in TIPOS_PRODUCCION else "otro",
        "fecha": fecha.isoformat(), "hora": _limpio(d.get("hora"), 10) or "9:00 am", "horas": horas, "crew": crew,
        "necesidades": nec, "mensaje": _limpio(d.get("mensaje"), 1000),
        "canal": _limpio(d.get("canal"), 24) or "directo",
    }
    folio = "P" + fecha.strftime("%y%m%d") + "-" + secrets.token_hex(2).upper()
    try:
        guardar(f"producciones/{folio}.json", dict(sol, folio=folio))
    except Exception as e:
        print("bucket fallo:", e)
    dia = tf.nombre_dia(fecha)
    abierto = fecha.weekday() != 0   # lunes cerrado: día libre completo
    if horas >= 12 and not abierto:
        referencia = 16000
    elif horas >= 8:
        referencia = 12000 + (horas - 8) * 1500
    else:
        referencia = max(3, horas) * 1800
    aviso = "" if not abierto else " ⚠️ ese día abrimos; la producción tendría que terminar antes de la apertura."
    ruta_pdf = None
    try:
        cfg = armar_cotizacion_locacion(sol, fecha, horas, crew, nec, referencia, abierto)
        ruta_pdf = os.path.join("/tmp" if os.name != "nt" else os.environ.get("TEMP", "."), cfg["archivo"])
        pdf_cotizacion.generar(cfg, ruta_pdf)
        if BUCKET:
            _bucket().blob(PREFIJO + f"producciones/{folio}.pdf").upload_from_filename(ruta_pdf)
    except Exception as e:
        print("pdf locación fallo:", e)
        ruta_pdf = None
    telegram(
        f"🎬 <b>Solicitud de locación</b> · folio {folio}\n"
        f"{nombre} · <a href=\"https://wa.me/{whatsapp.lstrip('+')}\">WhatsApp</a>" + (f" · {sol['email']}" if sol['email'] else "") + "\n"
        f"{TIPOS_PRODUCCION[sol['tipo']]}" + (f" — {sol['proyecto']}" if sol['proyecto'] else "") + "\n"
        f"{dia} {fecha.day}/{fecha.month} desde las {sol['hora']} · {horas} h · equipo de {crew}{aviso}\n"
        f"Tarifa de referencia solo del lugar: <b>{dinero(referencia)}</b> + IVA\n"
        + (f"Necesita (extra): {', '.join(NECESIDADES[n] for n in nec)}\n" if nec else "")
        + (f"«{sol['mensaje']}»" if sol['mensaje'] else "")
        + ("\n\nLa cotización en PDF va adjunta, lista para reenviar." if ruta_pdf else "")
        + (_borrador_locacion(sol, fecha, folio, ruta_pdf) if sol["email"] else ""),
        ruta_pdf, os.path.basename(ruta_pdf) if ruta_pdf else None
    )
    return jsonify(ok=True, folio=folio)


# ------------------------------------------------------------------ eventos
def _limpio(s, n=300):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def _carta_viva():
    """La carta publicada, para anexarla a las cotizaciones. {} si no hay."""
    try:
        with _lock:
            if _cache["carta"] and time.time() - _cache["t"] < 600:
                datos = _cache["carta"]
            else:
                datos = leer("carta.json")
                if datos:
                    _cache.update(carta=datos, t=time.time())
        return datos or {}
    except Exception:
        return {}


def _bloques_carta(es, lejano=False):
    """Cocina (tabla con precios) y barra (lista por seccion) desde /carta.

    Sin esto el cliente compromete consumo minimo sin haber visto un solo
    precio, que es el hallazgo mas repetido de la auditoria del 12-oct.
    """
    datos = _carta_viva()
    secs = datos.get("secciones") or []
    if not secs:
        return []
    cocina, barra = None, []
    for s in secs:
        t = (s.get("titulo") or "").strip()
        items = list(s.get("items") or [])
        subs = s.get("subsecciones") or []
        if t == "Para picar":
            cocina = items
            continue
        if items:
            barra.append((t, items))
        for sub in subs:
            si = list(sub.get("items") or [])
            if si:
                barra.append((f"{t} · {sub.get('titulo') or ''}".strip(" ·"), si))
    out = []
    if cocina:
        out.append({
            "tipo": "tabla",
            "titulo": "La cocina" if es else "The kitchen",
            "nota": (((
                "La carta completa de cocina de ROSSO. Todo se sirve al centro para "
                "compartir y cuenta para el consumo mínimo. Los precios de carta de este "
                "documento ya incluyen IVA y son los vigentes hoy: por tratarse de una "
                "fecha lejana, la noche de su evento aplica la carta de esa fecha. La "
                "renta y el consumo mínimo no cambian.") if lejano else (
                "La carta completa de cocina de ROSSO. Todo se sirve al centro para "
                "compartir y cuenta para el consumo mínimo. Los precios de carta de este "
                "documento ya incluyen IVA y se los sostenemos para la noche de su "
                "evento.")) if es else ((
                "ROSSO's full kitchen menu. Everything is served to share and counts "
                "toward the minimum spend. Menu prices here include VAT and are today's: "
                "as the date is far out, the menu in force on the night applies. The "
                "venue rental and the minimum spend do not change.") if lejano else (
                "ROSSO's full kitchen menu. Everything is served to share and counts "
                "toward the minimum spend. Menu prices in this document include VAT "
                "and are held for the night of your event."))),
            "filas": [[it.get("nombre", ""), dinero(it.get("precio", 0)), False] for it in cocina],
        })
    if barra:
        out.append({
            "tipo": "lista",
            "titulo": "La barra" if es else "The bar",
            "nota": ("Nuestra carta con precios, disponible toda la noche. Todo se cobra a "
                     "precio de carta y cuenta para el consumo mínimo. Si quieren una "
                     "etiqueta fuera de esta lista, la cotizamos con 5 días de "
                     "anticipación.") if es else
                    ("Our menu with prices, available all evening. Everything is charged at "
                     "menu price and counts toward the minimum spend. For a label outside "
                     "this list, we can quote it with 5 days' notice."),
            "columnas": [{"titulo": t,
                          "items": [f"{it.get('nombre','')} {dinero(it.get('precio',0))}"
                                    for it in its]}
                         for t, its in barra],
        })
    return out


def _otras_del_dia(folio, fecha):
    """Solicitudes que ya existen para esa fecha. [] si no hay o si falla.

    El folio es YYMMDD-XXXX, asi que las del mismo dia comparten prefijo y
    listar es una sola llamada al bucket.
    """
    if not BUCKET:
        return []
    try:
        pref = f"{PREFIJO}eventos/{fecha.strftime('%y%m%d')}-"
        otras = []
        for blob in _bucket().list_blobs(prefix=pref):
            if not blob.name.endswith(".json"):
                continue
            if blob.name.endswith(f"{folio}.json"):
                continue
            try:
                d = json.loads(blob.download_as_text())
            except Exception:
                continue
            if "prueba" in (d.get("nombre") or "").lower():
                continue
            otras.append(d)
        return otras
    except Exception as e:
        print("no pude revisar fechas duplicadas:", e)
        return []


def _confirmado_en(fecha):
    """Lo que ya se cerro para esa fecha, si algo. None si la noche esta libre."""
    try:
        ag = leer("eventos/_confirmados.json") or {}
        return (ag.get(fecha.isoformat()) or None)
    except Exception:
        return None


def _aviso_fecha(folio, fecha, sol):
    """Encabezado para el Telegram de Pablo cuando la noche ya tiene dueno o
    competencia. Cadena vacia si la fecha esta limpia."""
    cerrado = _confirmado_en(fecha)
    otras = _otras_del_dia(folio, fecha)
    if not cerrado and not otras:
        return ""
    lineas = []
    if cerrado:
        lineas.append(f"🚫 <b>ESTA NOCHE YA ESTÁ CERRADA</b>: {cerrado.get('nombre','?')}"
                      + (f" · {cerrado.get('nota')}" if cerrado.get("nota") else ""))
    if otras:
        lineas.append(f"⚠️ <b>Esta fecha ya tiene {len(otras)} solicitud"
                      f"{'es' if len(otras) > 1 else ''} más:</b>")
        for o in otras[:5]:
            c = o.get("calculo") or {}
            lineas.append(f"   · {o.get('nombre','?')} · {o.get('personas','?')} pax · "
                          f"{o.get('hora','?')} · {o.get('horas','?')} h · "
                          f"{dinero(c.get('total', 0))} · folio {o.get('folio','?')}")
        lineas.append(f"   Revisa si se traslapan antes de mandar las dos.")
    return "\n".join(lineas) + "\n\n"


def armar_cotizacion(sol, calc):
    """JSON para cotizador.py a partir de la solicitud y el calculo del tarifario."""
    fecha = sol["fecha"]
    es = sol["idioma"] == "es"
    pax = sol["personas"]
    dia = tf.fecha_larga(fecha, sol["idioma"])
    if calc["modalidad"] == "grupo":
        titulo = f"{sol['motivo'] or 'Tu noche'} en ROSSO" if es else f"{sol['motivo'] or 'Your night'} at ROSSO"
        filas = [
            [f"Reserva del área para {pax} personas" if es else f"Reserved area for {pax} guests",
             "Sin costo" if es else "No charge", False],
            ["Servicio dedicado para el grupo" if es else "Dedicated service for the group",
             "Incluido" if es else "Included", False],
            [(f"Consumo mínimo del grupo — {pax} personas × {dinero(calc['por_persona'])} "
              f"({dinero(calc['minimo'])} de carta)" if es
              else f"Group minimum spend — {pax} guests × {dinero(calc['por_persona'])} "
                   f"({dinero(calc['minimo'])} at menu prices)"),
             dinero(calc["minimo"] / 1.16), True],
            ["IVA 16%" if es else "VAT 16%", dinero(calc["minimo"] - calc["minimo"] / 1.16), False],
            ["Servicio 15% sobre consumos" if es else "15% service on consumption",
             dinero(calc["servicio"]), False],
        ]
        bloques = [
            {"tipo": "tabla", "titulo": "La reserva" if es else "The reservation",
             "nota": (f"Área reservada con servicio dedicado; ROSSO sigue abierto al público. "
                      f"Todo lo que consuman en barra y cocina se abona al mínimo, no es un cargo "
                      f"aparte. El mínimo se mide a precio de carta, que ya incluye IVA: "
                      f"{dinero(calc['minimo'])}, o {dinero(calc['por_persona'])} por persona.") if es else
                     ("Reserved area with dedicated service; ROSSO stays open to the public. "
                      "Everything the group orders counts toward the minimum; it is not an extra charge."),
             "filas": filas, "total": dinero(calc["total"]) + " MXN",
             "etiqueta_total": "MÍNIMO A CUBRIR" if es else "MINIMUM TO COVER"},
            {"tipo": "vinetas", "titulo": "Cómo apartar la mesa" if es else "How to hold the table",
             "items": [
                 (f"Un anticipo de {dinero(calc['anticipo'])} por transferencia bloquea la reserva y se abona íntegro al consumo." if es
                  else f"A {dinero(calc['anticipo'])} deposit by bank transfer holds the reservation and is fully credited to the bill."),
                 ("Nos confirmas el número final de invitados 48 horas antes." if es
                  else "Final guest count 48 hours before."),
                 ("El día del evento sólo se liquida la diferencia entre el anticipo y el consumo real." if es
                  else "On the night you only settle the difference between the deposit and the actual bill."),
                 ("Precios en pesos mexicanos con IVA desglosado; el servicio no causa IVA." if es
                  else "Prices in Mexican pesos with VAT itemized; the service charge is not subject to VAT."),
             ]},
        ]
        modalidad = "Mesa reservada — ROSSO abierto al público" if es else "Reserved table — ROSSO open to the public"
    else:
        titulo = f"{sol['motivo'] or 'Evento privado'} en ROSSO" if es else f"{sol['motivo'] or 'Private event'} at ROSSO"
        h_ini, h_fin = calc.get("hora_inicio"), calc.get("hora_fin")
        rango = (f"{tf.hora_bonita(h_ini)} a {tf.hora_bonita(h_fin)}"
                 if h_ini is not None and h_fin is not None else sol["hora"])
        fin_txt = tf.hora_bonita(h_fin) or "el cierre"
        min_carta = dinero(calc["minimo"])
        por_pax = dinero(calc["por_persona_minimo"])
        sub_neto = calc["subtotal"] / 1.16
        sub_iva = dinero(calc["subtotal"])

        # Si cada invitado paga lo suyo, el minimo NO se le factura a quien
        # organiza: es una garantia que se liquida al cierre y solo por el
        # faltante. Facturarselo por adelantado seria cobrarlo dos veces.
        invitados_pagan = sol.get("barra") == "invitados"
        if invitados_pagan:
            renta_iva = calc["renta"] + calc["extra"]
            srv_renta = round(renta_iva * tf.SERVICIO)
            total_anfitrion = renta_iva + srv_renta
            filas = [
                [(f"Renta exclusiva de la casa — {rango}" if es
                  else f"Exclusive venue rental — {rango}"), dinero(calc["renta"] / 1.16), False],
            ]
            if calc["horas_extra"]:
                filas.append([(f"Hora adicional × {calc['horas_extra']}" if es
                               else f"Additional hour × {calc['horas_extra']}"),
                              dinero(calc["extra"] / 1.16), False])
            filas.append(["Subtotal", dinero(renta_iva / 1.16), True])
            filas.append(["IVA 16%" if es else "VAT 16%",
                          dinero(renta_iva - renta_iva / 1.16), False])
            filas.append(["Subtotal con IVA" if es else "Subtotal with VAT",
                          dinero(renta_iva), True])
            filas.append([(f"Servicio 15% sobre {dinero(renta_iva)}, íntegro para el equipo" if es
                           else f"15% service charge on {dinero(renta_iva)}, in full to the team"),
                          dinero(srv_renta), False])
        else:
            filas = [
                [(f"Renta exclusiva de la casa — {rango}" if es
                  else f"Exclusive venue rental — {rango}"), dinero(calc["renta"] / 1.16), False],
                [(f"Consumo mínimo garantizado en barra y cocina ({min_carta} de carta)" if es
                  else f"Guaranteed minimum spend on bar and kitchen ({min_carta} at menu prices)"),
                 dinero(calc["minimo"] / 1.16), False],
            ]
        if not invitados_pagan:
            if calc["horas_extra"]:
                filas.append([(f"Hora adicional × {calc['horas_extra']}" if es
                               else f"Additional hour × {calc['horas_extra']}"),
                              dinero(calc["extra"] / 1.16), False])
            # Subtotal y Subtotal con IVA: sin estos renglones el 15% de servicio
            # es 15% de un numero que no aparece en ninguna parte del documento.
            filas.append(["Subtotal" if es else "Subtotal", dinero(sub_neto), True])
            filas.append(["IVA 16%" if es else "VAT 16%",
                          dinero(calc["subtotal"] - sub_neto), False])
            filas.append(["Subtotal con IVA" if es else "Subtotal with VAT", sub_iva, True])
            filas.append([(f"Servicio 15% sobre {sub_iva}, íntegro para el equipo" if es
                           else f"15% service charge on {sub_iva}, in full to the team"),
                          dinero(calc["servicio"]), False])

        de_pie = calc.get("de_pie", 0)
        aforo = ((f"Aforo de la casa: {tf.AFORO_SENTADOS} personas sentadas, hasta "
                  f"{tf.AFORO_TOTAL} entre sentadas y de pie.") if es else
                 (f"Capacity: {tf.AFORO_SENTADOS} seated, up to {tf.AFORO_TOTAL} "
                  f"seated and standing."))
        if de_pie:
            aforo += ((f" Con {pax} invitados el evento es de pie y sentados: no hay lugar "
                       f"sentado para los {pax} al mismo tiempo.") if es else
                      (f" With {pax} guests the event is seated and standing: there is no "
                       f"seat for all {pax} at once."))
        else:
            aforo += (f" Con {pax} invitados todos van sentados." if es
                      else f" With {pax} guests everyone is seated.")

        cocina_txt = ((f"Cocina abierta desde que inicia su evento y hasta las 11:00 pm, que es "
                       f"cuando cierra.") if calc.get("cocina_alcanza") else
                      (f"La cocina cierra a las 11:00 pm, antes de que termine su evento; "
                       f"la barra sigue abierta hasta el final.")) if es else (
                      ("The kitchen is open from the start of your event until it closes at "
                       "11:00 pm.") if calc.get("cocina_alcanza") else
                      ("The kitchen closes at 11:00 pm, before your event ends; the bar stays "
                       "open until the end."))

        incluye = [
            (f"Uso exclusivo de la casa de {rango}: ROSSO no abre al público." if es
             else f"Exclusive use of the house from {rango}: ROSSO does not open to the public."),
            ("El salón completo de 40 m²: barra con bancos alrededor, mesas, el mobiliario de "
             "la casa y el techo de círculos de luz." if es
             else "The full 40 m² room: bar with stools all around, tables, the house furniture "
                  "and the ceiling of light circles."),
            ("Equipo completo: bartenders en barra y personal de piso atendiendo toda la noche." if es
             else "Full team: bartenders behind the bar and floor staff all evening."),
            ("Recepción y control de acceso en la puerta, con lista de invitados si así lo "
             "prefieren." if es else "Reception and door control, with a guest list if you prefer."),
            ("Sonido de la casa y cabina de DJ. Pueden usar nuestra música, su propia playlist "
             "o traer a su DJ." if es
             else "House sound and the DJ booth. Use our music, your own playlist, or bring your DJ."),
            cocina_txt,
            ("Factura con IVA desglosado. Sólo necesitamos sus datos fiscales al confirmar." if es
             else "Invoice with VAT itemized. We only need your billing details on confirmation."),
        ]

        # El anticipo: si la fecha esta a menos de 15 dias, la ventana de
        # reembolso YA paso el dia que se emite la cotizacion. Decirlo.
        dias_falta = (fecha - dt.date.today()).days
        # El anticipo se calcula sobre lo que REALMENTE paga quien organiza:
        # en modo "cada quien paga lo suyo" el total del evento incluye un
        # consumo que no le facturamos a el, y pedirle el 50% de eso era
        # pedirle el 88% de su compromiso.
        base_anticipo = total_anfitrion if invitados_pagan else calc["total"]
        anticipo = tf.redondear(base_anticipo * 0.5, 500)
        # /eventos lo necesita para el aviso a Pablo, y solo lo sabe armar
        # esta funcion: depende de quien paga la barra.
        calc["anticipo"] = anticipo
        if dias_falta <= 15:
            anticipo_txt = (
                (f"Para bloquear la fecha se requiere un anticipo de {dinero(anticipo)} "
                 f"por transferencia. Por ser una fecha a menos de 15 días, no es reembolsable "
                 f"desde que se recibe, pero puede aplicarse a una fecha nueva sujeta a "
                 f"disponibilidad.") if es else
                (f"A {dinero(anticipo)} deposit by bank transfer secures the date. As the "
                 f"event is less than 15 days away, it is non-refundable from the moment it is "
                 f"received, but it can be applied to a new date subject to availability."))
        else:
            anticipo_txt = (
                (f"Para bloquear la fecha se requiere un anticipo de {dinero(anticipo)} "
                 f"por transferencia. Cancelando con más de 15 días se devuelve completo; dentro "
                 f"de los 15 días no es reembolsable, pero puede aplicarse a una fecha nueva.") if es else
                (f"A {dinero(anticipo)} deposit by bank transfer secures the date. Cancelling "
                 f"more than 15 days ahead, it is refunded in full; within 15 days it is "
                 f"non-refundable but can be applied to a new date."))

        # La vigencia nunca puede caer DESPUES del evento.
        vence = min(dt.date.today() + dt.timedelta(days=10),
                    fecha - dt.timedelta(days=2))
        if vence <= dt.date.today():
            vence = fecha - dt.timedelta(days=1)
        _hoy = tf.fecha_larga(dt.date.today(), sol["idioma"])
        _ven = tf.fecha_larga(vence, sol["idioma"])
        if es:
            _hoy, _ven = _hoy[0].lower() + _hoy[1:], _ven[0].lower() + _ven[1:]
        # Para fechas lejanas, la carta de hoy no se puede amarrar: ROSSO revisa
        # precios cada anio y el evento cae del otro lado de esa revision.
        lejano = dias_falta > 90
        aviso_carta = fecha - dt.timedelta(days=45)
        clausula_lejana = (
            (f"Por tratarse de una fecha a {dias_falta} días, la renta y el consumo mínimo "
             f"de esta propuesta quedan fijos, pero los precios de carta son los vigentes "
             f"hoy: la noche de su evento aplica la carta de esa fecha. Si la carta cambia "
             f"se lo avisamos a más tardar el {tf.fecha_larga(aviso_carta, 'es')[0].lower() + tf.fecha_larga(aviso_carta, 'es')[1:]}, "
             f"y si no está de acuerdo puede cancelar con devolución completa del anticipo "
             f"dentro de los 10 días siguientes al aviso.") if es else
            (f"As the event is {dias_falta} days away, the venue rental and the minimum "
             f"spend in this proposal are fixed, but menu prices are today's: the menu in "
             f"force on the night applies. If it changes we will tell you no later than "
             f"{tf.fecha_larga(aviso_carta, 'en')}, and if you do not agree you may cancel "
             f"with a full refund of the deposit within 10 days of that notice."))
        vig = (f"Cotización emitida el {_hoy}, vigente hasta el {_ven}." if es else
               f"Proposal issued {_hoy}, valid until {_ven}.")

        condiciones = [
            (((f"ROSSO está cerrado al público durante todo su evento, de {rango}. Esa "
               f"noche abrimos más tarde o no abrimos al público: la casa es suya hasta el "
               f"final, y a las {fin_txt} cerramos.")
              if calc.get("pasa_cierre") else
              (f"ROSSO está cerrado al público durante todo su evento, de {rango}. A las "
               f"{fin_txt} cerramos su evento, no la casa: quien quiera quedarse es bienvenido "
               f"como cliente del bar hasta las 2:00 am, y lo que consuma se le cobra "
               f"directamente.")) if es else
             (f"ROSSO is closed to the public for your whole event, {rango}. At {fin_txt} we "
              f"close your event, not the house: anyone who wants to stay is welcome as a "
              f"regular patron until 2:00 am, billed directly.")),
            aforo,
            (((f"La garantía de consumo del grupo es de {min_carta} a precio de carta, "
               f"{por_pax} por invitado. Lo que consuman sus invitados cuenta para ella; si al "
               f"cierre faltara, quien organiza cubre la diferencia más su 15%.")
              if invitados_pagan else
              (f"El consumo mínimo se mide a precio de carta, que ya incluye IVA: {min_carta}, "
               f"o {por_pax} por invitado. Si esa noche consumen más, se cobra lo consumido; si "
               f"consumen menos, se cobra el mínimo.")) if es else
             (f"The minimum spend is measured at menu prices, VAT included: {min_carta}, or "
              f"{por_pax} per guest. If you spend more, you pay what you spend; if less, the "
              f"minimum stands.")),
            ("El consumo mínimo aplica al grupo completo y se sostiene aunque asistan menos "
             f"de {pax}. Si asisten más, su consumo se suma a precio de carta." if es else
             f"The minimum applies to the group as a whole and holds even if fewer than {pax} "
             "attend. If more come, their consumption adds on at menu price."),
            ("Si algún invitado tiene restricción alimentaria, avísennos al confirmar: varios "
             "platillos llevan mariscos o cerdo y podemos ajustar la selección." if es else
             "If any guest has a dietary restriction, tell us on confirmation: several dishes "
             "contain shellfish or pork and we can adjust the selection."),
            ("Si necesitan micrófono, pantalla o proyección, díganos con anticipación: lo que "
             "no tengamos en casa lo cotizamos aparte." if es else
             "If you need a microphone, a screen or projection, tell us ahead of time: anything "
             "we do not have in house we quote separately."),
            ((f"Si traen su propio DJ, ROSSO pone la cabina y las tomas de corriente. Pueden "
              f"entrar a montar desde las {tf.hora_bonita((calc['hora_inicio'] or 20) - 2)}, dos "
              f"horas antes, y el montaje tiene que quedar listo antes de que inicie el evento. "
              f"Si necesitan más tiempo, avísennos y lo vemos.") if es else
             (f"If you bring your own DJ, ROSSO provides the booth and the power outlets. You can "
              f"come in to set up from {tf.hora_bonita((calc['hora_inicio'] or 20) - 2)}, two "
              f"hours before, and setup must be finished before the event starts. If you need "
              f"longer, tell us and we will work it out.")),
            ("El 15% de servicio se calcula sobre el total del evento, renta incluida, y va "
             "íntegro al equipo. No se espera propina adicional." if es else
             "The 15% service charge is calculated on the event total, venue rental included, "
             "and goes in full to the team. No additional gratuity is expected."),
            ((f"Cada hora adicional son {dinero(calc['hora_extra'])} por el espacio con IVA, "
              f"más su 15% de servicio: {dinero(round(calc['hora_extra'] * (1 + tf.SERVICIO)))} "
              f"en total, más el consumo de esa hora."
              + ("" if calc.get("pasa_cierre") else " Cerramos a las 2:00 am.")) if es else
             (f"Each additional hour is {dinero(calc['hora_extra'])} for the venue with VAT, plus "
              f"its 15% service charge: {dinero(round(calc['hora_extra'] * (1 + tf.SERVICIO)))} "
              f"in all, plus that hour's consumption. We close at 2:00 am.")),
            ("No se permite el ingreso de bebidas alcohólicas ajenas a la casa." if es else
             "Outside alcohol is not permitted."),
            ("El número final de invitados se confirma a más tardar 48 horas antes." if es else
             "The final guest count is confirmed no later than 48 hours before."),
            ("Facturamos con IVA desglosado. Mándennos la constancia de situación fiscal al "
             "confirmar y, si lo requieren, el número de orden de compra." if es else
             "We invoice with VAT itemized. Send us your tax details on confirmation and, if "
             "you need it, a purchase order number."),
            anticipo_txt + ((" Al recibirlo cerramos las reservaciones al público de esa noche. "
                             + ("El saldo de la renta se liquida la noche del evento, antes de "
                                "que inicie; la garantía, si quedara faltante, hasta el cierre."
                                if invitados_pagan else
                                "El saldo se liquida la noche del evento, antes de que inicie.")) if es else
                            (" On receipt we close public reservations for that night. The balance "
                             "is settled on the night, before the event starts.")),
            ("Precios en pesos mexicanos. Los de carta incluyen IVA; en el desglose del evento "
             "va señalado aparte. El servicio no causa IVA." if es else
             "Prices in Mexican pesos. Menu prices include VAT; in the event breakdown VAT is "
             "itemized separately. The service charge is not subject to VAT."),
            vig,
        ]
        if lejano:
            condiciones.insert(-1, clausula_lejana)

        # Cuando cada invitado paga lo suyo, el minimo deja de ser un cargo y
        # pasa a ser una garantia que se liquida AL CIERRE y solo por el faltante.
        # Facturarselo por adelantado a quien organiza seria cobrarlo dos veces.
        if invitados_pagan:
            peor = total_anfitrion + calc["minimo"] + round(calc["minimo"] * tf.SERVICIO)
            bloque_garantia = [{
                "tipo": "vinetas",
                "titulo": "El consumo de sus invitados" if es else "What your guests spend",
                "items": ([
                    "Cada invitado paga lo suyo en la barra, a precio de carta y con su 15% "
                    "de servicio. No pasa por la cuenta de quien organiza.",
                    f"Pedimos una garantía de consumo del grupo de {min_carta}, que son "
                    f"{por_pax} por invitado a precio de carta. Es un piso, no un cargo: todo "
                    f"lo que consuman sus invitados cuenta para ella.",
                    f"Con {pax} invitados en {sol['horas']} horas, {por_pax} por cabeza es "
                    f"menos de lo que gasta una mesa normal en ROSSO, así que lo habitual es "
                    f"que la garantía se cubra sola y quien organiza no ponga un peso más.",
                    f"Si al cierre de la noche el grupo consumió menos de {min_carta}, quien "
                    f"organiza cubre la diferencia más su 15%. Se liquida esa misma noche, al "
                    f"final y con la cuenta a la vista. Nunca por adelantado.",
                    f"En el peor de los casos —que nadie consuma nada— el total sería "
                    f"{dinero(peor)}. En la práctica no pasa.",
                    "Si prefieren invertirlo y que ROSSO cobre todo a una sola cuenta, "
                    "dígannos y se los recotizamos así.",
                ] if es else [
                    "Each guest pays their own tab at the bar, at menu prices and with their "
                    "15% service charge. It does not go through the host's bill.",
                    f"We ask for a group consumption guarantee of {min_carta}, which is "
                    f"{por_pax} per guest at menu prices. It is a floor, not a charge: "
                    f"everything your guests order counts toward it.",
                    f"With {pax} guests over {sol['horas']} hours, {por_pax} a head is less "
                    f"than a normal table spends at ROSSO, so the guarantee usually covers "
                    f"itself and the host pays nothing more.",
                    f"If at the end of the night the group spent less than {min_carta}, the "
                    f"host covers the difference plus its 15%. Settled that same night, at "
                    f"the end, with the bill in front of you. Never in advance.",
                    f"Worst case — nobody orders anything — the total would be "
                    f"{dinero(peor)}. In practice that does not happen.",
                    "If you would rather ROSSO put everything on one bill, tell us and we "
                    "will requote it that way.",
                ]),
            }]
        else:
            bloque_garantia = []

        bloques = [
            {"tipo": "vinetas", "titulo": "Qué incluye la noche" if es else "What the evening includes",
             "items": incluye},
            {"tipo": "tabla", "titulo": "La propuesta" if es else "The proposal",
             "nota": ((f"Esto es lo único que paga quien organiza: la casa cerrada para ustedes. "
                       f"Las bebidas y la comida las paga cada invitado en su cuenta, a precio "
                       f"de carta. Abajo explicamos la garantía de consumo, que no se cobra aquí."
                       if es else
                       f"This is all the host pays: the house closed for you. Each guest pays "
                       f"their own drinks and food at menu prices. The consumption guarantee is "
                       f"explained below and is not charged here.") if invitados_pagan else
                      ((f"El consumo mínimo NO es un cargo extra: es el piso de lo que se consume "
                       f"en barra y cocina esa noche, y todo lo que ordenen se descuenta de él. "
                       f"Se mide a precio de carta, con IVA: {min_carta}, o {por_pax} por "
                       f"invitado.") if es else
                      (f"The minimum spend is NOT an extra charge: it is the floor of what gets "
                       f"consumed at the bar and kitchen that night, and everything you order "
                       f"comes off it. It is measured at menu prices, VAT included: {min_carta}, "
                       f"or {por_pax} per guest."))),
             "filas": filas,
             "total": dinero(total_anfitrion if invitados_pagan else calc["total"]) + " MXN",
             "etiqueta_total": (("TOTAL QUE PAGA QUIEN ORGANIZA" if es else "TOTAL FOR THE HOST")
                                if invitados_pagan else "TOTAL")},
        ] + bloque_garantia + _bloques_carta(es, lejano) + [
            {"tipo": "vinetas", "titulo": "Condiciones" if es else "Terms",
             "items": condiciones},
        ]
        modalidad = "Evento privado — casa completa" if es else "Private event — full buyout"
    return {
        "archivo": f"ROSSO_{'Cotizacion' if es else 'Proposal'}_{fecha.isoformat()}_{re.sub(r'[^A-Za-z0-9]+', '-', sol['nombre'])[:30]}.docx",
        "idioma": sol["idioma"],
        "kicker": "Cotización de evento" if es else "Event proposal",
        "titulo": titulo,
        # el rango calculado, no la cadena cruda del formulario: si el cliente
        # escribio "7:30pm" el subtitulo decia 7:30 y el cuerpo 7:00 pm
        "subtitulo": (f"{dia} · {pax} {'personas' if es else 'guests'} · "
                      + (f"{tf.hora_bonita(calc['hora_inicio'])} a {tf.hora_bonita(calc['hora_fin'])}"
                         if calc.get("hora_fin") is not None else sol["hora"])),
        "cliente": sol["nombre"], "fecha": dia,
        "horario": (f"{tf.hora_bonita(calc['hora_inicio'])} a {tf.hora_bonita(calc['hora_fin'])}"
                    if calc.get("hora_fin") is not None else sol["hora"]),
        "duracion": f"{sol['horas']} {'horas' if es else 'hours'}",
        "invitados": f"{pax} {'personas' if es else 'guests'}", "modalidad": modalidad,
        "intro": (("Gracias por pensar en ROSSO. Somos un speakeasy en Puebla 329, Roma Norte. "
                   "Aquí va la propuesta para tu fecha; cualquier detalle lo ajustamos por WhatsApp.") if es else
                  ("Thank you for thinking of ROSSO. We are a speakeasy at Puebla 329, Roma Norte. "
                   "Here is the proposal for your date; we can fine-tune any detail over WhatsApp.")),
        "bloques": bloques,
        "cierre": (f"ROSSO · Puebla 329, Roma Norte, CDMX · hola@rossospeakeasy.com · "
                   f"WhatsApp +52 {WHATSAPP} · @rosso.speakeasy"),
    }


@app.post("/eventos")
def eventos():
    d = request.get_json(silent=True) or request.form.to_dict() or {}
    if _limpio(d.get("empresa_web")):           # honeypot
        return jsonify(ok=True)
    try:
        fecha = dt.date.fromisoformat(_limpio(d.get("fecha"), 10))
        personas = int(d.get("personas") or 0)
        horas = max(1, min(12, int(d.get("horas") or 5)))
    except (ValueError, TypeError):
        return jsonify(error="fecha o número de personas inválidos"), 400
    nombre = _limpio(d.get("nombre"), 80)
    whatsapp = re.sub(r"[^0-9+]", "", str(d.get("whatsapp") or ""))[:16]
    if not nombre or len(whatsapp) < 10:
        return jsonify(error="faltan nombre o WhatsApp"), 400
    if fecha < dt.date.today():
        return jsonify(error="la fecha ya pasó"), 400
    if personas < 5:
        return jsonify(error="para 4 personas o menos reserva directo en OpenTable"), 400
    # el aforo real son 50 (32 sentadas + de pie). La guarda estaba en 80 y el
    # mensaje decia 50, asi que cualquier solicitud de 51 a 80 recibia una
    # cotizacion para un grupo QUE NO CABE — y el propio PDF se contradecia
    # ("Aforo: hasta 50"). Caso Madeline Medina, 60 personas (12-oct-2026).
    if personas > tf.AFORO_TOTAL:
        return jsonify(error=(f"el aforo máximo de ROSSO es de {tf.AFORO_TOTAL} personas "
                              f"({tf.AFORO_SENTADOS} sentadas y el resto de pie). "
                              "Escríbenos por WhatsApp y vemos qué se puede hacer.")), 400
    sol = {
        "recibida": dt.datetime.now().isoformat(timespec="seconds"),
        "nombre": nombre, "whatsapp": whatsapp, "email": _limpio(d.get("email"), 120),
        "fecha": fecha, "hora": _limpio(d.get("hora"), 10) or "8:00 pm", "horas": horas,
        "personas": personas, "tipo": _limpio(d.get("tipo"), 20) or "no-se",
        "motivo": _limpio(d.get("motivo"), 60),
        "idioma": "en" if _limpio(d.get("idioma"), 2) == "en" else "es",
        # quien paga la barra: "invitados" = cada quien lo suyo, el minimo es
        # garantia y no cargo. Default "anfitrion", que es como venia hasta hoy.
        "barra": ("invitados" if _limpio(d.get("barra"), 12) == "invitados"
                  else "anfitrion"),
        "mensaje": _limpio(d.get("mensaje"), 1000),
    }
    modalidad = tf.decidir_modalidad(personas, sol["tipo"])
    # la hora SI se pasa: sin ella revisa_horario() nunca corria y el bot
    # cotizaba eventos que terminan despues del cierre (auditoria 12-oct)
    calc = (tf.cotizar_grupo(fecha, personas) if modalidad == "grupo"
            else tf.cotizar_exclusiva(fecha, personas, horas, sol["hora"]))
    folio = fecha.strftime("%y%m%d") + "-" + secrets.token_hex(2).upper()

    # cotización en membrete: PDF para el cliente, docx editable de respaldo
    cfg = armar_cotizacion(sol, calc)
    cfg["vigencia"] = fecha
    tmp = "/tmp" if os.name != "nt" else os.environ.get("TEMP", ".")
    ruta_docx = os.path.join(tmp, cfg["archivo"])
    ruta_pdf = os.path.join(tmp, cfg["archivo"].replace(".docx", ".pdf"))
    try:
        cotizador.generar(cfg, ruta_docx)
    except Exception as e:
        print("cotizador fallo:", e)
        ruta_docx = None
    try:
        pdf_cotizacion.generar(cfg, ruta_pdf)
    except Exception as e:
        print("pdf fallo:", e)
        ruta_pdf = None

    # copia en el bucket
    registro = dict(sol, fecha=fecha.isoformat(), folio=folio, modalidad=modalidad, calculo=calc)
    try:
        guardar(f"eventos/{folio}.json", registro)
        if ruta_docx and BUCKET:
            _bucket().blob(PREFIJO + f"eventos/{folio}.docx").upload_from_filename(ruta_docx)
        if ruta_pdf and BUCKET:
            _bucket().blob(PREFIJO + f"eventos/{folio}.pdf").upload_from_filename(ruta_pdf)
    except Exception as e:
        print("bucket fallo:", e)

    # aviso a Pablo
    dia = tf.nombre_dia(fecha)
    if modalidad == "grupo":
        resumen = (f"Mesa de grupo, ROSSO abierto. Sugerido: <b>{dinero(calc['por_persona'])}/persona</b> "
                   f"= mínimo {dinero(calc['minimo'])} (+15% = {dinero(calc['total'])}). "
                   f"Su justa parte del {dia}: {dinero(calc['justa_parte'])}. Anticipo {dinero(calc['anticipo'])}.")
    else:
        resumen = (f"Exclusiva. Sugerido: renta <b>{dinero(calc['renta'])}</b> + consumo mínimo "
                   f"<b>{dinero(calc['minimo'])}</b>"
                   + (f" + {calc['horas_extra']} h extra" if calc["horas_extra"] else "")
                   + f" → {dinero(calc['subtotal'])} +15% = <b>{dinero(calc['total'])}</b>. "
                   f"Anticipo {dinero(calc['anticipo'])}.")
    # Si el bloque no cabe antes del cierre, el PDF se genera igual (Pablo puede
    # querer ajustarlo y reenviarlo) pero el mensaje abre con el freno en vez de
    # esconderlo entre los avisos.
    freno = ("" if calc.get("horario_cabe", True) else
             "🚫 <b>NO MANDAR SIN REVISAR: el horario no cabe antes del cierre.</b>\n\n")
    # cuatro noches se vendieron dos veces sin que nada avisara (24-sep, 22-oct,
    # 3-nov y 14-nov): esto revisa el bucket y la agenda de cerrados.
    freno = _aviso_fecha(folio, fecha, sol) + freno
    texto = (freno
             + f"🍸 <b>Solicitud de evento desde la web</b> · folio {folio}\n"
             f"<b>{nombre}</b> · WhatsApp <a href=\"https://wa.me/{whatsapp.lstrip('+')}\">{whatsapp}</a>"
             + (f" · {sol['email']}" if sol["email"] else "") + "\n"
             f"{tf.fecha_larga(fecha)} · {sol['hora']} · {horas} h · <b>{personas} personas</b> · "
             f"pidió: {sol['tipo']} · idioma {sol['idioma']}"
             + (f"\nMotivo: {sol['motivo']}" if sol["motivo"] else "")
             + (f"\nMensaje: {sol['mensaje']}" if sol["mensaje"] else "")
             + f"\n\n{resumen}"
             + "".join(f"\n\n🔎 {a}" for a in calc.get("avisos", []))
             + "\n\nLa cotización en PDF va adjunta, lista para reenviar al cliente. Al cliente sólo se le dijo que le contestamos por WhatsApp en menos de 24 h.")
    if sol["email"] and ruta_pdf and correo_mod.configurado():
        try:
            asunto = (f"Cotización ROSSO · {tf.fecha_larga(fecha, 'es')}" if sol["idioma"] == "es" else f"ROSSO proposal · {tf.fecha_larga(fecha, 'en')}")
            ok = correo_mod.crear_borrador(sol["email"], asunto, correo_mod.texto_evento(dict(sol, fecha_larga=tf.fecha_larga(fecha, sol["idioma"])), calc, folio, sol["idioma"] == "es"),
                                           ruta_pdf, os.path.basename(ruta_pdf))
            texto += f"\n\n✉️ Borrador listo en tu Gmail (Borradores) para {sol['email']}, desde hola@. Ábrelo, revisa y Enviar." if ok else "\n\n✉️ No se pudo dejar el borrador en Gmail."
        except Exception as e:
            print("borrador gmail fallo:", e)
            texto += "\n\n✉️ No se pudo dejar el borrador en Gmail."
    elif sol["email"] and not correo_mod.configurado():
        texto += f"\n\n✉️ El cliente dejó correo: {sol['email']} (los borradores automáticos se activan con GMAIL_APP_PASSWORD)."
    try:
        telegram(texto, ruta_pdf or ruta_docx, os.path.basename(ruta_pdf) if ruta_pdf else (cfg["archivo"] if ruta_docx else None))
    except Exception as e:
        print("telegram fallo:", e)
    return jsonify(ok=True, folio=folio)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8081)), debug=False)
