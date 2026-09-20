# -*- coding: utf-8 -*-
"""Tarifario de eventos de Rosso (TARIFARIO.md) en codigo.
Todo en pesos con IVA. El 15% de servicio es del equipo y va aparte."""
import re

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# weekday() -> renta, consumo minimo garantizado, hora extra
#
# OJO: estas cifras YA vienen calibradas a NOVIEMBRE. En TARIFARIO.md la
# columna "Base noviembre" es agosto x 1.15, y las rentas recomendadas se
# derivaron de esa base. Por eso NO se les vuelve a aplicar uplift(): hacerlo
# cobraba el +15% de temporada dos veces (bug detectado el 17-sep-2026 en la
# cotizacion de Lizeth Kobrsi, que salio 13.7% arriba de lo que marca el
# tarifario).
EXCLUSIVA = {
    0: (15000, 25000, 6000),
    1: (15000, 25000, 6000),
    2: (18000, 35000, 6000),
    3: (25000, 45000, 6000),
    4: (35000, 60000, 9000),
    5: (45000, 70000, 9000),
    6: (18000, 30000, 6000),
}
# venta bruta de una noche normal (agosto 2026), base para la "justa parte" de
# un grupo. Esta SI es base agosto, asi que aqui uplift() aplica.
VENTA_NOCHE = {0: 0, 1: 7880, 2: 18850, 3: 32235, 4: 43875, 5: 53712, 6: 11643}
LUGARES = 32
BLOQUE = 0.65          # parte de la noche que ocupa un grupo de ~5 horas
PISO_PAX = 600         # consumo minimo por persona, nunca menos
SERVICIO = 0.15
AFORO_SENTADOS = 32
AFORO_TOTAL = 50

# --- topes de realidad ---------------------------------------------------
TRAGO = 273            # trago promedio ponderado de la carta real de Rosso
TRAGOS_HORA_MAX = 1.3  # ritmo maximo que se le puede exigir a un invitado
CIERRE = 2             # Rosso cierra a las 2:00 am (ultima cuenta 1:00 am)


def uplift(fecha):
    """+15% de noviembre en adelante (Buen Fin, posadas).

    Solo para cifras con base AGOSTO (VENTA_NOCHE). La tabla EXCLUSIVA ya
    trae la temporada adentro: ver la nota arriba.
    """
    return 1.15 if fecha.month >= 11 else 1.0


def redondear(x, a=100):
    return int(round(x / a) * a)


# --- validacion de horario ----------------------------------------------
def _hora_24(texto):
    """'9:00 pm' / '21:00' / '9' -> 21. None si no se entiende."""
    t = str(texto or "").strip().lower()
    m = re.search(r"(\d{1,2})(?::(\d{2}))?", t)
    if not m:
        return None
    h = int(m.group(1))
    if h > 23:
        return None
    tarde = "pm" in t or "p.m" in t
    manana = "am" in t or "a.m" in t
    if tarde and h < 12:
        h += 12
    elif not manana and not tarde and h <= 11:
        h += 12        # un evento que dice "9:00" es 9 de la noche
    return h


def revisa_horario(hora, horas):
    """Checa que el bloque quepa antes del cierre.

    Devuelve (cabe, hora_fin_24, aviso). hora_fin_24 es None si no se pudo
    interpretar la hora.
    """
    inicio = _hora_24(hora)
    if inicio is None:
        return True, None, ""
    fin = (inicio + int(horas)) % 24
    # el bloque es valido si termina a las 2 am o antes (madrugada = 0,1,2)
    cabe = fin <= CIERRE or fin == inicio
    if cabe:
        return True, fin, ""
    horas_max = (CIERRE + 24 - inicio) % 24
    aviso = (f"⚠️ el bloque termina a las {fin}:00 y ROSSO cierra a las "
             f"{CIERRE}:00 am. Desde las {inicio}:00 caben {horas_max} h. "
             f"Ajusta la hora de inicio o revisa el permiso ANTES de mandarla.")
    return False, fin, aviso


def cotizar_grupo(fecha, pax):
    """Mesa reservada con Rosso abierto. Minimo = justa parte de la noche x 1.15."""
    venta = VENTA_NOCHE[fecha.weekday()] * uplift(fecha)
    justa = (pax / LUGARES) * BLOQUE * venta
    por_pax = max(PISO_PAX, redondear(justa * 1.15 / max(pax, 1), 100))
    minimo = por_pax * pax
    return {"modalidad": "grupo", "por_persona": por_pax, "minimo": minimo,
            "servicio": round(minimo * SERVICIO), "total": round(minimo * (1 + SERVICIO)),
            "anticipo": min(5000, redondear(minimo * 0.3, 500)),
            "justa_parte": round(justa), "avisos": []}


def cotizar_exclusiva(fecha, pax, horas=5, hora=None):
    """Casa completa. La tabla ya trae la temporada: no se le aplica uplift.

    Dos topes de realidad:
      · el consumo minimo no puede exigir mas de 1.3 tragos por hora por
        persona; si se pasa, el excedente se mueve a la RENTA para que lo que
        paga el cliente no cambie.
      · el bloque tiene que terminar antes del cierre.
    """
    renta, cmg, extra = EXCLUSIVA[fecha.weekday()]
    horas = max(1, int(horas))
    horas_extra = max(0, horas - 5)
    avisos = []

    tope_pax = TRAGO * TRAGOS_HORA_MAX * horas
    if pax > 0 and cmg / pax > tope_pax:
        nuevo = redondear(tope_pax * pax, 500)
        avisos.append(
            f"consumo mínimo ajustado: ${cmg:,} pedía "
            f"{cmg / pax / TRAGO / horas:.1f} tragos por hora a cada invitado. "
            f"Bajó a ${nuevo:,} (1.3/hora) y la diferencia se movió a la renta, "
            f"así que el total al cliente no cambia.")
        renta += cmg - nuevo
        cmg = nuevo

    cabe, fin, aviso_hora = revisa_horario(hora, horas)
    if aviso_hora:
        avisos.append(aviso_hora)

    subtotal = renta + cmg + horas_extra * extra
    total = round(subtotal * (1 + SERVICIO))
    return {"modalidad": "exclusiva", "renta": renta, "minimo": cmg,
            "hora_extra": extra, "horas_extra": horas_extra, "subtotal": subtotal,
            "servicio": round(subtotal * SERVICIO), "total": total,
            "anticipo": redondear(total * 0.5, 500),
            "por_persona_minimo": round(cmg / pax) if pax else 0,
            "tragos_hora": round(cmg / pax / TRAGO / horas, 1) if pax else 0,
            "horario_cabe": cabe, "hora_fin": fin, "avisos": avisos}


def decidir_modalidad(pax, tipo):
    if tipo == "exclusiva" or pax > 20:
        return "exclusiva"
    return "grupo"


def nombre_dia(fecha):
    return DIAS[fecha.weekday()]


def fecha_larga(fecha, idioma="es"):
    if idioma == "en":
        return fecha.strftime("%A, %B %d, %Y")
    return f"{nombre_dia(fecha).capitalize()} {fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"
