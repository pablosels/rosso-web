# -*- coding: utf-8 -*-
"""Arregla la R del wordmark y rasteriza los SVG de marca a PNG (sin cairo).

- La R del archivo de Illustrator tenía un sub-trazo mal cerrado (tira de 2.5 unidades
  en la base) que dejaba una muesca visible en la esquina inferior izquierda. Aquí se
  reconstruye como cuadro + dos huecos (panza y pierna) con regla even-odd.
- Rasterizado propio: aplana curvas cúbicas y pinta polígonos con XOR (even-odd) a 4x
  y reduce con antialias. Solo entiende M/V/v/H/h/L/l/C/c/S/s/Z, que es lo que usan estos archivos.

Uso: python herramientas/logos.py   (desde la raíz del repo)
"""
import re
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageChops

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"

R_VIEJA = ("M320,414v252h82.7v-2.5c-44.3,0-80.2-35.9-80.2-80.2h164.2c24.1,0,45.8,10.3,60.9,26.8,13,14.2,21.1,32.9,21.7,53.4h0v2.5h2.5v-252h-252Z"
           "M567.4,517.2h0c-8.4,36.4-41,63.6-80,63.6h-164.8v-40.7c0-68.2,55.3-123.5,123.5-123.5h41.4c45.4,0,82.1,36.8,82.1,82.1s-.7,12.6-2.1,18.5Z")
R_NUEVA = ("M320,414h252v252h-252Z"
           "M322.5,583.3h164.2c24.1,0,45.8,10.3,60.9,26.8,13,14.2,21.1,32.9,21.7,53.4h-166.6c-44.3,0-80.2-35.9-80.2-80.2Z"
           "M567.4,517.2c-8.4,36.4-41,63.6-80,63.6h-164.8v-40.7c0-68.2,55.3-123.5,123.5-123.5h41.4c45.4,0,82.1,36.8,82.1,82.1s-.7,12.6-2.1,18.5Z")

CARMIN = (0xB4, 0x05, 0x19)
VERMOUTH = (0x28, 0x00, 0x0F)
GRIS = (0xE5, 0xE8, 0xE8)


def arreglar_r():
    n = 0
    for f in ASSETS.glob("*.svg"):
        s = f.read_text(encoding="utf-8")
        if R_VIEJA in s:
            f.write_text(s.replace(R_VIEJA, R_NUEVA), encoding="utf-8")
            n += 1
            print("R corregida en", f.name)
    return n


# ------------------------------------------------------------ parser mínimo de <path d>
_tok = re.compile(r"[MmLlHhVvCcSsZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")


def subtrazos(d, segs=24):
    """Devuelve lista de polígonos (listas de (x,y)) aplanando las curvas."""
    toks = _tok.findall(d)
    i, cmd = 0, None
    x = y = 0.0
    sx = sy = 0.0
    cx2 = cy2 = None      # último punto de control (para S/s)
    polys, cur = [], []

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    def curva(x0, y0, x1, y1, x2, y2, x3, y3):
        for k in range(1, segs + 1):
            t = k / segs
            u = 1 - t
            cur.append((u*u*u*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t*t*t*x3,
                        u*u*u*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t*t*t*y3))

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t; i += 1
            if cmd in "Zz":
                if cur:
                    polys.append(cur); cur = []
                x, y = sx, sy
                cx2 = cy2 = None
                continue
        if cmd in "Mm":
            nx, ny = num(), num()
            if cmd == "m":
                nx += x; ny += y
            if cur:
                polys.append(cur)
            cur = [(nx, ny)]
            x, y = sx, sy = nx, ny
            cmd = "L" if cmd == "M" else "l"
            cx2 = cy2 = None
        elif cmd in "Ll":
            nx, ny = num(), num()
            if cmd == "l":
                nx += x; ny += y
            x, y = nx, ny; cur.append((x, y)); cx2 = cy2 = None
        elif cmd in "Hh":
            nx = num()
            if cmd == "h":
                nx += x
            x = nx; cur.append((x, y)); cx2 = cy2 = None
        elif cmd in "Vv":
            ny = num()
            if cmd == "v":
                ny += y
            y = ny; cur.append((x, y)); cx2 = cy2 = None
        elif cmd in "Cc":
            x1, y1, x2, y2, x3, y3 = (num() for _ in range(6))
            if cmd == "c":
                x1 += x; y1 += y; x2 += x; y2 += y; x3 += x; y3 += y
            curva(x, y, x1, y1, x2, y2, x3, y3)
            cx2, cy2 = x2, y2; x, y = x3, y3
        elif cmd in "Ss":
            x2, y2, x3, y3 = (num() for _ in range(4))
            if cmd == "s":
                x2 += x; y2 += y; x3 += x; y3 += y
            x1, y1 = (2*x - cx2, 2*y - cy2) if cx2 is not None else (x, y)
            curva(x, y, x1, y1, x2, y2, x3, y3)
            cx2, cy2 = x2, y2; x, y = x3, y3
        else:
            raise ValueError(f"comando no soportado: {cmd}")
    if cur:
        polys.append(cur)
    return polys


