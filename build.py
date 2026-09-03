# -*- coding: utf-8 -*-
"""Generador estático de rossospeakeasy.com.

Lee content/ (site.json, noches.json), la carta (carta_snapshot.json, que sale de
api/carta.py) y assets/, y escribe el sitio completo en docs/ (GitHub Pages).

Uso:  python build.py
      BASE=/rosso-web python build.py   (para probar en pablosels.github.io/rosso-web)
"""
import datetime as dt
import html
import json
import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).parent
CONT = RAIZ / "content"
DOCS = RAIZ / "docs"
ASSETS = RAIZ / "assets"

SITE = json.loads((CONT / "site.json").read_text(encoding="utf-8"))
if os.environ.get("BASE") is not None:
    SITE["base"] = os.environ["BASE"].rstrip("/")
NOCHES = json.loads((CONT / "noches.json").read_text(encoding="utf-8"))
CARTA = json.loads((RAIZ / "carta_snapshot.json").read_text(encoding="utf-8"))
B = SITE["base"]
URL = "https://" + SITE["dominio"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

e = html.escape


def fecha_larga(iso):
    d = dt.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def wa(texto):
    from urllib.parse import quote
    return f"https://wa.me/{SITE['whatsapp']}?text={quote(texto)}"


# ---------------------------------------------------------------- plantilla
NAV = [("Carta", "/carta/"), ("Noches", "/noches/"), ("Eventos", "/eventos/"), ("Reservar", "/reservar/")]


def pagina(titulo, cuerpo, ruta, descripcion=None, clase="", extra_head="", script=""):
    descripcion = descripcion or SITE["descripcion"]
    canon = URL + ruta
    nav = "".join(
        f'<a href="{B}{href}"{" class=activo" if ruta == href else ""}>{e(t)}</a>' for t, href in NAV)
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "BarOrPub", "name": SITE["nombre_largo"],
        "url": URL, "telephone": "+" + SITE["whatsapp"], "servesCuisine": "Cocktails",
        "address": {"@type": "PostalAddress", "streetAddress": "Puebla 329", "addressLocality": "Ciudad de México",
                    "addressRegion": "CDMX", "postalCode": "06700", "addressCountry": "MX"},
        "acceptsReservations": SITE["opentable_url"], "menu": URL + "/carta/",
        "sameAs": [f"https://www.instagram.com/{SITE['instagram']}/", SITE["opentable_url"]],
        "openingHoursSpecification": [
            {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
             "opens": "18:00", "closes": "02:00"},
            {"@type": "OpeningHoursSpecification", "dayOfWeek": "Sunday", "opens": "16:00", "closes": "23:00"}],
    }, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<link rel="canonical" href="{canon}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descripcion)}">
<meta property="og:image" content="{URL}/assets/og.png">
<meta property="og:type" content="website">
<meta property="og:locale" content="es_MX">
<meta name="theme-color" content="#28000F">
<link rel="icon" href="{B}/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;700;900&family=Geist+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{B}/assets/style.css">
<script type="application/ld+json">{jsonld}</script>
{extra_head}
</head>
<body class="{clase}" data-api="{e(SITE['api'])}" data-base="{B}">
<a class="salto" href="#contenido">Ir al contenido</a>
<header class="cabecera">
  <a class="marca" href="{B}/" aria-label="ROSSO, inicio"><img src="{B}/assets/rosso-wordmark-letras.svg" alt="ROSSO" width="1280" height="252"></a>
  <button class="menu-btn" aria-expanded="false" aria-controls="nav">Menú</button>
  <nav id="nav" class="nav">{nav}</nav>
</header>
<main id="contenido">
{cuerpo}
</main>
<footer class="pie">
  <div class="pie-col">
    <div class="etiqueta">Dónde</div>
    <p><a href="{SITE['maps']}">{e(SITE['direccion'])}<br>{e(SITE['ciudad'])}</a></p>
  </div>
  <div class="pie-col">
    <div class="etiqueta">Cuándo</div>
    <p>{"<br>".join(f"{e(a)} · {e(b)}" for a, b in SITE['horario'])}</p>
  </div>
  <div class="pie-col">
    <div class="etiqueta">Contacto</div>
    <p><a href="{wa('Hola, ROSSO.')}">WhatsApp {e(SITE['whatsapp_bonito'])}</a><br><a href="https://www.instagram.com/{SITE['instagram']}/">@{SITE['instagram']}</a></p>
  </div>
  <div class="pie-col pie-legal">
    <p>Reservaciones hasta {SITE['max_widget']} personas por <a href="{SITE['opentable_url']}">OpenTable</a>. Grupos y eventos por WhatsApp.</p>
    <p class="mini">© {dt.date.today().year} Rosso Speakeasy · Puebla 329, Roma Norte, CDMX</p>
  </div>
