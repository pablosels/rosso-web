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
A = SITE["base"]          # raíz de assets (no cambia con el idioma)
B = SITE["base"]          # prefijo de las ligas internas: "" en español, "/en" en inglés
L = "es"
URL = "https://" + SITE["dominio"]
MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TITULOS_CARTA_EN = {"Cócteles de la casa": "House cocktails", "Clásicos": "Classics", "Sin alcohol": "Non-alcoholic", "Domingos": "Sundays",
                    "Destilados": "Spirits", "Cerveza": "Beer", "Para picar": "Snacks", "Ginebra": "Gin", "Ron": "Rum",
                    "Licores y vermut": "Liqueurs & vermouth", "Otros": "Others", "Whisky": "Whisky"}


def t(es, en):
    return en if L == "en" else es


def titulo_carta(x):
    return TITULOS_CARTA_EN.get(x, x) if L == "en" else x

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
    if L == "en":
        return f"{DIAS_EN[d.weekday()]}, {MESES_EN[d.month - 1]} {d.day}"
    return f"{DIAS[d.weekday()].capitalize()} {d.day} de {MESES[d.month - 1]}"


def wa(texto):
    from urllib.parse import quote
    return f"https://wa.me/{SITE['whatsapp']}?text={quote(texto)}"


# ---------------------------------------------------------------- plantilla
NAV = [("Carta", "Menu", "/carta/"), ("Noches", "Nights", "/noches/"), ("Eventos", "Events", "/eventos/"), ("Reservar", "Book", "/reservar/")]
if SITE.get("regalo_activo"):
    NAV.append(("Regalo", "Gift card", "/regalo/"))


def pagina(titulo, cuerpo, ruta, descripcion=None, clase="", extra_head="", script=""):
    descripcion = descripcion or t(SITE["descripcion"], SITE.get("descripcion_en", SITE["descripcion"]))
    canon = URL + B + ruta
    nav = "".join(
        f'<a href="{B}{href}"{" class=activo" if ruta == href else ""}>{e(t(es_, en_))}</a>' for es_, en_, href in NAV)
    otro = f'<a class="idioma" href="{A}{"" if L == "en" else "/en"}{ruta}" hreflang="{"es" if L == "en" else "en"}" lang="{"es" if L == "en" else "en"}">{"ES" if L == "en" else "EN"}</a>'
    alternos = (f'<link rel="alternate" hreflang="es" href="{URL}{ruta}">\n<link rel="alternate" hreflang="en" href="{URL}/en{ruta}">\n'
                f'<link rel="alternate" hreflang="x-default" href="{URL}{ruta}">')
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
<html lang="{L}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descripcion)}">
<link rel="canonical" href="{canon}">
{alternos}
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descripcion)}">
<meta property="og:image" content="{URL}/assets/og.png">
<meta property="og:type" content="website">
<meta property="og:locale" content="{"en_US" if L == "en" else "es_MX"}">
<meta name="theme-color" content="#28000F">
<link rel="icon" href="{A}/assets/favicon.svg" type="image/svg+xml">
<link rel="icon" href="{A}/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{A}/assets/apple-touch-icon.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;700;900&family=Geist+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="{A}/assets/style.css?v={V_CSS}">
<script type="application/ld+json">{jsonld}</script>
{extra_head}
</head>
<body class="{clase}" data-api="{e(SITE['api'])}" data-base="{B}">
<a class="salto" href="#contenido">{t("Ir al contenido", "Skip to content")}</a>
<header class="cabecera">
  <a class="marca" href="{B}/" aria-label="ROSSO, {t('inicio', 'home')}"><img src="{A}/assets/rosso-wordmark-letras.svg" alt="ROSSO" width="1280" height="252"></a>
  <button class="menu-btn" aria-expanded="false" aria-controls="nav">{t("Menú", "Menu")}</button>
  <nav id="nav" class="nav">{nav}{otro}</nav>
</header>
<main id="contenido">
{cuerpo}
</main>
<footer class="pie">
  <div class="pie-col">
    <div class="etiqueta">{t("Dónde", "Where")}</div>
    <p><a href="{SITE['maps']}">{e(SITE['direccion'])}<br>{e(SITE['ciudad'])}</a></p>
  </div>
  <div class="pie-col">
    <div class="etiqueta">{t("Cuándo", "When")}</div>
    <p>{"<br>".join(f"{e(a)} · {e(b)}" for a, b in (SITE['horario'] if L == "es" else SITE.get('horario_en', SITE['horario'])))}</p>
  </div>
  <div class="pie-col">
    <div class="etiqueta">{t("Contacto", "Contact")}</div>
    <p><a href="{wa('Hola, ROSSO.')}">WhatsApp {e(SITE['whatsapp_bonito'])}</a><br><a href="https://www.instagram.com/{SITE['instagram']}/">@{SITE['instagram']}</a></p>
  </div>
  <div class="pie-col pie-legal">
    <p>{t(f"Reservaciones hasta {SITE['max_widget']} personas por", f"Reservations for up to {SITE['max_widget']} on")} <a href="{SITE['opentable_url']}">OpenTable</a>. {t("Grupos y eventos por WhatsApp.", "Groups and events via WhatsApp.")}</p>
    <p class="mini">© {dt.date.today().year} Rosso Speakeasy · Puebla 329, Roma Norte, CDMX · <a href="{B}/producciones/">{t("Locación", "Location hire")}</a> · <a href="{B}/club/">Club ROSSO</a> · <a href="{B}/privacidad/">{t("Privacidad", "Privacy")}</a></p>
  </div>
