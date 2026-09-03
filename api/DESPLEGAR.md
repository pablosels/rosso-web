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
gcloud run deploy rosso-web-api --source . --region us-central1 --project motor-facturas --service-account motor-facturas-job@motor-facturas.iam.gserviceaccount.com --allow-unauthenticated --memory 512Mi --cpu 1 --timeout 600 --max-instances 2 --set-secrets "TELEGRAM_TOKEN_ROSSO=telegram-token-rosso:latest,TELEGRAM_CHAT_ID_ROSSO=telegram-chat-id-rosso:latest,WANSOFT_SUB=wansoft-rosso-sub:latest,WANSOFT_PWD=wansoft-rosso-pwd:latest" --set-env-vars "^|^BUCKET=motor-facturas-respaldos|REFRESH_KEY=$KEY|AGENDA_SHEET_ID=1dim5ILrXKBH4iMCPe9misxg9dQBQwM_h-yMkOyS6MZQ|ALLOWED_ORIGINS=https://rossospeakeasy.com,http://rossospeakeasy.com,https://www.rossospeakeasy.com,http://www.rossospeakeasy.com,https://pablosels.github.io,http://localhost:8765"
```

(El `^|^` al inicio cambia el separador a `|` porque ALLOWED_ORIGINS lleva comas.)

## Agenda de DJs (hoja "Agenda ROSSO")

Hoja en el Drive de pabloseldner87: `1dim5ILrXKBH4iMCPe9misxg9dQBQwM_h-yMkOyS6MZQ`, compartida como
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
