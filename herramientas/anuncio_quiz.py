# -*- coding: utf-8 -*-
"""Imagen 1080x1920 para el anuncio del quiz (Stories/Reels): foto de la mano abriendo la cortina,
wordmark ROSSO en blanco arriba y la pregunta abajo. Salida: plan/anuncios/quiz-cortina-1080x1920.jpg"""
import pathlib
from PIL import Image, ImageDraw, ImageFont, ImageOps

R = pathlib.Path(__file__).resolve().parent.parent
W, H = 1080, 1920
BLANCO = (229, 232, 232)

foto = Image.open(R / "fotos_originales" / "Rosso_cortinaentrada.jpg").convert("RGB")
fw, fh = foto.size
cw = int(fh * W / H)                      # recorte 9:16 a toda la altura
cx = int(fw * 0.53)                       # centrado en la mano
x0 = max(0, min(fw - cw, cx - cw // 2))
img = foto.crop((x0, 0, x0 + cw, fh)).resize((W, H), Image.LANCZOS)

# velo oscuro arriba y abajo para que se lea el texto
velo = Image.new("L", (1, H))
for y in range(H):
    t = y / H
    v = 0
    if t < 0.22:
        v = int(150 * (1 - t / 0.22))
    elif t > 0.68:
        v = int(190 * (t - 0.68) / 0.32)
    velo.putpixel((0, y), v)
velo = velo.resize((W, H))
img = Image.composite(Image.new("RGB", (W, H), (30, 0, 8)), img, velo.point(lambda v: v))

# wordmark en blanco
from PIL import ImageChops
wm = Image.open(R / "assets" / "rosso-wordmark-cutout.png").convert("RGBA")
alpha = ImageChops.invert(wm.split()[3])     # el cutout tiene las letras como huecos
wm = Image.new("RGBA", wm.size, BLANCO + (0,))
wm.putalpha(alpha)
ww = 620
wm = wm.resize((ww, int(wm.height * ww / wm.width)), Image.LANCZOS)
img.paste(wm, ((W - ww) // 2, 150), wm)

d = ImageDraw.Draw(img)
def fuente(nombre, tam):
    for f in (nombre, "arialbd.ttf"):
        try:
            return ImageFont.truetype("C:/Windows/Fonts/" + f, tam)
        except OSError:
            continue
    return ImageFont.load_default()

def centrado(texto, y, fnt, espaciado=0, color=BLANCO):
    anchos = [d.textlength(c, font=fnt) for c in texto]
    total = sum(anchos) + espaciado * (len(texto) - 1)
    x = (W - total) / 2
    for c, a in zip(texto, anchos):
        d.text((x, y), c, font=fnt, fill=color)
        x += a + espaciado

f1 = fuente("ARIALNB.TTF", 118)
f2 = fuente("ARIALNB.TTF", 44)
f3 = fuente("ARIALN.TTF", 40)
centrado("¿QUÉ CÓCTEL", 1390, f1, 4)
centrado("ERES?", 1515, f1, 4)
centrado("CINCO PREGUNTAS. UN TRAGO CON TU NOMBRE.", 1670, f2, 3)
centrado("rossospeakeasy.com/ads", 1740, f3, 1, (200, 200, 200))

out = R / "plan" / "anuncios" / "quiz-cortina-1080x1920.jpg"
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out, quality=92)
print(out, img.size)
