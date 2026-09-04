/**
 * Email Worker de ROSSO (Cloudflare Email Routing).
 * Recibe lo que llega a hola@rossospeakeasy.com, lo reenvía a la bandeja de Pablo
 * y contesta automáticamente desde hola@ a quien escribió.
 *
 * Reglas para no hacer ruido:
 *  - no contesta a boletines, rebotes ni respuestas automáticas (List-*, Auto-Submitted, Precedence);
 *  - no contesta a remitentes "noreply" ni a nosotros mismos;
 *  - una sola respuesta por remitente cada 4 días (KV AUTORESP).
 */
import { EmailMessage } from "cloudflare:email";

const DESTINO = "pabloseldner87@gmail.com";
const BUZON = "hola@rossospeakeasy.com";
const SILENCIO_SEG = 4 * 24 * 3600;

const TEXTO = `Hola, gracias por escribir a ROSSO. Ya recibimos tu mensaje y te respondemos en menos de 24 horas.

Mientras tanto:
- Reservas de hasta 4 personas: https://rossospeakeasy.com/reservar/
- Grupos de más de 4 y eventos privados: WhatsApp +52 56 6435 7899 o https://rossospeakeasy.com/eventos/
- Carta, horarios y DJs de la semana: https://rossospeakeasy.com

Nos vemos en la barra.

ROSSO
Puebla 329, Roma Norte, Ciudad de México
Martes a sábado 6 pm – 2 am · Domingo 4 pm – 11 pm
rossospeakeasy.com · @rosso.speakeasy`;

function b64utf8(s) {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  bytes.forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}

function direccionDe(cabecera) {
  const m = /<([^>]+)>/.exec(cabecera || "");
  return (m ? m[1] : (cabecera || "")).trim().toLowerCase();
}

function esAutomatico(h, remitente) {
  if (!remitente || remitente.endsWith("@rossospeakeasy.com") || remitente === DESTINO) return true;
  if (/^(no-?reply|noreply|mailer-daemon|postmaster|bounce)/i.test(remitente)) return true;
  if (h.get("auto-submitted") && h.get("auto-submitted").toLowerCase() !== "no") return true;
  if (/^(bulk|list|junk|auto_reply)$/i.test(h.get("precedence") || "")) return true;
  if (h.get("list-id") || h.get("list-unsubscribe") || h.get("x-autoreply") || h.get("x-auto-response-suppress")) return true;
  return false;
}

export default {
  async email(message, env, ctx) {
    // 1. siempre reenviar a Pablo
    await message.forward(DESTINO);

    // 2. respuesta automática, con freno
    const remitente = direccionDe(message.headers.get("from")) || (message.from || "").toLowerCase();
    if (esAutomatico(message.headers, remitente)) return;
    const msgId = message.headers.get("message-id");
    if (!msgId) return;

    if (env.AUTORESP) {
      const visto = await env.AUTORESP.get(remitente);
      if (visto) return;
      ctx.waitUntil(env.AUTORESP.put(remitente, new Date().toISOString(), { expirationTtl: SILENCIO_SEG }));
    }

    const asuntoOrig = (message.headers.get("subject") || "").replace(/[\r\n]+/g, " ").trim();
    const asunto = "Gracias por escribir a ROSSO" + (asuntoOrig ? ` (Re: ${asuntoOrig})` : "");
    const fecha = new Date().toUTCString().replace("GMT", "+0000");
    const raw =
      `From: ROSSO <${BUZON}>\r\n` +
      `To: <${remitente}>\r\n` +
      `Subject: =?UTF-8?B?${b64utf8(asunto)}?=\r\n` +
      `Date: ${fecha}\r\n` +
      `Message-ID: <auto-${Date.now()}-${Math.random().toString(36).slice(2)}@rossospeakeasy.com>\r\n` +
      `In-Reply-To: ${msgId}\r\n` +
      `References: ${msgId}\r\n` +
      `Auto-Submitted: auto-replied\r\n` +
      `X-Auto-Response-Suppress: All\r\n` +
      `MIME-Version: 1.0\r\n` +
      `Content-Type: text/plain; charset=UTF-8\r\n` +
      `Content-Transfer-Encoding: base64\r\n\r\n` +
      b64utf8(TEXTO).replace(/(.{76})/g, "$1\r\n");

    try {
      await message.reply(new EmailMessage(BUZON, remitente, raw));
    } catch (e) {
      console.log("respuesta automática falló:", e && e.message);
    }
  },
};
