# -*- coding: utf-8 -*-
"""Tarifario de eventos de Rosso (TARIFARIO.md, 27-ago-2026) en codigo.
Todo en pesos con IVA. El 15% de servicio es del equipo y va aparte."""

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

# weekday() -> renta, consumo minimo garantizado, hora extra
EXCLUSIVA = {
    0: (15000, 25000, 6000),
    1: (15000, 25000, 6000),
    2: (18000, 35000, 6000),
    3: (25000, 45000, 6000),
    4: (35000, 60000, 9000),
    5: (45000, 70000, 9000),
    6: (18000, 30000, 6000),
}
# venta bruta de una noche normal (agosto 2026), base para la "justa parte" de un grupo
VENTA_NOCHE = {0: 0, 1: 7880, 2: 18850, 3: 32235, 4: 43875, 5: 53712, 6: 11643}
LUGARES = 32
BLOQUE = 0.65          # parte de la noche que ocupa un grupo de ~5 horas
PISO_PAX = 600         # consumo minimo por persona, nunca menos
SERVICIO = 0.15
AFORO_SENTADOS = 32
AFORO_TOTAL = 50


def uplift(fecha):
    """+15% de noviembre en adelante (Buen Fin, posadas)."""
    return 1.15 if fecha.month >= 11 else 1.0


def redondear(x, a=100):
    return int(round(x / a) * a)


def cotizar_grupo(fecha, pax):
    """Mesa reservada con Rosso abierto. Minimo = justa parte de la noche x 1.15."""
    venta = VENTA_NOCHE[fecha.weekday()] * uplift(fecha)
    justa = (pax / LUGARES) * BLOQUE * venta
    por_pax = max(PISO_PAX, redondear(justa * 1.15 / max(pax, 1), 100))
    minimo = por_pax * pax
    return {"modalidad": "grupo", "por_persona": por_pax, "minimo": minimo,
            "servicio": round(minimo * SERVICIO), "total": round(minimo * (1 + SERVICIO)),
            "anticipo": min(5000, redondear(minimo * 0.3, 500)), "justa_parte": round(justa)}


def cotizar_exclusiva(fecha, pax, horas=5):
    renta, cmg, extra = EXCLUSIVA[fecha.weekday()]
    u = uplift(fecha)
    renta, cmg = redondear(renta * u, 500), redondear(cmg * u, 500)
    horas_extra = max(0, int(horas) - 5)
    subtotal = renta + cmg + horas_extra * extra
    return {"modalidad": "exclusiva", "renta": renta, "minimo": cmg, "hora_extra": extra,
            "horas_extra": horas_extra, "subtotal": subtotal,
            "servicio": round(subtotal * SERVICIO), "total": round(subtotal * (1 + SERVICIO)),
            "anticipo": redondear(renta * 0.5, 500)}


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
