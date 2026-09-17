# -*- coding: utf-8 -*-
"""Convocatoria para publicistas / agencias de PR (para enviar) y matriz de evaluación (interna).
Usa el mismo generador de PDF sobre membrete que las cotizaciones.

Uso: python herramientas/brief_pr.py
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "api"))
import pdf_cotizacion  # noqa: E402

OUT = RAIZ / "imprimibles"
OUT.mkdir(exist_ok=True)

BRIEF = {
    "idioma": "es",
    "kicker": "Convocatoria · relaciones públicas",
    "titulo": "Buscamos a quien cuente ROSSO",
    "subtitulo": "Brief para publicistas y agencias · propuestas hasta el viernes 9 de octubre de 2026",
    "intro": ("ROSSO es un speakeasy de 40 m² en Puebla 329, Roma Norte, Ciudad de México. Se entra por el restaurante "
              "Pavorosso: se cruza la cocina, se abre una cortina roja y del otro lado hay un bar de 32 lugares, con bancas "
              "alrededor de la barra, techo de círculos de luz y la cabina del DJ de frente. Explora el placer a través de "
              "los sentidos: coctelería de autor, selectores de miércoles a sábado y un vinilo completo cada domingo. "
              "Abrimos en 2026 y buscamos a la persona o agencia que nos ayude a contarlo en los próximos meses."),
    "bloques": [
        {"tipo": "vinetas", "titulo": "Qué queremos lograr en 90 días",
         "items": [
             "Entrar a las listas de speakeasies y bares de la Roma de los medios locales que la gente sí consulta para salir.",
             "Al menos una guía o nota en inglés para visitantes de la ciudad.",
             "Mover la historia de los domingos de vinilo completo en medios de música y cultura.",
             "Que cada mención enlace a rossospeakeasy.com/prensa: medimos visitas y reservas por canal, y con eso evaluamos el trabajo.",
             "Seis a diez visitas de creadores de contenido afines, con pieza publicada.",
         ]},
        {"tipo": "vinetas", "titulo": "Lo que ya tenemos",
         "items": [
             "Sitio en español e inglés con carta viva, agenda semanal de DJs, quiz “¿Qué cóctel eres?” y reservas.",
             "Identidad de marca completa, 10 fotografías profesionales en alta, logos en vector y textos del concepto en ambos idiomas.",
             "61 opiniones en Google, Instagram activo (@rosso.speakeasy) y medición de tráfico por canal.",
             "Historias propias: el bar al que se entra por una cocina; cócteles con nombre de obra (L'Origine du Monde, Voyeur, Shunga, Querido Diario); domingos de un solo disco.",
         ]},
        {"tipo": "vinetas", "titulo": "Qué te pedimos en la propuesta",
         "items": [
             "Enfoque: qué historias contarías, a qué medios y creadores, y por qué a esos.",
             "Entregables mensuales concretos y un calendario de los primeros 90 días.",
             "Casos de bares, restaurantes o marcas de hospitalidad con resultados: notas conseguidas y, si los tienes, datos de tráfico o reservas.",
             "Quién llevaría la cuenta en el día a día.",
             "Honorarios en tres niveles (esencial, recomendado, completo), qué incluye cada uno, y gastos que se cobran aparte: cortesías, producción, envíos.",
             "Plazo mínimo de contratación y condiciones de salida.",
         ]},
        {"tipo": "tabla", "titulo": "Cómo vamos a decidir",
         "nota": "Evaluamos todas las propuestas con los mismos criterios.",
         "filas": [["Entendimiento del concepto y calidad de las ideas", "30%", False],
                   ["Relaciones comprobables con los medios y creadores que nos interesan", "25%", False],
                   ["Entregables medibles y disposición a trabajar con nuestra liga de seguimiento", "20%", False],
                   ["Costo total contra lo que incluye", "15%", False],
                   ["Equipo asignado y forma de trabajo", "10%", False]]},
        {"tipo": "vinetas", "titulo": "Fechas y contacto",
         "items": [
             "Dudas y visita al bar: del 21 de septiembre al 2 de octubre, con cita. La mejor forma de entender ROSSO es venir.",
             "Entrega de propuestas: viernes 9 de octubre de 2026, en PDF, a hola@rossospeakeasy.com.",
             "Decisión: viernes 16 de octubre. Arranque: lunes 2 de noviembre, a tiempo para la temporada de fin de año.",
             "Contacto: Pablo Seldner · hola@rossospeakeasy.com · WhatsApp +52 56 6435 7899.",
         ]},
    ],
    "cierre": "ROSSO · Puebla 329, Roma Norte, Ciudad de México · rossospeakeasy.com · @rosso.speakeasy",
}

MATRIZ = {
    "idioma": "es",
    "kicker": "Uso interno · no enviar",
    "titulo": "Matriz para evaluar publicistas",
    "subtitulo": "Una hoja por propuesta. Califica de 1 a 5 y multiplica por el peso.",
    "intro": "Nombre de la agencia o publicista: ______________________________    Fecha de la llamada: ____________",
    "bloques": [
        {"tipo": "tabla", "titulo": "Calificación",
         "filas": [["Entendió el concepto y trajo ideas propias (peso 30)", "__ / 5", False],
                   ["Relaciones comprobables con medios y creadores que nos interesan (peso 25)", "__ / 5", False],
                   ["Entregables medibles; acepta la liga rossospeakeasy.com/prensa (peso 20)", "__ / 5", False],
                   ["Costo total contra lo que incluye (peso 15)", "__ / 5", False],
                   ["Equipo asignado: quién contesta el WhatsApp (peso 10)", "__ / 5", False]],
         "total": "____ / 500", "etiqueta_total": "PUNTAJE (calificación × peso)"},
        {"tipo": "vinetas", "titulo": "Preguntas para la llamada",
         "items": [
             "¿Qué tres medios o listas crees que podemos conseguir en 60 días, y a quién conoces ahí?",
             "Enséñame una nota que hayas conseguido para un bar o restaurante este año. ¿Cuánto tardó?",
             "¿Cómo mides tu trabajo? ¿Has trabajado con ligas de seguimiento o solo con “valor publicitario”?",
             "¿Qué no harías por nosotros aunque te lo pidiéramos?",
             "¿Quién lleva la cuenta en el día a día, y cuántas cuentas más lleva esa persona?",
             "¿Qué pasa si a los 60 días no hay resultados? ¿Cómo es la salida?",
         ]},
        {"tipo": "vinetas", "titulo": "Señales de alerta",
         "items": [
             "Promete medios específicos sin haber preguntado nada del bar.",
             "Mide todo en “alcance” o “valor publicitario equivalente” y no en notas, ligas y visitas.",
             "Plazo forzoso de 6 meses o más sin cláusula de salida.",
             "Cobra aparte cada cortesía, envío o “gestión” sin tope mensual.",
             "No vino al bar antes de mandar la propuesta.",
         ]},
        {"tipo": "vinetas", "titulo": "Referencias de mercado, para negociar",
         "items": [
             "Publicista independiente en CDMX para un bar: entre $12,000 y $25,000 al mes más IVA.",
             "Agencia boutique de hospitalidad: entre $25,000 y $50,000 al mes más IVA.",
             "Lo razonable para ROSSO hoy: el nivel esencial, 3 meses, con revisión a los 60 días contra visitas del canal “prensa”.",
         ]},
    ],
    "cierre": "Los rangos de honorarios son una referencia general del mercado; confírmalos con las propuestas que recibas.",
}

if __name__ == "__main__":
    pdf_cotizacion.generar(BRIEF, str(OUT / "ROSSO_convocatoria_publicistas.pdf"))
    pdf_cotizacion.generar(MATRIZ, str(OUT / "ROSSO_matriz_evaluacion_publicistas_INTERNO.pdf"))
    print("ok")