</footer>
<script src="{A}/assets/site.js?v={V_JS}" defer></script>
{script}
</body>
</html>"""


# ---------------------------------------------------------------- carta
def render_items(items):
    out = []
    for it in items:
        d_ = it.get("descripcion_en") if L == "en" and it.get("descripcion_en") else it.get("descripcion")
        desc = f'<span class="desc">{e(d_)}</span>' if d_ else ""
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
            inner += f'<h3 class="sub">{e(titulo_carta(sub["titulo"]))}</h3><ul class="items">{render_items(sub["items"])}</ul>'
        bloques.append(f'<section class="bloque" id="{e(slug(s["titulo"]))}"><h2>{e(titulo_carta(s["titulo"]))}</h2>{inner}</section>')
    return "\n".join(bloques)


def slug(t):
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def fecha_carta(carta):
    try:
        d = dt.datetime.fromisoformat(carta["generada"])
        return f"{MESES_EN[d.month - 1]} {d.day}, {d.year}" if L == "en" else f"{d.day} de {MESES[d.month - 1]} de {d.year}"
    except Exception:
        return ""

def img(nombre, alt, sizes="(max-width: 760px) 100vw, 60vw", lazy=True):
    return (f'<img src="{A}/assets/fotos/{nombre}.jpg" '
            f'srcset="{A}/assets/fotos/{nombre}-m.jpg 900w, {A}/assets/fotos/{nombre}.jpg 1800w" '
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
    return (f'<figure class="foto {clase}"><img src="{A}/assets/fotos/{nombre}.jpg" '
            f'srcset="{A}/assets/fotos/{nombre}-m.jpg 900w, {A}/assets/fotos/{nombre}.jpg 1800w" '
            f'sizes="(max-width: 760px) 100vw, 60vw" alt="{e(alt)}"{" loading=lazy decoding=async" if lazy else ""}></figure>')


# ---------------------------------------------------------------- páginas
def pag_inicio():
    top = [it for s in CARTA["secciones"] if s["titulo"] == "Cócteles de la casa" for it in s["items"]][:6]
    series = "".join(
        f'<li><span class="dia">{e(t(n["dia"], n.get("dia_en", n["dia"])))}</span><span class="que"><strong>{e(t(n["titulo"], n.get("titulo_en", n["titulo"])))}</strong> · {e(t(n["hora"], n.get("hora_en", n["hora"])))}</span></li>'
        for n in NOCHES["series"])
    cuerpo = f"""
<section class="hero">
  <div class="hero-marca"><img src="{A}/assets/rosso-wordmark.svg" alt="ROSSO" width="586" height="121" fetchpriority="high"></div>
  <div class="hero-ficha">
    <div class="ficha-l">PUEBLA, 329<br>ROMA NTE.<br>( CDMX )</div>
    <div class="ficha-r">SPEAKEASY<br>{t("MAR – DOM", "TUE – SUN")}<br>{t("DESDE 6 PM", "FROM 6 PM")}</div>
  </div>
  <p class="hero-texto">{t("Un bar que explora el placer a través de los sentidos. Una experiencia íntima e inmersiva que se esconde detrás de la cocina de Pavorosso.", "A bar that explores pleasure through the senses. An intimate, immersive experience hidden behind the kitchen of Pavorosso.")}</p>
  <p class="hero-texto hero-texto-2">{t("Inspirado en el rojo como símbolo del deseo, ROSSO envuelve a sus invitados con atmósfera, música y ritmo.", "Inspired by red as the color of desire, ROSSO wraps its guests in atmosphere, music and rhythm.")}</p>
  <div class="hero-cta">
    <a class="btn" href="{B}/reservar/">{t("Reservar mesa", "Book a table")}</a>
    <a class="btn btn-linea" href="{B}/carta/">{t("Ver la carta", "See the menu")}</a>
  </div>
</section>

{cine("espacio_vistaconsola", t("La consola de DJ de ROSSO bajo el techo de luces circulares", "ROSSO's DJ booth under the ceiling of circular lights"), t("La consola · Puebla 329, detrás de la cocina", "The booth · Puebla 329, behind the kitchen"), "50% 72%")}

<section class="franja">
  <div class="franja-col">
    <div class="etiqueta">{t("Esta semana", "This week")}</div>
    <ul class="series agenda-vacia">{series}</ul>
    <div data-agenda="6" hidden></div>
    <a class="enlace" href="{B}/noches/">{t("Todas las noches", "All the nights")}</a>
  </div>
  <div class="franja-col">
    <div class="etiqueta">{t("De la casa", "From the house")}</div>
    <ul class="items items-claros">{render_items(top)}</ul>
    <a class="enlace" href="{B}/carta/">{t("Carta completa", "Full menu")}</a>
  </div>
</section>

{mosaico(("espacio_corner", t("Sillón curvo rojo con mesas de cóctel", "Curved red sofa with cocktail tables"), t("El sillón", "The sofa")),
          ("coctel_queridodiario", t("Querido Diario, cóctel de la casa, servido en la barra", "Querido Diario, a house cocktail, served at the bar"), "Querido Diario"),
          ("voyeur", t("Invitados brindando en el sillón", "Guests toasting on the sofa"), t("Sábado, 1 am", "Saturday, 1 am")))}

<section class="bloque-eventos">
  <div class="etiqueta">{t("Eventos privados", "Private events")}</div>
  <h2>{t("La casa entera, para ustedes.", "The whole house, for you.")}</h2>
  <p>{t(f"Cenas de cumpleaños, lanzamientos, afters. Hasta {SITE['aforo_total']} personas entre sentadas y de pie, barra completa y equipo dedicado. Cotizamos según la fecha.", f"Birthday dinners, launches, afterparties. Up to {SITE['aforo_total']} guests seated and standing, full bar and a dedicated team. Quotes depend on the date.")}</p>
  <a class="btn btn-linea" href="{B}/eventos/">{t("Cotizar un evento", "Get a quote")}</a>
</section>
"""
    return pagina(t("ROSSO · Speakeasy en Roma Norte", "ROSSO · Speakeasy in Roma Norte"), cuerpo, "/", clase="inicio")


def pag_carta():
    cuerpo = f"""
<section class="encabezado claro">
  <div class="etiqueta">{t("La carta", "The menu")}</div>
  <h1>{t("Cócteles de la casa, clásicos y algo para picar.", "House cocktails, classics and something to snack on.")}</h1>
  <p class="nota" id="carta-nota">{t("Precios en pesos, IVA incluido. Actualizada desde nuestro punto de venta el", "Prices in Mexican pesos, tax included. Updated from our point of sale on")} {e(fecha_carta(CARTA))}.</p>
