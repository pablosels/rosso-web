# -*- coding: utf-8 -*-
"""Imagen semanal 1080x1920 de "Noche fuerte" para el anuncio de Instagram.

Lee la agenda de la API (miércoles a sábado), dibuja el mismo diseño que la historia del DJ
y la guarda en plan/anuncios/noche-fuerte-semana-AAAA-MM-DD.jpg. Se corre cada lunes:

    python herramientas/imagen_noche_fuerte.py

Necesita Chrome instalado (se usa sin ventana para dibujar con las fuentes Geist) y Pillow.
"""
import json, os, subprocess, urllib.request, pathlib
from PIL import Image
API = "https://rosso-web-api-703407013960.us-central1.run.app"
REPO = pathlib.Path(__file__).resolve().parent.parent
OUT = REPO / "plan" / "anuncios"
TMP = REPO / "herramientas" / "_tmp_noche_fuerte"; TMP.mkdir(exist_ok=True)
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
ag = json.load(urllib.request.urlopen(API + "/agenda"))
noches = [n for n in ag["noches"] if n["dia"][:2] in ("mi", "ju", "vi", "sá", "sa")]
fondo = (REPO / "assets/fotos/espacio_vistaconsola-m.jpg").as_uri()
logo = (REPO / "assets/rosso-wordmark-letras.svg").as_uri()
TPL = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;700;900&family=Geist+Mono:wght@400;500&display=swap">
<style>html,body{margin:0;background:#28000F}canvas{display:block}</style></head><body>
<canvas id="c" width="1080" height="1920"></canvas>
<script>
var N = __N__;
function pinta(){
  var W=1080,H=1920,c=document.getElementById("c"),x=c.getContext("2d");
  x.fillStyle="#28000F";x.fillRect(0,0,W,H);
  var fondo=new Image(),logo=new Image(),listos=0;
  function listo(){if(++listos===2)dibuja();}
  fondo.onload=listo;fondo.onerror=function(){fondo=null;listo();};logo.onload=listo;
  function dibuja(){
    if(fondo){var e=Math.max(W/fondo.width,H/fondo.height),fw=fondo.width*e,fh=fondo.height*e;x.drawImage(fondo,(W-fw)/2,(H-fh)/2,fw,fh);
      var g=x.createLinearGradient(0,0,0,H);g.addColorStop(0,"rgba(40,0,15,.78)");g.addColorStop(.5,"rgba(40,0,15,.66)");g.addColorStop(1,"rgba(40,0,15,.92)");x.fillStyle=g;x.fillRect(0,0,W,H);}
    x.fillStyle="#B40519";x.fillRect(0,0,W,28);x.fillRect(0,H-28,W,28);
    var lw=560,lh=lw*252/1280;x.drawImage(logo,(W-lw)/2,150,lw,lh);
    x.textAlign="center";x.fillStyle="#E0364A";x.font="500 34px 'Geist Mono', monospace";
    x.fillText("E S T A   S E M A N A   E N   R O S S O",W/2,400);
    var y=520;
    N.forEach(function(n,i){
      x.fillStyle="#E0364A";x.font="500 36px 'Geist Mono', monospace";
      x.fillText((n.dia+" "+n.num+"  \u00b7  "+n.hora).toUpperCase(),W/2,y);
      x.fillStyle="#E5E8E8";x.font="900 92px Geist, Helvetica, Arial, sans-serif";
      x.fillText(n.dj.toUpperCase(),W/2,y+104);
      x.fillStyle="rgba(229,232,232,.75)";x.font="400 40px Geist, Helvetica, Arial, sans-serif";
      x.fillText(n.genero,W/2,y+160);
      if(i<N.length-1){x.fillStyle="rgba(224,54,74,.45)";x.fillRect(W/2-60,y+206,120,3);}
      y+=262;
    });
    x.fillStyle="#E5E8E8";x.font="400 38px Geist, Helvetica, Arial, sans-serif";
    x.fillText("Puebla 329, Roma Norte \u00b7 se entra por la cocina",W/2,H-330);
    x.font="500 44px 'Geist Mono', monospace";x.fillText("rossospeakeasy.com/noches",W/2,H-255);
    x.font="500 38px 'Geist Mono', monospace";x.fillStyle="rgba(229,232,232,.85)";
    x.fillText("\u2193  RESERVA TU MESA",W/2,H-180);
  }
  fondo.src="__FONDO__";logo.src="__LOGO__";
}
Promise.all([document.fonts.load("900 92px Geist"),document.fonts.load("400 40px Geist"),document.fonts.load("400 38px Geist"),document.fonts.load("500 36px 'Geist Mono'"),document.fonts.load("500 44px 'Geist Mono'"),document.fonts.load("500 34px 'Geist Mono'"),document.fonts.load("500 38px 'Geist Mono'")]).then(pinta,pinta);
</script></body></html>"""
datos = [{"dia": n["dia"], "num": n["fecha"].split("-")[2].lstrip("0"), "hora": n["hora"].replace(":00 p.m.", " pm"), "dj": n["dj"], "genero": n["genero"]} for n in noches]
sem = noches[0]["fecha"]
h = TPL.replace("__N__", json.dumps(datos, ensure_ascii=False)).replace("__FONDO__", fondo).replace("__LOGO__", logo)
hp = TMP / f"semana-{sem}.html"; hp.write_text(h, encoding="utf-8")
png = TMP / f"semana-{sem}.png"
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                "--window-size=1080,1920", "--force-device-scale-factor=1", "--virtual-time-budget=10000",
                "--no-first-run", "--no-default-browser-check", f"--user-data-dir={TMP/'perfil'}",
                f"--screenshot={png}", hp.as_uri()], capture_output=True, timeout=120)
im = Image.open(png).convert("RGB")
jpg = OUT / f"noche-fuerte-semana-{sem}.jpg"
im.save(jpg, quality=90)
print(jpg, im.size, os.path.getsize(jpg) // 1024, "KB")
