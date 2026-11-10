# -*- coding: utf-8 -*-
"""Invitación en PDF (1080x1920, una página) con botón que abre el quiz de tres tragos en /invitacion/.
Tres opciones de diseño: cortina, cabina (foto de la consola con la entrada al fondo) y azul (tipográfica).

Uso:  python herramientas/invitacion_pdf.py                      las tres, genéricas
      python herramientas/invitacion_pdf.py --para "Andrea"      personal: saludo con nombre y liga ?para=Andrea
      python herramientas/invitacion_pdf.py --fotos C:\\ruta\\fotos_originales --salida C:\\ruta
Necesita Chrome o Edge (imprime el HTML a PDF sin ventana) e internet para la tipografía Geist."""
import argparse
import html
import json
import pathlib
import subprocess
import tempfile
import unicodedata
from urllib.parse import quote

R = pathlib.Path(__file__).resolve().parent.parent
INV = json.loads((R / "content" / "invitacion.json").read_text(encoding="utf-8"))["es"]
SITE = json.loads((R / "content" / "site.json").read_text(encoding="utf-8"))
NAVEGADORES = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]

ap = argparse.ArgumentParser()
ap.add_argument("--para", default="")
ap.add_argument("--fotos", default=str(R / "fotos_originales"))
ap.add_argument("--salida", default=str(R / "plan" / "invitacion"))
ap.add_argument("--png", action="store_true", help="además, una imagen de cada opción para revisar")
a = ap.parse_args()

e = html.escape
nombre = " ".join(a.para.split())[:40]
liga = f"https://{SITE['dominio']}/invitacion/" + (f"?para={quote(nombre)}" if nombre else "") + "#inv-quiz"
saludo = INV["saludo"].replace("{nombre}", nombre) if nombre else INV["saludo_sin_nombre"]
t1, _, t2 = INV["titulo"].partition(", ")
titulo = f"{e(t1)},<br>{e(t2)}" if t2 else e(INV["titulo"])
donde1, _, donde2 = INV["donde"].partition(" · ")


TMP = tempfile.TemporaryDirectory()


def foto(original, respaldo):
    """La foto original si está (fotos_originales/ no viaja en el repo), reducida a 2000 px para que el PDF pese poco."""
    from PIL import Image
    p = pathlib.Path(a.fotos) / original
    im = Image.open(p if p.exists() else R / "assets" / "fotos" / respaldo).convert("RGB")
    im.thumbnail((2000, 2000), Image.LANCZOS)
    chica = pathlib.Path(TMP.name) / respaldo
    im.save(chica, quality=86)
    return chica.as_uri()


MARCA = (R / "assets" / "rosso-wordmark-letras.svg").as_uri()
BASE = """
@page{size:1080px 1920px;margin:0}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
html,body{margin:0;width:1080px;height:1920px;overflow:hidden}
body{position:relative;background:#28000F;color:#E5E8E8;font-family:"Geist","Helvetica Neue",Arial,sans-serif}
.mono{font-family:"Geist Mono",Consolas,monospace;font-weight:500;text-transform:uppercase;letter-spacing:.3em}
.marca{display:block;width:520px}
.blanca{filter:brightness(0) invert(.92)}
.etq{font-size:27px;opacity:.82;margin:0 0 22px}
.saludo{font-size:29px;margin:0 0 30px}
h1{margin:0 0 44px;font-weight:900;font-size:120px;line-height:.95;letter-spacing:-.015em;text-transform:uppercase;white-space:nowrap}
.ficha{font-size:27px;line-height:1.95;margin:0 0 54px}
.btn{display:inline-block;background:#B40519;color:#E5E8E8;text-decoration:none;font-size:29px;padding:38px 56px;border:2px solid #B40519}
.pie{font-size:19px;opacity:.6;margin:34px 0 0;letter-spacing:.24em}
.caja{position:absolute;left:84px;right:84px}
"""
TEXTO = f"""
  <p class="mono etq">{e(INV["etiqueta"])}</p>
  <p class="mono saludo">{e(saludo)}</p>
  <h1>{titulo}</h1>
  <p class="mono ficha">{e(INV["cuando"])}<br>{e(donde1)}<br>{e(donde2)}</p>
  <a class="mono btn" href="{e(liga)}">{e(INV["boton"])} →</a>
  <p class="mono pie">{e(INV["privada"])}</p>
"""

