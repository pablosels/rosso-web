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
import cotizador
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
    resp = jsonify(datos)
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
    if pendientes:
        total = sum(p["_pago"] for p in pendientes)
        texto += ("\n\n💸 <b>Pagos a DJs pendientes</b> (" + dinero(total) + "):\n"
                  + "\n".join(f"· {p['dj']} — {p['fecha_larga']} — {dinero(p['_pago'])}" for p in pendientes)
                  + "\nMarca SI en la columna <i>pagado</i> cuando los liquides.")
    telegram(texto)
    with _lock:
        _agenda_cache.update(datos=None, t=0)
    return jsonify(ok=True, faltan=faltan)


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


# ------------------------------------------------------------------ eventos
def _limpio(s, n=300):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


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
            [(f"Consumo mínimo del grupo — {pax} personas × {dinero(calc['por_persona'])}" if es
              else f"Group minimum spend — {pax} guests × {dinero(calc['por_persona'])}"),
             dinero(calc["minimo"]), True],
            ["Servicio 15% sobre consumos" if es else "15% service on consumption",
             dinero(calc["servicio"]), False],
        ]
        bloques = [
            {"tipo": "tabla", "titulo": "La reserva" if es else "The reservation",
             "nota": ("Área reservada con servicio dedicado; ROSSO sigue abierto al público. "
                      "Todo lo que consuman en barra y cocina se abona al mínimo, no es un cargo aparte.") if es else
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
             ]},
        ]
        modalidad = "Mesa reservada — ROSSO abierto al público" if es else "Reserved table — ROSSO open to the public"
    else:
        titulo = f"{sol['motivo'] or 'Evento privado'} en ROSSO" if es else f"{sol['motivo'] or 'Private event'} at ROSSO"
        filas = [
            [(f"Renta exclusiva del espacio — {sol['horas']} horas" if es
              else f"Exclusive venue rental — {sol['horas']} hours"), dinero(calc["renta"]), False],
            [("Consumo mínimo garantizado en barra y cocina" if es
              else "Guaranteed minimum spend on bar and kitchen"), dinero(calc["minimo"]), False],
        ]
        if calc["horas_extra"]:
            filas.append([(f"Hora extra × {calc['horas_extra']}" if es else f"Extra hour × {calc['horas_extra']}"),
                          dinero(calc["horas_extra"] * calc["hora_extra"]), False])
        filas.append([("Servicio 15% sobre el total del evento, íntegro para el equipo" if es
                       else "15% service charge on the event total, distributed in full to the service team"),
                      dinero(calc["servicio"]), False])
        bloques = [
            {"tipo": "tabla", "titulo": "El evento" if es else "The event",
             "nota": (f"ROSSO cerrado al público para ustedes. Aforo: {tf.AFORO_SENTADOS} personas sentadas, "
                      f"hasta {tf.AFORO_TOTAL} entre sentadas y de pie. La cocina cierra a las 11:00 pm.") if es else
                     (f"ROSSO closed to the public for your party. Capacity: {tf.AFORO_SENTADOS} seated, "
                      f"up to {tf.AFORO_TOTAL} seated and standing. The kitchen closes at 11:00 pm."),
             "filas": filas, "total": dinero(calc["total"]) + " MXN",
             "etiqueta_total": "TOTAL" },
            {"tipo": "vinetas", "titulo": "Condiciones" if es else "Terms",
             "items": [
                 (f"Anticipo de {dinero(calc['anticipo'])} para bloquear la fecha; no reembolsable dentro de los 15 días previos." if es
                  else f"A {dinero(calc['anticipo'])} deposit secures the date; non-refundable within 15 days of the event."),
                 (f"Hora adicional: {dinero(calc['hora_extra'])} el local, más consumos." if es
                  else f"Additional hour: {dinero(calc['hora_extra'])} for the venue, plus consumption."),
                 ("No se permite el ingreso de bebidas alcohólicas ajenas a la casa." if es
                  else "Outside alcohol is not permitted."),
                 ("Precios en pesos mexicanos, IVA incluido. Vigencia de 10 días naturales." if es
                  else "Prices in Mexican pesos, VAT included. Valid for 10 calendar days."),
             ]},
        ]
        modalidad = "Evento privado — exclusiva" if es else "Private event — full buyout"
    return {
        "archivo": f"BORRADOR_{fecha.isoformat()}_{re.sub(r'[^A-Za-z0-9]+', '-', sol['nombre'])[:30]}.docx",
        "idioma": sol["idioma"],
        "kicker": "Cotización — borrador automático" if es else "Proposal — automatic draft",
        "titulo": titulo,
        "subtitulo": f"{dia} · {pax} {'personas' if es else 'guests'} · {sol['hora']}",
        "cliente": sol["nombre"], "fecha": dia, "horario": sol["hora"],
        "duracion": f"{sol['horas']} {'horas' if es else 'hours'}",
        "invitados": f"{pax} {'personas' if es else 'guests'}", "modalidad": modalidad,
        "intro": (("Gracias por pensar en ROSSO. Somos un speakeasy en Puebla 329, Roma Norte. "
                   "Aquí va la propuesta para tu fecha; cualquier detalle lo ajustamos por WhatsApp.") if es else
                  ("Thank you for thinking of ROSSO. We are a speakeasy at Puebla 329, Roma Norte. "
                   "Here is the proposal for your date; we can fine-tune any detail over WhatsApp.")),
        "bloques": bloques,
        "cierre": (f"ROSSO · WhatsApp +52 {WHATSAPP} · @rosso.speakeasy"),
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
    if personas > 80:
        return jsonify(error="el aforo máximo de ROSSO es de 50 personas"), 400
    sol = {
        "recibida": dt.datetime.now().isoformat(timespec="seconds"),
        "nombre": nombre, "whatsapp": whatsapp, "email": _limpio(d.get("email"), 120),
        "fecha": fecha, "hora": _limpio(d.get("hora"), 10) or "8:00 pm", "horas": horas,
        "personas": personas, "tipo": _limpio(d.get("tipo"), 20) or "no-se",
        "motivo": _limpio(d.get("motivo"), 60),
        "idioma": "en" if _limpio(d.get("idioma"), 2) == "en" else "es",
        "mensaje": _limpio(d.get("mensaje"), 1000),
    }
    modalidad = tf.decidir_modalidad(personas, sol["tipo"])
    calc = tf.cotizar_grupo(fecha, personas) if modalidad == "grupo" else tf.cotizar_exclusiva(fecha, personas, horas)
    folio = fecha.strftime("%y%m%d") + "-" + secrets.token_hex(2).upper()

    # borrador en membrete
    cfg = armar_cotizacion(sol, calc)
    ruta_docx = os.path.join("/tmp" if os.name != "nt" else os.environ.get("TEMP", "."), cfg["archivo"])
    try:
        cotizador.generar(cfg, ruta_docx)
    except Exception as e:
        print("cotizador fallo:", e)
        ruta_docx = None

    # copia en el bucket
    registro = dict(sol, fecha=fecha.isoformat(), folio=folio, modalidad=modalidad, calculo=calc)
    try:
        guardar(f"eventos/{folio}.json", registro)
        if ruta_docx and BUCKET:
            _bucket().blob(PREFIJO + f"eventos/{folio}.docx").upload_from_filename(ruta_docx)
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
    texto = (f"🍸 <b>Solicitud de evento desde la web</b> · folio {folio}\n"
             f"<b>{nombre}</b> · WhatsApp <a href=\"https://wa.me/{whatsapp.lstrip('+')}\">{whatsapp}</a>"
             + (f" · {sol['email']}" if sol["email"] else "") + "\n"
             f"{tf.fecha_larga(fecha)} · {sol['hora']} · {horas} h · <b>{personas} personas</b> · "
             f"pidió: {sol['tipo']} · idioma {sol['idioma']}"
             + (f"\nMotivo: {sol['motivo']}" if sol["motivo"] else "")
             + (f"\nMensaje: {sol['mensaje']}" if sol["mensaje"] else "")
             + f"\n\n{resumen}\n\nEl borrador en membrete va adjunto. Revísalo antes de mandarlo; al cliente sólo se le dijo que le contestamos por WhatsApp en menos de 24 h.")
    try:
        telegram(texto, ruta_docx, cfg["archivo"] if ruta_docx else None)
    except Exception as e:
        print("telegram fallo:", e)
    return jsonify(ok=True, folio=folio)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8081)), debug=False)