</footer>
<script src="{B}/assets/site.js" defer></script>
{script}
</body>
</html>"""


# ---------------------------------------------------------------- carta
def render_items(items):
    out = []
    for it in items:
        desc = f'<span class="desc">{e(it["descripcion"])}</span>' if it.get("descripcion") else ""
        out.append(f'<li><span class="nombre">{e(it["nombre"])}{desc}</span><span class="puntos" aria-hidden="true"></span>'
                   f'<span class="precio">{it["precio"]:,}</span></li>')
    return "\n".join(out)


def render_carta(carta):
    bloques = []
    for s in carta["secciones"]:
        inner = ""
        if s["items"]:
            inner += f'<ul class="items">{render_items(s["items"])}</ul>'
        for sub in s.get("subsecciones", []):
            inner += f'<h3 class="sub">{e(sub["titulo"])}</h3><ul class="items">{render_items(sub["items"])}</ul>'
        bloques.append(f'<section class="bloque" id="{e(slug(s["titulo"]))}"><h2>{e(s["titulo"])}</h2>{inner}</section>')
    return "\n".join(bloques)


def slug(t):
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def fecha_carta(carta):
    try:
        d = dt.datetime.fromisoformat(carta["generada"])
        return f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    except Exception:
        return ""

def img(nombre, alt, sizes="(max-width: 760px) 100vw, 60vw", lazy=True):
    return (f'<img src="{B}/assets/fotos/{nombre}.jpg" '
            f'srcset="{B}/assets/fotos/{nombre}-m.jpg 900w, {B}/assets/fotos/{nombre}.jpg 1800w" '
            f'sizes="{sizes}" alt="{e(alt)}"{" loading=lazy decoding=async" if lazy else ""}>')


def pie(texto):
    return f'<figcaption class="pie-foto">{e(texto)}</figcaption>' if texto else ""


def cine(nombre, alt, caption="", pos="50% 50%"):
    """Foto a sangre completa, formato cine, con pie en mono."""
    return (f'<figure class="cine"><div class="cine-img" style="--pos:{pos}">{img(nombre, alt, "100vw")}</div>{pie(caption)}</figure>')


def mosaico(a, b_, c):
    """Composicion asimetrica: A grande vertical, B desplazada a la derecha, C chica abajo."""
    return ('<section class="mosaico" aria-label="ROSSO por dentro">'
            f'<figure class="m-a">{img(a[0], a[1], "(max-width: 760px) 100vw, 50vw")}{pie(a[2])}</figure>'
            f'<figure class="m-b">{img(b_[0], b_[1], "(max-width: 760px) 60vw, 30vw")}{pie(b_[2])}</figure>'
            f'<figure class="m-c">{img(c[0], c[1], "(max-width: 760px) 70vw, 28vw")}{pie(c[2])}</figure>'
            '</section>')


def dupla(grande, chica, pos="50% 50%"):
    """Una foto ancha con otra chica encimada en la esquina."""
    return ('<section class="dupla">'
            f'<figure class="d-grande" style="--pos:{pos}">{img(grande[0], grande[1], "(max-width: 760px) 100vw, 80vw")}{pie(grande[2])}</figure>'
            f'<figure class="d-chica">{img(chica[0], chica[1], "(max-width: 760px) 40vw, 22vw")}{pie(chica[2])}</figure>'
            '</section>')


def foto(nombre, alt, clase="", lazy=True):
    """<figure> con srcset (900/1800 px) desde assets/fotos/."""
    return (f'<figure class="foto {clase}"><img src="{B}/assets/fotos/{nombre}.jpg" '
            f'srcset="{B}/assets/fotos/{nombre}-m.jpg 900w, {B}/assets/fotos/{nombre}.jpg 1800w" '
            f'sizes="(max-width: 760px) 100vw, 60vw" alt="{e(alt)}"{" loading=lazy decoding=async" if lazy else ""}></figure>')


# ---------------------------------------------------------------- páginas
def pag_inicio():
    top = [it for s in CARTA["secciones"] if s["titulo"] == "Cócteles de la casa" for it in s["items"]][:6]
    series = "".join(
        f'<li><span class="dia">{e(n["dia"])}</span><span class="que"><strong>{e(n["titulo"])}</strong> · {e(n["hora"])}</span></li>'
        for n in NOCHES["series"])
    cuerpo = f"""
