# Desplegar la API de rossospeakeasy.com

Servicio `rosso-web-api` en Cloud Run (proyecto `motor-facturas`, misma cuenta de
servicio que los jobs de facturas). **Todo se corre desde `rosso-web\api`**: si se
corre desde otra carpeta, Cloud Build no encuentra `app.py` ni el `Dockerfile` y
falla con "provide a main.py or app.py file".

## Redesplegar despues de cambiar codigo (lo normal)

**No pases `--set-env-vars` ni `--set-secrets`.** Si los omites, Cloud Run
conserva el entorno que ya tiene el servicio. Si los pasas, REEMPLAZA TODO:
el 17-sep-2026 el bloque de mas abajo listaba 4 variables y el servicio vivo
ya tenia 14 + 5 secretos — correrlo habria tumbado tarjetas de regalo, Club
ROSSO, metricas, vinilos, descripciones, visitas, perfiles de DJ y el correo
del bot.

```powershell
cd C:\Users\minis\Downloads\rosso-web\api
gcloud run deploy rosso-web-api --source . --region us-central1 --project motor-facturas
```

Antes de correrlo conviene ver que hay vivo:

```powershell
gcloud run services describe rosso-web-api --region us-central1 --project motor-facturas --format="value(spec.template.spec.containers[0].env)"
```

## Primer despliegue o reconstruir el servicio desde cero

Solo en este caso se pasan entorno y secretos, y hay que pasarlos TODOS.
Sacar la lista viva con el `describe` de arriba y confirmar que no falte
ninguno.

```powershell
cd C:\Users\minis\Downloads\rosso-web\api
if (-not (Test-Path .refresh_key)) { python -c "import secrets;print(secrets.token_urlsafe(24))" | Out-File -Encoding ascii -NoNewline .refresh_key }
$KEY = (Get-Content .refresh_key -Raw).Trim()
gcloud run deploy rosso-web-api --source . --region us-central1 --project motor-facturas --service-account motor-facturas-job@motor-facturas.iam.gserviceaccount.com --allow-unauthenticated --memory 512Mi --cpu 1 --timeout 600 --max-instances 2 --set-secrets "TELEGRAM_TOKEN_ROSSO=telegram-token-rosso:latest,TELEGRAM_CHAT_ID_ROSSO=telegram-chat-id-rosso:latest,WANSOFT_SUB=wansoft-rosso-sub:latest,WANSOFT_PWD=wansoft-rosso-pwd:latest,GMAIL_APP_PASSWORD=gmail-app-rosso:latest" --set-env-vars "^|^BUCKET=motor-facturas-respaldos|REFRESH_KEY=$KEY|AGENDA_SHEET_ID=19r4AcTUgtYO2SL8dxvSgQxTF2oeGOJOOgk2xFJjd6NY|METRICAS_SHEET_ID=15fGLQztLHOZpXmS2Az0WsUgZS1vrbIz47VMwQwTHtrg|REGALO_SHEET_ID=1op60hWGzKriYFXSf6-ZCr5x-aFx6gDo86dbDCotUxJM|CLIENTES_SHEET_ID=1GkCp6s-f8VV0bKhIl8MjYnAE_Klo2XIGv2cBQ3Rs4g0|DESCRIPCIONES_SHEET_ID=1Z-0yeDD-nMJnR0hvnSKyh6Adu2TmI7GER38TzerZzwY|VINILOS_SHEET_ID=1Cu9DkIA_yHkblMxnoW3_WtZ0NgGtErRhs4HF9gqYdcA|VISITAS_SHEET_ID=1bjMJKcMpXk2aG-qGx8wnYpbXWgK08hGX_6L8vzP4l24|DJS_SHEET_ID=1Bzi-5GKlEWhwo0L0MXBRNP_X6jMi9-ZFJywEjK5Ky-U|CANJE_PIN=918074|FECHAS_LITERAL=1|GMAIL_USER=pabloseldner87@gmail.com|ALLOWED_ORIGINS=https://rossospeakeasy.com,http://rossospeakeasy.com,https://www.rossospeakeasy.com,http://www.rossospeakeasy.com,https://pablosels.github.io,http://localhost:8765"
```

(El `^|^` al inicio cambia el separador a `|` porque ALLOWED_ORIGINS lleva comas.)

**Ojo con `.refresh_key`:** si el archivo local no existe, el bloque genera una
llave NUEVA y los jobs de Cloud Scheduler (`rosso-carta-diaria`,
`rosso-agenda-recordatorio`) se quedan mandando la vieja y empiezan a fallar
con 403. Verificar que la local y la viva coincidan antes de redesplegar.

