# Desplegar la API de rossospeakeasy.com

Servicio `rosso-web-api` en Cloud Run (proyecto `motor-facturas`, misma cuenta de
servicio que los jobs de facturas). Correr desde `rosso-web\api`.

## 1. Clave para el refresco de la carta

```bash
python -c "import secrets;print(secrets.token_urlsafe(24))" > .refresh_key
```

## 2. Deploy (la primera vez y cada cambio)

```bash
gcloud run deploy rosso-web-api --source . --region us-central1 --project motor-facturas --service-account motor-facturas-job@motor-facturas.iam.gserviceaccount.com --allow-unauthenticated --memory 512Mi --cpu 1 --timeout 600 --max-instances 2 --set-secrets "TELEGRAM_TOKEN_ROSSO=telegram-token-rosso:latest,TELEGRAM_CHAT_ID_ROSSO=telegram-chat-id-rosso:latest,WANSOFT_SUB=wansoft-rosso-sub:latest,WANSOFT_PWD=wansoft-rosso-pwd:latest" --set-env-vars "BUCKET=motor-facturas-respaldos,REFRESH_KEY=$(cat .refresh_key)"
```

Ojo: `--set-env-vars` reemplaza TODO el entorno en cada deploy (misma regla que el
motor de facturas), por eso se pasan siempre las dos variables.

La URL que imprime al final (`https://rosso-web-api-....run.app`) va en
`content/site.json` → `"api"`, y después `python build.py`.

## 3. Primera carta

```bash
curl -X POST -H "X-Refresh-Key: $(cat .refresh_key)" https://rosso-web-api-XXXX.run.app/carta/refresh
```

Tarda ~1–2 min (28 días de ventas de Wansoft). Deja `rosso-web/carta.json` en el
bucket `motor-facturas-respaldos`.

## 4. Refresco diario 6:00 (Cloud Scheduler)

```bash
gcloud scheduler jobs create http rosso-carta-diaria --location us-central1 --project motor-facturas --schedule "0 6 * * *" --time-zone "America/Mexico_City" --uri "https://rosso-web-api-XXXX.run.app/carta/refresh" --http-method POST --headers "X-Refresh-Key=$(cat .refresh_key)"
```

## Qué hace cada endpoint

- `GET /carta` — carta viva (JSON). El sitio la pide al cargar `/carta/`; si falla, muestra el snapshot que trae embebido.
- `POST /carta/refresh` — recalcula desde Wansoft (últimos 28 días de ventas; `GetProducts_Xml` viene vacío para Rosso).
- `POST /eventos` — solicitud del formulario: calcula con `tarifario.py`, genera el borrador `.docx` en membrete con `cotizador.py`, lo guarda en el bucket y lo manda al Telegram de Rosso. Al cliente sólo se le dice que se le contesta por WhatsApp.

## Nombres de la carta

`overrides.json` manda: nombres bonitos, descripciones, qué excluir y qué incluir
aunque venda poco. Cambiarlo requiere redeploy (va dentro de la imagen).
