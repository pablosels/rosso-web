/**
 * Vigilante de ROSSO (Cloudflare Worker con cron cada 10 min).
 * Revisa que el sitio y la API respondan; avisa por Telegram cuando algo se cae
 * y cuando se recupera. Guarda el último estado en KV para no repetir avisos.
 * Vive fuera de Google Cloud a propósito: si la API se cae, este sigue vivo.
 */
const OBJETIVOS = [
  { nombre: "Sitio rossospeakeasy.com", url: "https://rossospeakeasy.com/?vigilante=1", espera: "ROSSO" },
  { nombre: "API (salud)", url: "https://rosso-web-api-703407013960.us-central1.run.app/health", espera: '"ok":true' },
  { nombre: "API (carta viva)", url: "https://rosso-web-api-703407013960.us-central1.run.app/carta", espera: "secciones" },
];

async function revisar(o) {
  const inicio = Date.now();
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 15000);
    const r = await fetch(o.url, { signal: ctl.signal, headers: { "user-agent": "vigilante-rosso/1" }, cf: { cacheTtl: 0 } });
    clearTimeout(t);
    const cuerpo = await r.text();
    const ms = Date.now() - inicio;
    if (!r.ok) return { ok: false, detalle: `HTTP ${r.status} (${ms} ms)` };
    if (o.espera && !cuerpo.includes(o.espera)) return { ok: false, detalle: `respondió ${r.status} pero sin el contenido esperado (${ms} ms)` };
    return { ok: true, detalle: `${r.status} en ${ms} ms` };
  } catch (e) {
    return { ok: false, detalle: `sin respuesta: ${e && e.message}` };
  }
}

async function telegram(env, texto) {
  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: texto, parse_mode: "HTML", disable_web_page_preview: true }),
  });
}

export default {
  async scheduled(evento, env, ctx) {
    ctx.waitUntil(correr(env));
  },
  async fetch(req, env) {
    const u = new URL(req.url);
    if (u.pathname === "/estado") {
      const res = await Promise.all(OBJETIVOS.map(async (o) => ({ nombre: o.nombre, ...(await revisar(o)) })));
      return new Response(JSON.stringify(res, null, 2), { headers: { "content-type": "application/json" } });
    }
    return new Response("vigilante-rosso", { status: 200 });
  },
};

async function correr(env) {
  const ahora = new Date().toLocaleString("es-MX", { timeZone: "America/Mexico_City", hour12: true });
  for (const o of OBJETIVOS) {
    const clave = "estado:" + o.nombre;
    const res = await revisar(o);
    const previo = (await env.ESTADO.get(clave)) || "ok";
    if (!res.ok) {
      // segunda oportunidad 20 s después para no avisar por un parpadeo
      await new Promise((r) => setTimeout(r, 20000));
      const res2 = await revisar(o);
      if (res2.ok) continue;
      const fallas = parseInt((await env.ESTADO.get(clave + ":fallas")) || "0", 10) + 1;
      await env.ESTADO.put(clave + ":fallas", String(fallas));
      if (previo === "ok") {
        await env.ESTADO.put(clave, "caido");
        await env.ESTADO.put(clave + ":desde", ahora);
        await telegram(env, `🔴 <b>${o.nombre} no responde</b>\n${res2.detalle}\n${ahora}\nReviso cada 10 minutos y te aviso cuando vuelva.`);
      } else if (fallas % 18 === 0) {   // recordatorio cada 3 horas
        await telegram(env, `🔴 <b>${o.nombre} sigue caído</b> desde ${await env.ESTADO.get(clave + ":desde")}\n${res2.detalle}`);
      }
    } else if (previo !== "ok") {
      await env.ESTADO.put(clave, "ok");
      await env.ESTADO.put(clave + ":fallas", "0");
      await telegram(env, `🟢 <b>${o.nombre} volvió</b>\n${res.detalle}\nEstuvo caído desde ${await env.ESTADO.get(clave + ":desde")} hasta ${ahora}.`);
    }
  }
}
