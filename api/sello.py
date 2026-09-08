# -*- coding: utf-8 -*-
"""Sello ROSSO: lealtad por visitas para el Club.

La barra busca al cliente por WhatsApp (o por nombre) en la hoja "Clientes ROSSO", registra la
visita con el PIN de barra en la hoja "Visitas ROSSO" y, cada PREMIO_CADA visitas, la casa invita
un cóctel. Todo vive en las dos hojas; sin base de datos aparte.
"""
import datetime as dt
import os
import re
import unicodedata

import google.auth
from google.auth.transport.requests import AuthorizedSession

import clientes as clientes_mod

SHEET_ID = os.environ.get("VISITAS_SHEET_ID", "")
PREMIO_CADA = int(os.environ.get("SELLO_PREMIO_CADA", "5"))
COLS = ["fecha_hora", "whatsapp", "nombre", "visita_num", "premio", "registro"]

_sesion = None


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def _url(rango):
    return f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{rango}"


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def visitas():
    if not SHEET_ID:
        return []
    r = _session().get(_url("A2:F20000"), timeout=30)
    r.raise_for_status()
    out = []
    for f in r.json().get("values", []):
        f = f + [""] * (len(COLS) - len(f))
        out.append(dict(zip(COLS, f)))
    return out


def buscar(q):
    """Clientes del Club que coinciden por WhatsApp (últimos dígitos) o por nombre. Máx. 8."""
    q = str(q or "").strip()
    digitos = re.sub(r"\D", "", q)
    todos = clientes_mod._filas()
    if len(digitos) >= 4:
        cand = [c for c in todos if c["whatsapp"].endswith(digitos)]
    else:
        nq = _norm(q)
        cand = [c for c in todos if nq and nq in _norm(c["nombre"])]
    cand = cand[:8]
    if not cand:
        return []
    vis = visitas()
    res = []
    for c in cand:
        mias = [v for v in vis if v["whatsapp"] == c["whatsapp"]]
        res.append({"nombre": c["nombre"], "whatsapp": c["whatsapp"], "fin": c["whatsapp"][-4:],
                    "visitas": len(mias), "ultima": mias[-1]["fecha_hora"] if mias else "",
                    "faltan": PREMIO_CADA - (len(mias) % PREMIO_CADA), "alta": c["fecha_alta"]})
    return res


def registrar(whatsapp, quien=""):
    """Suma una visita. Devuelve el conteo y si toca premio. Bloquea doble registro el mismo día."""
    whatsapp = re.sub(r"\D", "", whatsapp or "")
    cli = next((c for c in clientes_mod._filas() if c["whatsapp"] == whatsapp), None)
    if not cli:
        raise LookupError("ese WhatsApp no está en el Club")
    hoy = dt.date.today().isoformat()
    mias = [v for v in visitas() if v["whatsapp"] == whatsapp]
    if any(v["fecha_hora"].startswith(hoy) for v in mias):
        raise ValueError("esta visita ya se registró hoy")
    n = len(mias) + 1
    premio = n % PREMIO_CADA == 0
    fila = [dt.datetime.now().strftime("%Y-%m-%d %H:%M"), whatsapp, cli["nombre"], str(n),
            "cóctel de la casa" if premio else "", quien[:40]]
    r = _session().post(_url("A1:F1:append") + "?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
                        json={"values": [fila]}, timeout=20)
    r.raise_for_status()
    return {"nombre": cli["nombre"], "whatsapp": whatsapp, "visitas": n, "premio": premio,
            "faltan": PREMIO_CADA - (n % PREMIO_CADA) if not premio else PREMIO_CADA}


def resumen_semana(dias=7):
    desde = (dt.datetime.now() - dt.timedelta(days=dias)).strftime("%Y-%m-%d")
    vis = [v for v in visitas() if v["fecha_hora"] >= desde]
    premios = [v for v in vis if v["premio"]]
    return {"visitas": len(vis), "personas": len({v["whatsapp"] for v in vis}), "premios": len(premios)}
