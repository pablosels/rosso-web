# correo-rosso (Cloudflare Email Worker)

Recibe todo lo que llega a hola@rossospeakeasy.com (regla de Email Routing -> worker `correo-rosso`),
lo reenvia a pabloseldner87@gmail.com y contesta desde hola@ con el texto de bienvenida.
Una respuesta por remitente cada 4 dias (KV `autoresp-rosso`, binding AUTORESP). No contesta a
boletines, rebotes, noreply ni a nosotros mismos.

Se subio 4-sep-2026 con la API del dashboard (sesion de Pablo en Chrome), no con wrangler.
Para cambiar el texto: editar `worker.js` y volver a subir (dashboard > Workers > correo-rosso > Edit code, o API).