def mascara(d, viewbox, ancho_px, escala=4):
    """Máscara 'L' (0/255) del path con regla even-odd, antialias por supermuestreo."""
    vx, vy, vw, vh = viewbox
    alto_px = round(ancho_px * vh / vw)
    W, H = ancho_px * escala, alto_px * escala
    f = W / vw
    acc = Image.new("1", (W, H), 0)
    for poly in subtrazos(d):
        if len(poly) < 3:
            continue
        capa = Image.new("1", (W, H), 0)
        ImageDraw.Draw(capa).polygon([((px - vx) * f, (py - vy) * f) for px, py in poly], fill=1)
        acc = ImageChops.logical_xor(acc, capa)
    return acc.convert("L").resize((ancho_px, alto_px), Image.LANCZOS)


def path_de(svg_texto):
    return re.search(r'd="([^"]+)"', svg_texto).group(1)


def viewbox_de(svg_texto):
    return tuple(float(v) for v in re.search(r'viewBox="([^"]+)"', svg_texto).group(1).split())


def rgba(mask, color):
    im = Image.new("RGBA", mask.size, color + (0,))
    im.putalpha(mask)
    return im


def wordmark_pngs():
    svg = (ASSETS / "rosso-wordmark.svg").read_text(encoding="utf-8")
    d, vb = path_de(svg), viewbox_de(svg)
    m = mascara(d, vb, 1800)
    rgba(m, CARMIN).save(ASSETS / "rosso-wordmark-cutout.png", optimize=True)      # rojo, letras transparentes
    fondo = Image.new("RGBA", m.size, GRIS + (255,))
    fondo.alpha_composite(rgba(m, CARMIN))
    fondo.save(ASSETS / "rosso-wordmark-solid.png", optimize=True)                # rojo sobre gris (antes)
    fondo2 = Image.new("RGBA", m.size, VERMOUTH + (255,))
    fondo2.alpha_composite(rgba(m, CARMIN))
    fondo2.save(ASSETS / "rosso-wordmark.png", optimize=True)                     # rojo sobre vino
    print("wordmark PNG:", m.size)


def favicons():
    """Favicon: cuadro carmín con el isotipo en vino. SVG + PNG 32/192/512 + apple 180."""
    svg = (ASSETS / "favicon.svg").read_text(encoding="utf-8")
    svg = svg.replace('fill="#E6E6E6"', 'fill="#28000F"')
    (ASSETS / "favicon.svg").write_text(svg, encoding="utf-8")
    # el isotipo viene con transform: translate(6 6) scale(0.0722) translate(-600 -180) en un viewBox 0 0 64 64
    d = path_de(svg)
    m_iso = mascara(d, (600, 180, 720, 720), 1040)     # icono 1040 px en un lienzo 1440 (52/64)
    for tam, nombre in ((32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icon-192.png"), (512, "icon-512.png")):
        lienzo = Image.new("RGBA", (1440, 1440), CARMIN + (255,))
        lienzo.alpha_composite(rgba(m_iso, VERMOUTH), (200, 200))   # 6/64 * 1440 = 135... se centra a ojo: (1440-1040)/2 = 200
        lienzo.resize((tam, tam), Image.LANCZOS).save(ASSETS / nombre, optimize=True)
    print("favicons listos")


def og():
    """Miniatura para compartir: foto oscurecida + wordmark recortado (las letras dejan ver la foto)."""
    foto = Image.open(ASSETS / "fotos" / "espacio_vistaconsola.jpg").convert("RGB")
    # recorte 1200x630 centrado
    w, h = foto.size
    esc = max(1200 / w, 630 / h)
    foto = foto.resize((round(w * esc), round(h * esc)), Image.LANCZOS)
    x0, y0 = (foto.width - 1200) // 2, (foto.height - 630) // 2
    foto = foto.crop((x0, y0, x0 + 1200, y0 + 630)).convert("RGBA")
    velo = Image.new("RGBA", foto.size, VERMOUTH + (150,))
    foto.alpha_composite(velo)
    marca = Image.open(ASSETS / "rosso-wordmark-cutout.png").convert("RGBA")
    mw = 880
    marca = marca.resize((mw, round(marca.height * mw / marca.width)), Image.LANCZOS)
    foto.alpha_composite(marca, ((1200 - mw) // 2, (630 - marca.height) // 2))
    foto.convert("RGB").save(ASSETS / "og.png", optimize=True)
    print("og.png listo")


if __name__ == "__main__":
    arreglar_r()
    wordmark_pngs()
    favicons()
    og()
