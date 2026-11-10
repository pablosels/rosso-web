# -*- coding: utf-8 -*-
"""Imágenes de la invitación a la noche de creadores y prensa (misma receta que anuncio_quiz.py):
  plan/invitacion/invitacion-1080x1920.jpg   para historia de Instagram o mandar por WhatsApp
  assets/invitacion-og.jpg (1200x630)        vista previa de la liga /invitacion/
Uso: python herramientas/invitacion_imagen.py [carpeta con Rosso_cortinaentrada.jpg]"""
import json
import pathlib
import sys
from PIL import Image, ImageChops, ImageDraw, ImageFont

R = pathlib.Path(__file__).resolve().parent.parent
INV = json.loads((R / "content" / "invitacion.json").read_text(encoding="utf-8"))["es"]
BLANCO = (229, 232, 232)
VELO = (30, 0, 8)

origen = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else R / "fotos_originales"
ruta = origen / "Rosso_cortinaentrada.jpg"
if not ruta.exists():
    ruta = R / "assets" / "fotos" / "cortinaentrada.jpg"
FOTO = Image.open(ruta).convert("RGB")


def fuente(nombre, tam):
    for f in (nombre, "arialbd.ttf"):
        try:
            return ImageFont.truetype("C:/Windows/Fonts/" + f, tam)
        except OSError:
            continue
    return ImageFont.load_default()


def recorte(W, H, cx, cy=0.5):
    fw, fh = FOTO.size
    if fw / fh > W / H:
        cw, ch = int(fh * W / H), fh
    else:
        cw, ch = fw, int(fw * H / W)
    x0 = max(0, min(fw - cw, int(fw * cx) - cw // 2))
    y0 = max(0, min(fh - ch, int(fh * cy) - ch // 2))
    return FOTO.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS)


def velo(img, arriba, abajo, fa=150, fb=215):
    W, H = img.size
    v = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        v.putpixel((0, y), int(fa * (1 - t / arriba)) if t < arriba else int(fb * (t - abajo) / (1 - abajo)) if t > abajo else 0)
    return Image.composite(Image.new("RGB", (W, H), VELO), img, v.resize((W, H)))


def marca(img, ancho, x, y):
    wm = Image.open(R / "assets" / "rosso-wordmark-cutout.png").convert("RGBA")
    alpha = ImageChops.invert(wm.split()[3])     # el cutout tiene las letras como huecos
    wm = Image.new("RGBA", wm.size, BLANCO + (0,))
    wm.putalpha(alpha)
    wm = wm.resize((ancho, int(wm.height * ancho / wm.width)), Image.LANCZOS)
    img.paste(wm, (x, y), wm)


def texto(d, s, x, y, fnt, esp=0, color=BLANCO):
    for c in s:
        d.text((x, y), c, font=fnt, fill=color)
        x += d.textlength(c, font=fnt) + esp


cuando = INV["cuando"].upper()
titulo = INV["titulo"].upper().split(", ")            # "TRES TRAGOS," / "A TU MEDIDA."
titulo = [titulo[0] + ",", titulo[1]] if len(titulo) == 2 else [INV["titulo"].upper()]

# historia 1080x1920: todo alineado a la izquierda, como la página
W, H, M = 1080, 1920, 84
img = velo(recorte(W, H, 0.53), 0.22, 0.56)
marca(img, 560, M, 150)
d = ImageDraw.Draw(img)
y = 1250
texto(d, INV["etiqueta"].upper(), M, y, fuente("ARIALNB.TTF", 38), 9, (214, 216, 216))
y += 86
for linea in titulo:
    texto(d, linea, M, y, fuente("ARIALNB.TTF", 146), 2)
    y += 150
y += 44
texto(d, cuando, M, y, fuente("ARIALNB.TTF", 44), 6)
texto(d, "PUEBLA 329, ROMA NORTE", M, y + 70, fuente("ARIALNB.TTF", 44), 6)
texto(d, "DETRÁS DE LA COCINA DE PAVOROSSO", M, y + 140, fuente("ARIALNB.TTF", 44), 6)
salida = R / "plan" / "invitacion" / "invitacion-1080x1920.jpg"
salida.parent.mkdir(parents=True, exist_ok=True)
img.save(salida, quality=92)
print(salida, img.size)

# vista previa de la liga 1200x630
W, H, M = 1200, 630, 64
img = velo(recorte(W, H, 0.5, 0.45), 0.3, 0.3, 120, 225)
marca(img, 300, M, 56)
d = ImageDraw.Draw(img)
y = 280
texto(d, INV["etiqueta"].upper(), M, y, fuente("ARIALNB.TTF", 26), 7, (214, 216, 216))
y += 50
for linea in titulo:
    texto(d, linea, M, y, fuente("ARIALNB.TTF", 92), 1)
    y += 94
texto(d, cuando + "  ·  ROMA NORTE", M, y + 26, fuente("ARIALNB.TTF", 30), 5)
salida = R / "assets" / "invitacion-og.jpg"
img.save(salida, quality=90)
print(salida, img.size)
