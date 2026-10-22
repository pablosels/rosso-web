# -*- coding: utf-8 -*-
"""Simula TODAS las combinaciones de respuestas del quiz (misma lógica que site.js) y reporta:
cuántas veces sale cada cóctel, cuántos empates se resolvieron por prioridad y si algún cóctel es inalcanzable."""
import itertools, json, pathlib
from collections import Counter
R = pathlib.Path(__file__).resolve().parent.parent
Q = json.loads((R / "content" / "quiz.json").read_text(encoding="utf-8"))
BASES = {"agave", "gin", "ron", "whiskey", "vermut"}; PESOS = Q.get("pesos", {})

def mejor(puntos, sin_alcohol):
    elegidas = [r for r in puntos if r in BASES]
    cand = [c for c in Q["cocteles"] if (c.get("sin_alcohol") if sin_alcohol else (not c.get("sin_alcohol") and (not elegidas or any(r in elegidas for r in c["rasgos"]))))]
    mejor_c, mx, empate = None, -1, False
    for c in cand:  # ya vienen en orden de prioridad
        s = sum(puntos.get(r, 0) * PESOS.get(r, 1) for r in c["rasgos"] if r not in BASES)
        if s > mx: mejor_c, mx, empate = c, s, False
        elif s == mx: empate = True
    return mejor_c, empate

cuenta, empates, total = Counter(), 0, 0
for combo in itertools.product(*[range(len(p["opciones"])) for p in Q["preguntas"]]):
    puntos, sin_alc = {}, False
    for p, k in zip(Q["preguntas"], combo):
        o = p["opciones"][k]
        for r in o["rasgos"]: puntos[r] = puntos.get(r, 0) + 1
        if o.get("sin_alcohol"): sin_alc = True
    c, emp = mejor(puntos, sin_alc)
    cuenta[c["slug"]] += 1; empates += emp; total += 1
print(f"{total} combinaciones, {empates} resueltas por prioridad ({empates*100//total}%)")
for c in Q["cocteles"]:
    print(f"{c['slug']:20} {cuenta[c['slug']]:5}  {cuenta[c['slug']]*100/total:5.1f}%")
faltan = [c["slug"] for c in Q["cocteles"] if not cuenta[c["slug"]]]
print("inalcanzables:", faltan or "ninguno")