</section>
{dupla(("barra_picarilla", t("Picarilla, cóctel de la casa, sobre la barra bajo el techo de luces", "Picarilla, a house cocktail, on the bar under the ceiling of lights"), t("Picarilla · cóctel de la casa", "Picarilla · house cocktail")),
        ("coctel_loriginedumonde", t("L'Origine du Monde, martini de la casa", "L'Origine du Monde, the house martini"), "L'Origine du Monde"), "50% 62%")}
<div class="carta claro" id="carta">
{render_carta(CARTA)}
</div>
{cine("coctel_kamazotz", t("Camasotz, cóctel de la casa en copa coupe sobre la barra", "Camasotz, a house cocktail in a coupe on the bar"), t("Camasotz · cóctel de la casa", "Camasotz · house cocktail"), "50% 55%")}
"""
    return pagina(t("Carta · ROSSO", "Menu · ROSSO"), cuerpo, "/carta/",
                  t("La carta de ROSSO: cócteles de la casa, clásicos, destilados, sin alcohol y botanas. Precios actualizados desde el punto de venta.", "ROSSO's menu: house cocktails, classics, spirits, non-alcoholic drinks and snacks. Prices updated from the point of sale."),
                  clase="pag-carta")


def pag_noches():
    series = "".join(f"""
<article class="noche">
  <div class="noche-dia">{e(t(n['dia'], n.get('dia_en', n['dia'])))}</div>
  <h2>{e(t(n['titulo'], n.get('titulo_en', n['titulo'])))}</h2>
  <div class="noche-hora">{e(t(n['hora'], n.get('hora_en', n['hora'])))}</div>
  <p>{e(t(n['texto'], n.get('texto_en', n['texto'])))}</p>
</article>""" for n in NOCHES["series"])
    hoy = dt.date.today().isoformat()
    fechas = [f for f in NOCHES.get("fechas", []) if f["fecha"] >= hoy]
    lista = ""
    if fechas:
        lista = f'<div class="etiqueta">{t("Próximas fechas", "Upcoming dates")}</div><ul class="fechas">' + "".join(
            f'<li><span class="f">{e(fecha_larga(f["fecha"]))}</span><span class="t"><strong>{e(f["titulo"])}</strong>'
            + (f' · {e(f["texto"])}' if f.get("texto") else "")
            + (f' <a class="enlace" href="{e(f["link"])}">{e(f.get("link_texto", "Preventa"))}</a>' if f.get("link") else "")
            + '</span></li>' for f in sorted(fechas, key=lambda x: x["fecha"])) + "</ul>"
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">{t("Noches", "Nights")}</div>
  <h1>{t("Lo que pasa cada semana en ROSSO.", "What happens every week at ROSSO.")}</h1>
</section>
{cine("espacio_vistaconsola", t("La consola de DJ de ROSSO bajo el techo de luces", "ROSSO's DJ booth under the ceiling of lights"), t("Miércoles a sábado · sesiones de DJ · 9 pm – 1 am", "Wednesday to Saturday · DJ sessions · 9 pm – 1 am"), "50% 72%")}
<section class="noches">{series}</section>
<section class="fechas-sec">
  <div class="etiqueta">{t("Quién toca", "Who's playing")}</div>
  <p class="agenda-vacia nota">{t("La programación de la semana se publica cada lunes. Síguenos en", "The week's lineup is posted every Monday. Follow us at")} <a href="https://www.instagram.com/{SITE['instagram']}/">@{SITE['instagram']}</a>.</p>
  <div data-agenda="21" hidden></div>
  {lista}
  <p class="nota">{t(f"Para las noches con música la mesa se reserva igual: hasta {SITE['max_widget']} personas", f"On music nights tables are booked the same way: up to {SITE['max_widget']} guests")} <a href="{B}/reservar/">{t("por OpenTable", "on OpenTable")}</a>, {t("grupos por", "groups via")} <a href="{wa(t('Hola, ROSSO. Quiero reservar para un grupo.', 'Hi ROSSO, I would like to book for a group.'))}">WhatsApp</a>.</p>
</section>
"""
    return pagina(t("Noches · ROSSO", "Nights · ROSSO"), cuerpo, "/noches/", t("Sesiones de DJ de miércoles a sábado y vinilos los domingos en ROSSO, Roma Norte.", "DJ sessions Wednesday to Saturday and vinyl Sundays at ROSSO, Roma Norte."))


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
    personas = "".join(f'<option value="{n}"{" selected" if n == 2 else ""}>{n} {t("persona" if n == 1 else "personas", "guest" if n == 1 else "guests")}</option>'
                       for n in range(1, SITE["max_widget"] + 1))
    widget = (f"//www.opentable.com.mx/widget/reservation/loader?rid={rid}&type=standard&theme=standard&iframe=true"
              f"&domain=commx&lang=es-MX&newtab=false&ot_source=Restaurant%20website")
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">{t("Reservar", "Book")}</div>
  <h1>{t(f"Mesas hasta {SITE['max_widget']} personas, aquí mismo.", f"Tables for up to {SITE['max_widget']}, right here.")}</h1>
  <p class="nota">{t("Elige fecha, hora y personas. La confirmación llega al instante por OpenTable, sin costo.", "Pick a date, time and party size. Confirmation is instant through OpenTable, free of charge.")}</p>
