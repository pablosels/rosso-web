# -*- coding: utf-8 -*-
"""Saca la carta viva de Rosso desde las ventas de Wansoft (Platillo, Grupo, precio modal)
y la actividad por dia de la semana. Uso: python extraer_carta.py 2026-08-05 2026-09-01"""
import sys, json, datetime as dt
from collections import defaultdict, Counter
sys.path.insert(0, r"C:\Users\minis\Downloads\rosso-eventos")
from catalogo_barra import dia, _num
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d0, d1 = (dt.date.fromisoformat(x) for x in sys.argv[1:3])
prod = defaultdict(lambda: {"n": 0.0, "precios": Counter(), "grupo": Counter(), "tipo": Counter()})
por_dia = Counter(); ventas_dia = {}
d = d0
while d <= d1:
    iso = d.isoformat()
    try:
        res = dia(iso)
    except Exception as e:
        print("ERR", iso, e); d += dt.timedelta(1); continue
    tot = 0.0
    for v in res.iter("Venta"):
        tot += _num(v.get("Total"))
        for l in v.iter("DetalleVenta"):
            nombre = (l.get("Platillo") or l.get("Descripcion") or "").strip()
            if not nombre: continue
            p = prod[nombre]
            cant = _num(l.get("Cantidad") or 1)
            p["n"] += cant
            pu = _num(l.get("PrecioUnitario"))
            if pu > 0: p["precios"][round(pu)] += cant
            p["grupo"][l.get("Grupo") or ""] += 1
            p["tipo"][l.get("TipoGrupo") or ""] += 1
    ventas_dia[iso] = round(tot, 2)
    if tot > 0: por_dia[d.strftime("%a")] += 1
    d += dt.timedelta(1)
out = []
for nombre, p in sorted(prod.items(), key=lambda kv: -kv[1]["n"]):
    out.append({"platillo": nombre, "unidades": p["n"],
                "precio": p["precios"].most_common(1)[0][0] if p["precios"] else None,
                "precios": dict(p["precios"].most_common(3)),
                "grupo": p["grupo"].most_common(1)[0][0], "tipo": p["tipo"].most_common(1)[0][0]})
json.dump({"desde": sys.argv[1], "hasta": sys.argv[2], "dias_con_venta": dict(por_dia),
           "ventas_por_dia": ventas_dia, "productos": out},
          open(r"C:\Users\minis\Downloads\rosso-web\carta_wansoft.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("productos:", len(out)); print("dias con venta:", dict(por_dia))
