# -*- coding: utf-8 -*-
"""Carta viva de Rosso: se arma desde las ventas de Wansoft (GetAllOrdersByDay),
porque GetProducts_Xml viene vacio para esta sucursal.

Regla: un producto aparece en la carta si se vendio >= MIN_UNIDADES veces en la
ventana, o si esta en overrides["incluir"]. Nombres y secciones salen de
overrides.json; lo que no tenga override se muestra en title-case.
"""
import datetime as dt
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
ENDPOINT = "https://www.wansoft.net/Wansoft.Web/API/IntegrationService.asmx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
VENTANA_DIAS = 28
MIN_UNIDADES = 2

OVERRIDES = json.load(open(os.path.join(AQUI, "overrides.json"), encoding="utf-8"))

# Grupo del POS -> (seccion, subseccion)
SECCIONES = [
    ("COCKTAILS DE LA CASA", "Cócteles de la casa", None),
    ("CLASICOS", "Clásicos", None),
    ("MOCKTAIL", "Sin alcohol", None),
    ("REFRESCOS", "Sin alcohol", None),
    ("DOMINGOS", "Domingos", None),
    ("TEQUILA.", "Destilados", "Tequila"),
    ("TEQUILA", "Destilados", "Tequila"),
    ("MEZCAL", "Destilados", "Mezcal"),
    ("WHISKY", "Destilados", "Whisky"),
    ("BOURBON", "Destilados", "Bourbon"),
    ("GINEBRA", "Destilados", "Ginebra"),
    ("VODKA", "Destilados", "Vodka"),
    ("RON", "Destilados", "Ron"),
    ("LICORES", "Destilados", "Licores y vermut"),
    ("DESTILADOS", "Destilados", "Otros"),
    ("CERVEZAS", "Cerveza", None),
    ("ALIMENTOS", "Para picar", None),
]
ORDEN_SECCIONES = ["Cócteles de la casa", "Clásicos", "Sin alcohol", "Domingos",
                   "Destilados", "Cerveza", "Para picar"]
ORDEN_SUB = ["Tequila", "Mezcal", "Whisky", "Bourbon", "Ginebra", "Vodka", "Ron",
             "Licores y vermut", "Otros"]

MINUSCULAS = {"de", "del", "la", "el", "con", "y", "a", "du", "en", "al"}


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def ventas_del_dia(fecha, sub, pwd):
    cuerpo = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><GetAllOrdersByDay_Xml xmlns="http://tempuri.org/">'
        f'<subsidiaryId>{sub}</subsidiaryId><pwdWebService>{pwd}</pwdWebService>'
        f'<operationdate>{fecha}</operationdate>'
        '</GetAllOrdersByDay_Xml></soap:Body></soap:Envelope>').encode("utf-8")
    headers = {"Content-Type": "text/xml; charset=utf-8",
               "SOAPAction": '"http://tempuri.org/GetAllOrdersByDay_Xml"',
               "User-Agent": UA}
    for intento in range(3):
        try:
            r = requests.post(ENDPOINT, data=cuerpo, headers=headers, timeout=40)
            r.raise_for_status()
            break
        except requests.exceptions.RequestException:
            if intento == 2:
                raise
            time.sleep(5)
    root = ET.fromstring(r.content)
    txt = next((el.text for el in root.iter() if el.tag.endswith("Result")), "") or ""
    return ET.fromstring(txt) if txt.strip() else ET.Element("Resultado")


def nombre_bonito(raw):
    if raw in OVERRIDES["nombres"]:
        return OVERRIDES["nombres"][raw]
    s = re.sub(r"\s+", " ", raw.replace("''", "'")).strip().lower()
    partes = []
    for i, w in enumerate(s.split(" ")):
        if i > 0 and w in MINUSCULAS:
            partes.append(w)
        else:
            partes.append(w[:1].upper() + w[1:])
    return " ".join(partes)