<section class="hero">
  <div class="hero-marca"><img src="{B}/assets/rosso-wordmark.svg" alt="ROSSO" width="586" height="121" fetchpriority="high"></div>
  <div class="hero-ficha">
    <div class="ficha-l">PUEBLA, 329<br>ROMA NTE.<br>( CDMX )</div>
    <div class="ficha-r">SPEAKEASY<br>MAR – DOM<br>DESDE 6 PM</div>
  </div>
  <p class="hero-texto">Un bar que explora el placer a través de los sentidos. Escondido dentro de Pavorosso, se entra por la cocina: ahí empieza una experiencia íntima e inmersiva.</p>
  <p class="hero-texto hero-texto-2">Inspirado en el rojo como símbolo del deseo, ROSSO envuelve a sus invitados con atmósfera, música y ritmo.</p>
  <div class="hero-cta">
    <a class="btn" href="{B}/reservar/">Reservar mesa</a>
    <a class="btn btn-linea" href="{B}/carta/">Ver la carta</a>
  </div>
</section>

{cine("espacio_vistaconsola", "La consola de DJ de ROSSO bajo el techo de luces circulares", "La consola · Puebla 329, detrás de la cocina", "50% 72%")}

<section class="franja">
  <div class="franja-col">
    <div class="etiqueta">Esta semana</div>
    <ul class="series agenda-vacia">{series}</ul>
    <div data-agenda="6" hidden></div>
    <a class="enlace" href="{B}/noches/">Todas las noches</a>
  </div>
  <div class="franja-col">
    <div class="etiqueta">De la casa</div>
    <ul class="items items-claros">{render_items(top)}</ul>
    <a class="enlace" href="{B}/carta/">Carta completa</a>
  </div>
</section>

{mosaico(("espacio_corner", "Sillón curvo rojo con mesas de cóctel", "El sillón"),
          ("coctel_queridodiario", "Querido Diario, cóctel de la casa, servido en la barra", "Querido Diario"),
          ("voyeur", "Invitados brindando en el sillón", "Sábado, 1 am"))}

<section class="bloque-eventos">
  <div class="etiqueta">Eventos privados</div>
  <h2>La casa entera, para ustedes.</h2>
  <p>Cenas de cumpleaños, lanzamientos, afters. Hasta {SITE['aforo_total']} personas entre sentadas y de pie, barra completa y equipo dedicado. Cotizamos según la fecha.</p>
  <a class="btn btn-linea" href="{B}/eventos/">Cotizar un evento</a>
</section>
"""
    return pagina("ROSSO · Speakeasy en Roma Norte", cuerpo, "/", clase="inicio")


def pag_carta():
    cuerpo = f"""
<section class="encabezado claro">
  <div class="etiqueta">La carta</div>
  <h1>Cócteles de la casa, clásicos y algo para picar.</h1>
  <p class="nota" id="carta-nota">Precios en pesos, IVA incluido. Actualizada desde nuestro punto de venta el {e(fecha_carta(CARTA))}.</p>
</section>
{dupla(("barra_picarilla", "Picarilla, cóctel de la casa, sobre la barra bajo el techo de luces", "Picarilla · cóctel de la casa"),
        ("coctel_loriginedumonde", "L'Origine du Monde, martini de la casa", "L'Origine du Monde"), "50% 62%")}
<div class="carta claro" id="carta">
{render_carta(CARTA)}
</div>
{cine("coctel_kamazotz", "Camasotz, cóctel de la casa en copa coupe sobre la barra", "Camasotz · cóctel de la casa", "50% 55%")}
"""
    return pagina("Carta · ROSSO", cuerpo, "/carta/",
                  "La carta de ROSSO: cócteles de la casa, clásicos, destilados, sin alcohol y botanas. Precios actualizados desde el punto de venta.",
                  clase="pag-carta")


def pag_noches():
    series = "".join(f"""