## Agenda de DJs (hoja "Agenda ROSSO")

Hoja en el Drive de pabloseldner87: `19r4AcTUgtYO2SL8dxvSgQxTF2oeGOJOOgk2xFJjd6NY`, compartida como
lector con `motor-facturas-job@motor-facturas.iam.gserviceaccount.com`. Columnas: fecha (AAAA-MM-DD),
hora, dj, genero, instagram, preventa (liga), destacado (SI), notas. Las filas cuyo dj empieza con
"Ejemplo" se ignoran. `GET /agenda` devuelve las próximas 3 semanas (caché 5 min).
Recordatorio lunes y martes 10:00:

```powershell
$KEY = (Get-Content .refresh_key -Raw).Trim()
gcloud scheduler jobs create http rosso-agenda-recordatorio --location us-central1 --project motor-facturas --schedule "0 10 * * 1,2" --time-zone "America/Mexico_City" --uri "https://rosso-web-api-703407013960.us-central1.run.app/agenda/recordatorio" --http-method POST --message-body "{}" --headers "X-Refresh-Key=$KEY,Content-Type=application/json"
```

Al final imprime `Service URL: https://rosso-web-api-....run.app`. Esa URL va en
`content/site.json` → `"api"`, y luego `python build.py` + commit + push.

Ojo: `--set-env-vars` reemplaza TODO el entorno en cada deploy (misma regla que el
motor de facturas), por eso siempre se pasan las dos variables.

## Primera carta (después del deploy)

```powershell
$KEY = (Get-Content .refresh_key -Raw).Trim()
curl.exe -X POST -d "" -H "X-Refresh-Key: $KEY" https://rosso-web-api-703407013960.us-central1.run.app/carta/refresh
```

(El `-d ""` importa: el frontal de Google rechaza POST sin `Content-Length` con un error 411.)

```powershell
```

Tarda 1–2 min (28 días de ventas de Wansoft). Deja `rosso-web/carta.json` en el
bucket `motor-facturas-respaldos`.

## Refresco diario 6:00 (Cloud Scheduler)

```powershell
$KEY = (Get-Content .refresh_key -Raw).Trim()
gcloud scheduler jobs create http rosso-carta-diaria --location us-central1 --project motor-facturas --schedule "0 6 * * *" --time-zone "America/Mexico_City" --uri "https://rosso-web-api-XXXX.run.app/carta/refresh" --http-method POST --headers "X-Refresh-Key=$KEY"
```

## Qué hace cada endpoint

- `GET /carta` — carta viva (JSON). El sitio la pide al cargar `/carta/`; si falla, muestra el snapshot embebido.
- `POST /carta/refresh` — recalcula desde Wansoft (últimos 28 días de ventas; `GetProducts_Xml` viene vacío para Rosso).
- `POST /eventos` — solicitud del formulario: calcula con `tarifario.py`, genera el borrador `.docx` en membrete con `cotizador.py`, lo guarda en el bucket y lo manda al Telegram de Rosso. Al cliente sólo se le dice que se le contesta por WhatsApp.

## Nombres de la carta

`overrides.json` manda: nombres bonitos, descripciones, qué excluir y qué incluir
aunque venda poco. Cambiarlo requiere redeploy (va dentro de la imagen).

## Tarjetas de regalo (Stripe)

La API ya sabe cobrar; solo faltan dos secretos de Stripe. Pablo, en el panel de Stripe (cuenta ROSSO SPEAKEASY, modo real):

1. **Llave restringida**: Desarrolladores > Claves de API > "Crear clave restringida". Nombre `rosso-web`. Permisos: *Checkout Sessions* = Escritura; todo lo demás Ninguno. Copiar la clave `rk_live_...`.
2. **Webhook**: Desarrolladores > Webhooks > "Agregar endpoint". URL `https://rosso-web-api-703407013960.us-central1.run.app/stripe/webhook`. Evento: `checkout.session.completed`. Copiar el "Secreto de firma" `whsec_...`.

Luego, en PowerShell (pegar cada valor cuando lo pida):

