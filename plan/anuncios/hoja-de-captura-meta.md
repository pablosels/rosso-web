# Hoja de captura · Anuncios de Instagram para ROSSO

## Estado al martes 6 de octubre

- **Quiz**: campaña, conjunto y anuncio ya publicados con la foto de la cortina. Meta la tiene "en revisión"; en cuanto apruebe, corre sola con $100 diarios.
- **Noche fuerte**: campaña y conjunto en borrador con todo capturado (radio 5 km, miércoles a sábado de 4 a 9 pm, $750 del 6 al 18 de octubre). Al anuncio le falta subir la imagen semanal, el texto y el botón; luego "Revisar y publicar".
- **Públicos**: existe "ROSSO" (base), "ROSSO 5 km - copy" y "ROSSO visitantes web 30 dias". Faltan "Interactuó en Instagram 90 días" y "Equipo" (exclusión); no estorban para encender.

Para pegar valor por valor en el Administrador de anuncios (business.facebook.com). Sigue el orden: públicos primero, campañas después. Todo queda en **borrador**; tú publicas al final.

Antes de empezar, confirma en Configuración › Cuentas:

- [ ] Página de Facebook de ROSSO existe
- [ ] Instagram @rosso.speakeasy conectado al portafolio
- [ ] Cuenta publicitaria en MXN, zona horaria Ciudad de México
- [ ] Método de pago cargado
- [ ] Píxel "ROSSO web" (1111695471183815) aparece con eventos recientes: PageView, ViewContent, Schedule, Contact, Lead, CompleteRegistration. Ya está instalado en el sitio desde el 17 de septiembre.

---

## Paso 3 · Públicos

Administrador de anuncios › Públicos › Crear público.

### 3a · Público guardado "ROSSO · Base"

| Campo | Valor |
|---|---|
| Nombre | ROSSO · Base |
| Ubicación | Personas que viven en este lugar o estuvieron hace poco |
| Lugares | Roma Norte, Roma Sur, Condesa, Hipódromo Condesa, Juárez, Cuauhtémoc, Escandón, Nápoles, Del Valle (todas en Ciudad de México). Si Meta no encuentra una colonia, usa un pin con radio de 2 km sobre ella. |
| Edad | 25 a 40 |
| Género | Todos |
| Intereses (segmentación detallada) | Coctelería, Cócteles, Bares, Vida nocturna, Música electrónica, Música disco, Discos de vinilo, Mixología |
| Idiomas | Dejar vacío |
| Tamaño estimado | Entre 150 mil y 400 mil. Si sale fuera de ese rango, quita o agrega intereses hasta entrar. |

### 3b · Público personalizado "ROSSO · Visitó el sitio 30 días"

| Campo | Valor |
|---|---|
| Fuente | Sitio web |
| Píxel | ROSSO web |
| Evento | Todos los visitantes del sitio web |
| Periodo | 30 días |
| Nombre | ROSSO · Visitó el sitio 30 días |

### 3c · Público personalizado "ROSSO · Interactuó en Instagram 90 días"

| Campo | Valor |
|---|---|
| Fuente | Cuenta de Instagram |
| Cuenta | @rosso.speakeasy |
| Evento | Todas las personas que interactuaron con esta cuenta profesional |
| Periodo | 90 días |
| Nombre | ROSSO · Interactuó en Instagram 90 días |

### 3d · Público personalizado "ROSSO · Equipo" (exclusión)

| Campo | Valor |
|---|---|
| Fuente | Lista de clientes |
| Archivo | Un CSV con una columna `email` y otra `phone` del equipo (tú, Doris, barra, DJs de casa). Prepáralo en tu computadora; no va al repo. |
| Nombre | ROSSO · Equipo |

Los públicos 3b y 3c se llenan solos con el tiempo. No esperes a que tengan gente para seguir.

---

## Paso 4 · Campaña "Quiz"

Administrador de anuncios › Crear › Configuración manual.

### Nivel campaña

| Campo | Valor |
|---|---|
| Nombre | ROSSO · Quiz |
| Objetivo | Tráfico |
| Categoría de anuncio especial | Ninguna |
| Presupuesto Advantage | Apagado (el presupuesto va en el conjunto) |

### Nivel conjunto de anuncios

| Campo | Valor |
|---|---|
| Nombre | Quiz · Base · Historias y reels |
| Conversión / destino | Sitio web |
| Optimización de la entrega | Visitas a la página de destino |
| Presupuesto | $100.00 MXN diarios |
| Programación | Continua, inicio el lunes que decidas encender |
| Público | Usar público guardado **ROSSO · Base** |
| Excluir | **ROSSO · Equipo** |
| Ubicaciones | Manual. Solo **Instagram**: Historias de Instagram y Reels de Instagram. Desmarcar Facebook, Messenger y Audience Network. |

### Nivel anuncio