def seccion_de(grupo, tipo):
    g = (grupo or "").strip().upper()
    for clave, sec, sub in SECCIONES:
        if g == clave:
            return sec, sub
    if (tipo or "").upper() == "ALIMENTOS":
        return "Para picar", None
    return "Destilados", "Otros"


def armar_carta(sub, pwd, hasta=None, dias=VENTANA_DIAS, log=print):
    hasta = hasta or (dt.date.today() - dt.timedelta(days=1))
    desde = hasta - dt.timedelta(days=dias - 1)
    prod = defaultdict(lambda: {"n": 0.0, "precios": Counter(), "grupo": Counter(),
                                "tipo": Counter()})
    d = desde
    while d <= hasta:
        try:
            res = ventas_del_dia(d.isoformat(), sub, pwd)
        except Exception as e:  # un dia caido no tumba la carta
            log(f"carta: {d} sin datos ({e})")
            d += dt.timedelta(1)
            continue
        for v in res.iter("Venta"):
            for l in v.iter("DetalleVenta"):
                nombre = (l.get("Platillo") or l.get("Descripcion") or "").strip()
                if not nombre:
                    continue
                p = prod[nombre]
                cant = _num(l.get("Cantidad") or 1)
                p["n"] += cant
                pu = _num(l.get("PrecioUnitario"))
                if pu > 0:
                    p["precios"][int(round(pu))] += cant
                p["grupo"][l.get("Grupo") or ""] += 1
                p["tipo"][l.get("TipoGrupo") or ""] += 1
        d += dt.timedelta(1)
    return clasificar(prod, desde, hasta)


def clasificar(prod, desde, hasta):
    excluir = set(OVERRIDES.get("excluir", []))
    incluir = set(OVERRIDES.get("incluir", []))
    secciones = {s: {"items": [], "sub": defaultdict(list)} for s in ORDEN_SECCIONES}
    for raw, p in prod.items():
        if raw in excluir or not p["precios"]:
            continue
        if p["n"] < MIN_UNIDADES and raw not in incluir:
            continue
        sec, sub = seccion_de(p["grupo"].most_common(1)[0][0],
                              p["tipo"].most_common(1)[0][0])
        item = {"nombre": nombre_bonito(raw), "raw": raw,
                "precio": p["precios"].most_common(1)[0][0],
                "unidades": int(p["n"])}
        if raw in OVERRIDES.get("descripciones", {}):
            item["descripcion"] = OVERRIDES["descripciones"][raw]
        if sub:
            secciones[sec]["sub"][sub].append(item)
        else:
            secciones[sec]["items"].append(item)
    salida = []
    for s in ORDEN_SECCIONES:
        blk = secciones[s]
        blk["items"].sort(key=lambda i: (-i["unidades"], i["nombre"]))
        subs = []
        for nombre_sub in ORDEN_SUB:
            its = blk["sub"].get(nombre_sub)
            if its:
                its.sort(key=lambda i: (-i["unidades"], i["nombre"]))
                subs.append({"titulo": nombre_sub, "items": its})
        if blk["items"] or subs:
            salida.append({"titulo": s, "items": blk["items"], "subsecciones": subs})
    # lo publico no lleva unidades vendidas ni el nombre crudo del POS
    for s in salida:
        for it in s["items"] + [i for sub in s["subsecciones"] for i in sub["items"]]:
            it.pop("unidades", None)
            it.pop("raw", None)
    return {"generada": dt.datetime.now().isoformat(timespec="minutes"),
            "ventana": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
            "secciones": salida}


def desde_snapshot(ruta):
    """Reconstruye la carta desde el JSON crudo de extraer_carta.py (uso local)."""
    d = json.load(open(ruta, encoding="utf-8"))
    prod = {}
    for p in d["productos"]:
        prod[p["platillo"]] = {
            "n": p["unidades"],
            "precios": Counter({int(k): v for k, v in p["precios"].items()}),
            "grupo": Counter({p["grupo"]: 1}), "tipo": Counter({p["tipo"]: 1})}
    return clasificar(prod, dt.date.fromisoformat(d["desde"]),
                      dt.date.fromisoformat(d["hasta"]))
