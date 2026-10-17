# -*- coding: utf-8 -*-
"""Tarifario de eventos de Rosso (TARIFARIO.md) en codigo.
Todo en pesos con IVA. El 15% de servicio es del equipo y va aparte."""
import re

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# Venta bruta de una noche normal. Mediana de las ultimas 6 semanas medida
# contra Wansoft (84 noches, 20-jul a 11-oct-2026; ver rosso-eventos/precios/
# noches.json y analisis.py).
#
# OJO: se EXCLUYEN las noches cerradas. El 15-sep-2026 fue martes y Rosso no
# abrio (vispera del Grito); contar ese cero bajaba la mediana del martes de
# $12,360 a $10,075 y hacia ver la noche mas barata de lo que es. Lunes es 0
# porque Rosso cierra ese dia, no porque no venda.
VENTA_NOCHE = {0: 0, 1: 12360, 2: 16965, 3: 27275, 4: 43600, 5: 48021, 6: 11945}

# --- exclusiva: renta plana por dia + consumo minimo POR PERSONA ----------
#
# La renta se calibro para que el evento le deje a Rosso ~2.5 veces lo que le
# dejaria esa noche abierto normal (viernes se sostuvo al precio de hoy, que
# ya estaba en 2.4x). El minimo es por persona porque es consumo del cliente,
# no precio: escala solo y se lee justo.
#
# Revision del 12-oct-2026. Lo que cambio contra la tabla anterior:
#   · el minimo dejo de ser plano por dia y pasa a ser por persona
#   · lunes y martes dejan de costar lo mismo: el lunes Rosso cierra (no cede
#     nada), el martes si vende
#   · miercoles bajo 22%: estaba calibrado sobre la temporada del jazz
#     (12-ago a 2-sep hacia $38k-$55k; desde el 9-sep hace $14k-$21k)
#   · domingo bajo 35%, que era el dia mas sobrepreciado de la semana
RENTA = {0: 9500, 1: 7500, 2: 15500, 3: 33000, 4: 59000, 5: 66500, 6: 7000}
MINIMO_PAX = {0: 600, 1: 600, 2: 650, 3: 750, 4: 900, 5: 1000, 6: 600}
MINIMO_PISO = {0: 15000, 1: 15000, 2: 16000, 3: 19000, 4: 22500, 5: 25000, 6: 15000}
HORA_EXTRA = {0: 2500, 1: 2500, 2: 3000, 3: 4000, 4: 6000, 5: 6500, 6: 2500}
BLOQUE_BASE = 5        # horas incluidas en la renta; arriba de eso se cobra extra

# Descuento sobre la RENTA por desocupar temprano, segun la hora a la que se
# van (no segun cuanto dura el evento).
#
# Pablo, 12-oct-2026: "acaba a las 12 y es dificil conseguir reservas despues
# de esa hora, entonces hay que tener criterio para meter toda la noche".
# Tiene razon y los datos lo confirman: lo que Rosso recupera si reabre, ya
# castigado porque arrancar en frio no es lo mismo que una noche corrida, es
# $2,886 a las 22:00, $573 a las 23:00 y menos de $300 a medianoche. O sea que
# un evento que termina tarde se llevo la noche entera, dure 3 horas o 6.
#
# POR ESO EL DEFAULT ES NOCHE ENTERA y la duracion no mueve el precio: lo que
# lo mueve es la hora de salida.
DESC_TEMPRANO = {20: 0.18, 21: 0.12, 22: 0.07, 23: 0.0}


def descuento_temprano(fin_abs):
    """Descuento sobre la renta segun la hora a la que desocupan.

    Se interpola entre los anclajes en vez de usar escalones: con la tabla
    seca, salir a las 22:00 daba 7% y salir a las 22:01 daba 0%.
    """
    if fin_abs is None:
        return 0.0
    ks = sorted(DESC_TEMPRANO)
    if fin_abs <= ks[0]:
        return DESC_TEMPRANO[ks[0]]
    if fin_abs >= ks[-1]:
        return 0.0
    lo = max(k for k in ks if k <= fin_abs)
    hi = min(k for k in ks if k >= fin_abs)
    if lo == hi:
        return DESC_TEMPRANO[lo]
    t = (fin_abs - lo) / (hi - lo)
    return DESC_TEMPRANO[lo] + (DESC_TEMPRANO[hi] - DESC_TEMPRANO[lo]) * t
AFORO_SENTADOS = 32
AFORO_TOTAL = 50

