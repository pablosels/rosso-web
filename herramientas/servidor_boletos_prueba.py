# -*- coding: utf-8 -*-
"""API de rosso-web en local con Stripe simulado, para probar los boletos en el navegador.
Uso: python servidor_prueba.py <ruta a rosso-web/api> <carpeta del libro>"""
import json
import os
import sys
import threading
import time

API_DIR, LIBRO = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(LIBRO, exist_ok=True)
os.environ.update({"BOLETOS_LOCAL": LIBRO, "STRIPE_KEY": "rk_test_falsa", "STRIPE_WEBHOOK_SECRET": "whsec_prueba",
                   "CANJE_PIN": "12345678", "PUERTA_PIN": "445566", "REFRESH_KEY": "llave-prueba",
                   "SITIO": "http://localhost:8765", "ALLOWED_ORIGINS": "http://localhost:8765"})
for k in ("BUCKET", "BOLETOS_BUCKET", "TELEGRAM_TOKEN_ROSSO", "K_SERVICE", "BOLETOS_SHEET_ID"):
    os.environ.pop(k, None)
sys.path.insert(0, API_DIR)
os.chdir(API_DIR)

import app as appmod     # noqa: E402
import boletos as bo     # noqa: E402
from flask import redirect, request   # noqa: E402

bo.SHOWS["carla-gibert"]["visible"] = "si"
SES = {}
_l = threading.Lock()


def stripe_falso(metodo, ruta, datos=None, idem=None):
    with _l:
        if metodo == "POST" and ruta == "checkout/sessions":
            cs = f"cs_test_{len(SES) + 1:04d}"
            md = {k[9:-1]: v for k, v in datos.items() if k.startswith("metadata[")}
            q = int(datos["line_items[0][quantity]"])
            SES[cs] = {"id": cs, "url": f"http://localhost:8081/_pago_falso/{cs}", "status": "open", "payment_status": "unpaid",
                       "metadata": md, "amount_total": int(datos["line_items[0][price_data][unit_amount]"]) * q,
                       "success_url": datos["success_url"], "cancel_url": datos["cancel_url"],
                       "item": datos["line_items[0][price_data][product_data][name]"], "customer_email": datos["customer_email"]}
            return 200, dict(SES[cs])
        if metodo == "POST" and ruta.endswith("/expire"):
            s = SES.get(ruta.split("/")[2])
            if not s or s["status"] != "open":
                return 400, {"error": {"message": "not expireable"}}
            s["status"] = "expired"
            return 200, dict(s)
        if metodo == "GET":
            s = SES.get(ruta.split("/")[2])
            return (200, dict(s)) if s else (404, {})
    raise AssertionError(ruta)


bo._stripe = stripe_falso


@appmod.app.get("/_pago_falso/<cs>")
def pago_falso(cs):
    s = SES[cs]
    return (f"<html><body style='font-family:sans-serif;padding:2rem;background:#f6f6f6'><h2>Stripe (simulado)</h2>"
            f"<p>{s['item']}<br>Total ${s['amount_total'] / 100:,.2f} MXN · {s['customer_email']}</p>"
            f"<p><a id='pagar' href='/_pago_falso/{cs}/pagar'>Pagar</a> · <a id='pagar-sin' href='/_pago_falso/{cs}/pagar?sin_webhook=1'>Pagar (sin webhook)</a>"
            f" · <a id='cancelar' href='{s['cancel_url']}'>Cancelar</a></p></body></html>")


@appmod.app.get("/_pago_falso/<cs>/pagar")
def pago_falso_pagar(cs):
    s = SES[cs]
    if s["status"] != "open":
        return f"sesión {s['status']}", 400
    s.update(status="complete", payment_status="paid", payment_intent="pi_" + cs[-4:],
             customer_details={"email": s["customer_email"], "name": s["metadata"].get("nombre")})
    if not request.args.get("sin_webhook"):
        bo.webhook("checkout.session.completed", dict(s))
    return redirect(s["success_url"].replace("{CHECKOUT_SESSION_ID}", cs))


print("API de prueba en http://localhost:8081 · libro en", LIBRO)
appmod.app.run(host="127.0.0.1", port=8081, debug=False, threaded=True)