</section>
{cine("espacio_01", t("Interior de ROSSO: sillones rojos, luz azul al fondo y techo de círculos", "Inside ROSSO: red sofas, blue light at the back and a ceiling of circles"), t("32 lugares · mesas hasta 4 personas", "32 seats · tables for up to 4"), "50% 60%")}
<section class="reserva">
  <div class="widget-caja">
    <form class="reserva-forma" id="forma-reserva" action="{SITE['opentable_url']}" method="get" target="_blank" rel="noopener">
      <div class="campo"><label for="r-fecha">{t("Fecha", "Date")}</label><input id="r-fecha" name="fecha" type="date" required min="{hoy}" value="{hoy}"></div>
      <div class="fila">
        <div class="campo"><label for="r-hora">{t("Hora", "Time")}</label><select id="r-hora" name="hora">{horas}</select></div>
        <div class="campo"><label for="r-personas">{t("Personas", "Guests")}</label><select id="r-personas" name="personas">{personas}</select></div>
      </div>
      <button class="btn" type="submit">{t("Buscar mesa en OpenTable", "Find a table on OpenTable")}</button>
      <p class="reserva-nota">{t(f"Se abre OpenTable con tu selección; ahí confirmas con tu tarjeta. Para más de {SITE['max_widget']} personas, escríbenos por WhatsApp.", f"OpenTable opens with your selection; you confirm there with a card. For more than {SITE['max_widget']} guests, message us on WhatsApp.")}</p>
    </form>
  </div>
  <aside class="reserva-lado">
    <div class="etiqueta">{t("5 personas o más", "5 guests or more")}</div>
    <p>{t("Los grupos los llevamos directo por WhatsApp para acomodarlos bien y, si hace falta, apartarles un área.", "We handle groups directly on WhatsApp so we can seat you properly and, if needed, hold an area for you.")}</p>
    <a class="btn" href="{wa(t('Hola, ROSSO. Quiero reservar para un grupo de ', 'Hi ROSSO, I would like to book for a group of '))}">{t("Escribir por WhatsApp", "Message us on WhatsApp")}</a>
    <div class="etiqueta" style="margin-top:2.5rem">{t("Horario", "Hours")}</div>
    <p>{"<br>".join(f"{e(a)} · {e(b)}" for a, b in (SITE['horario'] if L == "es" else SITE.get('horario_en', SITE['horario'])))}</p>
    <div class="etiqueta" style="margin-top:2.5rem">{t("Antes de venir", "Before you come")}</div>
    <p>{t("Toda reservación se garantiza con tarjeta. Puedes cancelar o modificar hasta las 2:30 pm del mismo día; después de esa hora, o si no llegan, se cobran $250 MXN por persona.", "Every reservation is guaranteed with a card. You can cancel or change it until 2:30 pm the same day; after that, or for no-shows, $250 MXN per guest is charged.")}</p>
    <p>{t(f"Te guardamos la mesa 15 minutos. No se permiten reservaciones múltiples ni juntar mesas. La cocina cierra a las {SITE['cocina_cierra']}.", f"We hold your table for 15 minutes. No multiple bookings or joining tables. The kitchen closes at {SITE.get('cocina_cierra_en', SITE['cocina_cierra'])}.")}</p>
  </aside>