# --- grupo (Rosso abierto) -----------------------------------------------
LUGARES = 32
BLOQUE = 0.65          # parte de la noche que ocupa un grupo de ~5 horas
PISO_PAX = 600         # consumo minimo por persona, nunca menos
SERVICIO = 0.15

# --- topes de realidad ---------------------------------------------------
TRAGO = 273            # trago promedio ponderado de la carta real de Rosso
TRAGOS_HORA_MAX = 1.3  # ritmo maximo que se le puede exigir a un invitado
CIERRE = 2             # Rosso cierra a las 2:00 am (ultima cuenta 1:00 am)
COCINA_CIERRA = 23     # la cocina cierra a las 11:00 pm


def uplift(fecha):
    """+15% de noviembre en adelante (Buen Fin, posadas).

    Solo para VENTA_NOCHE, que es una mediana de agosto-octubre. La tabla de
    exclusiva NO lleva uplift: sus cifras ya son el precio final.
    """
    return 1.15 if fecha.month >= 11 else 1.0


def redondear(x, a=100):
    return int(round(x / a) * a)


# --- validacion de horario ----------------------------------------------
def _hora_24(texto):
    """'9:00 pm' -> 21.0 · '7:30 pm' -> 19.5 · '9' -> 21.0. None si no se entiende.

    Devuelve horas con fraccion: los minutos SI cuentan. La version anterior
    los tiraba, asi que un evento pedido a las 7:30 pm se cotizaba e imprimia
    como de 7:00 pm (caso Andrea Martinez, 23-oct-2026).
    """
    t = str(texto or "").strip().lower()
    m = re.search(r"(\d{1,2})(?::(\d{2}))?", t)
    if not m:
        return None
    h = int(m.group(1))
    if h > 23:
        return None
    mins = int(m.group(2) or 0)
    if mins > 59:
        mins = 0
    tarde = "pm" in t or "p.m" in t
    manana = "am" in t or "a.m" in t
    if tarde and h < 12:
        h += 12
    elif not manana and not tarde and h <= 11:
        h += 12        # un evento que dice "9:00" es 9 de la noche
    return h + mins / 60.0