<article class="noche">
  <div class="noche-dia">{e(n['dia'])}</div>
  <h2>{e(n['titulo'])}</h2>
  <div class="noche-hora">{e(n['hora'])}</div>
  <p>{e(n['texto'])}</p>
</article>""" for n in NOCHES["series"])
    hoy = dt.date.today().isoformat()
    fechas = [f for f in NOCHES.get("fechas", []) if f["fecha"] >= hoy]
    lista = ""
    if fechas:
        lista = '<div class="etiqueta">Próximas fechas</div><ul class="fechas">' + "".join(
            f'<li><span class="f">{e(fecha_larga(f["fecha"]))}</span><span class="t"><strong>{e(f["titulo"])}</strong>'
            + (f' · {e(f["texto"])}' if f.get("texto") else "")
            + (f' <a class="enlace" href="{e(f["link"])}">{e(f.get("link_texto", "Preventa"))}</a>' if f.get("link") else "")
            + '</span></li>' for f in sorted(fechas, key=lambda x: x["fecha"])) + "</ul>"
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Noches</div>
  <h1>Lo que pasa cada semana en ROSSO.</h1>
</section>
{cine("espacio_vistaconsola", "La consola de DJ de ROSSO bajo el techo de luces", "Miércoles a sábado · sesiones de DJ · 9 pm – 1 am", "50% 72%")}
<section class="noches">{series}</section>
<section class="fechas-sec">
  <div class="etiqueta">Quién toca</div>
  <p class="agenda-vacia nota">La programación de la semana se publica cada lunes. Síguenos en <a href="https://www.instagram.com/{SITE['instagram']}/">@{SITE['instagram']}</a>.</p>
  <div data-agenda="21" hidden></div>
  {lista}
  <p class="nota">Para las noches con música la mesa se reserva igual: hasta {SITE['max_widget']} personas <a href="{B}/reservar/">por OpenTable</a>, grupos por <a href="{wa('Hola, ROSSO. Quiero reservar para un grupo.')}">WhatsApp</a>.</p>
</section>
"""
    return pagina("Noches · ROSSO", cuerpo, "/noches/", "Jazz en vivo los miércoles, DJ de jueves a sábado y la carta de domingo en ROSSO, Roma Norte.")


def pag_reservar():
    rid = SITE["opentable_rid"]
    hoy = dt.date.today().isoformat()
    slots = []
    for h, m in [(h, m) for h in range(18, 24) for m in (0, 30)] + [(0, 0), (0, 30), (1, 0)]:
        val = f"{h:02d}:{m:02d}"
        h12 = h % 12 or 12
        etiqueta = f"{h12}:{m:02d} {'pm' if h >= 12 else 'am'}"
        slots.append(f'<option value="{val}"{" selected" if val == "20:00" else ""}>{etiqueta}</option>')
    horas = "".join(slots)
    personas = "".join(f'<option value="{n}"{" selected" if n == 2 else ""}>{n} {"persona" if n == 1 else "personas"}</option>'
                       for n in range(1, SITE["max_widget"] + 1))
    widget = (f"//www.opentable.com.mx/widget/reservation/loader?rid={rid}&type=standard&theme=standard&iframe=true"
              f"&domain=commx&lang=es-MX&newtab=false&ot_source=Restaurant%20website")
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Reservar</div>
  <h1>Mesas hasta {SITE['max_widget']} personas, aquí mismo.</h1>
  <p class="nota">Elige fecha, hora y personas. La confirmación llega al instante por OpenTable, sin costo.</p>