</section>
"""
    return pagina(t("Reservar · ROSSO", "Book · ROSSO"), cuerpo, "/reservar/", t("Reserva tu mesa en ROSSO, Roma Norte: hasta 4 personas por OpenTable, grupos por WhatsApp.", "Book your table at ROSSO, Roma Norte: up to 4 guests on OpenTable, groups via WhatsApp."), clase="pag-reservar")


def pag_eventos():
    hoy = dt.date.today()
    minimo = (hoy + dt.timedelta(days=1)).isoformat()
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">{t("Eventos privados", "Private events")}</div>
  <h1>{t("Cerramos la puerta y la casa es de ustedes.", "We close the door and the house is yours.")}</h1>
  <p class="nota">{t("Cumpleaños, cenas de equipo, lanzamientos, afters. Cuéntanos la fecha y cuántos son; te mandamos una propuesta por WhatsApp en menos de 24 horas.", "Birthdays, team dinners, launches, afterparties. Tell us the date and how many you are; we send a proposal on WhatsApp within 24 hours.")}</p>
</section>
{dupla(("cortinaentrada", t("La cortina roja de la entrada a ROSSO", "The red curtain at the entrance to ROSSO"), t("La entrada, por la cocina de Pavorosso", "The entrance, through Pavorosso's kitchen")),
        ("shake_barra", t("Bartender agitando un cóctel bajo el techo de luces", "Bartender shaking a cocktail under the ceiling of lights"), t("La barra, para ustedes", "The bar, for you")), "50% 50%")}
<section class="eventos">
  <div class="eventos-datos">
    <dl class="ficha">
      <dt>{t("Aforo", "Capacity")}</dt><dd>{SITE['aforo_sentados']} {t("sentados · hasta", "seated · up to")} {SITE['aforo_total']} {t("de pie", "standing")}</dd>
      <dt>{t("Barra", "Bar")}</dt><dd>{t("Carta completa, barra libre o cóctel de bienvenida", "Full menu, open bar or welcome cocktail")}</dd>
      <dt>{t("Cocina", "Kitchen")}</dt><dd>{t(f"Botanas para compartir hasta las {SITE['cocina_cierra']}", f"Sharing snacks until {SITE.get('cocina_cierra_en', SITE['cocina_cierra'])}")}</dd>
      <dt>{t("Formato", "Format")}</dt><dd>{t("Área reservada con ROSSO abierto, o exclusiva total", "Reserved area with ROSSO open, or full buyout")}</dd>
      <dt>{t("Música", "Music")}</dt><dd>{t("DJ de la casa o el suyo; audio incluido", "House DJ or your own; sound included")}</dd>
    </dl>
    <p class="nota">{t("Si son entre 5 y 8 y sólo quieren mesa, mejor", "If you are 5 to 8 and just want a table,")} <a href="{wa(t('Hola, ROSSO. Quiero reservar para un grupo.', 'Hi ROSSO, I would like to book for a group.'))}">{t("escríbenos por WhatsApp", "message us on WhatsApp")}</a>.</p>
    <p class="nota">{t("¿Es una producción de foto o video? Ve a", "Photo or video shoot? Go to")} <a href="{B}/producciones/">{t("locación", "location hire")}</a>.</p>
  </div>
  <form class="forma" id="forma-eventos" novalidate>
    <div class="campo"><label for="nombre">{t("Nombre", "Name")}</label><input id="nombre" name="nombre" required maxlength="80" autocomplete="name"></div>
    <div class="campo"><label for="whatsapp">WhatsApp</label><input id="whatsapp" name="whatsapp" required inputmode="tel" autocomplete="tel" placeholder="55 1234 5678"></div>
    <div class="campo"><label for="email">{t("Correo", "Email")} <span>({t("opcional", "optional")})</span></label><input id="email" name="email" type="email" autocomplete="email"></div>
    <div class="fila">
      <div class="campo"><label for="fecha">{t("Fecha", "Date")}</label><input id="fecha" name="fecha" type="date" required min="{minimo}"></div>
      <div class="campo"><label for="hora">{t("Hora de inicio", "Start time")}</label><input id="hora" name="hora" placeholder="8:00 pm" required></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="personas">{t("Personas", "Guests")}</label><input id="personas" name="personas" type="number" min="5" max="80" required></div>
      <div class="campo"><label for="horas">{t("Duración", "Duration")}</label><select id="horas" name="horas">{"".join(f'<option value="{h}"{" selected" if h == 5 else ""}>{h} {t("horas", "hours")}</option>' for h in range(3, 8))}</select></div>
    </div>
    <div class="campo"><label for="tipo">{t("Formato", "Format")}</label><select id="tipo" name="tipo"><option value="no-se">{t("No sé todavía", "Not sure yet")}</option><option value="grupo">{t("Área reservada, ROSSO abierto", "Reserved area, ROSSO open")}</option><option value="exclusiva">{t("Exclusiva, ROSSO cerrado para nosotros", "Full buyout, ROSSO closed for us")}</option></select></div>
    <div class="campo"><label for="motivo">{t("Motivo", "Occasion")} <span>({t("opcional", "optional")})</span></label><input id="motivo" name="motivo" maxlength="60" placeholder="{t('Cumpleaños, cena de equipo, after…', 'Birthday, team dinner, afterparty…')}"></div>
    <div class="campo"><label for="mensaje">{t("Algo más", "Anything else")} <span>({t("opcional", "optional")})</span></label><textarea id="mensaje" name="mensaje" rows="3" maxlength="1000"></textarea></div>
    <div class="campo"><label for="idioma">{t("Idioma de la propuesta", "Proposal language")}</label><select id="idioma" name="idioma"><option value="es"{"" if L == "en" else " selected"}>Español</option><option value="en"{" selected" if L == "en" else ""}>English</option></select></div>
    <div class="campo miel" aria-hidden="true"><label for="empresa_web">Sitio web</label><input id="empresa_web" name="empresa_web" tabindex="-1" autocomplete="off"></div>
    <button class="btn" type="submit">{t("Pedir propuesta", "Request a proposal")}</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina(t("Eventos privados · ROSSO", "Private events · ROSSO"), cuerpo, "/eventos/", t("Renta ROSSO para tu evento privado en Roma Norte: hasta 50 personas, barra completa, propuesta en 24 horas.", "Hire ROSSO for your private event in Roma Norte: up to 50 guests, full bar, proposal within 24 hours."), clase="pag-eventos")


# ---------------------------------------------------------------- tarjetas de regalo
def pag_regalo():
    montos = SITE.get("regalo_montos", [500, 1000, 2000, 3000])
    notas = ({500: "Dos cócteles y algo de picar", 1000: "Una noche para dos", 2000: "La cuenta de una mesa", 3000: "Una celebración"} if L == "es"
             else {500: "Two cocktails and a snack", 1000: "A night for two", 2000: "A table's bill", 3000: "A celebration"})
    opciones = "".join(
        f'<label class="monto"><input type="radio" name="monto" value="{m}"{" checked" if i == 1 else ""}>'
        f'<span class="monto-cifra">${m:,}</span><span class="monto-nota">{notas.get(m, "")}</span></label>'
        for i, m in enumerate(montos))
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">{t("Tarjeta de regalo", "Gift card")}</div>
  <h1>{t("Regala una noche en ROSSO.", "Give someone a night at ROSSO.")}</h1>
  <p class="nota">{t("Eliges el monto, escribes a quién va y pagas en línea. El código aparece al instante y se canjea en barra: cócteles, botanas o la cuenta completa. Vale 12 meses y el saldo que sobre se queda para la siguiente visita.", "Pick the amount, say who it is for and pay online. The code appears instantly and is redeemed at the bar: cocktails, snacks or the whole bill. Valid for 12 months; any remaining balance stays for the next visit.")}</p>
</section>
{cine("coctel_queridodiario", t("Cóctel Querido Diario sobre la barra de ROSSO", "Querido Diario cocktail on ROSSO's bar"), t("Querido Diario, uno de la casa", "Querido Diario, one of the house cocktails"), "50% 60%")}
<section class="regalo" id="regalo">
  <div class="regalo-pasos">
    <ol class="pasos">
      <li><strong>{t("Eliges y pagas.", "Choose and pay.")}</strong> {t("Tarjeta de crédito o débito, cobro seguro con Stripe.", "Credit or debit card, secure checkout with Stripe.")}</li>
      <li><strong>{t("Recibes el código.", "Get the code.")}</strong> {t("En pantalla al terminar, con una tarjeta para compartir o imprimir.", "On screen when you finish, with a card to share or print.")}</li>
      <li><strong>{t("Se canjea en barra.", "Redeem at the bar.")}</strong> {t("Quien lo reciba dicta el código y se descuenta de su cuenta.", "Whoever receives it reads out the code and it comes off their bill.")}</li>
    </ol>
    <p class="nota mini">{t("Vigencia de 12 meses desde la compra. No es canjeable por efectivo. Para más de 4 personas o eventos,", "Valid for 12 months from purchase. Not redeemable for cash. For more than 4 guests or events,")} <a href="{B}/eventos/">{t("ver eventos privados", "see private events")}</a>.</p>
  </div>
  <form class="forma" id="forma-regalo" novalidate>
    <fieldset class="montos"><legend>{t("Monto", "Amount")}</legend>{opciones}</fieldset>
    <div class="fila">
      <div class="campo"><label for="g-de">{t("De parte de", "From")}</label><input id="g-de" name="de" maxlength="80" autocomplete="name" required></div>
      <div class="campo"><label for="g-para">{t("Para", "To")}</label><input id="g-para" name="para" maxlength="80" required></div>
    </div>
    <div class="campo"><label for="g-mensaje">{t("Mensaje", "Message")} <span>({t("opcional, va en la tarjeta", "optional, goes on the card")})</span></label><textarea id="g-mensaje" name="mensaje" rows="2" maxlength="200"></textarea></div>
    <div class="campo"><label for="g-email">{t("Tu correo", "Your email")} <span>({t("para el recibo", "for the receipt")})</span></label><input id="g-email" name="email" type="email" autocomplete="email" required></div>
    <button class="btn" type="submit" id="g-pagar">{t("Pagar", "Pay")} $1,000</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina(t("Tarjeta de regalo · ROSSO", "Gift card · ROSSO"), cuerpo, "/regalo/", t("Regala una noche en ROSSO: tarjeta de regalo canjeable en barra, pago en línea, código al instante, vigencia de 12 meses.", "Give a night at ROSSO: gift card redeemable at the bar, online payment, instant code, valid 12 months."), clase="pag-regalo")


def pag_regalo_gracias():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">{t("Tarjeta de regalo", "Gift card")}</div>
  <h1 id="g-titulo">{t("Confirmando tu pago…", "Confirming your payment…")}</h1>
  <p class="nota" id="g-nota">{t("Un momento, estamos generando tu código.", "One moment, we are generating your code.")}</p>
</section>
<section class="regalo-resultado" id="g-resultado" hidden>
  <div class="codigo-caja">
    <div class="etiqueta">{t("Código", "Code")}</div>
    <div class="codigo" id="g-codigo">ROSSO-····-····</div>
    <div class="codigo-datos" id="g-datos"></div>
    <div class="codigo-acciones">
      <button class="btn" type="button" id="g-copiar">{t("Copiar código", "Copy code")}</button>
      <a class="btn btn-linea" id="g-ver" href="#">{t("Ver la tarjeta", "See the card")}</a>
      <a class="btn btn-linea" id="g-wa" href="#" rel="noopener">{t("Enviar por WhatsApp", "Send on WhatsApp")}</a>
    </div>
  </div>
  <p class="nota mini">{t("Guarda este código: es lo único que se necesita en barra. También te llegó el recibo de Stripe al correo que pusiste.", "Keep this code: it is all you need at the bar. Stripe also emailed the receipt to the address you gave.")}</p>
</section>
"""
    return pagina(t("Gracias · ROSSO", "Thank you · ROSSO"), cuerpo, "/regalo/gracias/", t("Tu tarjeta de regalo de ROSSO.", "Your ROSSO gift card."), clase="pag-regalo", extra_head='<meta name="robots" content="noindex">')