def revisa_horario(hora, horas, exclusiva=False):
    """Checa que el bloque quepa antes del cierre.

    Devuelve (cabe, hora_fin_24, aviso). hora_fin_24 es None si no se pudo
    interpretar la hora.

    Con exclusiva=True NO se rechaza nada: con la casa cerrada al publico
    ROSSO puede terminar mas tarde de las 2:00 am y mover su horario de
    apertura (criterio de Pablo, 17-oct). Solo se avisa, para que el horario
    al publico y el permiso se revisen antes de mandar la cotizacion.
    """
    inicio = _hora_24(hora)
    if inicio is None:
        return True, None, ""
    horas = int(horas)
    fin = (inicio + horas) % 24
    # ROSSO abre de tarde y cierra a las 2 am. En reloj corrido esas 2 am son
    # la hora 26, asi que el bloque cabe mientras inicio + horas no se pase.
    # (La version anterior comparaba solo `fin <= 2` y por eso rechazaba
    #  cualquier evento que terminara de noche: 6 pm + 5 h = 11 pm salia
    #  "NO CABE". Bug encontrado por la auditoria del 29-sep.)
    CIERRE_ABS = CIERRE + 24
    dentro = inicio + horas <= CIERRE_ABS
    if dentro:
        return True, fin, ""
    if exclusiva:
        # la casa cerrada puede correr mas tarde: se avisa, no se bloquea
        return True, fin, (
            f"🌙 el evento termina a las {hora_bonita(fin)}, despues del cierre "
            f"normal de las {hora_bonita(CIERRE)}. Con la casa cerrada se puede, "
            f"pero hay que mover el horario al publico de esa noche y confirmar "
            f"el permiso.")
    horas_max = CIERRE_ABS - inicio
    # hora_bonita porque desde el 15-oct las horas llevan fraccion: sin esto el
    # aviso decia "termina a las 3.0:00" y "caben 4.0 h"
    aviso = (f"⚠️ el bloque termina a las {hora_bonita(fin)} y ROSSO cierra a las "
             f"{hora_bonita(CIERRE)}. Desde las {hora_bonita(inicio)} caben "
             f"{horas_max:g} h. Ajusta la hora de inicio o revisa el permiso "
             f"ANTES de mandarla.")
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
    """Casa completa. El default es NOCHE ENTERA: la duracion no abarata.

    Lo unico que mueve el precio por horario es a que hora DESOCUPAN, porque
    es lo unico que de verdad le devuelve noche a Rosso (ver DESC_TEMPRANO).

    Dos topes de realidad:
      · el consumo minimo no puede exigir mas de 1.3 tragos por hora por
        persona; si se pasa, el excedente se mueve a la RENTA para que lo que
        paga el cliente no cambie (la casa se cierra igual con 15 que con 40).
      · el bloque tiene que terminar antes del cierre.
    """
    d = fecha.weekday()
    horas = max(1, int(horas))
    avisos = []

    cabe, fin, aviso_hora = revisa_horario(hora, horas, exclusiva=True)
    if aviso_hora:
        avisos.append(aviso_hora)

    # La guarda de aforo vivia SOLO en el endpoint HTTP, asi que cualquier
    # script que llamara al tarifario directo cotizaba grupos que no caben
    # (asi salieron las dos de Roberta, 70 y 75 personas, el 24-sep).
    if pax > AFORO_TOTAL:
        avisos.append(
            f"⚠️ {pax} personas NO CABEN: el aforo de ROSSO son {AFORO_TOTAL} "
            f"({AFORO_SENTADOS} sentadas y el resto de pie). No mandes esta "
            f"cotización sin resolverlo primero con el cliente.")

    # --- renta: plana, con descuento solo si desocupan temprano de verdad
    renta = RENTA[d]
    desc = 0.0
    if fin is not None and cabe:
        inicio = _hora_24(hora)
        fin_abs = inicio + horas if inicio is not None else None
        desc = descuento_temprano(fin_abs)
        if desc > 0:
            renta = redondear(renta * (1 - desc), 500)
            avisos.append(
                f"descuento de {desc:.0%} en la renta: desocupan a las "
                f"{hora_bonita(fin_abs)} y ROSSO alcanza a reabrir. A partir de "
                f"las 11:00 pm ya no aplica.")

    horas_extra = max(0, horas - BLOQUE_BASE)
    extra = horas_extra * HORA_EXTRA[d]

    # --- consumo minimo: por persona, con piso para grupos chicos
    cmg = max(MINIMO_PISO[d], MINIMO_PAX[d] * pax)
    tope_pax = TRAGO * TRAGOS_HORA_MAX * horas
    if pax > 0 and cmg / pax > tope_pax:
        # hacia ABAJO: redondear al 500 mas cercano podia dejar el minimo POR ENCIMA
        # del propio tope (5 personas x 1 h daba 1.5 tragos/hora contra un tope de 1.3)
        nuevo = max(500, int(tope_pax * pax // 500) * 500)
        avisos.append(
            f"consumo mínimo ajustado: ${cmg:,} pedía "
            f"{cmg / pax / TRAGO / horas:.1f} tragos por hora a cada invitado. "
            f"Bajó a ${nuevo:,} (1.3/hora) y la diferencia se movió a la renta, "
            f"así que el total al cliente no cambia.")
        renta += cmg - nuevo
        cmg = nuevo

    subtotal = renta + cmg + extra
    total = round(subtotal * (1 + SERVICIO))
    return {"modalidad": "exclusiva", "renta": renta, "minimo": cmg,
            "hora_extra": HORA_EXTRA[d], "horas_extra": horas_extra,
            "extra": extra, "subtotal": subtotal,
            "servicio": round(subtotal * SERVICIO), "total": total,
            "anticipo": redondear(total * 0.5, 500),
            "por_persona_minimo": round(cmg / pax) if pax else 0,
            "tragos_hora": round(cmg / pax / TRAGO / horas, 1) if pax else 0,
            "descuento_temprano": desc,
            "horario_cabe": cabe, "hora_inicio": _hora_24(hora), "hora_fin": fin,
            "cocina_alcanza": fin is None or (_hora_24(hora) or 0) + horas <= COCINA_CIERRA,
            "pasa_cierre": fin is not None and (_hora_24(hora) or 0) + horas > CIERRE + 24,
            "de_pie": max(0, pax - AFORO_SENTADOS),
            "avisos": avisos}


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


def hora_bonita(h24):
    """22 -> '10:00 pm' · 19.5 -> '7:30 pm' · 24 -> '12:00 am' · 25 -> '1:00 am'."""
    if h24 is None:
        return None
    mins = int(round(h24 * 60)) % (24 * 60)
    h, m = divmod(mins, 60)
    suf = "am" if h < 12 else "pm"
    hh = h % 12 or 12
    return f"{hh}:{m:02d} {suf}"
