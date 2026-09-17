# -*- coding: utf-8 -*-
"""Imprimibles de ROSSO con QR: tarjeta de mesa (carta + Club), tarjeta de reseñas en Google,
tarjeta para Pavorosso y guía del Sello para barra. Salen en imprimibles/ como PDF listos para imprenta.

Uso: python herramientas/imprimibles.py
"""
import pathlib

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

RAIZ = pathlib.Path(__file__).resolve().parent.parent
OUT = RAIZ / "imprimibles"
OUT.mkdir(exist_ok=True)
LOGO = str(RAIZ / "assets" / "rosso-wordmark.png")          # rojo sobre vino
CARMIN, VINO, GRIS = HexColor("#B40519"), HexColor("#28000F"), HexColor("#E5E8E8")


def qr(c, url, x, y, lado, color=VINO, fondo=GRIS):
    w = QrCodeWidget(url, barLevel="M")
    w.barFillColor = color
    b = w.getBounds()
    tam = b[2] - b[0]
    d = Drawing(lado, lado, transform=[lado / tam, 0, 0, lado / tam, 0, 0])
    d.add(w)
    c.setFillColor(fondo)
    c.rect(x - 6, y - 6, lado + 12, lado + 12, stroke=0, fill=1)
    renderPDF.draw(d, c, x, y)


def espaciado(c, texto, x, y, size, color, font="Helvetica-Bold", track=2.2, centro=True):
    c.setFont(font, size)
    c.setFillColor(color)
    ancho = sum(c.stringWidth(ch, font, size) + track for ch in texto) - track
    cx = x - ancho / 2 if centro else x
    for ch in texto:
        c.drawString(cx, y, ch)
        cx += c.stringWidth(ch, font, size) + track


def tarjeta(nombre, ancho, alto, titulo, lineas, url, liga_visible, pie):
    """Tarjeta vertical en vino con QR en gris. Con marcas de corte implícitas: el PDF mide exactamente la tarjeta."""
    c = canvas.Canvas(str(OUT / nombre), pagesize=(ancho, alto))
    c.setFillColor(VINO); c.rect(0, 0, ancho, alto, stroke=0, fill=1)
    lw = ancho * 0.62; lh = lw * 354 / 1800
    c.drawImage(LOGO, (ancho - lw) / 2, alto - lh - 1.0 * cm, lw, lh, mask="auto")
    y = alto - lh - 2.0 * cm
    espaciado(c, titulo.upper(), ancho / 2, y, 8.5, HexColor("#E0364A"))
    y -= 0.75 * cm
    c.setFillColor(GRIS)
    for txt, size, bold in lineas:
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawCentredString(ancho / 2, y, txt)
        y -= size * 1.35
    lado = min(ancho - 3.2 * cm, y - 2.6 * cm)
    qr(c, url, (ancho - lado) / 2, y - lado - 0.2 * cm, lado)
    y = y - lado - 0.95 * cm
    c.setFont("Helvetica-Bold", 9); c.setFillColor(GRIS)
    c.drawCentredString(ancho / 2, y, liga_visible)
    espaciado(c, pie.upper(), ancho / 2, 0.7 * cm, 6.5, HexColor("#E0364A"), track=1.6)
    c.showPage(); c.save()
    print("ok", nombre)


