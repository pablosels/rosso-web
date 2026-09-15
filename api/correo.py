# -*- coding: utf-8 -*-
"""Borradores de correo en el Gmail de Pablo, listos para enviar desde hola@rossospeakeasy.com.

Usa IMAP con la contraseña de aplicación de Gmail (la misma que sirve para 'enviar como'): el
mensaje se deposita en la carpeta de Borradores con el PDF adjunto; Pablo solo lo abre y da Enviar.
Variables: GMAIL_USER (pabloseldner87@gmail.com), GMAIL_APP_PASSWORD (secreto). Sin ellas, no hace nada.
"""
import imaplib
import os
import re
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

USUARIO = os.environ.get("GMAIL_USER", "")
CLAVE = os.environ.get("GMAIL_APP_PASSWORD", "")
REMITENTE = os.environ.get("GMAIL_FROM", "Pablo Seldner · ROSSO <hola@rossospeakeasy.com>")


def configurado():
    return bool(USUARIO and CLAVE)


def armar(para, asunto, cuerpo, adjunto=None, nombre_adjunto=None):
    m = EmailMessage()
    m["From"] = REMITENTE
    m["To"] = para
    m["Subject"] = asunto
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain="rossospeakeasy.com")
    m.set_content(cuerpo)
    if adjunto and os.path.exists(adjunto):
        with open(adjunto, "rb") as fh:
            m.add_attachment(fh.read(), maintype="application", subtype="pdf",
                             filename=nombre_adjunto or os.path.basename(adjunto))
    return m


def _carpeta_borradores(imap):
    """Gmail nombra la carpeta según el idioma de la cuenta; se busca por el atributo \\Drafts."""
    ok, cajas = imap.list()
    for linea in cajas or []:
        s = linea.decode("utf-8", "replace") if isinstance(linea, bytes) else str(linea)
        if "\\Drafts" in s:
            m = re.search(r'"([^"]+)"\s*$', s) or re.search(r"\s(\S+)\s*$", s)
            if m:
                return m.group(1)
    return "[Gmail]/Drafts"


def crear_borrador(para, asunto, cuerpo, adjunto=None, nombre_adjunto=None):
    """Deja el borrador en Gmail. Devuelve True si quedó."""
    if not configurado():
        return False
    msg = armar(para, asunto, cuerpo, adjunto, nombre_adjunto)
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    try:
        imap.login(USUARIO, CLAVE)
        carpeta = _carpeta_borradores(imap)
        ok, _ = imap.append(f'"{carpeta}"', "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
        return ok == "OK"
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def texto_evento(sol, calc, folio, es=True):
    nombre = sol["nombre"].split()[0] if sol["nombre"] else ""
    if es:
        return (f"Hola {nombre}:\n\n"
                f"Gracias por pensar en ROSSO para tu fecha. Te adjunto la cotización en PDF con el detalle "
                f"de la propuesta para el {sol['fecha_larga']} ({sol['personas']} personas).\n\n"
                f"Cualquier ajuste lo vemos con gusto por aquí o por WhatsApp al +52 56 6435 7899. "
                f"Para apartar la fecha basta con el anticipo que viene en el documento.\n\n"
                f"Un abrazo,\nPablo Seldner\nROSSO · Puebla 329, Roma Norte\nrossospeakeasy.com · @rosso.speakeasy\n\nFolio {folio}")
    return (f"Hi {nombre}:\n\n"
            f"Thank you for thinking of ROSSO for your date. Attached is the PDF proposal with the details "
            f"for {sol['fecha_larga']} ({sol['personas']} guests).\n\n"
            f"Happy to adjust anything here or on WhatsApp at +52 56 6435 7899. "
            f"The deposit in the document holds the date.\n\n"
            f"Best,\nPablo Seldner\nROSSO · Puebla 329, Roma Norte\nrossospeakeasy.com · @rosso.speakeasy\n\nRef. {folio}")


def texto_locacion(sol, folio):
    nombre = sol["nombre"].split()[0] if sol["nombre"] else ""
    return (f"Hola {nombre}:\n\n"
            f"Gracias por considerar ROSSO como locación" + (f" para {sol['proyecto']}" if sol.get("proyecto") else "") + ". "
            f"Te adjunto la cotización en PDF con la renta del espacio para el {sol['fecha_larga']}, "
            f"y lo que se cotiza aparte según lo que necesiten.\n\n"
            f"Si quieren hacer scouting antes, coordinamos una visita por WhatsApp al +52 56 6435 7899. "
            f"La fecha se aparta con el 50% que indica el documento.\n\n"
            f"Saludos,\nPablo Seldner\nROSSO · Puebla 329, Roma Norte\nrossospeakeasy.com · @rosso.speakeasy\n\nFolio {folio}")
