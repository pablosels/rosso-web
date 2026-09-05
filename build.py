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


def version_de(nombre):
    """Hash corto del archivo para romper caché (style.css?v=abc123)."""
    import hashlib
    p = ASSETS / nombre
    return hashlib.md5(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"


V_CSS = version_de("style.css")
V_JS = version_de("site.js")


def fecha_larga(iso):
    d = dt.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def wa(texto):
    from urllib.parse import quote
    return f"https://wa.me/{SITE['whatsapp']}?text={quote(texto)}"


# ---------------------------------------------------------------- plantilla
NAV = [("Carta", "/carta/"), ("Noches", "/noches/"), ("Eventos", "/eventos/"), ("Reservar", "/reservar/")]
if SITE.get("regalo_activo"):
    NAV.append(("Regalo", "/regalo/"))


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
<link rel="icon" href="{B}/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{B}/assets/apple-touch-icon.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;700;900&family=Geist+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{B}/assets/style.css?v={V_CSS}">
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
    <p class="mini">© {dt.date.today().year} Rosso Speakeasy · Puebla 329, Roma Norte, CDMX · <a href="{B}/producciones/">Locación</a> · <a href="{B}/club/">Club ROSSO</a> · <a href="{B}/privacidad/">Privacidad</a></p>
  </div>
</footer>
<script src="{B}/assets/site.js?v={V_JS}" defer></script>
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
  <p class="hero-texto">Un bar que explora el placer a través de los sentidos. Una experiencia íntima e inmersiva que se esconde detrás de la cocina de Pavorosso.</p>
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
    <p class="nota">¿Es una producción de foto o video? Ve a <a href="{B}/producciones/">locación</a>.</p>
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


# ---------------------------------------------------------------- tarjetas de regalo
def pag_regalo():
    montos = SITE.get("regalo_montos", [500, 1000, 2000, 3000])
    notas = {500: "Dos cócteles y algo de picar", 1000: "Una noche para dos", 2000: "La cuenta de una mesa", 3000: "Una celebración"}
    opciones = "".join(
        f'<label class="monto"><input type="radio" name="monto" value="{m}"{" checked" if i == 1 else ""}>'
        f'<span class="monto-cifra">${m:,}</span><span class="monto-nota">{notas.get(m, "")}</span></label>'
        for i, m in enumerate(montos))
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Tarjeta de regalo</div>
  <h1>Regala una noche en ROSSO.</h1>
  <p class="nota">Eliges el monto, escribes a quién va y pagas en línea. El código aparece al instante y se canjea en barra: cócteles, botanas o la cuenta completa. Vale 12 meses y el saldo que sobre se queda para la siguiente visita.</p>
</section>
{cine("coctel_queridodiario", "Cóctel Querido Diario sobre la barra de ROSSO", "Querido Diario, uno de la casa", "50% 60%")}
<section class="regalo" id="regalo">
  <div class="regalo-pasos">
    <ol class="pasos">
      <li><strong>Eliges y pagas.</strong> Tarjeta de crédito o débito, cobro seguro con Stripe.</li>
      <li><strong>Recibes el código.</strong> En pantalla al terminar, con una tarjeta para compartir o imprimir.</li>
      <li><strong>Se canjea en barra.</strong> Quien lo reciba dicta el código y se descuenta de su cuenta.</li>
    </ol>
    <p class="nota mini">Vigencia de 12 meses desde la compra. No es canjeable por efectivo. Para más de 4 personas o eventos, <a href="{B}/eventos/">ver eventos privados</a>.</p>
  </div>
  <form class="forma" id="forma-regalo" novalidate>
    <fieldset class="montos"><legend>Monto</legend>{opciones}</fieldset>
    <div class="fila">
      <div class="campo"><label for="g-de">De parte de</label><input id="g-de" name="de" maxlength="80" autocomplete="name" required></div>
      <div class="campo"><label for="g-para">Para</label><input id="g-para" name="para" maxlength="80" required></div>
    </div>
    <div class="campo"><label for="g-mensaje">Mensaje <span>(opcional, va en la tarjeta)</span></label><textarea id="g-mensaje" name="mensaje" rows="2" maxlength="200"></textarea></div>
    <div class="campo"><label for="g-email">Tu correo <span>(para el recibo)</span></label><input id="g-email" name="email" type="email" autocomplete="email" required></div>
    <button class="btn" type="submit" id="g-pagar">Pagar $1,000</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina("Tarjeta de regalo · ROSSO", cuerpo, "/regalo/", "Regala una noche en ROSSO: tarjeta de regalo canjeable en barra, pago en línea, código al instante, vigencia de 12 meses.", clase="pag-regalo")


def pag_regalo_gracias():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Tarjeta de regalo</div>
  <h1 id="g-titulo">Confirmando tu pago…</h1>
  <p class="nota" id="g-nota">Un momento, estamos generando tu código.</p>
</section>
<section class="regalo-resultado" id="g-resultado" hidden>
  <div class="codigo-caja">
    <div class="etiqueta">Código</div>
    <div class="codigo" id="g-codigo">ROSSO-····-····</div>
    <div class="codigo-datos" id="g-datos"></div>
    <div class="codigo-acciones">
      <button class="btn" type="button" id="g-copiar">Copiar código</button>
      <a class="btn btn-linea" id="g-ver" href="#">Ver la tarjeta</a>
      <a class="btn btn-linea" id="g-wa" href="#" rel="noopener">Enviar por WhatsApp</a>
    </div>
  </div>
  <p class="nota mini">Guarda este código: es lo único que se necesita en barra. También te llegó el recibo de Stripe al correo que pusiste.</p>
</section>
"""
    return pagina("Gracias · ROSSO", cuerpo, "/regalo/gracias/", "Tu tarjeta de regalo de ROSSO.", clase="pag-regalo", extra_head='<meta name="robots" content="noindex">')


def pag_regalo_tarjeta():
    cuerpo = f"""
<section class="tarjeta-envoltura">
  <article class="tarjeta" id="tarjeta">
    <img class="tarjeta-marca" src="{B}/assets/rosso-wordmark-letras.svg" alt="ROSSO" width="1280" height="252">
    <div class="tarjeta-tipo">Tarjeta de regalo</div>
    <div class="tarjeta-monto" id="t-monto">$ —</div>
    <div class="tarjeta-para" id="t-para"></div>
    <p class="tarjeta-mensaje" id="t-mensaje"></p>
    <div class="tarjeta-codigo" id="t-codigo">—</div>
    <div class="tarjeta-pie"><span id="t-vence"></span><span>Canjeable en barra · Puebla 329, Roma Norte</span></div>
  </article>
  <p class="nota mini tarjeta-nota" id="t-nota">Abre esta página desde la liga de tu tarjeta.</p>
  <p class="tarjeta-acciones"><button class="btn" type="button" onclick="window.print()">Imprimir o guardar en PDF</button></p>
</section>
"""
    return pagina("Tu tarjeta · ROSSO", cuerpo, "/regalo/tarjeta/", "Tarjeta de regalo de ROSSO.", clase="pag-regalo pag-tarjeta", extra_head='<meta name="robots" content="noindex">')


def pag_regalo_canje():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Barra · uso interno</div>
  <h1>Canje de tarjetas.</h1>
  <p class="nota">Escribe el código que dicta el cliente. Si tiene saldo, pon el monto de la cuenta y el PIN de la barra.</p>
</section>
<section class="canje">
  <form class="forma" id="forma-canje-buscar" novalidate>
    <div class="campo"><label for="c-codigo">Código</label><input id="c-codigo" name="codigo" placeholder="ROSSO-XXXX-XXXX" autocomplete="off" autocapitalize="characters" maxlength="16"></div>
    <button class="btn" type="submit">Consultar</button>
  </form>
  <div class="canje-tarjeta" id="c-info" hidden></div>
  <form class="forma" id="forma-canje" novalidate hidden>
    <div class="fila">
      <div class="campo"><label for="c-monto">Monto a descontar</label><input id="c-monto" name="monto" type="number" inputmode="numeric" min="1" step="1"></div>
      <div class="campo"><label for="c-pin">PIN de barra</label><input id="c-pin" name="pin" type="password" inputmode="numeric" autocomplete="off" maxlength="8"></div>
    </div>
    <button class="btn" type="submit">Descontar</button>
  </form>
  <p class="forma-msg" id="forma-msg" role="status"></p>
</section>
"""
    return pagina("Canje · ROSSO", cuerpo, "/regalo/canje/", "Uso interno.", clase="pag-regalo", extra_head='<meta name="robots" content="noindex,nofollow">')


# ---------------------------------------------------------------- club ROSSO y privacidad
def pag_club():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Club ROSSO</div>
  <h1>Los de la casa se enteran primero.</h1>
  <p class="nota">Déjanos tu WhatsApp y te avisamos de las noches especiales, los DJs invitados y lo nuevo de la carta. Si nos dices cuándo cumples años, la casa invita un cóctel esa semana.</p>
</section>
{cine("espacio_corner", "Rincón de ROSSO con luz roja y sillones", "El rincón, para quedarse", "50% 50%")}
<section class="club">
  <form class="forma" id="forma-club" novalidate>
    <div class="campo"><label for="k-nombre">Nombre</label><input id="k-nombre" name="nombre" required maxlength="80" autocomplete="name"></div>
    <div class="campo"><label for="k-whatsapp">WhatsApp</label><input id="k-whatsapp" name="whatsapp" required inputmode="tel" autocomplete="tel" placeholder="55 1234 5678"></div>
    <div class="fila">
      <div class="campo"><label for="k-email">Correo <span>(opcional)</span></label><input id="k-email" name="email" type="email" autocomplete="email"></div>
      <div class="campo"><label for="k-cumple">Cumpleaños <span>(día/mes, opcional)</span></label><input id="k-cumple" name="cumple" placeholder="14/02" inputmode="numeric" maxlength="10"></div>
    </div>
    <label class="acepto"><input type="checkbox" name="acepto" value="1"> <span>Acepto el <a href="{B}/privacidad/">aviso de privacidad</a>. Solo mensajes de ROSSO, nunca más de dos al mes, y me puedo dar de baja cuando quiera.</span></label>
    <div class="campo miel" aria-hidden="true"><label for="empresa_web">Sitio web</label><input id="empresa_web" name="empresa_web" tabindex="-1" autocomplete="off"></div>
    <button class="btn" type="submit">Unirme</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina("Club ROSSO", cuerpo, "/club/", "Únete al Club ROSSO: noches especiales, DJs invitados y un cóctel de cumpleaños por cuenta de la casa.", clase="pag-club")


def pag_privacidad():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Aviso de privacidad</div>
  <h1>Qué hacemos con tus datos.</h1>
  <p class="nota">Versión corta: solo los usamos para escribirte de ROSSO. No los vendemos ni los compartimos.</p>
</section>
<section class="legal">
  <p><strong>Responsable.</strong> {e(SITE.get('razon_social', SITE['nombre_largo']))}, con domicilio en Puebla 329, Roma Norte, 06700, Ciudad de México, es responsable del tratamiento de tus datos personales conforme a la Ley Federal de Protección de Datos Personales en Posesión de los Particulares.</p>
  <p><strong>Datos que recabamos.</strong> Nombre, número de WhatsApp y, si nos los das, correo electrónico y fecha de cumpleaños (día y mes). Al reservar o cotizar un evento, también la fecha, hora y número de personas.</p>
  <p><strong>Para qué.</strong> Para avisarte de noches especiales, DJs invitados y novedades de la carta; para invitarte un cóctel en tu cumpleaños; para atender tu reservación o cotización; y para medir de dónde llegan nuestras visitas, sin identificarte. No usamos tus datos para ningún otro fin.</p>
  <p><strong>Cuántos mensajes.</strong> No más de dos al mes. Puedes darte de baja en cualquier momento contestando "baja" al WhatsApp o escribiendo a hola@rossospeakeasy.com.</p>
  <p><strong>Con quién se comparten.</strong> Con nadie. Los datos se guardan en servicios de Google (hojas de cálculo y nube) y, si compras una tarjeta de regalo, el pago lo procesa Stripe con sus propios términos. Las reservaciones de hasta 4 personas se hacen a través de OpenTable, sujeto a su aviso de privacidad.</p>
  <p><strong>Tus derechos (ARCO).</strong> Puedes acceder, rectificar, cancelar u oponerte al uso de tus datos, o revocar tu consentimiento, escribiendo a <a href="mailto:hola@rossospeakeasy.com">hola@rossospeakeasy.com</a> con tu nombre y el dato que quieres consultar o borrar. Respondemos en un máximo de 20 días hábiles.</p>
  <p><strong>Cambios.</strong> Si este aviso cambia, publicamos la nueva versión en esta misma página.</p>
  <p class="mini">Última actualización: {dt.date.today().strftime('%d/%m/%Y')}.</p>
</section>
"""
    return pagina("Aviso de privacidad · ROSSO", cuerpo, "/privacidad/", "Aviso de privacidad de Rosso Speakeasy.", clase="pag-legal")


# ---------------------------------------------------------------- locación para producciones
def pag_producciones():
    hoy = dt.date.today()
    minimo = (hoy + dt.timedelta(days=2)).isoformat()
    precio = "$1,800 por hora con mínimo de 3 horas. Jornada de 8 horas, $12,000. Lunes, jornada completa de 12 horas, $16,000. Más IVA."
    tipos = [("foto", "Fotografía"), ("video", "Video / comercial"), ("cine", "Cine / serie"), ("redes", "Contenido para redes"), ("podcast", "Podcast / grabación"), ("otro", "Otro")]
    necesidades = [("barra", "Barra con bartender"), ("audio", "Audio y cabina de DJ"), ("cocina", "Cocina de Pavorosso"), ("vestidor", "Espacio de vestidor y maquillaje"), ("carga", "Carga y descarga por la calle")]
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Locación</div>
  <h1>ROSSO también se renta como set.</h1>
  <p class="nota">Fotografía, video, cine, contenido de marca y grabaciones. Un speakeasy de luz roja con techo de focos, sillones, barra y cabina de DJ, disponible en las horas en que el bar está cerrado.</p>
</section>
{mosaico(("voyeur", "Detalle del salón de ROSSO bajo luz roja", "El salón"),
         ("espacio_corner", "Rincón con sillones y luz roja", "El rincón"),
         ("shake_barra", "Bartender agitando un cóctel en la barra", "La barra"))}
<section class="eventos">
  <div class="eventos-datos">
    <dl class="ficha">
      <dt>Espacio</dt><dd>40 m² de salón con techo de luces, barra completa, cabina de DJ y rincón de sillones. Se entra por la cocina de Pavorosso.</dd>
      <dt>Cuándo</dt><dd>Lunes todo el día. Martes a sábado hasta las 4:00 pm. Domingo hasta las 2:00 pm.</dd>
      <dt>Incluye</dt><dd>Solo el lugar: acceso, luz de sala y energía. Bartender, barra, cocina, audio y personal se cotizan aparte.</dd>
      <dt>Aforo</dt><dd>Hasta {SITE['aforo_total']} personas entre equipo y talento.</dd>
      <dt>Tarifa</dt><dd>{e(precio)}</dd>
      <dt>Apartado</dt><dd>50% para bloquear la fecha; el resto el día del llamado. Respondemos en menos de 24 horas.</dd>
    </dl>
    <p class="nota">Para fiestas y cenas privadas, la página es <a href="{B}/eventos/">eventos</a>.</p>
  </div>
  <form class="forma" id="forma-produccion" novalidate>
    <div class="campo"><label for="p-nombre">Nombre</label><input id="p-nombre" name="nombre" required maxlength="80" autocomplete="name"></div>
    <div class="fila">
      <div class="campo"><label for="p-whatsapp">WhatsApp</label><input id="p-whatsapp" name="whatsapp" required inputmode="tel" autocomplete="tel" placeholder="55 1234 5678"></div>
      <div class="campo"><label for="p-email">Correo <span>(opcional)</span></label><input id="p-email" name="email" type="email" autocomplete="email"></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="p-proyecto">Productora o proyecto <span>(opcional)</span></label><input id="p-proyecto" name="proyecto" maxlength="120"></div>
      <div class="campo"><label for="p-tipo">Tipo de producción</label><select id="p-tipo" name="tipo">{"".join(f'<option value="{v}">{t}</option>' for v, t in tipos)}</select></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="p-fecha">Fecha</label><input id="p-fecha" name="fecha" type="date" required min="{minimo}"></div>
      <div class="campo"><label for="p-hora">Hora de llamado</label><input id="p-hora" name="hora" placeholder="9:00 am" required></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="p-horas">Horas en locación</label><select id="p-horas" name="horas">{"".join(f'<option value="{h}"{" selected" if h == 4 else ""}>{h} horas</option>' for h in range(2, 13))}</select></div>
      <div class="campo"><label for="p-crew">Personas en el equipo</label><input id="p-crew" name="crew" type="number" min="1" max="80" required></div>
    </div>
    <fieldset class="opciones"><legend>Necesitan</legend>{"".join(f'<label class="opcion"><input type="checkbox" name="necesidades" value="{v}"> <span>{t}</span></label>' for v, t in necesidades)}</fieldset>
    <div class="campo"><label for="p-mensaje">Cuéntanos del proyecto <span>(opcional)</span></label><textarea id="p-mensaje" name="mensaje" rows="3" maxlength="1000"></textarea></div>
    <div class="campo miel" aria-hidden="true"><label for="empresa_web">Sitio web</label><input id="empresa_web" name="empresa_web" tabindex="-1" autocomplete="off"></div>
    <button class="btn" type="submit">Pedir cotización</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina("Locación para producciones · ROSSO", cuerpo, "/producciones/", "Renta ROSSO como locación para fotografía, video, cine y contenido: speakeasy de luz roja en Roma Norte, disponible cuando el bar está cerrado.", clase="pag-producciones")


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
    """La miniatura para compartir (assets/og.png) la genera herramientas/logos.py: foto + wordmark."""
    return


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
               "reservar/index.html": pag_reservar(), "eventos/index.html": pag_eventos(), "404.html": pag_404(),
               "regalo/index.html": pag_regalo(), "regalo/gracias/index.html": pag_regalo_gracias(),
               "regalo/tarjeta/index.html": pag_regalo_tarjeta(), "regalo/canje/index.html": pag_regalo_canje(),
               "club/index.html": pag_club(), "privacidad/index.html": pag_privacidad(),
               "producciones/index.html": pag_producciones()}
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
    urls = ["/", "/carta/", "/noches/", "/reservar/", "/eventos/", "/producciones/", "/club/", "/privacidad/"] + (["/regalo/"] if SITE.get("regalo_activo") else [])
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{URL}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    if SITE.get("cname"):
        (DOCS / "CNAME").write_text(SITE["dominio"] + "\n")
    print(f"docs/ generado: {len(paginas)} páginas, base='{B}', api='{SITE['api'] or '(sin API, sólo snapshot)'}'")


if __name__ == "__main__":
    main()