</section>
{cine("espacio_01", "Interior de ROSSO: sillones rojos, luz azul al fondo y techo de círculos", "32 lugares · mesas hasta 4 personas", "50% 60%")}
<section class="reserva">
  <div class="widget-caja">
    <form class="reserva-forma" id="forma-reserva" action="{SITE['opentable_url']}" method="get" target="_blank" rel="noopener">
      <div class="campo"><label for="r-fecha">Fecha</label><input id="r-fecha" name="fecha" type="date" required min="{hoy}" value="{hoy}"></div>
      <div class="fila">
        <div class="campo"><label for="r-hora">Hora</label><select id="r-hora" name="hora">{horas}</select></div>
        <div class="campo"><label for="r-personas">Personas</label><select id="r-personas" name="personas">{personas}</select></div>
      </div>
      <button class="btn" type="submit">Buscar mesa en OpenTable</button>
      <p class="reserva-nota">Se abre OpenTable con tu selección; ahí confirmas con tu tarjeta. Para más de {SITE['max_widget']} personas, escríbenos por WhatsApp.</p>
    </form>
  </div>
  <aside class="reserva-lado">
    <div class="etiqueta">5 personas o más</div>
    <p>Los grupos los llevamos directo por WhatsApp para acomodarlos bien y, si hace falta, apartarles un área.</p>
    <a class="btn" href="{wa('Hola, ROSSO. Quiero reservar para un grupo de ')}">Escribir por WhatsApp</a>
    <div class="etiqueta" style="margin-top:2.5rem">Horario</div>
    <p>{"<br>".join(f"{e(a)} · {e(b)}" for a, b in SITE['horario'])}</p>
    <div class="etiqueta" style="margin-top:2.5rem">Antes de venir</div>
    <p>Toda reservación se garantiza con tarjeta. Puedes cancelar o modificar hasta las 2:30 pm del mismo día; después de esa hora, o si no llegan, se cobran $250 MXN por persona.</p>
    <p>Te guardamos la mesa 15 minutos. No se permiten reservaciones múltiples ni juntar mesas. La cocina cierra a las {SITE['cocina_cierra']}.</p>
  </aside>
</section>
"""
    return pagina("Reservar · ROSSO", cuerpo, "/reservar/", "Reserva tu mesa en ROSSO, Roma Norte: hasta 4 personas por OpenTable, grupos por WhatsApp.", clase="pag-reservar")


def pag_eventos():
    hoy = dt.date.today()
    minimo = (hoy + dt.timedelta(days=1)).isoformat()
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Eventos privados</div>
  <h1>Cerramos la puerta y la casa es de ustedes.</h1>
  <p class="nota">Cumpleaños, cenas de equipo, lanzamientos, afters. Cuéntanos la fecha y cuántos son; te mandamos una propuesta por WhatsApp en menos de 24 horas.</p>
</section>
{dupla(("cortinaentrada", "La cortina roja de la entrada a ROSSO", "La entrada, por la cocina de Pavorosso"),
        ("shake_barra", "Bartender agitando un cóctel bajo el techo de luces", "La barra, para ustedes"), "50% 50%")}
<section class="eventos">
  <div class="eventos-datos">
    <dl class="ficha">
      <dt>Aforo</dt><dd>{SITE['aforo_sentados']} sentados · hasta {SITE['aforo_total']} de pie</dd>
      <dt>Barra</dt><dd>Carta completa, barra libre o cóctel de bienvenida</dd>
      <dt>Cocina</dt><dd>Botanas para compartir hasta las {SITE['cocina_cierra']}</dd>
      <dt>Formato</dt><dd>Área reservada con ROSSO abierto, o exclusiva total</dd>
      <dt>Música</dt><dd>DJ de la casa o el suyo; audio incluido</dd>
    </dl>
    <p class="nota">Si son entre 5 y 8 y sólo quieren mesa, mejor <a href="{wa('Hola, ROSSO. Quiero reservar para un grupo.')}">escríbenos por WhatsApp</a>.</p>
  </div>
  <form class="forma" id="forma-eventos" novalidate>
    <div class="campo"><label for="nombre">Nombre</label><input id="nombre" name="nombre" required maxlength="80" autocomplete="name"></div>
    <div class="campo"><label for="whatsapp">WhatsApp</label><input id="whatsapp" name="whatsapp" required inputmode="tel" autocomplete="tel" placeholder="55 1234 5678"></div>
    <div class="campo"><label for="email">Correo <span>(opcional)</span></label><input id="email" name="email" type="email" autocomplete="email"></div>
    <div class="fila">
      <div class="campo"><label for="fecha">Fecha</label><input id="fecha" name="fecha" type="date" required min="{minimo}"></div>
      <div class="campo"><label for="hora">Hora de inicio</label><input id="hora" name="hora" placeholder="8:00 pm" required></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="personas">Personas</label><input id="personas" name="personas" type="number" min="5" max="80" required></div>
      <div class="campo"><label for="horas">Duración</label><select id="horas" name="horas"><option value="3">3 horas</option><option value="4">4 horas</option><option value="5" selected>5 horas</option><option value="6">6 horas</option><option value="7">7 horas</option></select></div>
    </div>
    <div class="campo"><label for="tipo">Formato</label><select id="tipo" name="tipo"><option value="no-se">No sé todavía</option><option value="grupo">Área reservada, ROSSO abierto</option><option value="exclusiva">Exclusiva, ROSSO cerrado para nosotros</option></select></div>
    <div class="campo"><label for="motivo">Motivo <span>(opcional)</span></label><input id="motivo" name="motivo" maxlength="60" placeholder="Cumpleaños, cena de equipo, after…"></div>
    <div class="campo"><label for="mensaje">Algo más <span>(opcional)</span></label><textarea id="mensaje" name="mensaje" rows="3" maxlength="1000"></textarea></div>
    <div class="campo"><label for="idioma">Idioma de la propuesta</label><select id="idioma" name="idioma"><option value="es">Español</option><option value="en">English</option></select></div>
    <div class="campo miel" aria-hidden="true"><label for="empresa_web">Sitio web</label><input id="empresa_web" name="empresa_web" tabindex="-1" autocomplete="off"></div>
    <button class="btn" type="submit">Pedir propuesta</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina("Eventos privados · ROSSO", cuerpo, "/eventos/", "Renta ROSSO para tu evento privado en Roma Norte: hasta 50 personas, barra completa, propuesta en 24 horas.", clase="pag-eventos")


def pag_404():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">404</div>
  <h1>Esa puerta no existe.</h1>
  <p class="nota"><a class="enlace" href="{B}/">Volver a ROSSO</a></p>
</section>"""
    return pagina("No encontrado · ROSSO", cuerpo, "/404.html")


