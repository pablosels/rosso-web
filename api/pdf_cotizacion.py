# -*- coding: utf-8 -*-
"""Cotizaciones en PDF sobre el membrete oficial de ROSSO (plantilla/image1.jpg a página completa).

Recibe el mismo diccionario que cotizador.generar (kicker, titulo, subtitulo, ficha, intro,
bloques[tabla|vinetas|texto|lista], cierre) y escribe un PDF carta, varias páginas si hace falta,
con el membrete repetido en cada una. Sin Word ni LibreOffice: solo reportlab.
"""
import os

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle, KeepTogether, PageBreak)

AQUI = os.path.dirname(os.path.abspath(__file__))
MEMBRETE = os.path.join(AQUI, "plantilla", "image1.jpg")

ROJO = HexColor("#B10714")
GRIS = HexColor("#555555")
NEGRO = HexColor("#111111")
LINEA = HexColor("#D8D8D8")
SOMBRA = HexColor("#F1F1F1")

FICHA = {"es": [("Cliente", "cliente"), ("Fecha", "fecha"), ("Horario", "horario"), ("Duración", "duracion"),
                ("Invitados", "invitados"), ("Modalidad", "modalidad")],
         "en": [("Client", "cliente"), ("Date", "fecha"), ("Time", "horario"), ("Duration", "duracion"),
                ("Guests", "invitados"), ("Format", "modalidad")]}
ETIQ = {"es": ("CONCEPTO", "IMPORTE", "TOTAL"), "en": ("ITEM", "AMOUNT", "TOTAL")}


def _st(nombre, size, color=NEGRO, bold=False, leading=None, before=0, after=0, caps=False, spacing=0, align=0):
    return ParagraphStyle(nombre, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                          leading=leading or size * 1.3, textColor=color, spaceBefore=before, spaceAfter=after,
                          alignment=align)


def _e(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _caps(s):
    """Mayúsculas con tracking, como el kicker del membrete: letras con un espacio duro, palabras con tres."""
    return "&nbsp;&nbsp;&nbsp;".join("&nbsp;".join(_e(pal).upper()) for pal in str(s or "").split())


def _fondo(canvas, doc):
    canvas.saveState()
    canvas.drawImage(MEMBRETE, 0, 0, width=letter[0], height=letter[1], preserveAspectRatio=False)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GRIS)
    canvas.drawRightString(letter[0] - inch, 0.62 * inch, f"{doc.page}")
    canvas.restoreState()


