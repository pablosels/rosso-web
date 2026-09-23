# -*- coding: utf-8 -*-
"""Fotos de cócteles para el quiz: toma los originales de Hormiga (carpeta Drive "Cocteles", bajados a
Downloads o a fotos_originales/cocteles) y deja versiones web en assets/fotos/cocteles/<slug>.jpg (1200 px)
y <slug>-m.jpg (640 px), recorte 4:5 centrado. Los slugs son los de content/quiz.json."""
import pathlib, shutil
from PIL import Image, ImageOps

R = pathlib.Path(__file__).resolve().parent.parent
DESC = pathlib.Path.home() / "Downloads"
ORIG = R / "fotos_originales" / "cocteles"; ORIG.mkdir(parents=True, exist_ok=True)
OUT = R / "assets" / "fotos" / "cocteles"; OUT.mkdir(parents=True, exist_ok=True)

# slug del quiz -> archivo original (Downloads o fotos_originales/cocteles)
FUENTES = {
    "spf-0": "Rosso_SPF0_1.JPG",
    "querido-diario": "Rosso_queridoDiario.jpg",
    "camasotz": "Rosso_Posts_Camazotz.jpg",
    "picarilla": "Rosso_Picarilla.jpg",
    "sabor-a-mi": "Rosso_SaborAmi.jpg",
    "rococócrème": "Rosso_Rococo_2.jpg",
    "voyeur": "Rosso_Voyeur.jpg",
    "paola": "Rosso_Paola_2.jpg",
    "l-origine-du-monde": "Rosso_Coctel_lorigineDuMonde.jpg",
}
ALTERNAS = {"l-origine-du-monde": R / "fotos_originales" / "Rosso_Coctel_lorigineDuMonde.jpg"}
# recorte manual (fracciones x0,y0,x1,y1) cuando el centrado no sirve
CAJAS = {"l-origine-du-monde": (0.60, 0.45, 1.0, 0.78)}


def recorte(im, ancho, prop=(4, 5), caja=None):
    im = ImageOps.exif_transpose(im).convert("RGB")
    if caja:
        w, h = im.size; im = im.crop((int(caja[0]*w), int(caja[1]*h), int(caja[2]*w), int(caja[3]*h)))
    w, h = im.size
    objetivo = prop[0] / prop[1]
    if w / h > objetivo:      # muy ancha: recorta lados
        nw = int(h * objetivo); x0 = (w - nw) // 2; im = im.crop((x0, 0, x0 + nw, h))
    else:                     # muy alta: recorta arriba/abajo, un poco más arriba (la copa suele ir al centro-alto)
        nh = int(w / objetivo); y0 = max(0, int((h - nh) * 0.45)); im = im.crop((0, y0, w, y0 + nh))
    return im.resize((ancho, int(ancho / objetivo)), Image.LANCZOS)


hechos, faltan = [], []
for slug, nombre in FUENTES.items():
    src = None
    for cand in (DESC / nombre, ORIG / nombre, ALTERNAS.get(slug)):
        if cand and pathlib.Path(cand).exists():
            src = pathlib.Path(cand); break
    if not src:
        faltan.append(slug); continue
    if src.parent == DESC:                       # guarda el original en el repo (gitignored) y limpia Downloads
        shutil.move(str(src), str(ORIG / nombre)); src = ORIG / nombre
    im = Image.open(src)
    recorte(im, 1200, caja=CAJAS.get(slug)).save(OUT / f"{slug}.jpg", quality=84, optimize=True, progressive=True)
    recorte(im, 640, caja=CAJAS.get(slug)).save(OUT / f"{slug}-m.jpg", quality=82, optimize=True, progressive=True)
    hechos.append(slug)
print("listas:", ", ".join(hechos))
print("sin foto:", ", ".join(faltan) or "ninguna")