# ---------------------------------------------------------------- assets
def og_image():
    from PIL import Image
    fondo = Image.new("RGBA", (1200, 630), (0x28, 0x00, 0x0F, 255))
    marca = Image.open(ASSETS / "rosso-wordmark-solid.png").convert("RGBA")
    w = 900
    h = int(marca.height * w / marca.width)
    marca = marca.resize((w, h), Image.LANCZOS)
    fondo.alpha_composite(marca, ((1200 - w) // 2, (630 - h) // 2))
    fondo.convert("RGB").save(DOCS / "assets" / "og.png", optimize=True)


def main():
    if DOCS.exists():
        shutil.rmtree(DOCS)
    (DOCS / "assets").mkdir(parents=True)
    for f in ASSETS.iterdir():
        if f.is_file():
            shutil.copy(f, DOCS / "assets" / f.name)
        elif f.is_dir():
            shutil.copytree(f, DOCS / "assets" / f.name)
    og_image()

    paginas = {"index.html": pag_inicio(), "carta/index.html": pag_carta(), "noches/index.html": pag_noches(),
               "reservar/index.html": pag_reservar(), "eventos/index.html": pag_eventos(), "404.html": pag_404()}
    for ruta, contenido in paginas.items():
        destino = DOCS / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(contenido, encoding="utf-8")

    # ligas cortas por canal: /ig, /qr, /google... -> destino con ?de=<canal>
    canales = json.loads((CONT / "canales.json").read_text(encoding="utf-8"))
    for clave, c in canales.items():
        if clave.startswith("_"):
            continue
        destino = f"{B}{c['destino']}?de={clave}"
        (DOCS / clave).mkdir(parents=True, exist_ok=True)
        (DOCS / clave / "index.html").write_text(
            f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>ROSSO</title>'
            f'<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0;url={destino}">'
            f'<script>location.replace("{destino}")</script></head>'
            f'<body style="background:#28000F;color:#E6E6E6;font-family:sans-serif;padding:2rem">'
            f'<a href="{destino}" style="color:#E6E6E6">Entrar a ROSSO</a></body></html>', encoding="utf-8")

    (DOCS / "carta.json").write_text(json.dumps(CARTA, ensure_ascii=False), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")
    (DOCS / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {URL}/sitemap.xml\n")
    urls = ["/", "/carta/", "/noches/", "/reservar/", "/eventos/"]
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{URL}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    if SITE.get("cname"):
        (DOCS / "CNAME").write_text(SITE["dominio"] + "\n")
    print(f"docs/ generado: {len(paginas)} páginas, base='{B}', api='{SITE['api'] or '(sin API, sólo snapshot)'}'")


if __name__ == "__main__":
    main()
