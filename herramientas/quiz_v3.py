# -*- coding: utf-8 -*-
"""Quiz v3 '¿Qué cóctel eres?' en TRES preguntas (97 de cada 100 que llegaban del anuncio no terminaban cinco):
base (filtra), fruta y textura. Con esas tres, cada cóctel de la carta queda separado del resto de su base.
Color y aroma quedan en preguntas_reserva. Perfil de cada cóctel sacado de sus ingredientes; sin azar.
Conserva los textos (ingredientes, notas, porque). Corre: python herramientas/quiz_v3.py → reescribe content/quiz.json"""
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
ruta = R / "content" / "quiz.json"
viejo = json.loads(ruta.read_text(encoding="utf-8"))
textos = {c["slug"]: c for c in viejo["cocteles"]}

P_BASE = {"sentido": {"es": "Gusto", "en": "Taste"},
          "es": "Para empezar: ¿con qué se hace tu trago?", "en": "First things first: what is your drink made with?",
          "opciones": [
              {"es": "Agave: tequila o mezcal", "en": "Agave: tequila or mezcal", "rasgos": ["agave"]},
              {"es": "Ginebra", "en": "Gin", "rasgos": ["gin"]},
              {"es": "Ron", "en": "Rum", "rasgos": ["ron"]},
              {"es": "Whiskey", "en": "Whiskey", "rasgos": ["whiskey"]},
              {"es": "Vermut o burbujas, algo bajito para durar toda la noche", "en": "Vermouth or bubbles, something light to last the night", "rasgos": ["vermut"]},
              {"es": "Hoy sin alcohol", "en": "No alcohol tonight", "rasgos": [], "sin_alcohol": True}]}
P_FRUTA = {"sentido": {"es": "Olfato", "en": "Smell"},
           "es": "Lo acercas antes del primer trago. ¿Qué fruta hay adentro?", "en": "You bring it close before the first sip. What fruit is in there?",
           "opciones": [
               {"es": "Tropical: mango, coco, maracuyá o piña", "en": "Tropical: mango, coconut, passion fruit or pineapple", "rasgos": ["tropical"]},
               {"es": "De hueso: durazno, pera, ciruela o higo", "en": "Stone fruit: peach, pear, plum or fig", "rasgos": ["hueso"]},
               {"es": "Fresa, guayaba o jamaica", "en": "Strawberry, guava or hibiscus", "rasgos": ["roja"]},
               {"es": "Nada de fruta: cacao, café o nuez", "en": "No fruit: cacao, coffee or nuts", "rasgos": ["ninguna"]}]}
P_TEXTURA = {"sentido": {"es": "Tacto", "en": "Touch"},
             "es": "Y al final, el primer trago. ¿Qué sientes en la boca?", "en": "And finally, the first sip. What do you feel?",
             "opciones": [
                 {"es": "Limpio y seco", "en": "Clean and dry", "rasgos": ["seco"]},
                 {"es": "Sedoso, casi cremoso", "en": "Silky, almost creamy", "rasgos": ["sedoso"]},
                 {"es": "Burbujas", "en": "Bubbles", "rasgos": ["burbujas"]},
                 {"es": "Con cuerpo, que pesa", "en": "Full-bodied, with weight", "rasgos": ["cuerpo"]}]}
P_COLOR = {"sentido": {"es": "Vista", "en": "Sight"},
           "es": "Lo ponen en la barra, bajo los círculos rojos del techo. ¿De qué color es?", "en": "It lands on the bar under the red circles. What colour is it?",
           "opciones": [
               {"es": "Pálido o transparente", "en": "Pale or clear", "rasgos": ["palido"]},
               {"es": "Rosa o rojo", "en": "Pink or red", "rasgos": ["rosa"]},
               {"es": "Dorado, amarillo o ámbar", "en": "Golden, yellow or amber", "rasgos": ["dorado"]},
               {"es": "Oscuro: café o negro", "en": "Dark: brown or black", "rasgos": ["oscuro"]}]}
P_AROMA = {"sentido": {"es": "Olfato", "en": "Smell"},
           "es": "¿A qué huele?", "en": "What does it smell of?",
           "opciones": [
               {"es": "A cítricos recién cortados", "en": "Freshly cut citrus", "rasgos": ["citrico"]},
               {"es": "A hierbas y flores", "en": "Herbs and flowers", "rasgos": ["hierbas_flores"]},
               {"es": "A cacao, café o nuez tostada", "en": "Cacao, coffee or toasted nuts", "rasgos": ["tostado"]},
               {"es": "A humo, especias y un poco de chile", "en": "Smoke, spice and a little chile", "rasgos": ["humo_especias"]}]}

