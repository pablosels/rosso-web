# -*- coding: utf-8 -*-
"""Tarjetas de regalo de ROSSO.

Compra: el sitio pide una sesión de Stripe Checkout (/regalo/checkout) y manda al cliente a
pagar. Stripe avisa por webhook (/stripe/webhook) cuando el pago está hecho; ahí se genera
el código, se guarda en la hoja "Tarjetas ROSSO" y se avisa a Pablo por Telegram. La página
de gracias consulta /regalo/estado hasta que el código existe.

Canje: en barra se busca el código (/regalo/saldo) y se descuenta con un PIN (/regalo/canjear).
Todo se guarda en la hoja; no hay base de datos aparte.
"""
import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import time

import google.auth
import requests
from google.auth.transport.requests import AuthorizedSession

SHEET_ID = os.environ.get("REGALO_SHEET_ID", "")
STRIPE_KEY = os.environ.get("STRIPE_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
CANJE_PIN = os.environ.get("CANJE_PIN", "")
SITIO = os.environ.get("SITIO", "https://rossospeakeasy.com")
MONTOS = (500, 1000, 2000, 3000)
VIGENCIA_DIAS = 365
COLS = ["codigo", "monto", "saldo", "estado", "fecha_compra", "vence", "comprador", "email",
        "para", "mensaje", "sesion_stripe", "canjes"]
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O/1/I para dictarlo en barra

_sesion = None


def configurado():
    return bool(SHEET_ID and STRIPE_KEY and WEBHOOK_SECRET)


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def _url(rango):
    return f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{rango}"


# ------------------------------------------------------------------ hoja
def _filas():
    r = _session().get(_url("A2:L5000"), timeout=30)
    r.raise_for_status()
    out = []
    for i, f in enumerate(r.json().get("values", []), start=2):
        f = f + [""] * (len(COLS) - len(f))
        out.append((i, dict(zip(COLS, f))))
    return out


def buscar(codigo=None, sesion=None):
    codigo = (codigo or "").strip().upper()
    for fila, d in _filas():
        if (codigo and d["codigo"] == codigo) or (sesion and d["sesion_stripe"] == sesion):
            return fila, d
    return None, None


def _escribir(fila, d):
    valores = [[d.get(c, "") for c in COLS]]
    r = _session().put(_url(f"A{fila}:L{fila}") + "?valueInputOption=RAW", json={"values": valores}, timeout=20)
    r.raise_for_status()


def _agregar(d):
    valores = [[d.get(c, "") for c in COLS]]
    r = _session().post(_url("A1:L1:append") + "?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
                        json={"values": valores}, timeout=20)
    r.raise_for_status()


def nuevo_codigo():
    while True:
        cuerpo = "".join(secrets.choice(ALFABETO) for _ in range(8))
        codigo = f"ROSSO-{cuerpo[:4]}-{cuerpo[4:]}"
        if buscar(codigo=codigo)[0] is None:
            return codigo


# ------------------------------------------------------------------ stripe
def crear_sesion(monto, de, para, mensaje, email, canal="directo"):
    if monto not in MONTOS:
        raise ValueError("monto no permitido")
    datos = {
        "mode": "payment",
        "locale": "es-419",
        "success_url": f"{SITIO}/regalo/gracias/?s={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{SITIO}/regalo/",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "mxn",
        "line_items[0][price_data][unit_amount]": str(monto * 100),
        "line_items[0][price_data][product_data][name]": f"Tarjeta de regalo ROSSO · ${monto:,}",
        "line_items[0][price_data][product_data][description]": "Canjeable en barra en ROSSO, Puebla 329, Roma Norte. Vigencia de 12 meses.",
        "metadata[tipo]": "regalo",
        "metadata[monto]": str(monto),
        "metadata[de]": de[:80],
        "metadata[para]": para[:80],
        "metadata[mensaje]": mensaje[:200],
        "metadata[canal]": canal[:24],
        "custom_text[submit][message]": "Al pagar verás tu código de regalo en pantalla y te llegará el recibo por correo.",
    }
    if email:
        datos["customer_email"] = email
    r = requests.post("https://api.stripe.com/v1/checkout/sessions", data=datos,
                      auth=(STRIPE_KEY, ""), timeout=30)
    if not r.ok:
        raise RuntimeError(f"stripe {r.status_code}: {r.text[:300]}")
    j = r.json()
    return j["id"], j["url"]


def verificar_firma(payload: bytes, header: str, tolerancia=300):
    """Firma Stripe-Signature: t=..., v1=... (HMAC-SHA256 del 't.payload')."""
    partes = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t, v1 = partes.get("t"), partes.get("v1")
    if not t or not v1:
        return False
    if abs(time.time() - int(t)) > tolerancia:
        return False
    esperado = hmac.new(WEBHOOK_SECRET.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


def registrar_pago(sesion: dict):
    """checkout.session.completed → fila nueva en la hoja. Idempotente por id de sesión."""
    sid = sesion.get("id", "")
    if sesion.get("payment_status") != "paid":
        return None
    fila, existente = buscar(sesion=sid)
    if existente:
        return existente
    md = sesion.get("metadata") or {}
    cd = sesion.get("customer_details") or {}
    monto = int(md.get("monto") or round(int(sesion.get("amount_total", 0)) / 100))
    hoy = dt.date.today()
    d = {
        "codigo": nuevo_codigo(), "monto": str(monto), "saldo": str(monto), "estado": "activa",
        "fecha_compra": hoy.isoformat(), "vence": (hoy + dt.timedelta(days=VIGENCIA_DIAS)).isoformat(),
        "comprador": (md.get("de") or cd.get("name") or "")[:80], "email": (cd.get("email") or "")[:120],
        "para": (md.get("para") or "")[:80], "mensaje": (md.get("mensaje") or "")[:200],
        "sesion_stripe": sid, "canjes": "",
    }
    _agregar(d)
    return d


# ------------------------------------------------------------------ consulta y canje
def publica(d):
    hoy = dt.date.today().isoformat()
    estado = d["estado"]
    if estado == "activa" and d["vence"] and d["vence"] < hoy:
        estado = "vencida"
    return {"codigo": d["codigo"], "monto": int(float(d["monto"] or 0)), "saldo": int(float(d["saldo"] or 0)),
            "estado": estado, "vence": d["vence"], "para": d["para"], "de": d["comprador"], "mensaje": d["mensaje"],
            "fecha_compra": d["fecha_compra"]}


def canjear(codigo, monto, pin):
    if not CANJE_PIN or pin != CANJE_PIN:
        raise PermissionError("PIN incorrecto")
    fila, d = buscar(codigo=codigo)
    if not d:
        raise LookupError("código no existe")
    p = publica(d)
    if p["estado"] != "activa":
        raise ValueError(f"la tarjeta está {p['estado']}")
    monto = int(monto)
    if monto <= 0 or monto > p["saldo"]:
        raise ValueError(f"saldo disponible: ${p['saldo']:,}")
    nuevo = p["saldo"] - monto
    d["saldo"] = str(nuevo)
    d["estado"] = "agotada" if nuevo == 0 else "activa"
    d["canjes"] = (d["canjes"] + " | " if d["canjes"] else "") + f"{dt.datetime.now():%Y-%m-%d %H:%M} -${monto:,}"
    _escribir(fila, d)
    return publica(d)


def limpiar_texto(s, n):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]