```powershell
Read-Host "rk_live" | Set-Content -NoNewline $env:TEMP\rk.txt; gcloud secrets create stripe-key-rosso --data-file=$env:TEMP\rk.txt --project motor-facturas; Remove-Item $env:TEMP\rk.txt
k.txt; gcloud secrets create stripe-key-rosso --data-file=$env:TEMP
k.txt --project motor-facturas; Remove-Item $env:TEMP
k.txt
Read-Host "whsec" | Set-Content -NoNewline $env:TEMP\wh.txt; gcloud secrets create stripe-webhook-rosso --data-file=$env:TEMP\wh.txt --project motor-facturas; Remove-Item $env:TEMP\wh.txt
gcloud secrets add-iam-policy-binding stripe-key-rosso --member=serviceAccount:motor-facturas-job@motor-facturas.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor --project motor-facturas
gcloud secrets add-iam-policy-binding stripe-webhook-rosso --member=serviceAccount:motor-facturas-job@motor-facturas.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor --project motor-facturas
gcloud run services update rosso-web-api --region us-central1 --project motor-facturas --update-secrets=STRIPE_KEY=stripe-key-rosso:latest,STRIPE_WEBHOOK_SECRET=stripe-webhook-rosso:latest
```

Después: `content/site.json` → `"regalo_activo": true`, `python build.py`, commit y push (aparece "Regalo" en el menú).

Variables ya puestas: `REGALO_SHEET_ID` (hoja "Tarjetas ROSSO", 1op60hWGzKriYFXSf6-ZCr5x-aFx6gDo86dbDCotUxJM) y `CANJE_PIN` (guardado en `api/.canje_pin`, no se sube a git).
Páginas: `/regalo/` compra · `/regalo/gracias/?s=cs_...` código · `/regalo/tarjeta/?c=ROSSO-XXXX-XXXX` tarjeta imprimible · `/regalo/canje/` barra (PIN).

## Vigilante (servicio aparte)

Carpeta `vigilante/`. Cloud Run `rosso-vigilante` + Cloud Scheduler `rosso-vigilante` cada 10 min (POST /revisar, header X-Refresh-Key).
Redesplegar: `gcloud run deploy rosso-vigilante --source vigilante --region us-central1 --project motor-facturas` (conserva secretos y variables).

## Variables nuevas de la API

`DESCRIPCIONES_SHEET_ID` = hoja "Carta ROSSO descripciones" (1Z-0yeDD-nMJnR0hvnSKyh6Adu2TmI7GER38TzerZzwY). GET /carta cruza descripciones por nombre.

## Sitio bilingüe

`python build.py` genera / y /en/. Textos con t(es, en) en build.py; site.js usa tt() según <html lang>. Campos *_en en content/site.json y content/noches.json.

`VINILOS_SHEET_ID` = hoja "Vinilos ROSSO" (1Cu9DkIA_yHkblMxnoW3_WtZ0NgGtErRhs4HF9gqYdcA). GET /vinilo; el recordatorio del lunes avisa si falta el disco del domingo.

`VISITAS_SHEET_ID` = hoja "Visitas ROSSO" (1bjMJKcMpXk2aG-qGx8wnYpbXWgK08hGX_6L8vzP4l24, SA writer). Sello ROSSO: /club/sello/ con CANJE_PIN; GET /sello/buscar (X-Pin), POST /sello/registrar. Perfiles: GET /djs, GET /dj/<slug>, página /dj/?n=. Playlist: site.json spotify_playlist.

`FECHAS_LITERAL=1` (15-sep): las hojas Agenda y Vinilos ya están en locale es_MX (POST /hojas/arreglar lo puso y reescribió las fechas); con la variable puesta el parser NO adivina día/mes. Si alguien vuelve a poner la hoja en inglés, quitar la variable.

## Borradores de correo automáticos (cotizaciones)

Cuando el cliente deja correo, la API deja un borrador en el Gmail de Pablo (desde hola@) con el PDF adjunto.
Necesita la contraseña de aplicación de Gmail (Cuenta Google > Seguridad > Contraseñas de aplicaciones; puede ser la misma "hola rosso" o una nueva "rosso api"). Pablo, en PowerShell:

```powershell
Read-Host "contraseña de aplicación (16 letras, sin espacios)" | Set-Content -NoNewline $env:TEMP\ga.txt; gcloud secrets create gmail-app-rosso --data-file=$env:TEMP\ga.txt --project motor-facturas; Remove-Item $env:TEMP\ga.txt
gcloud secrets add-iam-policy-binding gmail-app-rosso --member=serviceAccount:motor-facturas-job@motor-facturas.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor --project motor-facturas
gcloud run services update rosso-web-api --region us-central1 --project motor-facturas --update-secrets=GMAIL_APP_PASSWORD=gmail-app-rosso:latest --update-env-vars=GMAIL_USER=pabloseldner87@gmail.com
```
