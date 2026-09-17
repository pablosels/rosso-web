# -*- coding: utf-8 -*-
"""Marcador de DJs: qué vendió ROSSO la noche que tocó cada selector, contra lo normal de ese día.

Para cada noche de la agenda ya pasada: venta total con IVA (suma de <Ventas>/Venta@Total), venta
de 9 pm en adelante (incluye madrugada), personas, ticket por persona y cortesías de cuenta completa.
La referencia es el promedio del mismo día de la semana en las 6 semanas anteriores. Cada fecha se
consulta una vez a Wansoft y se guarda en el bucket (rosso-web/ventas/AAAA-MM-DD.json).
"""
import datetime as dt

import agenda as agenda_mod
import carta as carta_mod

SEMANAS_BASE = 6
SEMANAS_MAX = 12
import json as _json, os as _os
try:
    with open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "noches_especiales.json"), encoding="utf-8") as _fh:
        ESPECIALES = {k: v for k, v in _json.load(_fh).items() if not k.startswith("_")}
except Exception:
    ESPECIALES = {}


def _num(x):
    return carta_mod._num(x)


def _hora(v):
    h = (v.get("HoraApertura") or "")
    try:
        parte = h.split("T")[-1] if "T" in h else h.split(" ")[-1]
        return int(parte[:2])
    except (ValueError, IndexError):
        return -1


def resumen_dia(fecha, sub, pwd, leer, guardar):
    """{'venta','venta_noche','personas','cuentas','cortesias'} del día operativo. Cachea fechas pasadas."""
    clave = f"ventas/{fecha.isoformat()}.json"
    hoy = dt.date.today()
    if fecha < hoy - dt.timedelta(days=1):
        try:
            c = leer(clave)
            if c:
                return c
        except Exception:
            pass
    res = carta_mod.ventas_del_dia(fecha.isoformat(), sub, pwd)
    venta = noche = cort = 0.0
    personas = cuentas = 0
    ventas = res.find("Ventas")
    for v in (ventas.iter("Venta") if ventas is not None else res.iter("Venta")):
        t = _num(v.get("Total"))
        venta += t
        cuentas += 1
        personas += int(_num(v.get("Personas")))
        h = _hora(v)
        if h >= 21 or 0 <= h < 6:
            noche += t
    cs = res.find("Cortesias")
    if cs is not None:
        for v in cs.iter("Venta"):
            cort += sum(_num(l.get("Descuento")) or _num(l.get("PrecioUnitario")) * (_num(l.get("Cantidad")) or 1) for l in v.iter("DetalleVenta"))
    d = {"fecha": fecha.isoformat(), "venta": round(venta), "venta_noche": round(noche), "personas": personas,
         "cuentas": cuentas, "cortesias": round(cort)}
    if fecha < hoy - dt.timedelta(days=1):
        try:
            guardar(clave, d)
        except Exception:
            pass
    return d


def marcador(sub, pwd, leer, guardar, dias=8, hoy=None):
    hoy = hoy or dt.date.today()
    desde = hoy - dt.timedelta(days=dias)
    noches = [x for x in agenda_mod.leer_filas() if desde.isoformat() <= x["fecha"] < hoy.isoformat()]
    out = []
    for n in noches:
        f = dt.date.fromisoformat(n["fecha"])
        try:
            r = resumen_dia(f, sub, pwd, leer, guardar)
        except Exception as e:
            print("marcador: sin datos", f, e)
            continue
        base, saltadas = [], []
        for k in range(1, SEMANAS_MAX + 1):
            if len(base) >= SEMANAS_BASE or (k > SEMANAS_BASE and len(base) >= 3):
                break
            fb = f - dt.timedelta(days=7 * k)
            if fb.isoformat() in ESPECIALES:          # noche de evento: no es "lo normal"
                saltadas.append(ESPECIALES[fb.isoformat()])
                continue
            try:
                b = resumen_dia(fb, sub, pwd, leer, guardar)
                if b["venta"] > 0:
                    base.append(b)
            except Exception:
                continue
        prom = sum(b["venta"] for b in base) / len(base) if base else 0
        prom_pers = sum(b["personas"] for b in base) / len(base) if base else 0
        out.append({"fecha": n["fecha"], "fecha_larga": n["fecha_larga"], "dj": n["dj"], "pago": n.get("_pago", 0),
                    **{k: r[k] for k in ("venta", "venta_noche", "personas", "cuentas", "cortesias")},
                    "ticket": round(r["venta"] / r["personas"]) if r["personas"] else 0,
                    "promedio_dia": round(prom), "promedio_personas": round(prom_pers),
                    "vs": round((r["venta"] / prom - 1) * 100) if prom else None,
                    "base_n": len(base), "base_sin": sorted(set(saltadas))})
    return out


def texto(filas):
    if not filas:
        return "🎚️ <b>Marcador de DJs</b>: sin noches con DJ en la última semana."
    lin = ["🎚️ <b>Marcador de DJs, última semana</b>", "Venta de la noche contra lo normal de ese día (promedio de 6 semanas)."]
    for x in filas:
        flecha = "" if x["vs"] is None else (" 🟢 +" if x["vs"] >= 10 else " 🔴 " if x["vs"] <= -10 else " ⚪ ") + (f"{x['vs']}%" if x["vs"] < 0 or x["vs"] < 10 else f"{x['vs']}%")
        lin.append(f"\n<b>{x['dj']}</b> · {x['fecha_larga']}")
        lin.append(f"Venta ${x['venta']:,} (normal ${x['promedio_dia']:,}){flecha}"
                   + (f" · referencia de {x['base_n']} noches, sin {', '.join(x['base_sin'])}" if x.get("base_sin") else ""))
        lin.append(f"{x['personas']} personas (normal {x['promedio_personas']}) · ticket ${x['ticket']:,} por persona · de 9 pm en adelante ${x['venta_noche']:,}")
        extra = []
        if x["cortesias"]:
            extra.append(f"cortesías ${x['cortesias']:,}")
        if x["pago"]:
            extra.append(f"pago al DJ ${int(x['pago']):,} = {round(x['pago'] / x['venta'] * 100) if x['venta'] else 0}% de la venta")
        if extra:
            lin.append(" · ".join(extra))
        if x["vs"] is not None and x["promedio_personas"] and x["personas"] > x["promedio_personas"] * 1.15 and x["vs"] < 5:
            lin.append("⚠️ Trajo gente pero no consumo: más personas que lo normal y la venta no subió.")
    return "\n".join(lin)