OPCIONES = {
    # A: la cortina a sangre, como el anuncio del quiz
    "cortina": f"""<style>{BASE}
.fondo{{position:absolute;inset:0;background:url("{foto("Rosso_cortinaentrada.jpg", "cortinaentrada.jpg")}") 53% 50%/cover}}
.velo{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(30,0,8,.6) 0%,rgba(30,0,8,0) 20%,rgba(30,0,8,0) 34%,rgba(30,0,8,.88) 62%,rgba(30,0,8,.97) 100%)}}
</style><div class="fondo"></div><div class="velo"></div>
<div class="caja" style="top:130px"><img class="marca blanca" src="{MARCA}" alt="ROSSO"></div>
<div class="caja" style="bottom:110px">{TEXTO}</div>""",

    # B: la cabina con la entrada al fondo, arriba; el texto abajo sobre vermouth
    "cabina": f"""<style>{BASE}
.foto{{position:absolute;left:0;top:0;width:1080px;height:1000px;background:url("{foto("ROSSO_Espacio_vistaConsola.jpg", "espacio_vistaconsola.jpg")}") 50% 62%/cover}}
.velo{{position:absolute;left:0;top:0;width:1080px;height:1002px;background:linear-gradient(180deg,rgba(40,0,15,.55) 0%,rgba(40,0,15,0) 26%,rgba(40,0,15,0) 78%,#28000F 100%)}}
</style><div class="foto"></div><div class="velo"></div>
<div class="caja" style="top:96px"><img class="marca blanca" src="{MARCA}" alt="ROSSO" style="width:400px"></div>
<div class="caja" style="bottom:110px">{TEXTO}</div>""",

    # C: tipográfica, azul terciopelo con carmín, como el cartel de CARLA
    "azul": f"""<style>{BASE}
body{{background:#001EB4;color:#E5E8E8}}
h1{{color:#E0364A}}
.tres{{position:absolute;left:66px;top:330px;font-weight:900;font-size:800px;line-height:.78;color:#B40519;letter-spacing:-.04em}}
</style>
<div class="tres">3</div>
<div class="caja" style="top:130px"><img class="marca" src="{MARCA}" alt="ROSSO"></div>
<div class="caja" style="bottom:110px">{TEXTO}</div>""",
}

navegador = next((n for n in NAVEGADORES if pathlib.Path(n).exists()), None)
if not navegador:
    raise SystemExit("No encontré Chrome ni Edge.")
salida = pathlib.Path(a.salida)
salida.mkdir(parents=True, exist_ok=True)
sufijo = ""
if nombre:
    sufijo = "-" + "".join(c for c in unicodedata.normalize("NFKD", nombre.lower()) if c.isalnum() or c == " ").strip().replace(" ", "-")

with tempfile.TemporaryDirectory() as tmp:
    for clave, cuerpo in OPCIONES.items():
        h = pathlib.Path(tmp) / f"{clave}.html"
        h.write_text('<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Invitación · ROSSO</title>'
                     '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;700;900&family=Geist+Mono:wght@500&display=block">'
                     f"</head><body>{cuerpo}</body></html>", encoding="utf-8")
        comun = [navegador, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=6000", f"--user-data-dir={tmp}/perfil"]
        pdf = salida / f"invitacion-rosso-{clave}{sufijo}.pdf"
        subprocess.run(comun + ["--no-pdf-header-footer", f"--print-to-pdf={pdf}", h.as_uri()], check=True, capture_output=True, timeout=90)
        print(pdf)
        if a.png:
            png = salida / f"invitacion-rosso-{clave}{sufijo}.png"
            subprocess.run(comun + ["--window-size=1080,1920", f"--screenshot={png}", h.as_uri()], check=True, capture_output=True, timeout=90)
print("Botón:", liga)
