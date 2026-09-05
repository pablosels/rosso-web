# -*- coding: utf-8 -*-
"""Vigilante de ROSSO: servicio aparte en Cloud Run que Cloud Scheduler llama cada 10 minutos.

Revisa que rossospeakeasy.com y la API respondan con el contenido esperado. Avisa por
Telegram cuando algo se cae, recuerda cada 3 horas si sigue caído y avisa cuando vuelve.
El último estado vive en el bucket (rosso-web/vigilante/estado.json) para no repetir avisos.
"""
import datetime as dt
import json
import os
import time
import zoneinfo

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_TOKEN_ROSSO", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID_ROSSO", "")
BUCKET = os.environ.get("BUCKET", "")
KEY = os.environ.get("REFRESH_KEY", "")
RUTA = "rosso-web/vigilante/estado.json"
TZ = zoneinfo.ZoneInfo("America/Mexico_City")

OBJETIVOS = [
    {"nombre": "Sitio rossospeakeasy.com", "url": "https://rossospeakeasy.com/?vigilante=1", "espera": "ROSSO"},
    {"nombre": "API (salud)", "url": "https://rosso-web-api-703407013960.us-central1.run.app/health", "espera": '"ok"'},
    {"nombre": "API (carta viva)", "url": "https://rosso-web-api-703407013960.us-central1.run.app/carta", "espera": "secciones"},
    {"nombre": "API (agenda)", "url": "https://rosso-web-api-703407013960.us-central1.run.app/agenda", "espera": "noches"},
]


def ahora():
    return dt.datetime.now(TZ).strftime("%d/%m %I:%M %p").lower()


def revisar(o):
    t0 = time.time()
    try:
        r = requests.get(o["url"], timeout=15, headers={"User-Agent": "vigilante-rosso/1"})
        ms = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} ({ms} ms)"
        if o["espera"] not in r.text:
            return False, f"respondió 200 pero sin el contenido esperado ({ms} ms)"
        return True, f"200 en {ms} ms"
    except Exception as e:
        return False, f"sin respuesta: {type(e).__name__}"


def telegram(texto):
    if not TOKEN or not CHAT:
        print("sin telegram:", texto)
        return
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", timeout=15,
                  json={"chat_id": CHAT, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})


def _blob():
    from google.cloud import storage
    return storage.Client().bucket(BUCKET).blob(RUTA)


def leer_estado():
    if not BUCKET:
        return {}
    try:
        b = _blob()
        return json.loads(b.download_as_text()) if b.exists() else {}
    except Exception as e:
        print("estado no leído:", e)
        return {}


def guardar_estado(est):
    if not BUCKET:
        return
    try:
        _blob().upload_from_string(json.dumps(est, ensure_ascii=False), content_type="application/json")
    except Exception as e:
        print("estado no guardado:", e)


@app.get("/")
def raiz():
    return "vigilante-rosso"


@app.get("/estado")
def estado():
    return jsonify([{"nombre": o["nombre"], "ok": ok, "detalle": det} for o in OBJETIVOS for ok, det in [revisar(o)]])


@app.post("/revisar")
def revisar_todo():
    if KEY and request.headers.get("X-Refresh-Key") != KEY:
        return jsonify(error="no autorizado"), 403
    est = leer_estado()
    cambios = []
    for o in OBJETIVOS:
        n = o["nombre"]
        ok, det = revisar(o)
        if not ok:
            time.sleep(20)                     # segunda oportunidad: no avisar por un parpadeo
            ok, det = revisar(o)
        reg = est.get(n, {"caido": False, "fallas": 0})
        if not ok:
            reg["fallas"] = reg.get("fallas", 0) + 1
            if not reg.get("caido"):
                reg.update(caido=True, desde=ahora())
                telegram(f"🔴 <b>{n} no responde</b>\n{det}\n{ahora()}\nReviso cada 10 minutos y aviso cuando vuelva.")
                cambios.append(n)
            elif reg["fallas"] % 18 == 0:       # cada 3 horas
                telegram(f"🔴 <b>{n} sigue caído</b> desde {reg.get('desde')}\n{det}")
        elif reg.get("caido"):
            telegram(f"🟢 <b>{n} volvió</b>\n{det}\nEstuvo caído desde {reg.get('desde')} hasta {ahora()}.")
            reg = {"caido": False, "fallas": 0}
            cambios.append(n)
        est[n] = reg
    guardar_estado(est)
    return jsonify(ok=True, cambios=cambios, estado=est)


if __name__ == "__main__":
    app.run(port=8081, debug=True)
