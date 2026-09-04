# -*- coding: utf-8 -*-
"""Base de clientes de ROSSO (Club ROSSO): altas desde el sitio y cumpleaños de la semana.

Hoja "Clientes ROSSO": fecha_alta, nombre, whatsapp, email, cumple, consentimiento, canal, notas.
La persona da su consentimiento en el formulario (aviso de privacidad en /privacidad/).
Cada lunes, /clientes/cumples manda por Telegram quién cumple en los próximos 7 días.
"""
import datetime as dt
import os
import re

import google.auth
from google.auth.transport.requests import AuthorizedSession

SHEET_ID = os.environ.get("CLIENTES_SHEET_ID", "")
COLS = ["fecha_alta", "nombre", "whatsapp", "email", "cumple", "consentimiento", "canal", "notas"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

_sesion = None


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def _url(rango):
    return f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{rango}"


def limpiar_whatsapp(s):
    """Deja solo dígitos; 10 dígitos mexicanos → 52 + 10."""
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) == 10:
        d = "52" + d
    if len(d) == 12 and d.startswith("52"):
        return d
    if len(d) == 13 and d.startswith("521"):
        return "52" + d[3:]
    return d if 10 <= len(d) <= 15 else ""


def limpiar_cumple(s):
    """Acepta dd/mm, dd-mm, 'dd de mes' o yyyy-mm-dd; guarda dd/mm."""
    t = str(s or "").strip().lower()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
    if m:
        d, mo = int(m.group(3)), int(m.group(2))
    else:
        m = re.match(r"^(\d{1,2})\s*[/\-.]\s*(\d{1,2})", t)
        if m:
            d, mo = int(m.group(1)), int(m.group(2))
        else:
            m = re.match(r"^(\d{1,2})\s+de\s+([a-záéíóú]+)", t)
            if not m or m.group(2) not in MESES:
                return ""
            d, mo = int(m.group(1)), MESES.index(m.group(2)) + 1
    try:
        dt.date(2024, mo, d)   # 2024 es bisiesto: acepta 29/02
    except ValueError:
        return ""
    return f"{d:02d}/{mo:02d}"


def _filas():
    r = _session().get(_url("A2:H5000"), timeout=30)
    r.raise_for_status()
    out = []
    for f in r.json().get("values", []):
        f = f + [""] * (len(COLS) - len(f))
        out.append(dict(zip(COLS, f)))
    return out


def existe(whatsapp="", email=""):
    for d in _filas():
        if (whatsapp and d["whatsapp"] == whatsapp) or (email and email and d["email"].lower() == email.lower()):
            return True
    return False


def alta(nombre, whatsapp, email, cumple, canal):
    if not SHEET_ID:
        raise RuntimeError("CLIENTES_SHEET_ID no configurado")
    if existe(whatsapp, email):
        return {"nuevo": False}
    d = {"fecha_alta": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "nombre": nombre, "whatsapp": whatsapp,
         "email": email, "cumple": cumple, "consentimiento": "sí (web)", "canal": canal or "directo", "notas": ""}
    r = _session().post(_url("A1:H1:append") + "?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
                        json={"values": [[d[c] for c in COLS]]}, timeout=20)
    r.raise_for_status()
    return {"nuevo": True}


def cumples(dias=7, hoy=None):
    """Clientes que cumplen entre hoy y hoy+dias, ordenados por fecha."""
    hoy = hoy or dt.date.today()
    out = []
    for d in _filas():
        c = limpiar_cumple(d["cumple"])
        if not c:
            continue
        dd, mm = int(c[:2]), int(c[3:])
        for anio in (hoy.year, hoy.year + 1):
            try:
                f = dt.date(anio, mm, dd)
            except ValueError:
                f = dt.date(anio, 3, 1)   # 29/02 en año no bisiesto
            if 0 <= (f - hoy).days <= dias:
                out.append({"fecha": f, "nombre": d["nombre"], "whatsapp": d["whatsapp"], "email": d["email"]})
                break
    out.sort(key=lambda x: x["fecha"])
    return out


def texto_cumples(dias=7, hoy=None):
    hoy = hoy or dt.date.today()
    lista = cumples(dias, hoy)
    total = len(_filas())
    if not lista:
        return f"🎂 <b>Cumpleaños esta semana</b>: ninguno. Club ROSSO: {total} personas."
    lineas = []
    for x in lista:
        cuando = "hoy" if x["fecha"] == hoy else f"{x['fecha'].day} de {MESES[x['fecha'].month - 1]}"
        wa = f' · <a href="https://wa.me/{x["whatsapp"]}">WhatsApp</a>' if x["whatsapp"] else ""
        lineas.append(f"• {x['nombre']} — {cuando}{wa}")
    return f"🎂 <b>Cumpleaños próximos 7 días</b> (Club ROSSO: {total} personas)\n" + "\n".join(lineas) + \
        "\nIdea: mándales un cóctel de cumpleaños si vienen esta semana."
