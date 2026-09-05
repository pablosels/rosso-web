# -*- coding: utf-8 -*-
"""Descripciones de la carta desde la hoja "Carta ROSSO descripciones".

Columnas: nombre, ingredientes, descripcion, descripcion_en. Se cruzan por nombre (sin acentos,
minúsculas) con los items de la carta que sale de Wansoft. Caché de 10 minutos.
"""
import os
import re
import time
import unicodedata

import google.auth
from google.auth.transport.requests import AuthorizedSession

SHEET_ID = os.environ.get("DESCRIPCIONES_SHEET_ID", "")
_sesion = None
_cache = {"t": 0, "mapa": {}}


def _session():
    global _sesion
    if _sesion is None:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        _sesion = AuthorizedSession(creds)
    return _sesion


def clave(nombre):
    s = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def mapa():
    if not SHEET_ID:
        return {}
    if time.time() - _cache["t"] < 600 and _cache["mapa"]:
        return _cache["mapa"]
    try:
        r = _session().get(f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A1:D500", timeout=20)
        r.raise_for_status()
        filas = r.json().get("values", [])
        cab = [c.strip().lower() for c in filas[0]] if filas else []
        m = {}
        for f in filas[1:]:
            d = {cab[i]: (f[i].strip() if i < len(f) else "") for i in range(len(cab))}
            if d.get("nombre") and (d.get("descripcion") or d.get("descripcion_en")):
                m[clave(d["nombre"])] = {"descripcion": d.get("descripcion", ""), "descripcion_en": d.get("descripcion_en", "")}
        _cache.update(t=time.time(), mapa=m)
    except Exception as e:
        print("descripciones no leídas:", e)
    return _cache["mapa"]


def aplicar(carta):
    """Devuelve una copia de la carta con descripcion/descripcion_en en los items que tengan."""
    m = mapa()
    if not m or not carta:
        return carta
    import copy
    c = copy.deepcopy(carta)

    def poner(items):
        for it in items:
            d = m.get(clave(it.get("nombre")))
            if d:
                if d["descripcion"]:
                    it["descripcion"] = d["descripcion"]
                if d["descripcion_en"]:
                    it["descripcion_en"] = d["descripcion_en"]

    for s in c.get("secciones", []):
        poner(s.get("items", []))
        for sub in s.get("subsecciones", []):
            poner(sub.get("items", []))
    return c