def pag_regalo_tarjeta():
    cuerpo = f"""
<section class="tarjeta-envoltura">
  <article class="tarjeta" id="tarjeta">
    <img class="tarjeta-marca" src="{A}/assets/rosso-wordmark-letras.svg" alt="ROSSO" width="1280" height="252">
    <div class="tarjeta-tipo">{t("Tarjeta de regalo", "Gift card")}</div>
    <div class="tarjeta-monto" id="t-monto">$ —</div>
    <div class="tarjeta-para" id="t-para"></div>
    <p class="tarjeta-mensaje" id="t-mensaje"></p>
    <div class="tarjeta-codigo" id="t-codigo">—</div>
    <div class="tarjeta-pie"><span id="t-vence"></span><span>{t("Canjeable en barra · Puebla 329, Roma Norte", "Redeem at the bar · Puebla 329, Roma Norte")}</span></div>
  </article>
  <p class="nota mini tarjeta-nota" id="t-nota">{t("Abre esta página desde la liga de tu tarjeta.", "Open this page from your gift card link.")}</p>
  <p class="tarjeta-acciones"><button class="btn" type="button" onclick="window.print()">{t("Imprimir o guardar en PDF", "Print or save as PDF")}</button></p>
</section>
"""
    return pagina(t("Tu tarjeta · ROSSO", "Your card · ROSSO"), cuerpo, "/regalo/tarjeta/", t("Tarjeta de regalo de ROSSO.", "ROSSO gift card."), clase="pag-regalo pag-tarjeta", extra_head='<meta name="robots" content="noindex">')


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
  <h1>{t("Los de la casa se enteran primero.", "Friends of the house hear it first.")}</h1>
  <p class="nota">{t("Déjanos tu WhatsApp y te avisamos de las noches especiales, los DJs invitados y lo nuevo de la carta. Si nos dices cuándo cumples años, la casa invita un cóctel esa semana.", "Leave us your WhatsApp and we will tell you about special nights, guest DJs and what is new on the menu. Tell us your birthday and the house buys you a cocktail that week.")}</p>
</section>
{cine("espacio_corner", t("Rincón de ROSSO con luz roja y sillones", "ROSSO's corner with red light and sofas"), t("El rincón, para quedarse", "The corner, to stay a while"), "50% 50%")}
<section class="club">
  <form class="forma" id="forma-club" novalidate>
    <div class="campo"><label for="k-nombre">{t("Nombre", "Name")}</label><input id="k-nombre" name="nombre" required maxlength="80" autocomplete="name"></div>
    <div class="campo"><label for="k-whatsapp">WhatsApp</label><input id="k-whatsapp" name="whatsapp" required inputmode="tel" autocomplete="tel" placeholder="55 1234 5678"></div>
    <div class="fila">
      <div class="campo"><label for="k-email">{t("Correo", "Email")} <span>({t("opcional", "optional")})</span></label><input id="k-email" name="email" type="email" autocomplete="email"></div>
      <div class="campo"><label for="k-cumple">{t("Cumpleaños", "Birthday")} <span>({t("día/mes, opcional", "day/month, optional")})</span></label><input id="k-cumple" name="cumple" placeholder="14/02" inputmode="numeric" maxlength="10"></div>
    </div>
    <label class="acepto"><input type="checkbox" name="acepto" value="1"> <span>{t("Acepto el", "I accept the")} <a href="{B}/privacidad/">{t("aviso de privacidad", "privacy notice")}</a>. {t("Solo mensajes de ROSSO, nunca más de dos al mes, y me puedo dar de baja cuando quiera.", "Only messages from ROSSO, never more than two a month, and I can opt out any time.")}</span></label>
    <div class="campo miel" aria-hidden="true"><label for="empresa_web">Sitio web</label><input id="empresa_web" name="empresa_web" tabindex="-1" autocomplete="off"></div>
    <button class="btn" type="submit">{t("Unirme", "Join")}</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina("Club ROSSO", cuerpo, "/club/", t("Únete al Club ROSSO: noches especiales, DJs invitados y un cóctel de cumpleaños por cuenta de la casa.", "Join Club ROSSO: special nights, guest DJs and a birthday cocktail on the house."), clase="pag-club")