def generar(cfg, salida):
    idioma = cfg.get("idioma", "es") if cfg.get("idioma") in ("es", "en") else "es"
    concepto, importe, total_txt = ETIQ[idioma]
    doc = BaseDocTemplate(salida, pagesize=letter, leftMargin=inch, rightMargin=inch,
                          topMargin=1.55 * inch, bottomMargin=0.95 * inch,
                          title=cfg.get("titulo", "Cotización ROSSO"), author="ROSSO Speakeasy")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="cuerpo", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="membrete", frames=[frame], onPage=_fondo)])

    s_kicker = _st("kicker", 8.5, ROJO, bold=True, after=3)
    s_titulo = _st("titulo", 21, NEGRO, bold=True, leading=23, after=3)
    s_sub = _st("sub", 10, GRIS, after=12)
    s_k = _st("k", 8, GRIS, bold=True)
    s_v = _st("v", 10, NEGRO)
    s_p = _st("p", 10, NEGRO, leading=14, before=6, after=4)
    s_sec = _st("sec", 8.5, ROJO, bold=True, before=14, after=4)
    s_nota = _st("nota", 9.5, GRIS, leading=13, after=6)
    s_cel = _st("cel", 9.5, NEGRO, leading=12.5)
    s_celb = _st("celb", 9.5, NEGRO, bold=True, leading=12.5)
    s_celg = _st("celg", 8, GRIS, bold=True)
    s_vin = _st("vin", 9.5, NEGRO, leading=13.5, after=3)
    s_cierre = _st("cierre", 9, GRIS, before=14)
    s_col = _st("col", 9.5, NEGRO, bold=True, before=6, after=2)

    f = []
    f.append(Paragraph(_caps(cfg.get("kicker") or ("Cotización de evento" if idioma == "es" else "Event proposal")), s_kicker))
    f.append(Paragraph(_e(cfg["titulo"]), s_titulo))
    if cfg.get("subtitulo"):
        f.append(Paragraph(_e(cfg["subtitulo"]), s_sub))

    ficha = [(k, cfg.get(v)) for k, v in FICHA[idioma] if cfg.get(v)]
    if ficha:
        t = Table([[Paragraph(_e(k).upper(), s_k), Paragraph(_e(v), s_v)] for k, v in ficha],
                  colWidths=[3.6 * cm, doc.width - 3.6 * cm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        f.append(t)
        f.append(Spacer(1, 4))

    if cfg.get("intro"):
        f.append(Paragraph(_e(cfg["intro"]), s_p))

    for b in cfg.get("bloques", []):
        tipo = b.get("tipo", "lista")
        if b.get("salto"):
            f.append(PageBreak())
        grupo = [Paragraph(_caps(b["titulo"]), s_sec)]
        if b.get("nota"):
            grupo.append(Paragraph(_e(b["nota"]), s_nota))
        if tipo == "tabla":
            filas = [[Paragraph(concepto, s_celg), Paragraph(importe, s_celg)]]
            estilos = [("LINEBELOW", (0, 0), (-1, 0), 0.6, LINEA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                       ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                       ("ALIGN", (1, 0), (1, -1), "RIGHT")]
            for i, fila in enumerate(b["filas"], start=1):
                negrita = bool(fila[2]) if len(fila) > 2 else False
                st = s_celb if negrita else s_cel
                filas.append([Paragraph(_e(fila[0]), st), Paragraph(_e(fila[1]), ParagraphStyle("r", parent=st, alignment=2))])
                estilos.append(("LINEBELOW", (0, i), (-1, i), 0.4, LINEA))
            if b.get("total"):
                filas.append([Paragraph(_e(b.get("etiqueta_total") or total_txt).upper(), ParagraphStyle("tk", parent=s_celb, fontSize=8.5)),
                              Paragraph(_e(b["total"]), ParagraphStyle("tv", parent=s_celb, fontSize=11, alignment=2))])
                n = len(filas) - 1
                estilos += [("BACKGROUND", (0, n), (-1, n), SOMBRA), ("TOPPADDING", (0, n), (-1, n), 7),
                            ("BOTTOMPADDING", (0, n), (-1, n), 7), ("LEFTPADDING", (0, n), (0, n), 6), ("RIGHTPADDING", (1, n), (1, n), 6)]
            t = Table(filas, colWidths=[doc.width - 4.2 * cm, 4.2 * cm], repeatRows=1)
            t.setStyle(TableStyle(estilos))
            grupo.append(t)
        elif tipo == "vinetas":
            for it in b.get("items", []):
                grupo.append(Paragraph("·&nbsp;&nbsp;" + _e(it), s_vin))
        elif tipo == "texto":
            for par in b.get("parrafos", []):
                grupo.append(Paragraph(_e(par), s_vin))
        else:   # lista de columnas
            for col in b.get("columnas", []):
                if col.get("titulo"):
                    grupo.append(Paragraph(_e(col["titulo"]), s_col))
                if col.get("nota"):
                    grupo.append(Paragraph(_e(col["nota"]), s_nota))
                grupo.append(Paragraph("&nbsp;&nbsp;·&nbsp;&nbsp;".join(_e(x) for x in col.get("items", [])), s_vin))
        f.append(KeepTogether(grupo))

    if cfg.get("cierre"):
        f.append(Paragraph(_e(cfg["cierre"]), s_cierre))

    doc.build(f)
    return salida
