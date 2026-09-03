# -*- coding: utf-8 -*-
"""Métricas de origen: cada visita y cada clic importante del sitio se anota en la hoja
"Métricas ROSSO" (una fila por evento), y el resumen semanal sale por Telegram.

Sin cookies ni datos personales: sólo tipo de evento, canal de origen (ig, qr, google,
prensa, directo...), página, si fue móvil y el dominio de referencia.
"""
import datetime as dt
import os
import re
import threading
from collections import Counter, defaultdict

import google.auth
from google.auth.transport.requests import AuthorizedSession

SHEET_ID = os.environ.get("METRICAS_SHEET_ID", "")
TIPOS = {"visita", "reservar", "whatsapp", "evento", "carta", "opentable"}
CANAL_RE = re.compile(r"^[a-z0-9_-]{1,24}$")

_sesion = None
_lock = threading.Lock()
_pendientes = []


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def limpiar(d):
    tipo = str(d.get("tipo", "")).strip().lower()
    canal = str(d.get("canal", "") or "directo").strip().lower()
    if tipo not in TIPOS or not CANAL_RE.match(canal):
        return None
    pagina = re.sub(r"[^a-z0-9/_-]", "", str(d.get("pagina", "/")).lower())[:60] or "/"
    ref = re.sub(r"^https?://", "", str(d.get("ref", "")).lower()).split("/")[0][:60]
    return [dt.datetime.now().isoformat(timespec="seconds"), tipo, canal, pagina,
            "1" if d.get("movil") else "0", ref]


def anotar(fila):
    """Acumula y manda en lote (una llamada a Sheets por cada pocos eventos)."""
    with _lock:
        _pendientes.append(fila)
        if len(_pendientes) < 5:
            return
        lote, _pendientes[:] = list(_pendientes), []
    _append(lote)


def vaciar():
    with _lock:
        lote, _pendientes[:] = list(_pendientes), []
    if lote:
        _append(lote)


def _append(filas):
    if not SHEET_ID:
        return
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A1:F1:append"
           "?valueInputOption=RAW&insertDataOption=INSERT_ROWS")
    r = _session().post(url, json={"values": filas}, timeout=20)
    r.raise_for_status()


def leer(dias=7):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A2:F100000"
    r = _session().get(url, timeout=30)
    r.raise_for_status()
    desde = (dt.datetime.now() - dt.timedelta(days=dias)).isoformat()
    return [f for f in r.json().get("values", []) if len(f) >= 4 and f[0] >= desde]


def resumen(dias=7):
    filas = leer(dias)
    por_canal = defaultdict(Counter)
    total = Counter()
    for f in filas:
        tipo, canal = f[1], f[2]
        por_canal[canal][tipo] += 1
        total[tipo] += 1
    return {"dias": dias, "total": dict(total), "canales": {c: dict(v) for c, v in por_canal.items()}}


def texto_resumen(dias=7):
    r = resumen(dias)
    t = r["total"]
    lineas = [f"📊 <b>Sitio web, últimos {dias} días</b>",
              f"Visitas {t.get('visita', 0)} · Buscaron mesa {t.get('reservar', 0)} · "
              f"WhatsApp {t.get('whatsapp', 0)} · Eventos {t.get('evento', 0)}", ""]
    canales = sorted(r["canales"].items(), key=lambda kv: -kv[1].get("visita", 0))
    for canal, v in canales:
        conv = v.get("reservar", 0) + v.get("whatsapp", 0) + v.get("evento", 0)
        lineas.append(f"· <b>{canal}</b>: {v.get('visita', 0)} visitas → {conv} contactos "
                      f"(mesa {v.get('reservar', 0)}, WhatsApp {v.get('whatsapp', 0)}, eventos {v.get('evento', 0)})")
    if not canales:
        lineas.append("Sin datos todavía.")
    lineas.append(f"\nHoja: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
    return "\n".join(lineas)