def pag_privacidad():
    if L == "en":
        cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">Privacy notice</div>
  <h1>What we do with your data.</h1>
  <p class="nota">Short version: we only use it to write to you about ROSSO. We never sell or share it.</p>
</section>
<section class="legal">
  <p><strong>Who is responsible.</strong> {e(SITE.get('razon_social', SITE['nombre_largo']))}, Puebla 329, Roma Norte, 06700, Mexico City, under Mexico's Federal Law on the Protection of Personal Data Held by Private Parties.</p>
  <p><strong>What we collect.</strong> Name, WhatsApp number and, if you give them, email and birthday (day and month). When you book or request a quote, also the date, time and party size.</p>
  <p><strong>What for.</strong> To tell you about special nights, guest DJs and menu news; to buy you a birthday cocktail; to handle your booking or quote; and to measure where our visits come from, without identifying you.</p>
  <p><strong>How often.</strong> No more than two messages a month. Opt out any time by replying "baja" on WhatsApp or writing to hola@rossospeakeasy.com.</p>
  <p><strong>Who we share it with.</strong> No one. Data is stored on Google services; gift card payments are processed by Stripe and reservations for up to 4 guests go through OpenTable, each under their own terms.</p>
  <p><strong>Your rights.</strong> You can access, correct, delete or object to the use of your data, or withdraw consent, by writing to <a href="mailto:hola@rossospeakeasy.com">hola@rossospeakeasy.com</a>. We answer within 20 business days. The Spanish version at <a href="{A}/privacidad/">rossospeakeasy.com/privacidad</a> is the binding one.</p>
  <p class="mini">Last updated: {SITE.get('privacidad_fecha', '05/09/2026')}.</p>
</section>
"""
        return pagina("Privacy notice · ROSSO", cuerpo, "/privacidad/", "Privacy notice of Rosso Speakeasy.", clase="pag-legal")
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
  <p class="mini">Última actualización: {SITE.get('privacidad_fecha', '05/09/2026')}.</p>
</section>
"""
    return pagina("Aviso de privacidad · ROSSO", cuerpo, "/privacidad/", "Aviso de privacidad de Rosso Speakeasy.", clase="pag-legal")


# ---------------------------------------------------------------- locación para producciones
def pag_producciones():
    hoy = dt.date.today()
    minimo = (hoy + dt.timedelta(days=2)).isoformat()
    precio = t("$1,800 por hora con mínimo de 3 horas. Jornada de 8 horas, $12,000. Lunes, jornada completa de 12 horas, $16,000. Más IVA.",
               "$1,800 MXN per hour, 3-hour minimum. 8-hour day, $12,000. Mondays, full 12-hour day, $16,000. Plus VAT.")
    tipos = [("foto", t("Fotografía", "Photography")), ("video", t("Video / comercial", "Video / commercial")), ("cine", t("Cine / serie", "Film / series")), ("redes", t("Contenido para redes", "Social content")), ("podcast", t("Podcast / grabación", "Podcast / recording")), ("otro", t("Otro", "Other"))]
    necesidades = [("barra", t("Barra con bartender", "Bar with bartender")), ("audio", t("Audio y cabina de DJ", "Sound and DJ booth")), ("cocina", t("Cocina de Pavorosso", "Pavorosso's kitchen")), ("vestidor", t("Espacio de vestidor y maquillaje", "Dressing and makeup space")), ("carga", t("Carga y descarga por la calle", "Street loading and unloading"))]
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">{t("Locación", "Location hire")}</div>
  <h1>{t("ROSSO también se renta como set.", "ROSSO is also for hire as a set.")}</h1>
  <p class="nota">{t("Fotografía, video, cine, contenido de marca y grabaciones. Un speakeasy de luz roja con techo de focos, sillones, barra y cabina de DJ, disponible en las horas en que el bar está cerrado.", "Photography, video, film, brand content and recordings. A red-lit speakeasy with a ceiling of lights, sofas, bar and DJ booth, available in the hours the bar is closed.")}</p>
</section>
{mosaico(("voyeur", t("Detalle del salón de ROSSO bajo luz roja", "Detail of ROSSO's room under red light"), t("El salón", "The room")),
         ("espacio_corner", t("Rincón con sillones y luz roja", "Corner with sofas and red light"), t("El rincón", "The corner")),
         ("shake_barra", t("Bartender agitando un cóctel en la barra", "Bartender shaking a cocktail at the bar"), t("La barra", "The bar")))}
