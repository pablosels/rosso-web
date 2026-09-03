# rossospeakeasy.com

Sitio de ROSSO Speakeasy (Puebla 329, Roma Norte). Estático, generado con `build.py`
y servido por GitHub Pages desde `docs/`. La carta y el formulario de eventos hablan
con una API chica en Cloud Run (`api/`).

```
content/site.json        datos del negocio (horario, WhatsApp, OpenTable rid, URL de la API, base)
content/noches.json      series semanales y fechas puntuales (con link de preventa opcional)
carta_snapshot.json      carta embebida en el sitio; se regenera con extraer_carta.py + api/carta.py
assets/                  CSS, JS, logo, favicon (fonts/ para los .woff2 de ABC Diatype con licencia)
build.py                 genera docs/
docs/                    salida publicada (GitHub Pages, rama main, carpeta /docs)
api/                     servicio Cloud Run: /carta, /carta/refresh, /eventos  (ver api/DESPLEGAR.md)
```

## Publicar un cambio

```bash
python build.py
git add -A && git commit -m "..." && git push
```

Mientras el sitio viva en `pablosels.github.io/rosso-web`, generar con
`BASE=/rosso-web python build.py`. Cuando el dominio apunte a GitHub Pages, poner
`"base": ""` y `"cname": true` en `content/site.json` y volver a generar.

## Refrescar la carta a mano

```bash
python extraer_carta.py 2026-08-05 2026-09-01     # ventas de Wansoft -> carta_wansoft.json
python -c "import sys,json;sys.path.insert(0,'api');import carta;json.dump(carta.desde_snapshot('carta_wansoft.json'),open('carta_snapshot.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
python build.py
```

En producción la API lo hace sola cada día (Cloud Scheduler → `/carta/refresh`) y el
sitio la lee al cargar `/carta/`; el snapshot es el respaldo y lo que ven los buscadores.

## Reglas de negocio que viven aquí

- Reservaciones hasta 4 personas por el widget de OpenTable (plan Core: $0 por comensal desde el sitio propio). 5 o más: WhatsApp.
- Eventos: `api/tarifario.py` calcula renta + consumo mínimo por día de la semana (TARIFARIO.md de `rosso-eventos`) y `api/cotizador.py` arma el borrador en membrete. Nunca se publican precios de eventos.
- Nombres de la carta: `api/overrides.json`.

## Dominio

`rossospeakeasy.com` (Cloudflare Registrar). DNS para GitHub Pages:
`A @ → 185.199.108.153 / .109.153 / .110.153 / .111.153` y `CNAME www → pablosels.github.io`.
En el repo: Settings → Pages → Custom domain → rossospeakeasy.com, con "Enforce HTTPS".
