# Desplegar la API de rossospeakeasy.com

Servicio `rosso-web-api` en Cloud Run (proyecto `motor-facturas`, misma cuenta de
servicio que los jobs de facturas). **Todo se corre desde `rosso-web\api`**: si se
corre desde otra carpeta, Cloud Build no encuentra `app.py` ni el `Dockerfile` y
falla con "provide a main.py or app.py file".

## En PowerShell (Windows), copiar y pegar tal cual

```powershell
cd C:\Users\minis\Downloads\rosso-web\api
if (-not (Test-Path .refresh_key)) { python -c "import secrets;print(secrets.token_urlsafe(24))" | Out-File -Encoding ascii -NoNewline .refresh_key }
$KEY = (Get-Content .refresh_key -Raw).Trim()
gcloud run deploy rosso-web-api --source . --region us-central1 --project motor-facturas --service-account motor-facturas-job@motor-facturas.iam.gserviceaccount.com --allow-unauthenticated --memory 512Mi --cpu 1 --timeout 600 --max-instances 2 --set-secrets "TELEGRAM_TOKEN_ROSSO=telegram-token-rosso:latest,TELEGRAM_CHAT_ID_ROSSO=telegram-chat-id-rosso:latest,WANSOFT_SUB=wansoft-rosso-sub:latest,WANSOFT_PWD=wansoft-rosso-pwd:latest" --set-env-vars "^|^BUCKET=motor-facturas-respaldos|REFRESH_KEY=$KEY|AGENDA_SHEET_ID=19r4AcTUgtYO2SL8dxvSgQxTF2oeGOJOOgk2xFJjd6NY|ALLOWED_ORIGINS=https://rossospeakeasy.com,http://rossospeakeasy.com,https://www.rossospeakeasy.com,http://www.rossospeakeasy.com,https://pablosels.github.io,http://localhost:8765"
```

(El `^|^` al inicio cambia el separador a `|` porque ALLOWED_ORIGINS lleva comas.)

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