| Campo | Valor |
|---|---|
| Nombre | Quiz · Cortina · Imagen 9:16 |
| Identidad | Página de Facebook ROSSO, cuenta de Instagram @rosso.speakeasy |
| Formato | Una sola imagen |
| Pieza | Foto de la cortina con el texto ya puesto: `plan/anuncios/quiz-cortina-1080x1920.jpg` (1080x1920, 9:16). Subirla tal cual, sin recortar ni dejar que Meta la ajuste a 1:1. |
| Texto en la imagen (ya viene) | ¿Qué cóctel eres? Cinco preguntas. Un trago con tu nombre. rossospeakeasy.com/ads |
| Texto principal | Cinco preguntas. Un trago con tu nombre. Descubre qué cóctel eres. |
| Sitio web (URL) | https://rossospeakeasy.com/ads |
| Mostrar enlace | rossospeakeasy.com |
| Llamada a la acción | Más información |
| Seguimiento | Píxel ROSSO web encendido; sin parámetros de URL (la liga /ads ya marca el canal). |

---

## Paso 5 · Campaña "Noche fuerte"

### Nivel campaña

| Campo | Valor |
|---|---|
| Nombre | ROSSO · Noche fuerte |
| Objetivo | Tráfico |
| Presupuesto Advantage | Apagado |

### Nivel conjunto de anuncios

| Campo | Valor |
|---|---|
| Nombre | Noche fuerte · 5 km · Mié-Sáb tarde |
| Conversión / destino | Sitio web |
| Optimización de la entrega | Visitas a la página de destino |
| Presupuesto | Total por tiempo: $375.00 MXN por semana. Si Meta solo permite presupuesto total por periodo, pon $750 para dos semanas y fecha de fin a los 14 días. |
| Programación de anuncios | Activar "Publicar anuncios según un calendario". Marcar **miércoles, jueves, viernes y sábado de 16:00 a 21:00**, hora de la cuenta. |
| Público | **ROSSO · Base**, cambiando la ubicación a: pin en Puebla 329, Roma Norte, Ciudad de México, radio **5 km**. Mantener edad e intereses. |
| Excluir | **ROSSO · Equipo** |
| Ubicaciones | Manual. Solo Instagram: Historias y Reels. |

### Nivel anuncio (uno por semana, se renueva cada lunes)

Un solo anuncio con las noches de la semana (miércoles a sábado). Si fuera un anuncio por noche en el mismo conjunto, Meta mostraría el del jueves también el sábado; separarlos en conjuntos repartiría el presupuesto en pedazos muy chicos y no aprendería nada.

| Campo | Valor |
|---|---|
| Nombre | Noche fuerte · semana del [fecha del miércoles] |
| Formato | Una sola imagen |
| Pieza | `plan/anuncios/noche-fuerte-semana-AAAA-MM-DD.jpg` (1080x1920). Se genera cada lunes con la agenda de la semana: miércoles a sábado con DJ, género y hora. |
| Texto principal | Miércoles [DJ], jueves [DJ], viernes [DJ] y sábado [DJ] en ROSSO. Puebla 329, Roma Norte. Reserva tu mesa. |
| Sitio web (URL) | `https://rossospeakeasy.com/noches/?de=ads` |
| Llamada a la acción | Reservar |

Alternativa por noche, si algún día se quiere empujar a un solo DJ: imagen `plan/anuncios/noche-fuerte-AAAA-MM-DD-slug.jpg` y liga `https://rossospeakeasy.com/dj/?n=SLUG&de=ads` (el parámetro de la página del DJ es `n`, no `dj`).

Cada lunes, al salir la agenda: cambiar la imagen y el texto del anuncio por los de la nueva semana (o duplicarlo y apagar el anterior).

---

## Paso 6 · Revisión y encendido

- [ ] Todo en borrador. Revisar juntos: públicos, presupuestos, ubicaciones solo Instagram, ligas correctas.
- [ ] Publicar. Meta aprueba en 2 a 24 horas.
- [ ] Al día siguiente, confirmar en Administrador de eventos que llegan visitas con `de=ads`.

## Paso 7 · Corte a dos semanas

El resumen del lunes trae el canal "ads". Cada campaña sigue solo si cumple las dos:

| Medida | Sigue si |
|---|---|
| Costo por visita al sitio | $6 o menos |
| De cada 100 visitas, cuántas buscan mesa | 10 o más |

Si una no pasa, se apaga y su presupuesto va a la otra.

## Calendario recorrido (arranque semana del 6 de octubre)

| Fecha | Qué |
|---|---|
| Martes 6 oct | Quiz publicada (en revisión). Noche fuerte en borrador; falta imagen, texto y botón. |
| Miércoles 7 oct | Primera noche con anuncio: OZZO. Jueves ALEJAINA, viernes HARFUSH, sábado RO LAUTREC. |
| Lunes 12 oct | Renovar la imagen semanal de Noche fuerte con la agenda nueva. Confirmar en Administrador de eventos que llegan visitas con `de=ads`. |
| Lunes 19 oct | Corte a dos semanas (paso 7). |
| Semana del 26 oct | Segunda ola si pasó el corte: campaña en inglés ($1,000/mes, liga /en/speakeasy-roma-norte, texto "A speakeasy behind a kitchen.") y retorno ($500/mes, público "Visitó el sitio 30 días" excluyendo quien ya buscó mesa, texto "Tu mesa te espera", liga /reservar/). |
