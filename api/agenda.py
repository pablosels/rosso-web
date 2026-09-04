# -*- coding: utf-8 -*-
"""Agenda semanal de DJs: se lee de la hoja de Google "Agenda ROSSO".

Columnas (fila 1): fecha, hora, dj, genero, instagram, preventa, destacado, pago, pagado, notas.
La hoja se comparte como lector con la cuenta de servicio del servicio de Cloud Run;
se lee con las credenciales por defecto (ADC), sin llaves en el código.
"""
import datetime as dt
import os
import re

import google.auth
from google.auth.transport.requests import AuthorizedSession

SHEET_ID = os.environ.get("AGENDA_SHEET_ID", "")
RANGO = "A1:L400"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

_sesion = None


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def _fecha(txt):
    t = (txt or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    return None


def _ig(handle):
    h = (handle or "").strip()
    if not h:
        return None
    if h.startswith("http"):
        m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", h)
        h = m.group(1) if m else ""
    return h.lstrip("@").strip("/") or None


def leer_filas():
    if not SHEET_ID:
        return []
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{RANGO}"
    r = _session().get(url, timeout=20)
    r.raise_for_status()
    filas = r.json().get("values", [])
    if not filas:
        return []
    cab = [c.strip().lower() for c in filas[0]]
    out = []
    for f in filas[1:]:
        d = {cab[i]: (f[i].strip() if i < len(f) else "") for i in range(len(cab))}
        fecha = _fecha(d.get("fecha"))
        dj = d.get("dj", "")
        if not fecha or not dj or dj.lower().startswith("ejemplo"):
            continue
        pago = re.sub(r"[^0-9.]", "", d.get("pago", "") or "")
        out.append({
            "_pago": float(pago) if pago else 0.0,          # privado: nunca sale por /agenda
            "_pagado": d.get("pagado", "").strip().lower() in ("si", "sí", "x", "1", "true", "pagado"),
            "fecha": fecha.isoformat(),
            "dia": DIAS[fecha.weekday()],
            "fecha_larga": f"{DIAS[fecha.weekday()].capitalize()} {fecha.day} de {MESES[fecha.month - 1]}",
            "hora": re.sub(r"s*(AM|PM)$", lambda m: " " + m.group(1).lower(), d.get("hora", "").strip()),
            "dj": dj,
            "genero": d.get("genero", ""),
            "instagram": _ig(d.get("instagram")),
            "preventa": d.get("preventa", "") if d.get("preventa", "").startswith("http") else "",
            "destacado": d.get("destacado", "").strip().lower() in ("si", "sí", "x", "1", "true"),
            "_notas": d.get("notas", ""),
        })
    out.sort(key=lambda x: (x["fecha"], x["hora"]))
    return out


def _publica(x):
    return {k: v for k, v in x.items() if not k.startswith("_")}


def proximas(dias=21, hoy=None):
    hoy = hoy or dt.date.today()
    lim = hoy + dt.timedelta(days=dias)
    return [_publica(x) for x in leer_filas() if hoy.isoformat() <= x["fecha"] <= lim.isoformat()]


def pagos_pendientes(dias=45, hoy=None):
    """DJs ya tocaron (fecha pasada), con monto y sin marcar pagado."""
    hoy = hoy or dt.date.today()
    desde = hoy - dt.timedelta(days=dias)
    return [x for x in leer_filas()
            if desde.isoformat() <= x["fecha"] < hoy.isoformat() and x["_pago"] > 0 and not x["_pagado"]]


def semana_faltante(hoy=None):
    """Noches de esta semana (mar–dom desde hoy) sin fila en la hoja. Para el recordatorio del lunes."""
    hoy = hoy or dt.date.today()
    lunes = hoy - dt.timedelta(days=hoy.weekday())
    con_fila = {x["fecha"] for x in leer_filas()}
    faltan = []
    for i in range(1, 7):  # martes..domingo
        d = lunes + dt.timedelta(days=i)
        if d >= hoy and d.isoformat() not in con_fila:
            faltan.append(f"{DIAS[d.weekday()]} {d.day}")
    return faltan
