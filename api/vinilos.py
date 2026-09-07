# -*- coding: utf-8 -*-
"""Vinilo del domingo: hoja "Vinilos ROSSO" (fecha, artista, disco, anio, spotify, nota, selector).

La portada y el título salen solos de Spotify (oEmbed público, sin llave) a partir de la liga
del álbum. Caché de 10 minutos. Filas cuyo artista empiece con "Ejemplo" se ignoran.
"""
import datetime as dt
import os
import re
import time

import google.auth
import requests
from google.auth.transport.requests import AuthorizedSession

SHEET_ID = os.environ.get("VINILOS_SHEET_ID", "")
_sesion = None
_cache = {"t": 0, "filas": []}
_oembed = {}


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def _fecha(txt, hoy):
    t = (txt or "").strip()
    f = None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            f = dt.datetime.strptime(t, fmt).date()
            break
        except ValueError:
            pass
    if not f:
        return None
    if f < hoy - dt.timedelta(days=3) and f.day <= 12:     # hoja en formato gringo: día y mes volteados
        try:
            v = f.replace(month=f.day, day=f.month)
            if hoy - dt.timedelta(days=3) <= v <= hoy + dt.timedelta(days=120):
                return v
        except ValueError:
            pass
    return f


def spotify_info(url):
    """Portada, título y id del álbum vía oEmbed. Devuelve {} si no es una liga válida."""
    m = re.search(r"open\.spotify\.com/(?:intl-[a-z]+/)?(album|playlist|track)/([A-Za-z0-9]+)", url or "")
    if not m:
        return {}
    tipo, sid = m.group(1), m.group(2)
    if sid in _oembed:
        return _oembed[sid]
    info = {"tipo": tipo, "id": sid, "embed": f"https://open.spotify.com/embed/{tipo}/{sid}", "url": f"https://open.spotify.com/{tipo}/{sid}"}
    try:
        r = requests.get("https://open.spotify.com/oembed", params={"url": info["url"]}, timeout=10)
        if r.ok:
            j = r.json()
            info["portada"] = j.get("thumbnail_url", "")
            info["titulo_spotify"] = j.get("title", "")
    except Exception as e:
        print("oembed fallo:", e)
    _oembed[sid] = info
    return info


def filas(hoy=None):
    hoy = hoy or dt.date.today()
    if not SHEET_ID:
        return []
    if time.time() - _cache["t"] < 600 and _cache["filas"]:
        return _cache["filas"]
    r = _session().get(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A1:H400", timeout=20)
    r.raise_for_status()
    vals = r.json().get("values", [])
    if not vals:
        return []
    cab = [c.strip().lower() for c in vals[0]]
    out = []
    for f in vals[1:]:
        d = {cab[i]: (f[i].strip() if i < len(f) else "") for i in range(len(cab))}
        fecha = _fecha(d.get("fecha"), hoy)
        if not fecha or not d.get("disco") or d.get("artista", "").lower().startswith("ejemplo"):
            continue
        sp = spotify_info(d.get("spotify", ""))
        out.append({
            "fecha": fecha.isoformat(), "artista": d.get("artista", ""), "disco": d.get("disco", ""),
            "anio": d.get("anio", "") or d.get("año", ""), "nota": d.get("nota", ""), "selector": d.get("selector", ""),
            "spotify": sp.get("url", ""), "embed": sp.get("embed", ""), "portada": sp.get("portada", ""),
        })
    out.sort(key=lambda x: x["fecha"])
    _cache.update(t=time.time(), filas=out)
    return out


def proximo_domingo(hoy=None):
    hoy = hoy or dt.date.today()
    return hoy + dt.timedelta(days=(6 - hoy.weekday()) % 7)


def actual(hoy=None):
    """El disco del próximo domingo (o de hoy si es domingo) y los últimos 8 anteriores."""
    hoy = hoy or dt.date.today()
    dom = proximo_domingo(hoy)
    todos = filas(hoy)
    ahora = next((x for x in todos if x["fecha"] == dom.isoformat()), None)
    if not ahora:   # si no está capturado el próximo, se muestra el más reciente
        pasados = [x for x in todos if x["fecha"] <= dom.isoformat()]
        ahora = pasados[-1] if pasados else None
    anteriores = [x for x in todos if x["fecha"] < (ahora["fecha"] if ahora else dom.isoformat())][-8:][::-1]
    return {"domingo": dom.isoformat(), "vinilo": ahora, "anteriores": anteriores}


def falta_domingo(hoy=None):
    hoy = hoy or dt.date.today()
    dom = proximo_domingo(hoy)
    return not any(x["fecha"] == dom.isoformat() for x in filas(hoy))