# perfil de cada cóctel, sacado de sus ingredientes. Orden = prioridad en empates (firmas de la casa primero).
PERFIL = [
    ("picarilla",          False, ["agave", "dorado", "humo_especias", "citrico", "seco", "hueso"]),       # tequila, miel, ciruela, chile de árbol, limón
    ("l-origine-du-monde", False, ["gin", "palido", "tostado", "cuerpo", "ninguna"]),                      # gin con manteca de cacao, licor de coco, vermut blanco, bitter de chocolate
    ("camasotz",           False, ["agave", "rosa", "hierbas_flores", "seco", "roja"]),                    # tequila, jerez fino, guayaba, jamaica, nuez moscada
    ("querido-diario",     False, ["whiskey", "oscuro", "humo_especias", "tostado", "cuerpo", "hueso"]),  # whiskey, vermut rosso, vinagre de higo, angostura
    ("sabor-a-mi",         False, ["ron", "dorado", "citrico", "seco", "tropical"]),                       # ron con coco, maracuyá, agua de coco, vinagre de piña
    ("voyeur",             False, ["gin", "dorado", "hierbas_flores", "citrico", "sedoso", "tropical"]),   # gin, mango, limón, tomillo, lactosa
    ("rosso-tonic",        False, ["gin", "rosa", "citrico", "burbujas", "roja"]),                         # gin de fresa, vermut rosso, limón, tónica
    ("pellizco",           False, ["agave", "palido", "humo_especias", "tostado", "sedoso", "hueso"]),     # mezcal, bitter de nuez, cordial de pera, limón amarillo, clara
    ("paola",              False, ["vermut", "rosa", "hierbas_flores", "seco", "roja"]),                   # vermut blanco y seco, compota de fresa, rosas
    ("rococócrème",        False, ["vermut", "dorado", "hierbas_flores", "burbujas", "hueso"]),            # Cirilo, durazno, bitter de lavanda
    ("under-wear",         True,  ["dorado", "citrico", "seco", "tropical"]),                              # maracuyá, agua de coco, vinagre de piña
    ("el-ojo",             True,  ["dorado", "hierbas_flores", "citrico", "sedoso", "tropical"]),          # mango, limón, tomillo, lactosa
    ("copa-de-edipo",      True,  ["palido", "tostado", "citrico", "sedoso", "hueso"]),                    # nuez, cordial de pera, limón amarillo, clara
    ("spf-0",              True,  ["oscuro", "tostado", "cuerpo", "ninguna"]),                             # licor de coco (sin alcohol) y cold brew
    ("a-coup-de-creme",    True,  ["palido", "hierbas_flores", "burbujas", "hueso"]),                      # té espumoso, durazno, bitter de lavanda
]
ETIQUETAS = {
    "agave": {"es": "agave", "en": "agave"}, "gin": {"es": "ginebra", "en": "gin"}, "ron": {"es": "ron", "en": "rum"},
    "whiskey": {"es": "whiskey", "en": "whiskey"}, "vermut": {"es": "vermut o burbujas", "en": "vermouth or bubbles"},
    "palido": {"es": "pálido", "en": "pale"}, "rosa": {"es": "rosa o rojo", "en": "pink or red"}, "dorado": {"es": "dorado", "en": "golden"}, "oscuro": {"es": "oscuro", "en": "dark"},
    "citrico": {"es": "cítricos", "en": "citrus"}, "hierbas_flores": {"es": "hierbas y flores", "en": "herbs and flowers"}, "tostado": {"es": "cacao, café o nuez", "en": "cacao, coffee or nuts"}, "humo_especias": {"es": "humo, especias y chile", "en": "smoke, spice and chile"},
    "seco": {"es": "limpio y seco", "en": "clean and dry"}, "sedoso": {"es": "sedoso", "en": "silky"}, "burbujas": {"es": "burbujas", "en": "bubbles"}, "cuerpo": {"es": "con cuerpo", "en": "full-bodied"},
    "tropical": {"es": "fruta tropical", "en": "tropical fruit"}, "hueso": {"es": "fruta de hueso", "en": "stone fruit"}, "roja": {"es": "fresa, guayaba o jamaica", "en": "strawberry, guava or hibiscus"}, "ninguna": {"es": "sin fruta", "en": "no fruit"},
}
PESOS = {"palido": 2, "rosa": 2, "dorado": 2, "oscuro": 2, "seco": 2, "sedoso": 2, "burbujas": 2, "cuerpo": 2,
         "tropical": 2, "hueso": 2, "roja": 2, "ninguna": 2, "citrico": 1, "hierbas_flores": 1, "tostado": 1, "humo_especias": 1}

cocteles = []
for i, (slug, sin_alc, rasgos) in enumerate(PERFIL):
    c = dict(textos[slug]); c["rasgos"] = rasgos; c["sin_alcohol"] = sin_alc; c["prioridad"] = i
    cocteles.append(c)
nuevo = {"_nota": "Quiz v3 (22-oct-2026): TRES preguntas — base (filtra), fruta y textura — porque 97 de cada 100 del anuncio no terminaban cinco. "
                  "Cada cóctel tiene un perfil sacado de sus ingredientes; gana el de más coincidencias (fruta y textura pesan 2). Empates: gana la prioridad "
                  "(orden de la lista). Sin azar: mismas respuestas, mismo resultado. Color y aroma quedan en preguntas_reserva por si se vuelve a cinco.",
         "pesos": PESOS, "etiquetas": ETIQUETAS, "preguntas": [P_BASE, P_FRUTA, P_TEXTURA], "preguntas_reserva": [P_COLOR, P_AROMA], "cocteles": cocteles}
ruta.write_text(json.dumps(nuevo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("quiz v3 (3 preguntas) escrito:", len(cocteles), "cócteles")