def guia_sello():
    from reportlab.lib.pagesizes import letter
    c = canvas.Canvas(str(OUT / "ROSSO_guia_sello_barra.pdf"), pagesize=letter)
    W, H = letter
    c.setFillColor(VINO); c.rect(0, H - 3.2 * cm, W, 3.2 * cm, stroke=0, fill=1)
    c.drawImage(LOGO, 2 * cm, H - 2.45 * cm, 6 * cm, 6 * cm * 354 / 1800, mask="auto")
    espaciado(c, "SELLO ROSSO · GUÍA PARA BARRA", W - 2 * cm - 190, H - 1.75 * cm, 9, GRIS, centro=False)
    y = H - 4.6 * cm
    def h(t):
        nonlocal y
        espaciado(c, t.upper(), 2 * cm, y, 9, CARMIN, centro=False); y -= 0.75 * cm
    def p(t, bold=False, size=11):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size); c.setFillColor(HexColor("#111111"))
        for linea in t.split("\n"):
            c.drawString(2 * cm, y, linea); y -= size * 1.5
        y -= 0.2 * cm
    h("Qué es")
    p("Cada visita de un miembro del Club ROSSO suma un sello. A la quinta visita, la casa invita\nun cóctel de la casa. Un sello por persona por día.")
    h("Cómo se registra una visita")
    p("1. Abre en el teléfono de barra:  rossospeakeasy.com/club/sello", bold=True)
    p("2. Escribe los 4 últimos dígitos del WhatsApp del cliente (o su nombre) y el PIN de barra.\n3. Toca Buscar. Aparece el cliente con sus sellos.\n4. Toca Registrar visita. Listo.")
    h("Si dice que toca premio")
    p("La pantalla se pone roja y dice “Toca cóctel de la casa”. Invítale un cóctel de la casa de la carta\n(no destilados ni botellas). A Pablo le llega el aviso por Telegram, no hay que reportarlo.")
    h("Si el cliente no aparece")
    p("No está en el Club. Que escanee el QR de la mesa o entre a rossospeakeasy.com/club,\nse da de alta en un minuto desde su teléfono, y lo vuelves a buscar.")
    h("Qué decirle al cliente")
    p("“¿Ya estás en el Club? A la quinta visita la casa te invita un cóctel, y te avisamos de las noches\nespeciales. Es con tu WhatsApp, te tardas un minuto.”")
    h("Reglas")
    p("· El PIN de barra no se comparte con clientes.\n· Una visita por persona por día; el sistema no deja registrar dos.\n· El premio es personal y se entrega la noche en que sale.")
    qr(c, "https://rossospeakeasy.com/club/sello/", W - 6.2 * cm, 2 * cm, 4 * cm, fondo=HexColor("#FFFFFF"))
    c.setFont("Helvetica", 8); c.setFillColor(HexColor("#555555")); c.drawCentredString(W - 4.2 * cm, 1.4 * cm, "Página de barra")
    c.showPage(); c.save()
    print("ok ROSSO_guia_sello_barra.pdf")


if __name__ == "__main__":
    A6 = (10.5 * cm, 14.8 * cm)
    tarjeta("ROSSO_mesa_carta_y_club.pdf", *A6, "La carta",
            [("Escanea para ver la carta", 13, True), ("con precios de hoy.", 13, True), ("", 6, False),
             ("Únete al Club: a la quinta visita,", 10, False), ("la casa invita un cóctel.", 10, False)],
            "https://rossospeakeasy.com/qr/", "rossospeakeasy.com/qr", "Puebla 329 · Roma Norte")
    tarjeta("ROSSO_tarjeta_resena_google.pdf", 9 * cm, 12.5 * cm, "Gracias por venir",
            [("¿Te gustó la noche?", 13, True), ("Cuéntalo en Google.", 13, True), ("", 6, False),
             ("Toma un minuto y nos ayuda", 9.5, False), ("a que más gente encuentre la cortina.", 9.5, False)],
            "https://rossospeakeasy.com/resena/", "rossospeakeasy.com/resena", "@rosso.speakeasy")
    tarjeta("ROSSO_tarjeta_pavorosso.pdf", 9 * cm, 12.5 * cm, "Detrás de la cocina",
            [("Hay un bar escondido", 13, True), ("atrás de esta cocina.", 13, True), ("", 6, False),
             ("Cócteles de autor, DJ de miércoles", 9.5, False), ("a sábado y vinilos los domingos.", 9.5, False)],
            "https://rossospeakeasy.com/pavo/", "rossospeakeasy.com", "Pregúntale a tu mesero")
    guia_sello()