<section class="eventos">
  <div class="eventos-datos">
    <dl class="ficha">
      <dt>{t("Espacio", "Space")}</dt><dd>{t("40 m² de salón con techo de luces, barra completa, cabina de DJ y rincón de sillones. Se entra por la cocina de Pavorosso.", "40 m² (430 sq ft) room with a ceiling of lights, full bar, DJ booth and a corner of sofas. Entrance through Pavorosso's kitchen.")}</dd>
      <dt>{t("Cuándo", "When")}</dt><dd>{t("Lunes todo el día. Martes a sábado hasta las 4:00 pm. Domingo hasta las 2:00 pm.", "Mondays all day. Tuesday to Saturday until 4:00 pm. Sundays until 2:00 pm.")}</dd>
      <dt>{t("Incluye", "Included")}</dt><dd>{t("Solo el lugar: acceso, luz de sala y energía. Bartender, barra, cocina, audio y personal se cotizan aparte.", "The venue only: access, room lighting and power. Bartender, bar, kitchen, sound and staff are quoted separately.")}</dd>
      <dt>{t("Aforo", "Capacity")}</dt><dd>{t(f"Hasta {SITE['aforo_total']} personas entre equipo y talento.", f"Up to {SITE['aforo_total']} people including crew and talent.")}</dd>
      <dt>{t("Tarifa", "Rate")}</dt><dd>{e(precio)}</dd>
      <dt>{t("Apartado", "Booking")}</dt><dd>{t("50% para bloquear la fecha; el resto el día del llamado. Respondemos en menos de 24 horas.", "50% to hold the date; the rest on the day of the call. We answer within 24 hours.")}</dd>
    </dl>
    <p class="nota">{t("Para fiestas y cenas privadas, la página es", "For parties and private dinners, see")} <a href="{B}/eventos/">{t("eventos", "events")}</a>.</p>
  </div>
  <form class="forma" id="forma-produccion" novalidate>
    <div class="campo"><label for="p-nombre">{t("Nombre", "Name")}</label><input id="p-nombre" name="nombre" required maxlength="80" autocomplete="name"></div>
    <div class="fila">
      <div class="campo"><label for="p-whatsapp">WhatsApp</label><input id="p-whatsapp" name="whatsapp" required inputmode="tel" autocomplete="tel" placeholder="55 1234 5678"></div>
      <div class="campo"><label for="p-email">{t("Correo", "Email")} <span>({t("opcional", "optional")})</span></label><input id="p-email" name="email" type="email" autocomplete="email"></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="p-proyecto">{t("Productora o proyecto", "Production company or project")} <span>({t("opcional", "optional")})</span></label><input id="p-proyecto" name="proyecto" maxlength="120"></div>
      <div class="campo"><label for="p-tipo">{t("Tipo de producción", "Type of production")}</label><select id="p-tipo" name="tipo">{"".join(f'<option value="{v}">{tx}</option>' for v, tx in tipos)}</select></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="p-fecha">{t("Fecha", "Date")}</label><input id="p-fecha" name="fecha" type="date" required min="{minimo}"></div>
      <div class="campo"><label for="p-hora">{t("Hora de llamado", "Call time")}</label><input id="p-hora" name="hora" placeholder="9:00 am" required></div>
    </div>
    <div class="fila">
      <div class="campo"><label for="p-horas">{t("Horas en locación", "Hours on location")}</label><select id="p-horas" name="horas">{"".join(f'<option value="{h}"{" selected" if h == 4 else ""}>{h} {t("horas", "hours")}</option>' for h in range(2, 13))}</select></div>
      <div class="campo"><label for="p-crew">{t("Personas en el equipo", "Crew size")}</label><input id="p-crew" name="crew" type="number" min="1" max="80" required></div>
    </div>
    <fieldset class="opciones"><legend>{t("Necesitan", "You need")}</legend>{"".join(f'<label class="opcion"><input type="checkbox" name="necesidades" value="{v}"> <span>{tx}</span></label>' for v, tx in necesidades)}</fieldset>
    <div class="campo"><label for="p-mensaje">{t("Cuéntanos del proyecto", "Tell us about the project")} <span>({t("opcional", "optional")})</span></label><textarea id="p-mensaje" name="mensaje" rows="3" maxlength="1000"></textarea></div>
    <div class="campo miel" aria-hidden="true"><label for="empresa_web">Sitio web</label><input id="empresa_web" name="empresa_web" tabindex="-1" autocomplete="off"></div>
    <button class="btn" type="submit">{t("Pedir cotización", "Request a quote")}</button>
    <p class="forma-msg" id="forma-msg" role="status"></p>
  </form>
</section>
"""
    return pagina(t("Locación para producciones · ROSSO", "Location hire · ROSSO"), cuerpo, "/producciones/", t("Renta ROSSO como locación para fotografía, video, cine y contenido: speakeasy de luz roja en Roma Norte, disponible cuando el bar está cerrado.", "Hire ROSSO as a location for photo, video, film and content: a red-lit speakeasy in Roma Norte, available when the bar is closed."), clase="pag-producciones")


def pag_404():
    cuerpo = f"""
<section class="encabezado">
  <div class="etiqueta">404</div>
  <h1>{t("Esa puerta no existe.", "That door does not exist.")}</h1>
  <p class="nota"><a class="enlace" href="{B}/">{t("Volver a ROSSO", "Back to ROSSO")}</a></p>
</section>"""
    return pagina(t("No encontrado · ROSSO", "Not found · ROSSO"), cuerpo, "/404.html")


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

    global L, B
    total = 0
    for idioma in ("es", "en"):
        L, B = idioma, (A + "/en" if idioma == "en" else A)
        paginas = {"index.html": pag_inicio(), "carta/index.html": pag_carta(), "noches/index.html": pag_noches(),
                   "reservar/index.html": pag_reservar(), "eventos/index.html": pag_eventos(), "404.html": pag_404(),
                   "regalo/index.html": pag_regalo(), "regalo/gracias/index.html": pag_regalo_gracias(),
                   "regalo/tarjeta/index.html": pag_regalo_tarjeta(), "regalo/canje/index.html": pag_regalo_canje(),
                   "club/index.html": pag_club(), "privacidad/index.html": pag_privacidad(),
                   "producciones/index.html": pag_producciones()}
        if idioma == "en":
            paginas.pop("regalo/canje/index.html")     # la barra trabaja en español
        for ruta, contenido in paginas.items():
            destino = DOCS / ("en/" if idioma == "en" else "") / ruta
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido, encoding="utf-8")
            total += 1
    L, B = "es", A
    paginas = {"total": total}

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
    urls = urls + ["/en" + u for u in urls]
    (DOCS / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{URL}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    if SITE.get("cname"):
        (DOCS / "CNAME").write_text(SITE["dominio"] + "\n")
    print(f"docs/ generado: {paginas['total']} páginas (es+en), base='{A}', api='{SITE['api'] or '(sin API, sólo snapshot)'}'")


if __name__ == "__main__":
    main()
