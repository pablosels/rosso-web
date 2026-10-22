/* rossospeakeasy.com — menú móvil, carta viva y formulario de eventos. */
(function () {
  var API = document.body.dataset.api || "";
  var EN = document.documentElement.lang === "en";
  function tt(es, en) { return EN ? en : es; }
  window.ROSSO_EN = EN; window.ROSSO_tt = tt;
  var TITULOS_EN = { "Cócteles de la casa": "House cocktails", "Clásicos": "Classics", "Sin alcohol": "Non-alcoholic", "Domingos": "Sundays", "Destilados": "Spirits", "Cerveza": "Beer", "Para picar": "Snacks", "Ginebra": "Gin", "Ron": "Rum", "Licores y vermut": "Liqueurs & vermouth", "Otros": "Others" };
  function titulo(x) { return EN && TITULOS_EN[x] ? TITULOS_EN[x] : x; }

  // métricas de origen: ?de=<canal> se recuerda 30 días; cada visita y clic importante se anota.
  var CANAL = "directo";
  try {
    var q = new URLSearchParams(location.search), de = (q.get("de") || "").toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 24);
    if (de) {
      localStorage.setItem("rosso_canal", JSON.stringify({ c: de, t: Date.now() }));
      q.delete("de");
      history.replaceState(null, "", location.pathname + (q.toString() ? "?" + q : "") + location.hash);
    }
    var g = JSON.parse(localStorage.getItem("rosso_canal") || "null");
    if (g && g.c && Date.now() - g.t < 30 * 864e5) CANAL = g.c;
  } catch (e) { /* sin storage: canal directo */ }
  window.ROSSO_medir = medir;
  var PIXEL = { reservar: "Schedule", whatsapp: "Contact", evento: "Lead", produccion_envio: "Lead", club_alta: "CompleteRegistration", quiz: "ViewContent", boleto_pago: "InitiateCheckout" };
  function medir(tipo) {
    try { if (window.fbq && PIXEL[tipo]) window.fbq("track", PIXEL[tipo], { content_name: tipo }); } catch (e) { /* sin píxel */ }
    if (tipo === "produccion_envio" || tipo === "club_alta" || tipo === "boleto_pago") return;   // solo para el píxel; la métrica propia ya se cuenta aparte
    if (!API) return;
    try {
      var datos = JSON.stringify({ tipo: tipo, canal: CANAL, pagina: location.pathname, movil: /Mobi|Android/i.test(navigator.userAgent), ref: document.referrer });
      if (navigator.sendBeacon) navigator.sendBeacon(API + "/clic", new Blob([datos], { type: "text/plain" }));
      else fetch(API + "/clic", { method: "POST", mode: "cors", keepalive: true, headers: { "Content-Type": "text/plain" }, body: datos });
    } catch (e) { /* nada */ }
  }
  try {
    if (!sessionStorage.getItem("rosso_visita")) { sessionStorage.setItem("rosso_visita", "1"); medir("visita"); }
  } catch (e) { medir("visita"); }
  var ruta = location.pathname.replace(/^\/en/, "");
  ["carta", "noches", "club", "producciones", "regalo", "boletos"].forEach(function (p) {
    if (ruta.indexOf("/" + p) === 0) medir(p === "producciones" ? "produccion" : p);
  });
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[href*='wa.me'], a[href*='opentable.com'], a[href*='instagram.com'], a[href*='spotify.com']");
    if (!a) return;
    var h = a.href;
    medir(h.indexOf("wa.me") >= 0 ? "whatsapp" : h.indexOf("opentable") >= 0 ? "opentable" : h.indexOf("instagram") >= 0 ? "instagram" : "spotify");
  });

  // menú móvil
  var btn = document.querySelector(".menu-btn"), nav = document.getElementById("nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var abierto = nav.classList.toggle("abierto");
      btn.setAttribute("aria-expanded", abierto ? "true" : "false");
    });
  }

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function slug(t) { return t.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""); }
  function items(lista) {
    return '<ul class="items">' + lista.map(function (it) {
      var dd = EN && it.descripcion_en ? it.descripcion_en : it.descripcion;
      var d = dd ? '<span class="desc">' + esc(dd) + "</span>" : "";
      return '<li><span class="nombre">' + esc(it.nombre) + d + '</span><span class="puntos" aria-hidden="true"></span><span class="precio">' + Number(it.precio).toLocaleString("es-MX") + "</span></li>";
    }).join("") + "</ul>";
  }
  var MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  var MESES_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

  // carta viva: si la API responde, reemplaza el snapshot embebido
  var carta = document.getElementById("carta");
  if (carta && API) {
    fetch(API + "/carta", { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      if (!data || !data.secciones || !data.secciones.length) return;
      carta.innerHTML = data.secciones.map(function (s) {
        var inner = s.items && s.items.length ? items(s.items) : "";
        (s.subsecciones || []).forEach(function (sub) { inner += '<h3 class="sub">' + esc(titulo(sub.titulo)) + "</h3>" + items(sub.items); });
        return '<section class="bloque" id="' + slug(s.titulo) + '"><h2>' + esc(titulo(s.titulo)) + "</h2>" + inner + "</section>";
      }).join("");
      var nota = document.getElementById("carta-nota");
      if (nota && data.generada) {
        var d = new Date(data.generada);
        if (!isNaN(d)) nota.textContent = EN ? "Prices in Mexican pesos, tax included. Updated from our point of sale on " + MESES_EN[d.getMonth()] + " " + d.getDate() + ", " + d.getFullYear() + "." : "Precios en pesos, IVA incluido. Actualizada desde nuestro punto de venta el " + d.getDate() + " de " + MESES[d.getMonth()] + " de " + d.getFullYear() + ".";
      }
    }).catch(function () { /* se queda el snapshot */ });
  }

  // agenda de DJs: la hoja "Agenda ROSSO" vía la API
  var agendaCajas = document.querySelectorAll("[data-agenda]");
  if (agendaCajas.length && API) {
    fetch(API + "/agenda", { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      if (!data || !data.noches || !data.noches.length) return;
      agendaCajas.forEach(function (caja) {
        var max = parseInt(caja.dataset.agenda, 10) || 99;
        var lista = data.noches.slice(0, max);
        caja.innerHTML = '<ul class="agenda">' + lista.map(function (n) {
          var ig = n.instagram ? ' <a class="ig" href="https://www.instagram.com/' + esc(n.instagram) + '/" rel="noopener">@' + esc(n.instagram) + "</a>" : "";
          var pre = n.preventa ? ' <a class="enlace enlace-mini" href="' + esc(n.preventa) + '" rel="noopener">' + tt("Preventa", "Tickets") + '</a>' : "";
          var fl = EN && n.fecha_larga_en ? n.fecha_larga_en : n.fecha_larga;
          return '<li' + (n.destacado ? ' class="destacada"' : "") + '><span class="f">' + esc(fl) + (n.hora ? " · " + esc(n.hora) : "") + '</span><span class="t"><strong>' + esc(n.dj) + "</strong>" + (n.genero ? ' <span class="g">' + esc(n.genero) + "</span>" : "") + ig + pre + "</span></li>";
        }).join("") + "</ul>";
        caja.hidden = false;
        var vacio = caja.previousElementSibling;
        if (vacio && vacio.classList.contains("agenda-vacia")) vacio.hidden = true;
      });
    }).catch(function () { /* se queda el texto general */ });
  }

  // reservar: arma el link de OpenTable con fecha, hora y personas (tope = opciones del select)
  var reserva = document.getElementById("forma-reserva");
  if (reserva) {
    var rFecha = document.getElementById("r-fecha"), rHora = document.getElementById("r-hora"), rPers = document.getElementById("r-personas"), rDirecto = document.getElementById("r-directo");
    function hoyLocal() { var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
    // la página es estática: la fecha mínima y la inicial son las de HOY en el reloj del cliente, no las del día en que se construyó
    var hoy = hoyLocal();
    rFecha.min = hoy;
    if (!rFecha.value || rFecha.value < hoy) rFecha.value = hoy;
    // destino: la página RestRef de OpenTable, la misma que abre su widget oficial. Lleva restref, así que cuenta como reserva del restaurante (sin comisión).
    // Va directo a /booking/: en iPhone la app de OpenTable reclama /r/ y /restref/ (universal links) pero no /booking/, y en la app la reserva contaría como de la red.
    // El canal (?de=ads, ?de=quiz...) viaja como campaña y sale en el reporte de reservas de GuestCenter.
    var campana = CANAL !== "directo" ? CANAL : "";
    function urlRestRef(c) {
      var f = rFecha.value || hoy, h = rHora.value || "20:00", p = rPers.value || "2";
      return reserva.dataset.restref + "&lang=" + (EN ? "en-US" : "es-MX") + "&datetime=" + encodeURIComponent(f + "T" + h) + "&partysize=" + p +
        "&ot_source=Restaurant%20website" + (c ? "&ot_campaign=" + encodeURIComponent(c) : "");
    }
    // respaldo: la misma página con su propia campaña, para ver en GuestCenter cuántos entran por la liga y no por el botón
    // respaldo por OTRA ruta: la ficha pública /r/ (sin restref). Toda liga con restref acaba en /booking/restref/availability,
    // y si esa página no abrió para alguien, mandarlo de nuevo ahí no sirve. Cuenta como reserva de la red, pero la reserva ocurre.
    function urlFicha() {
      var f = rFecha.value || hoy, h = rHora.value || "20:00", p = rPers.value || "2";
      return (reserva.dataset.ficha || "https://www.opentable.com.mx/r/rosso-speakeasy-ciudad-de-mexico") + "?covers=" + p + "&dateTime=" + encodeURIComponent(f + "T" + h) + "&lang=" + (EN ? "en-US" : "es-MX");
    }
    var rRegreso = document.getElementById("r-regreso");
    function actualizarDirecto() {
      if (rDirecto) rDirecto.href = urlFicha();
      var a = rRegreso && rRegreso.querySelector("a"); if (a) a.href = urlFicha();
    }
    // si ya pulsó el botón hace poco y está de vuelta, OpenTable no le cargó: recupera su selección y ofrece la otra ruta
    try {
      var intento = JSON.parse(sessionStorage.getItem("rosso_ot_intento") || "null");
      if (intento && Date.now() - intento.t < 20 * 60 * 1000 && rRegreso) {
        if (intento.f && intento.f >= hoy) rFecha.value = intento.f;
        if (intento.h) rHora.value = intento.h;
        if (intento.p) rPers.value = intento.p;
        rRegreso.hidden = false;
        setTimeout(function () { rRegreso.scrollIntoView({ behavior: "smooth", block: "center" }); }, 300);
        if (window.ROSSO_medir) window.ROSSO_medir("opentable");
      }
    } catch (e) { /* sin storage */ }
    [rFecha, rHora, rPers].forEach(function (el) { el.addEventListener("change", actualizarDirecto); el.addEventListener("input", actualizarDirecto); });
    actualizarDirecto();
    reserva.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (rFecha.value && rFecha.value < hoy) rFecha.value = hoy;
      var url = urlRestRef(campana);
      try { sessionStorage.setItem("rosso_ot_intento", JSON.stringify({ t: Date.now(), f: rFecha.value, h: rHora.value, p: rPers.value })); } catch (e) { /* sin storage */ }
      medir("reservar");
      // navegación normal en la misma pestaña: window.open no abre nada en el navegador interno de Instagram/Facebook (iPhone)
      location.assign(url);
    });
  }

  // formulario de eventos
  var forma = document.getElementById("forma-eventos"), msg = document.getElementById("forma-msg");
  if (forma) {
    forma.addEventListener("submit", function (ev) {
      ev.preventDefault();
      msg.className = "forma-msg";
      var datos = {};
      new FormData(forma).forEach(function (v, k) { datos[k] = v; });
      var pax = parseInt(datos.personas, 10) || 0;
      if (!datos.nombre || !datos.whatsapp || !datos.fecha || !datos.hora) { msg.textContent = tt("Nos faltan nombre, WhatsApp, fecha y hora.", "We need your name, WhatsApp, date and time."); msg.classList.add("error"); return; }
      if (pax < 5) { msg.innerHTML = tt('Para 4 personas o menos reserva directo <a href="' + document.body.dataset.base + '/reservar/">aquí</a>.', 'For 4 guests or fewer, book directly <a href="' + document.body.dataset.base + '/reservar/">here</a>.'); msg.classList.add("error"); return; }
      if (!API) { msg.textContent = tt("El formulario todavía no está conectado; escríbenos por WhatsApp.", "The form is not connected yet; message us on WhatsApp."); msg.classList.add("error"); return; }
      var boton = forma.querySelector("button[type=submit]");
      boton.disabled = true; msg.textContent = tt("Enviando…", "Sending…");
      fetch(API + "/eventos", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok && res.j.ok) {
            medir("evento");
            forma.reset();
            msg.textContent = tt("Listo. Te escribimos por WhatsApp en menos de 24 horas con la propuesta (folio " + res.j.folio + ").", "Done. We will message you on WhatsApp within 24 hours with the proposal (ref. " + res.j.folio + ").");
            msg.classList.add("ok");
          } else {
            msg.textContent = (res.j && res.j.error) || tt("No se pudo enviar. Inténtalo otra vez o escríbenos por WhatsApp.", "Could not send. Try again or message us on WhatsApp.");
            msg.classList.add("error");
          }
        })
        .catch(function () { msg.textContent = tt("No se pudo enviar. Inténtalo otra vez o escríbenos por WhatsApp.", "Could not send. Try again or message us on WhatsApp."); msg.classList.add("error"); })
        .finally(function () { boton.disabled = false; });
    });
  }
})();

/* tarjetas de regalo: compra, gracias, tarjeta y canje */
(function () {
  var API = document.body.dataset.api || "", B = document.body.dataset.base || "";
  var EN = window.ROSSO_EN, tt = window.ROSSO_tt;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function pesos(n) { return "$" + Number(n || 0).toLocaleString("es-MX"); }
  function fechaLarga(iso) {
    if (!iso) return "";
    var p = iso.split("-"), M = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    var ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    return EN ? ME[parseInt(p[1], 10) - 1] + " " + parseInt(p[2], 10) + ", " + p[0] : parseInt(p[2], 10) + " de " + M[parseInt(p[1], 10) - 1] + " de " + p[0];
  }
  function canal() { try { var g = JSON.parse(localStorage.getItem("rosso_canal") || "null"); return g && g.c ? g.c : "directo"; } catch (e) { return "directo"; } }
  var msg = document.getElementById("forma-msg");
  function aviso(t, clase) { if (!msg) return; msg.textContent = t; msg.className = "forma-msg" + (clase ? " " + clase : ""); }

  // compra
  var forma = document.getElementById("forma-regalo");
  if (forma) {
    var pagar = document.getElementById("g-pagar");
    var montoElegido = function () { var r = forma.querySelector("input[name=monto]:checked"); return r ? parseInt(r.value, 10) : 0; };
    forma.addEventListener("change", function () { pagar.textContent = tt("Pagar ", "Pay ") + pesos(montoElegido()); });
    if (API) fetch(API + "/regalo/config", { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (c) {
      if (c && !c.activo) { pagar.disabled = true; aviso(tt("Las tarjetas de regalo están por activarse. Mientras, escríbenos por WhatsApp y te la armamos a mano.", "Gift cards are about to go live. Meanwhile, message us on WhatsApp and we will set one up by hand."), "error"); }
    }).catch(function () { /* nada */ });
    forma.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var d = { monto: montoElegido(), de: forma.de.value.trim(), para: forma.para.value.trim(), mensaje: forma.mensaje.value.trim(), email: forma.email.value.trim(), canal: canal() };
      if (!d.de || !d.para || !d.email) { aviso(tt("Nos faltan de parte de quién, para quién y tu correo.", "We need who it is from, who it is for and your email."), "error"); return; }
      if (!API) { aviso(tt("El pago todavía no está conectado; escríbenos por WhatsApp.", "Payment is not connected yet; message us on WhatsApp."), "error"); return; }
      pagar.disabled = true; aviso(tt("Abriendo el pago seguro…", "Opening secure checkout…"));
      fetch(API + "/regalo/checkout", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok && res.j.url) { location.href = res.j.url; return; }
          aviso((res.j && res.j.error) || tt("No se pudo iniciar el pago. Inténtalo otra vez.", "Could not start checkout. Try again."), "error"); pagar.disabled = false;
        })
        .catch(function () { aviso(tt("No se pudo iniciar el pago. Inténtalo otra vez.", "Could not start checkout. Try again."), "error"); pagar.disabled = false; });
    });
  }

  // gracias: espera el código que genera el webhook de Stripe
  var res = document.getElementById("g-resultado");
  if (res && API) {
    var sid = new URLSearchParams(location.search).get("s") || "", intentos = 0;
    var titulo = document.getElementById("g-titulo"), nota = document.getElementById("g-nota");
    var pinta = function (t) {
      titulo.textContent = tt("Listo. Aquí está tu regalo.", "Done. Here is your gift.");
      nota.textContent = tt("Tarjeta de " + pesos(t.monto) + (t.para ? " para " + t.para : "") + ". Vale hasta el " + fechaLarga(t.vence) + ".", pesos(t.monto) + " gift card" + (t.para ? " for " + t.para : "") + ". Valid until " + fechaLarga(t.vence) + ".");
      document.getElementById("g-codigo").textContent = t.codigo;
      document.getElementById("g-datos").innerHTML = (t.de ? tt("De ", "From ") + esc(t.de) : "") + (t.para ? tt(" para ", " to ") + esc(t.para) : "") + (t.mensaje ? " · <em>" + esc(t.mensaje) + "</em>" : "");
      var liga = location.origin + B + "/regalo/tarjeta/?c=" + encodeURIComponent(t.codigo);
      document.getElementById("g-ver").href = liga;
      document.getElementById("g-wa").href = "https://wa.me/?text=" + encodeURIComponent(tt("Te regalo una noche en ROSSO. Tarjeta de " + pesos(t.monto) + ". Tu código: " + t.codigo + " · " + liga, "A night at ROSSO, on me. " + pesos(t.monto) + " gift card. Your code: " + t.codigo + " · " + liga));
      document.getElementById("g-copiar").addEventListener("click", function () {
        var b = this; (navigator.clipboard ? navigator.clipboard.writeText(t.codigo) : Promise.reject()).then(function () { b.textContent = tt("Copiado", "Copied"); }, function () { b.textContent = t.codigo; });
      });
      res.hidden = false;
    };
    var consulta = function () {
      fetch(API + "/regalo/estado?s=" + encodeURIComponent(sid), { mode: "cors" }).then(function (r) { return r.json(); }).then(function (j) {
        if (j.listo) { pinta(j.tarjeta); return; }
        if (++intentos < 30) setTimeout(consulta, 2000);
        else { titulo.textContent = tt("Tu pago quedó registrado.", "Your payment was recorded."); nota.innerHTML = tt("El código tarda unos minutos en generarse. Si no te llega, <a href=\"https://wa.me/525664357899?text=" + encodeURIComponent("Hola, compré una tarjeta de regalo y no vi mi código. Mi correo es: ") + "\">escríbenos por WhatsApp</a> con el correo que usaste.", "The code takes a few minutes to generate. If it does not show up, <a href=\"https://wa.me/525664357899?text=" + encodeURIComponent("Hi, I bought a gift card and did not see my code. My email is: ") + "\">message us on WhatsApp</a> with the email you used."); }
      }).catch(function () { if (++intentos < 30) setTimeout(consulta, 3000); });
    };
    if (sid) consulta(); else { titulo.textContent = tt("Falta el número de pago.", "Payment reference missing."); nota.textContent = tt("Abre esta página desde la liga que te dio Stripe.", "Open this page from the link Stripe gave you."); }
  }

  // tarjeta imprimible
  var tarjeta = document.getElementById("tarjeta");
  if (tarjeta && API) {
    var cod = (new URLSearchParams(location.search).get("c") || "").toUpperCase();
    if (cod) fetch(API + "/regalo/saldo?c=" + encodeURIComponent(cod), { mode: "cors" }).then(function (r) { return r.json(); }).then(function (j) {
      var n = document.getElementById("t-nota");
      if (!j.tarjeta) { n.textContent = j.error || tt("No encontramos ese código.", "We could not find that code."); return; }
      var t = j.tarjeta;
      document.getElementById("t-monto").textContent = pesos(t.monto);
      document.getElementById("t-para").textContent = (t.para ? tt("Para ", "For ") + t.para : "") + (t.de ? (t.para ? tt(", de ", ", from ") : tt("De ", "From ")) + t.de : "");
      document.getElementById("t-mensaje").textContent = t.mensaje || "";
      document.getElementById("t-codigo").textContent = t.codigo;
      document.getElementById("t-vence").textContent = tt("Vale hasta ", "Valid until ") + fechaLarga(t.vence);
      n.textContent = t.estado === "activa" ? tt("Saldo disponible: " + pesos(t.saldo) + ". Preséntala en barra; con el código basta.", "Available balance: " + pesos(t.saldo) + ". Show it at the bar; the code is all you need.") : tt("Esta tarjeta está " + t.estado + ".", "This card is " + ({ agotada: "used up", vencida: "expired" }[t.estado] || t.estado) + ".");
      document.title = tt("Tarjeta ", "Card ") + t.codigo + " · ROSSO";
    }).catch(function () { document.getElementById("t-nota").textContent = tt("No se pudo cargar la tarjeta.", "Could not load the card."); });
  }

  // canje en barra
  var buscar = document.getElementById("forma-canje-buscar"), canje = document.getElementById("forma-canje"), info = document.getElementById("c-info");
  if (buscar && API) {
    var actual = null;
    var muestra = function (t) {
      actual = t;
      info.innerHTML = "<div class=\"estado\">" + esc(t.estado) + "</div><div class=\"saldo\">" + pesos(t.saldo) + " de " + pesos(t.monto) + "</div><div>" + (t.para ? "Para " + esc(t.para) : "") + (t.de ? " · de " + esc(t.de) : "") + "</div><div class=\"mini\">Vence " + esc(fechaLarga(t.vence)) + "</div>";
      info.hidden = false; canje.hidden = t.estado !== "activa";
      if (!canje.hidden) { canje.monto.max = t.saldo; canje.monto.value = ""; canje.monto.focus(); }
    };
    buscar.addEventListener("submit", function (ev) {
      ev.preventDefault(); aviso("Buscando…"); info.hidden = true; canje.hidden = true;
      var c = buscar.codigo.value.trim().toUpperCase().replace(/[^A-Z0-9-]/g, "");
      if (c.length === 8 && c.indexOf("-") < 0) c = "ROSSO-" + c.slice(0, 4) + "-" + c.slice(4);
      if (c.length === 13 && c.indexOf("ROSSO") === 0 && c.indexOf("-") < 0) c = "ROSSO-" + c.slice(5, 9) + "-" + c.slice(9);
      buscar.codigo.value = c;
      fetch(API + "/regalo/saldo?c=" + encodeURIComponent(c), { mode: "cors" }).then(function (r) { return r.json(); }).then(function (j) {
        if (!j.tarjeta) { aviso(j.error || "No existe.", "error"); return; }
        aviso(""); muestra(j.tarjeta);
      }).catch(function () { aviso("Sin conexión con la API.", "error"); });
    });
    canje.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (!actual) return;
      var monto = parseInt(canje.monto.value, 10) || 0, pin = canje.pin.value.trim();
      if (!monto || !pin) { aviso("Pon el monto y el PIN.", "error"); return; }
      aviso("Descontando…");
      fetch(API + "/regalo/canjear", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ codigo: actual.codigo, monto: monto, pin: pin }) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (r) {
          if (!r.ok) { aviso(r.j.error || "No se pudo.", "error"); return; }
          canje.pin.value = ""; muestra(r.j.tarjeta);
          aviso("Descontado " + pesos(monto) + ". Saldo: " + pesos(r.j.tarjeta.saldo) + ".", "ok");
        }).catch(function () { aviso("Sin conexión con la API.", "error"); });
    });
  }
})();

/* club ROSSO: alta de clientes */
(function () {
  var API = document.body.dataset.api || "", forma = document.getElementById("forma-club"), msg = document.getElementById("forma-msg");
  if (!forma) return;
  var tt = window.ROSSO_tt;
  function canal() { try { var g = JSON.parse(localStorage.getItem("rosso_canal") || "null"); return g && g.c ? g.c : "directo"; } catch (e) { return "directo"; } }
  forma.addEventListener("submit", function (ev) {
    ev.preventDefault();
    msg.className = "forma-msg";
    var d = { nombre: forma.nombre.value.trim(), whatsapp: forma.whatsapp.value.trim(), email: forma.email.value.trim(), cumple: forma.cumple.value.trim(), acepto: forma.acepto.checked ? 1 : 0, empresa_web: forma.empresa_web.value, canal: canal() };
    if (!d.nombre || !d.whatsapp) { msg.textContent = tt("Nos faltan tu nombre y tu WhatsApp.", "We need your name and WhatsApp."); msg.classList.add("error"); return; }
    if (!d.acepto) { msg.textContent = tt("Marca la casilla del aviso de privacidad para continuar.", "Tick the privacy notice box to continue."); msg.classList.add("error"); return; }
    if (!API) { msg.textContent = tt("El formulario no está conectado; escríbenos por WhatsApp.", "The form is not connected; message us on WhatsApp."); msg.classList.add("error"); return; }
    var boton = forma.querySelector("button[type=submit]"); boton.disabled = true; msg.textContent = tt("Guardando…", "Saving…");
    fetch(API + "/clientes", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok && res.j.ok && window.ROSSO_medir) window.ROSSO_medir("club_alta");
        if (res.ok && res.j.ok) { forma.reset(); msg.textContent = res.j.nuevo ? tt("Listo, ya estás dentro. Nos vemos en la barra.", "Done, you are in. See you at the bar.") : tt("Ya estabas en la lista. Nos vemos en la barra.", "You were already on the list. See you at the bar."); msg.classList.add("ok"); }
        else { msg.textContent = (res.j && res.j.error) || tt("No se pudo guardar. Inténtalo otra vez.", "Could not save. Try again."); msg.classList.add("error"); }
      })
      .catch(function () { msg.textContent = tt("No se pudo guardar. Inténtalo otra vez.", "Could not save. Try again."); msg.classList.add("error"); })
      .finally(function () { boton.disabled = false; });
  });
})();

/* locación para producciones */
(function () {
  var API = document.body.dataset.api || "", forma = document.getElementById("forma-produccion"), msg = document.getElementById("forma-msg");
  if (!forma) return;
  var tt = window.ROSSO_tt;
  function canal() { try { var g = JSON.parse(localStorage.getItem("rosso_canal") || "null"); return g && g.c ? g.c : "directo"; } catch (e) { return "directo"; } }
  forma.addEventListener("submit", function (ev) {
    ev.preventDefault();
    msg.className = "forma-msg";
    var d = { necesidades: [], canal: canal() };
    new FormData(forma).forEach(function (v, k) { if (k === "necesidades") d.necesidades.push(v); else d[k] = v; });
    if (!d.nombre || !d.whatsapp || !d.fecha || !d.hora || !d.crew) { msg.textContent = tt("Nos faltan nombre, WhatsApp, fecha, hora y tamaño del equipo.", "We need your name, WhatsApp, date, call time and crew size."); msg.classList.add("error"); return; }
    if (!API) { msg.textContent = tt("El formulario no está conectado; escríbenos por WhatsApp.", "The form is not connected; message us on WhatsApp."); msg.classList.add("error"); return; }
    var boton = forma.querySelector("button[type=submit]"); boton.disabled = true; msg.textContent = tt("Enviando…", "Sending…");
    fetch(API + "/produccion", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok && res.j.ok && window.ROSSO_medir) window.ROSSO_medir("produccion_envio");
        if (res.ok && res.j.ok) { forma.reset(); msg.textContent = tt("Listo. Te escribimos por WhatsApp en menos de 24 horas (folio " + res.j.folio + ").", "Done. We will message you on WhatsApp within 24 hours (ref. " + res.j.folio + ")."); msg.classList.add("ok"); }
        else { msg.textContent = (res.j && res.j.error) || tt("No se pudo enviar. Inténtalo otra vez.", "Could not send. Try again."); msg.classList.add("error"); }
      })
      .catch(function () { msg.textContent = tt("No se pudo enviar. Inténtalo otra vez o escríbenos por WhatsApp.", "Could not send. Try again or message us on WhatsApp."); msg.classList.add("error"); })
      .finally(function () { boton.disabled = false; });
  });
})();

/* vinilo del domingo */
(function () {
  var API = document.body.dataset.api || "", EN = window.ROSSO_EN, tt = window.ROSSO_tt;
  var caja = document.querySelector("[data-vinilo]"), mini = document.querySelector("[data-vinilo-mini]");
  if (!(caja || mini) || !API) return;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fecha(iso) {
    var p = iso.split("-"), M = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    return EN ? "Sunday, " + ME[+p[1] - 1] + " " + (+p[2]) : "Domingo " + (+p[2]) + " de " + M[+p[1] - 1];
  }
  fetch(API + "/vinilo", { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    if (!d || !d.vinilo) return;
    var v = d.vinilo, hoy = v.fecha === d.domingo;
    var titulo = esc(v.disco) + (v.anio ? ' <span class="g">(' + esc(v.anio) + ")</span>" : "");
    var portada = v.portada ? '<img src="' + esc(v.portada) + '" alt="' + esc(v.artista + " — " + v.disco) + '" loading="lazy">' : "";
    if (caja) {
      var ant = (d.anteriores || []).map(function (x) { return "<li>" + (x.portada ? '<img src="' + esc(x.portada) + '" alt="" loading="lazy">' : "") + "<strong>" + esc(x.disco) + "</strong>" + esc(x.artista) + "</li>"; }).join("");
      caja.innerHTML = '<div class="vinilo"><div class="vinilo-portada">' + portada + '</div><div><div class="vinilo-fecha">' + esc(fecha(v.fecha)) + (hoy ? "" : " · " + tt("último disco", "latest record")) + "</div><h2>" + titulo + '</h2><p class="artista">' + esc(v.artista) + (v.selector ? " · " + tt("elige", "picked by") + " " + esc(v.selector) : "") + "</p>" + (v.nota ? '<p class="nota">' + esc(v.nota) + "</p>" : "") + (v.embed ? '<iframe src="' + esc(v.embed) + '?theme=0" loading="lazy" allow="encrypted-media" title="Spotify"></iframe>' : v.spotify ? '<a class="enlace" href="' + esc(v.spotify) + '" rel="noopener">Spotify</a>' : "") + "</div></div>" + (ant ? '<div class="etiqueta" style="margin-top:2.5rem">' + tt("Domingos anteriores", "Past Sundays") + '</div><ul class="vinilo-anteriores">' + ant + "</ul>" : "");
      caja.hidden = false;
      var vacio = document.querySelector(".vinilo-vacio"); if (vacio) vacio.hidden = true;
    }
    if (mini && hoy) {
      mini.innerHTML = '<a class="vinilo-mini" href="' + document.body.dataset.base + '/noches/#vinilo">' + portada + '<span class="t"><strong>' + tt("Vinilo del domingo", "Sunday vinyl") + "</strong>" + esc(v.artista) + " — " + esc(v.disco) + "</span></a>";
      mini.hidden = false;
    }
  }).catch(function () { /* nada */ });
})();

/* esta noche (inicio) + reservar con fecha en la liga */
(function () {
  var API = document.body.dataset.api || "", B = document.body.dataset.base || "", EN = window.ROSSO_EN, tt = window.ROSSO_tt;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function hoyISO() { var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  var fecha = document.getElementById("r-fecha");
  if (fecha) { var q = new URLSearchParams(location.search).get("fecha"); if (q && /^\d{4}-\d{2}-\d{2}$/.test(q) && q >= hoyISO()) { fecha.min = hoyISO(); fecha.value = q; fecha.dispatchEvent(new Event("change")); } }
  var caja = document.querySelector("[data-hoy]");
  if (!caja || !API) return;
  var hoy = hoyISO(), dow = new Date().getDay();   // 0 domingo, 1 lunes
  function pinta(html) { caja.innerHTML = html; caja.hidden = false; }
  var reservaHoy = '<a class="enlace" href="' + B + '/reservar/?fecha=' + hoy + '">' + tt("Reservar hoy", "Book tonight") + "</a>";
  if (dow === 1) { pinta('<span class="k">' + tt("Hoy", "Today") + '</span><span class="t">' + tt("Lunes cerrado. Nos vemos mañana desde las 6 pm.", "Closed on Mondays. See you tomorrow from 6 pm.") + "</span>"); return; }
  if (dow === 0) {
    fetch(API + "/vinilo", { mode: "cors" }).then(function (r) { return r.json(); }).then(function (d) {
      var v = d && d.vinilo;
      if (v && v.fecha === hoy) pinta('<span class="k">' + tt("Hoy", "Today") + "</span>" + (v.portada ? '<img src="' + esc(v.portada) + '" alt="">' : "") + '<span class="t"><strong>' + tt("Vinilo del domingo", "Sunday vinyl") + ":</strong> " + esc(v.artista) + " — " + esc(v.disco) + " · 4 pm</span>" + reservaHoy);
      else pinta('<span class="k">' + tt("Hoy", "Today") + '</span><span class="t">' + tt("Domingo de vinilos completos, 4 a 11 pm.", "Full-vinyl Sunday, 4 to 11 pm.") + "</span>" + reservaHoy);
    }).catch(function () { });
    return;
  }
  fetch(API + "/agenda", { mode: "cors" }).then(function (r) { return r.json(); }).then(function (d) {
    var n = (d.noches || []).filter(function (x) { return x.fecha === hoy; })[0];
    if (n) pinta('<span class="k">' + tt("Hoy", "Today") + '</span><span class="t"><strong>' + esc(n.dj) + "</strong>" + (n.genero ? " · " + esc(n.genero) : "") + (n.hora ? " · " + esc(n.hora) : "") + "</span>" + reservaHoy);
    else if (dow === 2) pinta('<span class="k">' + tt("Hoy", "Today") + '</span><span class="t">' + tt("Martes tranquilo: barra abierta desde las 6 pm.", "Quiet Tuesday: bar open from 6 pm.") + "</span>" + reservaHoy);
    else pinta('<span class="k">' + tt("Hoy", "Today") + '</span><span class="t">' + tt("Sesión de DJ desde las 9 pm.", "DJ session from 9 pm.") + "</span>" + reservaHoy);
  }).catch(function () { });
})();

/* selectores: lista en noches, liga en la agenda y perfil */
(function () {
  var API = document.body.dataset.api || "", B = document.body.dataset.base || "", EN = window.ROSSO_EN, tt = window.ROSSO_tt;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function fl(iso) { var p = iso.split("-"), M = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]; return EN ? ME[+p[1] - 1] + " " + (+p[2]) : (+p[2]) + " de " + M[+p[1] - 1]; }
  var lista = document.querySelector("[data-djs]");
  if (lista && API) fetch(API + "/djs", { mode: "cors" }).then(function (r) { return r.json(); }).then(function (d) {
    if (!d.djs || !d.djs.length) return;
    lista.innerHTML = '<ul class="djs">' + d.djs.map(function (x) {
      return '<li><a href="' + B + "/dj/?n=" + encodeURIComponent(x.slug) + '">' + esc(x.dj) + "</a>" + (x.genero ? '<span class="g">' + esc(x.genero) + "</span>" : "") + '<span class="p">' + (x.proxima ? tt("vuelve el ", "back on ") + esc(fl(x.proxima)) : x.fechas + " " + tt(x.fechas === 1 ? "noche" : "noches", x.fechas === 1 ? "night" : "nights")) + "</span></li>";
    }).join("") + "</ul>";
    lista.hidden = false;
  }).catch(function () { });
  // en las agendas, el nombre del DJ enlaza a su perfil
  document.querySelectorAll("[data-agenda]").forEach(function (caja) {
    new MutationObserver(function () {
      caja.querySelectorAll("li .t > strong").forEach(function (st) {
        if (st.querySelector("a")) return;
        var slug = st.textContent.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
        st.innerHTML = '<a href="' + B + "/dj/?n=" + encodeURIComponent(slug) + '">' + esc(st.textContent) + "</a>";
      });
    }).observe(caja, { childList: true, subtree: true });
  });
  var perfil = document.getElementById("dj");
  if (perfil && API) {
    var k = (new URLSearchParams(location.search).get("n") || "").toLowerCase().replace(/[^a-z0-9-]/g, "");
    var MARIDAJE = {}; try { MARIDAJE = JSON.parse(document.getElementById("dj-maridaje").textContent); } catch (e) { }
    // qué pedir según lo que suena; el orden importa: gana la primera coincidencia
    var REGLAS = [[/italo|synth|new wave|pop/i, "rosso-tonic"], [/hip.?hop|rap|r&b|rnb/i, "pellizco"], [/latin|mundo|world|afro|cumbia|salsa|tropical/i, "camasotz"],
                  [/house|techno|electr/i, "picarilla"], [/disco|funk|boogie/i, "sabor-a-mi"], [/soul|jazz|groove|cinematic/i, "querido-diario"]];
    function slugDe(t) { return String(t || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, ""); }
    function pon(id, txt) { var el = document.getElementById(id); if (el) el.textContent = txt; return el; }
    fetch(API + "/dj/" + k, { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) { pon("dj-nombre", "ROSSO"); document.getElementById("dj-error").hidden = false; return; }
      var p = d.perfil || {};
      pon("dj-nombre", p.dj || k);
      document.title = (p.dj || k) + " · ROSSO";
      var generos = String(p.genero || "").split(/\s*(?:,|&|\/|\sy\s|\sand\s)\s*/).map(function (g) { return g.trim(); }).filter(Boolean);
      document.getElementById("dj-chips").innerHTML = generos.map(function (g) { return "<span>" + esc(g) + "</span>"; }).join("");
      document.getElementById("dj-ig").innerHTML = (p.instagram ? '<a class="enlace" href="https://www.instagram.com/' + esc(p.instagram) + '/" rel="noopener">@' + esc(p.instagram) + "</a>" : "")
        + (p.musica ? ' <a class="enlace" href="' + esc(p.musica) + '" rel="noopener">' + tt("Escúchalo", "Listen") + "</a>" : "");
      pon("dj-resumen", tt(p.fechas + (p.fechas === 1 ? " noche" : " noches") + " en ROSSO.", p.fechas + (p.fechas === 1 ? " night" : " nights") + " at ROSSO."));
      if (p.bio) { pon("dj-bio", p.bio).hidden = false; }
      if (p.foto) { var f = document.getElementById("dj-foto"); f.innerHTML = '<img src="' + esc(p.foto) + '" alt="' + esc(p.dj || "") + '" loading="lazy">'; f.hidden = false; }
      // próxima fecha, con reserva de esa noche
      var n = d.proximas[0];
      if (n) {
        var hoy = new Date(), hoyISO = hoy.getFullYear() + "-" + String(hoy.getMonth() + 1).padStart(2, "0") + "-" + String(hoy.getDate()).padStart(2, "0");
        if (n.fecha === hoyISO) pon("dj-proxima-k", tt("Hoy toca", "Playing tonight"));
        pon("dj-proxima-fecha", (EN && n.fecha_larga_en ? n.fecha_larga_en : n.fecha_larga) + (n.hora ? " · " + n.hora : ""));
        document.getElementById("dj-reservar").href = B + "/reservar/?fecha=" + n.fecha;
        document.getElementById("dj-proxima").hidden = false;
      }
      // trago: el que eligió el DJ en la hoja, o el maridaje por género
      var trago = null, deDJ = false;
      if (p.trago && MARIDAJE[slugDe(p.trago)]) { trago = MARIDAJE[slugDe(p.trago)]; deDJ = true; }
      if (!trago) { for (var i = 0; i < REGLAS.length; i++) { if (REGLAS[i][0].test(p.genero || "")) { trago = MARIDAJE[REGLAS[i][1]]; break; } } }
      if (!trago) trago = MARIDAJE["l-origine-du-monde"];
      if (trago) {
        if (deDJ) pon("dj-trago-k", (p.dj || "") + " " + tt("toma", "drinks"));
        pon("dj-trago-nombre", trago.nombre); pon("dj-trago-notas", trago.notas); pon("dj-trago-ing", trago.ingredientes);
        document.getElementById("dj-trago").hidden = false;
      }
      function li(n, conDJ) { return '<li><span class="f">' + esc(EN && n.fecha_larga_en ? n.fecha_larga_en : n.fecha_larga) + (n.hora ? " · " + esc(n.hora) : "") + '</span><span class="t">' + (conDJ ? '<strong><a href="' + B + "/dj/?n=" + encodeURIComponent(n.slug) + '">' + esc(n.dj) + "</a></strong> " : "") + (n.genero ? '<span class="g">' + esc(n.genero) + "</span>" : "") + (n.preventa ? ' <a class="enlace enlace-mini" href="' + esc(n.preventa) + '" rel="noopener">' + tt("Preventa", "Tickets") + "</a>" : "") + "</span></li>"; }
      var resto = d.proximas.slice(1);
      document.getElementById("dj-proximas").innerHTML = resto.map(function (x) { return li(x); }).join("");
      if (!resto.length) { document.getElementById("dj-proximas").hidden = true; document.getElementById("dj-prox-k").hidden = true; }
      document.getElementById("dj-pasadas").innerHTML = d.pasadas.map(function (x) { return li(x); }).join("");
      if (!d.pasadas.length) { var hp = document.getElementById("dj-pasadas"); hp.hidden = true; hp.previousElementSibling.hidden = true; }
      if (d.semana && d.semana.length) { document.getElementById("dj-semana").innerHTML = d.semana.map(function (x) { return li(x, true); }).join(""); document.getElementById("dj-semana-caja").hidden = false; }
      perfil.hidden = false;
    }).catch(function () { document.getElementById("dj-error").hidden = false; });
  }
})();

/* Sello ROSSO (barra) */
(function () {
  var API = document.body.dataset.api || "", forma = document.getElementById("forma-sello-buscar"), lista = document.getElementById("s-lista"), msg = document.getElementById("forma-msg");
  if (!forma || !API) return;
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function aviso(t, c) { msg.textContent = t; msg.className = "forma-msg" + (c ? " " + c : ""); }
  function sellos(n, cada) { var k = n % cada, s = ""; for (var i = 0; i < cada; i++) s += i < k ? "●" : "○"; return s; }
  function pinta(cl, cada) {
    lista.innerHTML = cl.map(function (c) {
      return '<div class="sello-item" data-wa="' + esc(c.whatsapp) + '"><div><div class="n">' + esc(c.nombre) + ' <span class="d">· …' + esc(c.fin) + "</span></div><div class=\"d\">" + c.visitas + " visitas" + (c.ultima ? " · última " + esc(c.ultima.slice(0, 10)) : "") + " · faltan " + c.faltan + " para el cóctel</div></div><div class=\"sellos\">" + sellos(c.visitas, cada) + '</div><button class="btn" type="button">Registrar visita</button></div>';
    }).join("");
  }
  forma.addEventListener("submit", function (ev) {
    ev.preventDefault(); aviso("Buscando…"); lista.innerHTML = "";
    var pin = forma.pin.value.trim();
    fetch(API + "/sello/buscar?q=" + encodeURIComponent(forma.q.value.trim()), { mode: "cors", headers: { "X-Pin": pin } })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (r) {
        if (!r.ok) { aviso(r.j.error || "No se pudo.", "error"); return; }
        if (!r.j.clientes.length) { aviso("No está en el Club con esos datos.", "error"); return; }
        aviso(""); pinta(r.j.clientes, r.j.premio_cada);
      }).catch(function () { aviso("Sin conexión con la API.", "error"); });
  });
  lista.addEventListener("click", function (ev) {
    var b = ev.target.closest("button"); if (!b) return;
    var item = b.closest(".sello-item"); b.disabled = true; aviso("Registrando…");
    fetch(API + "/sello/registrar", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ whatsapp: item.dataset.wa, pin: forma.pin.value.trim(), quien: "barra" }) })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (r) {
        if (!r.ok) { aviso(r.j.error || "No se pudo.", "error"); b.disabled = false; return; }
        item.classList.toggle("premio", r.j.premio);
        aviso(r.j.premio ? "¡Visita " + r.j.visitas + "! Toca cóctel de la casa para " + r.j.nombre + "." : "Visita " + r.j.visitas + " registrada. Faltan " + r.j.faltan + " para el cóctel.", "ok");
        b.textContent = r.j.premio ? "¡Premio!" : "Registrada";
      }).catch(function () { aviso("Sin conexión con la API.", "error"); b.disabled = false; });
  });
})();

/* quiz: ¿qué cóctel eres? */
(function () {
  var nodo = document.getElementById("q-datos"), caja = document.getElementById("q-caja");
  if (!nodo || !caja) return;
  var EN = window.ROSSO_EN, tt = window.ROSSO_tt, D = JSON.parse(nodo.textContent);
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  var puntos = {}, i = 0, sinAlcohol = false, barra = document.getElementById("q-barra");
  function pregunta() {
    var p = D.preguntas[i];
    barra.style.width = (i / D.preguntas.length * 100) + "%";
    caja.innerHTML = '<div class="q-num">' + (i + 1) + " / " + D.preguntas.length + (p.sentido ? " · " + esc(p.sentido) : "") + "</div><h2>" + esc(p.q) + '</h2><ul class="q-opciones">' + p.opciones.map(function (o, k) { return '<li><button type="button" data-k="' + k + '">' + esc(o.t) + "</button></li>"; }).join("") + "</ul>";
    var b = caja.querySelector("button"); if (b && i > 0) b.focus();
  }
  caja.addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-k]"); if (!b) return;
    var o = D.preguntas[i].opciones[+b.dataset.k];
    o.rasgos.forEach(function (r) { puntos[r] = (puntos[r] || 0) + 1; });
    if (o.sin_alcohol) sinAlcohol = true;
    if (i === 0 && window.ROSSO_medir) window.ROSSO_medir("quiz_inicio");   // contestó la primera: para ver dónde se van
    i++;
    if (i < D.preguntas.length) pregunta(); else resultado(mejor());
  });
  function mejor() {
    var BASES = { agave: 1, gin: 1, ron: 1, whiskey: 1, vermut: 1 };
    var elegidas = Object.keys(puntos).filter(function (r) { return BASES[r]; });
    var cand = D.cocteles.filter(function (c) {
      if (sinAlcohol) return c.sin_alcohol;
      if (c.sin_alcohol) return false;
      return !elegidas.length || c.rasgos.some(function (r) { return elegidas.indexOf(r) >= 0; });   // la base elegida filtra
    });
    var top = null, max = -1;
    cand.forEach(function (c) {
      var s = 0; c.rasgos.forEach(function (r, idx) { if (!BASES[r]) s += (puntos[r] || 0) * (idx < 3 ? 2 : 1); });   // los 3 primeros rasgos pesan doble
      if (s > max) { max = s; top = c; }
    });
    return top;
  }
  function resultado(c) {
    barra.style.width = "100%";
    caja.hidden = true;
    var fijo = document.getElementById("q-fijo"); if (fijo) fijo.hidden = true;   // el resultado trae su propio botón
    document.getElementById("q-nombre").textContent = c.nombre;
    document.getElementById("q-notas").textContent = c.notas;
    document.getElementById("q-ingredientes").textContent = c.ingredientes;
    document.getElementById("q-porque").textContent = c.porque;
    var res = document.getElementById("q-resultado"); res.hidden = false;
    var fig = document.getElementById("q-foto"), conFoto = (res.dataset.fotos || "").split(" ").indexOf(c.slug) >= 0;
    if (fig) {
      if (conFoto) {
        var img = fig.querySelector("img"), A = document.body.dataset.assets || "";
        img.src = A + "/assets/fotos/cocteles/" + c.slug + "-m.jpg";
        img.srcset = A + "/assets/fotos/cocteles/" + c.slug + "-m.jpg 640w, " + A + "/assets/fotos/cocteles/" + c.slug + ".jpg 1200w";
        img.sizes = "(min-width: 900px) 420px, 100vw"; img.alt = c.nombre;
      }
      fig.hidden = !conFoto; res.classList.toggle("con-foto", conFoto);
    }
    document.title = tt("Soy ", "I am ") + c.nombre + " · ROSSO";
    try { history.replaceState(null, "", location.pathname + "?r=" + c.slug); } catch (e) { }
    if (window.ROSSO_medir) window.ROSSO_medir("quiz");
    var liga = location.origin + location.pathname + "?r=" + c.slug;
    var texto = tt("Hice el quiz de ROSSO y soy " + c.nombre + ". ¿Y tú?", "I took the ROSSO quiz and I am " + c.nombre + ". What about you?");
    document.getElementById("q-compartir").onclick = function () {
      var b = this;
      if (navigator.share) { navigator.share({ title: "ROSSO", text: texto, url: liga }).catch(function () { }); return; }
      (navigator.clipboard ? navigator.clipboard.writeText(texto + " " + liga) : Promise.reject()).then(function () { b.textContent = tt("Liga copiada", "Link copied"); }, function () { prompt(tt("Copia la liga:", "Copy the link:"), liga); });
    };
    res.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  var r = new URLSearchParams(location.search).get("r");
  var previo = r && D.cocteles.filter(function (c) { return c.slug === r; })[0];
  if (previo) {
    resultado(previo);
    var vuelve = document.createElement("p"); vuelve.className = "nota";
    vuelve.innerHTML = '<a class="enlace" href="' + location.pathname + '">' + tt("Haz el quiz tú también", "Take the quiz yourself") + "</a>";
    document.getElementById("q-resultado").appendChild(vuelve);
  } else pregunta();
})();

/* perfil de DJ: imagen 1080x1920 para historia de Instagram, hecha en el teléfono */
(function () {
  var boton = document.getElementById("dj-historia");
  if (!boton) return;
  var API = document.body.dataset.api || "", EN = window.ROSSO_EN, tt = window.ROSSO_tt;
  var k = (new URLSearchParams(location.search).get("n") || "").toLowerCase().replace(/[^a-z0-9-]/g, "");
  var datos = null;
  fetch(API + "/dj/" + k, { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    if (!d || !d.proximas || !d.proximas.length) return;
    datos = d; boton.hidden = false;
  }).catch(function () { });
  function lineas(ctx, texto, maxw) {
    var pal = texto.split(" "), out = [], cur = "";
    pal.forEach(function (w) { var t = cur ? cur + " " + w : w; if (ctx.measureText(t).width > maxw && cur) { out.push(cur); cur = w; } else cur = t; });
    if (cur) out.push(cur); return out;
  }
  boton.addEventListener("click", function () {
    var n = datos.proximas[0], p = datos.perfil || {};
    var W = 1080, H = 1920, c = document.createElement("canvas"); c.width = W; c.height = H;
    var x = c.getContext("2d");
    x.fillStyle = "#28000F"; x.fillRect(0, 0, W, H);
    var fondo = new Image(), logo = new Image(), listos = 0;
    function listo() { if (++listos === 2) pinta(); }
    fondo.onload = listo; fondo.onerror = function () { fondo = null; listo(); };
    logo.onload = listo;
    fondo.src = "/assets/fotos/espacio_vistaconsola-m.jpg";
    function pinta() {
      if (fondo) {   // foto de la cabina cubriendo el lienzo, con velo vino para que el texto se lea
        var e = Math.max(W / fondo.width, H / fondo.height), fw = fondo.width * e, fh = fondo.height * e;
        x.drawImage(fondo, (W - fw) / 2, (H - fh) / 2, fw, fh);
        var g = x.createLinearGradient(0, 0, 0, H); g.addColorStop(0, "rgba(40,0,15,.78)"); g.addColorStop(.5, "rgba(40,0,15,.62)"); g.addColorStop(1, "rgba(40,0,15,.92)");
        x.fillStyle = g; x.fillRect(0, 0, W, H);
      }
      x.fillStyle = "#B40519"; x.fillRect(0, 0, W, 28); x.fillRect(0, H - 28, W, 28);
      (function () {
      var lw = 760, lh = lw * 252 / 1280; x.drawImage(logo, (W - lw) / 2, 230, lw, lh);
      x.textAlign = "center"; x.fillStyle = "#E0364A";
      x.font = "500 34px 'Geist Mono', monospace";
      x.fillText((EN ? "T O N I G H T   A T   R O S S O" : "E S T A   N O C H E   E N   R O S S O"), W / 2, 560);
      x.fillStyle = "#E5E8E8"; x.font = "900 130px Geist, Helvetica, Arial, sans-serif";
      var y = 760; lineas(x, (p.dj || k).toUpperCase(), W - 160).forEach(function (l) { x.fillText(l, W / 2, y); y += 140; });
      x.font = "400 50px Geist, Helvetica, Arial, sans-serif"; x.fillStyle = "rgba(229,232,232,.75)";
      if (n.genero) { lineas(x, n.genero, W - 200).forEach(function (l) { x.fillText(l, W / 2, y + 10); y += 66; }); }
      x.fillStyle = "#E0364A"; x.font = "500 40px 'Geist Mono', monospace";
      x.fillText(((EN && n.fecha_larga_en ? n.fecha_larga_en : n.fecha_larga) + (n.hora ? "  ·  " + n.hora : "")).toUpperCase(), W / 2, y + 110);
      x.fillStyle = "#E5E8E8"; x.font = "400 38px Geist, Helvetica, Arial, sans-serif";
      x.fillText("Puebla 329, Roma Norte · " + (EN ? "through the kitchen" : "se entra por la cocina"), W / 2, H - 330);
      x.font = "500 44px 'Geist Mono', monospace"; x.fillText("rossospeakeasy.com/dj", W / 2, H - 250);
      x.font = "500 38px 'Geist Mono', monospace"; x.fillStyle = "rgba(229,232,232,.85)";
      x.fillText(EN ? "\u2191  TAP THE STICKER TO BOOK" : "\u2191  TOCA EL STICKER PARA RESERVAR", W / 2, H - 170);
      c.toBlob(function (blob) {
        var archivo = new File([blob], "rosso-" + k + ".png", { type: "image/png" });
        var liga = "https://rossospeakeasy.com/dj/?n=" + k + "&de=dj";
        if (navigator.canShare && navigator.canShare({ files: [archivo] })) {
          navigator.share({ files: [archivo], text: (EN ? "Tonight at ROSSO. Book: " : "Hoy toco en ROSSO. Reserva: ") + liga }).catch(function () { });
        } else {
          var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = archivo.name; a.click();
        }
      }, "image/png");
      })();
    }
    logo.src = (document.querySelector(".marca img") || {}).src || "/assets/rosso-wordmark-letras.svg";
  });
})();

/* boletos de shows: compra, gracias, puerta y aviso en portada */
(function () {
  var API = document.body.dataset.api || "";
  var EN = window.ROSSO_EN, tt = window.ROSSO_tt;
  function $(id) { return document.getElementById(id); }
  function pesos(n) { return "$" + Number(n || 0).toLocaleString("es-MX"); }
  function hora12(h) {
    if (!h) return "";
    var p = String(h).split(":"), hh = parseInt(p[0], 10), mm = p[1] || "00";
    return ((hh + 11) % 12 + 1) + ":" + mm + (hh < 12 ? " am" : " pm");
  }
  function fechaLarga(iso) {
    if (!iso) return "";
    var p = iso.split("-"), d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2])), w = d.getUTCDay();
    var M = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    var ME = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
    var D = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"], DE = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    return EN ? DE[w] + ", " + ME[+p[1] - 1] + " " + (+p[2]) : D[w] + " " + (+p[2]) + " de " + M[+p[1] - 1];
  }
  function canal() { try { var g = JSON.parse(localStorage.getItem("rosso_canal") || "null"); return g && g.c ? g.c : "directo"; } catch (e) { return "directo"; } }
  var msg = $("forma-msg");
  // origen: quién puso el mensaje ("pinta" = el refresco de cupo); el refresco sólo borra los suyos
  function aviso(t, clase, origen) {
    if (!msg) return;
    msg.textContent = t; msg.className = "forma-msg" + (clase ? " " + clase : ""); msg.dataset.origen = origen || "";
  }
  function post(ruta, datos) {
    return fetch(API + ruta, { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, j: j || {} }; }); });
  }
  function nuevaOp() {
    try { if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); } catch (e) { /* sin crypto */ }
    return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 12);
  }
  var ESTADOS = {
    por_abrir: tt("La venta abre pronto", "Sales open soon"),
    pausada: tt("Venta en pausa", "Sales paused"),
    cerrada_en_linea: tt("Venta en línea cerrada; pregunta en la puerta", "Online sales closed; ask at the door"),
    pasada: tt("Ya pasó", "Over"),
    agotada: tt("Agotado", "Sold out"),
    en_pago: tt("Lugares en proceso de pago; vuelve en 20 min", "Seats being paid for; check back in 20 min")
  };
  // el API contesta en español; en /en/ se traduce por código
  function errorCompra(j) {
    if (!EN || !j || !j.codigo) return (j && j.error) || tt("No se pudo iniciar el pago. Inténtalo otra vez.", "Could not start checkout. Try again.");
    var T = {
      correo: "Check your email address.", nombre: "We need your name (it is the one we look up at the door).",
      cantidad: "You can buy 1 to " + (j.max || 4) + " tickets per purchase.", sesion: "Pick a set.", show: "That show does not exist.",
      quedan: "Only " + j.quedan + " seats left in this set.", agotada: "This set is sold out.",
      en_pago: "No seats right now; some payments are in progress, try again in 20 minutes.",
      tope: "There are other payments in progress from your connection; finish them or wait a few minutes.",
      carrera: "The last seats were just taken; try fewer tickets or try again in a few minutes.",
      por_abrir: "Sales have not opened yet.", pausada: "Sales are paused; message us on WhatsApp.",
      cerrada_en_linea: "Online sales for this set have closed; ask at the door.", pasada: "This set is over.",
      ocupado: "Many people are buying right now; try again in a few seconds.", inactivo: "Ticket sales are not open yet.",
      stripe: "Could not start checkout; try again."
    };
    return T[j.codigo] || "Could not start checkout. Try again.";
  }
  function prioridad(sesiones) {   // el estado que vale la pena decir cuando ninguna sesión está abierta
    var orden = ["en_pago", "cerrada_en_linea", "pausada", "por_abrir", "agotada", "pasada"];
    for (var i = 0; i < orden.length; i++) for (var k = 0; k < sesiones.length; k++) if (sesiones[k].estado === orden[i]) return orden[i];
    return "";
  }
  function nota(x) { return x.estado === "abierta" ? (EN ? x.quedan + " left" : "Quedan " + x.quedan) : (ESTADOS[x.estado] || ""); }

  // ---------------- página del show
  var forma = $("forma-boletos"), datosEl = $("b-datos");
  if (forma && datosEl) {
    var D = JSON.parse(datosEl.textContent), pagar = $("b-pagar"), info = null, primera = true;
    var radio = function () { return forma.querySelector("input[name=sesion]:checked"); };
    var sel = function () { var r = radio(); return r ? r.value : ""; };
    var cuantos = function () { return parseInt(forma.cantidad.value, 10) || 1; };
    var etiqueta = function () {
      var r = radio(), nombre = r ? r.closest(".monto").querySelector(".monto-cifra").textContent : "";
      pagar.textContent = tt("Pagar ", "Pay ") + pesos(D.precio * cuantos()) + (nombre ? " · " + nombre : "");
    };
    var pinta = function () {
      if (!info) return;
      var abiertas = 0, perdida = "";
      info.sesiones.forEach(function (x) {
        var n = forma.querySelector("[data-cupo='" + x.id + "']"), r = forma.querySelector("input[name=sesion][value='" + x.id + "']");
        if (n) n.textContent = tt("Puertas ", "Doors ") + hora12(x.puertas) + " · " + nota(x);
        var ok = x.estado === "abierta";
        if (r) {
          r.disabled = !ok; r.closest(".monto").classList.toggle("agotado", !ok);
          if (!ok && r.checked) { r.checked = false; if (!primera) perdida = EN ? x.en : x.es; }
        }
        if (ok) abiertas++;
      });
      if (primera && !sel()) { var otra = forma.querySelector("input[name=sesion]:not(:disabled)"); if (otra) otra.checked = true; }
      primera = false;
      etiqueta();
      pagar.disabled = !abiertas || !sel();
      if (perdida) aviso(tt("La sesión de las " + perdida + " se llenó o tiene pagos en curso. Elige otra.", "The " + perdida + " set filled up or has payments in progress. Pick another one."), "error");
      else if (!abiertas) aviso((ESTADOS[prioridad(info.sesiones)] || tt("Ahorita no hay lugares en línea", "No seats online right now")) + ".", "error", "pinta");
      else if (msg && msg.dataset.origen === "pinta") aviso("");
    };
    var cargar = function () {
      if (!API) return;
      fetch(API + "/boletos/show/" + encodeURIComponent(D.slug), { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (!j) return;
        if (!j.activo) { pagar.disabled = true; aviso(tt("La venta en línea abre muy pronto.", "Online sales open very soon."), "error", "pinta"); return; }
        info = j; pinta();
      }).catch(function () { /* se queda lo que dice la página */ });
    };
    forma.addEventListener("change", function () { etiqueta(); if (info) pagar.disabled = !sel() || !!pagar.dataset.ocupado; });
    etiqueta(); cargar(); setInterval(function () { if (!document.hidden && !pagar.dataset.ocupado) cargar(); }, 60000);
    // volvió con "atrás" desde Stripe y el navegador restauró la página tal cual
    window.addEventListener("pageshow", function (e) { if (e.persisted) { delete pagar.dataset.ocupado; pagar.disabled = false; aviso(""); cargar(); } });

    // regresó de Stripe sin pagar: se sueltan sus lugares
    var q = new URLSearchParams(location.search), hold = q.get("cancelado");
    if (hold && API) {
      history.replaceState(null, "", location.pathname);
      post("/boletos/cancelar", { show: D.slug, sesion: q.get("f") || "", hold: hold }).then(function (r) {
        if (r.ok && r.j.pagado && r.j.compra) aviso(tt("Tu pago sí entró. Tu código: ", "Your payment went through. Your code: ") + r.j.compra.codigo, "ok");
        else if (r.ok) aviso(tt("Cancelaste el pago; tus lugares quedaron libres. Puedes volver a intentarlo.", "You cancelled the payment; your seats were released. You can try again."));
        cargar();
      }).catch(function () { /* se liberan solos */ });
    }

    forma.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var d = { show: D.slug, sesion: sel(), cantidad: cuantos(), nombre: forma.nombre.value.trim(), email: forma.email.value.trim(),
                whatsapp: forma.whatsapp.value.trim(), canal: canal(), idioma: EN ? "en" : "es", empresa_web: forma.empresa_web.value };
      if (!d.sesion) { aviso(tt("Elige la sesión.", "Pick a set."), "error"); return; }
      if (d.nombre.length < 2 || !d.email) { aviso(tt("Nos faltan tu nombre y tu correo.", "We need your name and email."), "error"); return; }
      if (!API) { aviso(tt("El pago todavía no está conectado; escríbenos por WhatsApp.", "Payment is not connected yet; message us on WhatsApp."), "error"); return; }
      pagar.disabled = true; pagar.dataset.ocupado = "1"; aviso(tt("Apartando tus lugares…", "Holding your seats…"));
      if (window.ROSSO_medir) window.ROSSO_medir("boleto_pago");
      post("/boletos/checkout", d).then(function (r) {
        if (r.ok && r.j.url) { location.href = r.j.url; return; }
        delete pagar.dataset.ocupado;
        aviso(errorCompra(r.j), "error");
        pagar.disabled = false; cargar();
      }).catch(function () {
        delete pagar.dataset.ocupado;
        aviso(tt("No se pudo iniciar el pago. Inténtalo otra vez.", "Could not start checkout. Try again."), "error"); pagar.disabled = false;
      });
    });
  }

  // ---------------- gracias: espera el registro del pago
  var res = $("b-resultado");
  if (res && API) {
    var qs = new URLSearchParams(location.search), ref = { b: qs.get("b") || "", f: qs.get("f") || "", s: qs.get("s") || "" };
    try {
      if (ref.s) sessionStorage.setItem("rosso_boleto", JSON.stringify(ref));
      else ref = JSON.parse(sessionStorage.getItem("rosso_boleto") || "null") || ref;
    } catch (e) { /* sin storage */ }
    if (qs.get("s")) history.replaceState(null, "", location.pathname);   // que el id del pago no se quede en la barra
    var titulo = $("b-titulo"), notaG = $("b-nota"), intentos = 0;
    var waRosso = function (texto) {
      var a = document.createElement("a");
      a.href = "https://wa.me/525664357899?text=" + encodeURIComponent(texto);
      a.textContent = tt("escríbenos por WhatsApp", "message us on WhatsApp");
      return a;
    };
    var pintaG = function (c) {
      if (c.estado === "anulada") {
        titulo.textContent = tt("Este boleto fue cancelado.", "This ticket was cancelled.");
        notaG.textContent = tt("Si crees que es un error, ", "If you think this is a mistake, ");
        notaG.appendChild(waRosso(tt("Hola, mi boleto " + c.codigo + " aparece cancelado.", "Hi, my ticket " + c.codigo + " shows as cancelled.")));
        notaG.appendChild(document.createTextNode("."));
        return;
      }
      var ses = (EN ? c.sesion.en : c.sesion.es) || hora12(c.sesion.hora);
      titulo.textContent = tt("Listo. Nos vemos en ROSSO.", "Done. See you at ROSSO.");
      notaG.textContent = c.cantidad + (EN ? (c.cantidad === 1 ? " ticket" : " tickets") : (c.cantidad === 1 ? " boleto" : " boletos")) + " · " + c.artista + " · "
        + fechaLarga(c.fecha) + " · " + ses + " (" + tt("puertas ", "doors ") + hora12(c.sesion.puertas) + ")";
      $("b-codigo").textContent = c.codigo;
      $("b-datos-compra").textContent = tt("A nombre de ", "Under the name ") + c.nombre;
      var texto = tt("Mis boletos para " + c.artista + " en ROSSO: " + fechaLarga(c.fecha) + ", " + ses + ". Código " + c.codigo + " a nombre de " + c.nombre + ". Puebla 329, Roma Norte.",
                     "My tickets for " + c.artista + " at ROSSO: " + fechaLarga(c.fecha) + ", " + ses + ". Code " + c.codigo + " under " + c.nombre + ". Puebla 329, Roma Norte.");
      $("b-wa").href = "https://wa.me/?text=" + encodeURIComponent(texto);
      $("b-copiar").onclick = function () {
        var b = this; (navigator.clipboard ? navigator.clipboard.writeText(c.codigo) : Promise.reject()).then(function () { b.textContent = tt("Copiado", "Copied"); }, function () { b.textContent = c.codigo; });
      };
      res.hidden = false;
    };
    var rendirse = function () {
      titulo.textContent = tt("Tu pago quedó en Stripe.", "Your payment is with Stripe.");
      notaG.textContent = tt("Tu código tarda un poco más de lo normal. Lo tienes también en el recibo de Stripe; si no te llegó, ", "Your code is taking longer than usual. It is also on your Stripe receipt; if you did not get it, ");
      notaG.appendChild(waRosso(tt("Hola, compré boletos y no vi mi código. Mi correo es: ", "Hi, I bought tickets and did not see my code. My email is: ")));
      notaG.appendChild(document.createTextNode("."));
    };
    var consulta = function () {
      intentos++;
      var v = intentos % 3 === 0 ? "&v=1" : "";   // cada tercer intento el API le pregunta directo a Stripe
      fetch(API + "/boletos/estado?b=" + encodeURIComponent(ref.b) + "&f=" + encodeURIComponent(ref.f) + "&s=" + encodeURIComponent(ref.s) + v, { mode: "cors" })
        .then(function (r) { return r.json(); }).then(function (j) {
          if (j.listo) { pintaG(j.compra); return; }
          if (intentos < 45) setTimeout(consulta, 2000); else rendirse();
        }).catch(function () { if (intentos < 45) setTimeout(consulta, 3000); else rendirse(); });
    };
    if (ref.s) consulta();
    else { titulo.textContent = tt("Falta el número de pago.", "Payment reference missing."); notaG.textContent = tt("Abre esta página desde la liga a la que te regresó Stripe.", "Open this page from the link Stripe sent you back to."); }
  }

  // ---------------- aviso del show en portada y noches
  if (API) [].forEach.call(document.querySelectorAll("[data-show]"), function (el) {
    var span = el.querySelector("[data-show-cupo]");
    if (!span) return;
    fetch(API + "/boletos/show/" + encodeURIComponent(el.getAttribute("data-show")), { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!j || !j.activo) return;
      var quedan = 0, abiertas = 0;
      j.sesiones.forEach(function (x) { if (x.estado === "abierta") { abiertas++; quedan += x.quedan; } });
      span.textContent = abiertas ? (EN ? " · " + quedan + " seats left" : " · quedan " + quedan + " lugares") : " · " + (ESTADOS[prioridad(j.sesiones)] || tt("Agotado", "Sold out"));
    }).catch(function () { /* nada */ });
  });

  // ---------------- puerta
  var fp = $("forma-puerta");
  if (fp && API) {
    var PIN = "", SHOW = "", datos = null, ultima = null, reloj = null, ultimaActual = "";
    var panel = $("p-panel"), cont = $("p-sesiones"), estadoEl = $("p-estado"), buscar = $("p-buscar"), fv = $("forma-puerta-venta");
    var abiertos = {};   // los "Más" abiertos, para que el refresco no los cierre
    var norm = function (s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); };
    var hhmm = function (d) { return ("0" + d.getHours()).slice(-2) + ":" + ("0" + d.getMinutes()).slice(-2); };
    // el show de hoy (o el siguiente) ya elegido
    (function () {
      var hoy = new Date(), iso = hoy.getFullYear() + "-" + ("0" + (hoy.getMonth() + 1)).slice(-2) + "-" + ("0" + hoy.getDate()).slice(-2);
      for (var i = 0; i < fp.show.options.length; i++) if ((fp.show.options[i].getAttribute("data-fecha") || "") >= iso) { fp.show.selectedIndex = i; break; }
    })();
    var parar = function () { if (reloj) clearInterval(reloj); reloj = null; };
    var pedirPin = function (texto) { PIN = ""; parar(); fp.hidden = false; fp.pin.value = ""; fp.pin.focus(); aviso(texto, "error"); };
    var llamar = function (ruta, extra, reintento) {
      var d = { show: SHOW, pin: PIN };
      for (var k in (extra || {})) d[k] = extra[k];
      return post(ruta, d).then(function (r) {
        if (r.status === 403 || r.status === 429) { pedirPin(r.j.error || "PIN incorrecto"); throw new Error("pin"); }
        return r;
      }, function (e) {
        // sin señal: se reintenta UNA vez con la misma op (el API no la aplica dos veces)
        if (!reintento) return new Promise(function (ok) { setTimeout(ok, 1500); }).then(function () { return llamar(ruta, extra, true); });
        throw e;
      });
    };
    var sinRed = function (e) { if (e && e.message === "pin") return; aviso("Sin conexión: no se hizo. Inténtalo otra vez o anótalo en papel.", "error"); };
    var resultado = function (r, exito) { aviso(r.ok ? exito : (r.j.error || "No se pudo."), r.ok ? "ok" : "error"); cargar(); };
    var sinConexion = function () { estadoEl.textContent = "SIN CONEXIÓN · lista de las " + (ultima ? hhmm(ultima) : "—") + ". Anota en papel lo que pase."; estadoEl.className = "mini error"; };
    var cargar = function () {
      return llamar("/boletos/puerta/lista").then(function (r) {
        if (!r.ok) { aviso(r.j.error || "No se pudo cargar la lista.", "error"); return; }
        datos = r.j; ultima = new Date(); pintar();
      }).catch(function (e) { if (e.message !== "pin") sinConexion(); });
    };
    var actual = function () {   // la sesión que está por empezar o en curso
      if (!datos) return null;
      var ahora = Date.now(), mejor = datos.sesiones[0];
      datos.sesiones.forEach(function (x) { if (new Date(x.inicio).getTime() + 50 * 60000 > ahora && new Date(mejor.inicio).getTime() + 50 * 60000 <= ahora) mejor = x; });
      return mejor;
    };
    // cuadro dentro de la página en vez de confirm()/prompt(): en el celular «Cancelar» se leía como
    // «cancelar el boleto», y hay navegadores que ni los muestran. Regresa true, el texto escrito o null.
    var pendiente = null;   // el cierre del cuadro abierto: si se abre otro, el anterior se resuelve como "No"
    var dialogo = function (o) {
      if (pendiente) pendiente(null);
      return new Promise(function (listo) {
        var caja = $("p-dialogo"), campo = $("p-dialogo-campo"), si = $("p-dialogo-si"), no = $("p-dialogo-no");
        var antes = document.activeElement;
        $("p-dialogo-texto").textContent = o.texto;
        $("p-dialogo-campo-caja").hidden = !o.campo;
        if (o.campo) { campo.value = o.campo.valor == null ? "" : o.campo.valor; campo.placeholder = o.campo.placeholder || ""; campo.inputMode = o.campo.numero ? "numeric" : "text"; }
        si.textContent = o.si || "Sí"; si.className = "btn" + (o.peligro ? " peligro-lleno" : "");
        no.textContent = o.no || "No";
        var cerrar = function (v) {
          caja.hidden = true; si.onclick = no.onclick = null; pendiente = null;
          panel.inert = fp.inert = false;   // el fondo vuelve a responder
          if (antes && document.contains(antes) && antes.focus) antes.focus();
          listo(v);
        };
        si.onclick = function () { cerrar(o.campo ? campo.value.trim() : true); };
        no.onclick = function () { cerrar(null); };
        pendiente = cerrar;
        panel.inert = fp.inert = true;   // mientras el cuadro está abierto, nada de atrás se alcanza con Tab o las flechas del iPhone
        caja.hidden = false;
        if (o.campo) campo.focus(); else si.focus();
      });
    };
    var boton = function (texto, fn, clase) { var b = document.createElement("button"); b.type = "button"; b.className = "btn btn-linea " + (clase || ""); b.textContent = texto; b.onclick = fn; return b; };
    var txt = function (tag, clase, texto) { var el = document.createElement(tag); if (clase) el.className = clase; el.textContent = texto; return el; };

    var pintar = function () {
      if (!datos) return;
      estadoEl.className = "mini";
      estadoEl.textContent = datos.artista + " · actualizada " + hhmm(ultima) + (datos.pausada ? " · VENTA EN LÍNEA EN PAUSA" : "") + " · cortesías " + datos.cortesias + "/" + datos.cortesias_max;
      $("p-pausa").textContent = datos.pausada ? "Reanudar venta en línea" : "Pausar venta en línea";
      var q = norm(buscar.value).replace(/-/g, ""), cur = actual();
      // la venta en puerta va a la sesión de ahora, salvo que alguien haya elegido otra desde que empezó la actual
      if (cur && cur.id !== ultimaActual) { ultimaActual = cur.id; delete fv.dataset.elegida; }
      fv.sesion.innerHTML = "";
      datos.sesiones.forEach(function (x) { var o = document.createElement("option"); o.value = x.id; o.textContent = x.etiqueta + " (quedan " + Math.max(0, x.quedan) + ")"; fv.sesion.appendChild(o); });
      fv.sesion.value = fv.dataset.elegida || (cur && cur.id) || "";
      cont.innerHTML = "";
      datos.sesiones.forEach(function (x) {
        var caja = document.createElement("section"); caja.className = "puerta-sesion" + (cur && cur.id === x.id ? " actual" : "");
        caja.appendChild(txt("h2", "", x.etiqueta + (cur && cur.id === x.id ? " · ahora" : "")));
        caja.appendChild(txt("p", "mini", x.vendidos + " de " + x.cupo + " vendidos · entraron " + x.entraron + " · quedan " + Math.max(0, x.quedan)
          + (x.en_pago ? " · " + x.en_pago + " en pago en línea (vencen " + x.apartados.map(function (a) { return a.vence; }).join(", ") + ")" : "") + " · puertas " + hora12(x.puertas)));
        var acc = document.createElement("div"); acc.className = "puerta-acciones";
        if (x.en_pago) acc.appendChild(boton("Soltar pagos en curso", function () {
          dialogo({ texto: "Esto cancela en Stripe los pagos en línea que estén a medias en " + x.etiqueta + " y libera esos lugares.", si: "Sí, soltarlos", no: "No", peligro: true }).then(function (ok) {
            if (!ok) return;
            aviso("Soltando…");
            llamar("/boletos/puerta/soltar", { sesion: x.id }).then(function (r) {
              resultado(r, "Soltados: " + (r.j.sueltos || 0) + (r.j.pagados ? " · ya estaban pagados: " + r.j.pagados : "") + (r.j.abiertos ? " · siguen abiertos: " + r.j.abiertos : ""));
            }).catch(sinRed);
          });
        }));
        acc.appendChild(boton("Cambiar cupo", function () {
          dialogo({ texto: "Cupo de " + x.etiqueta + " (ahora " + x.cupo + "):", campo: { valor: x.cupo, numero: true }, si: "Guardar", no: "Cancelar" }).then(function (v) {
            var n = parseInt(v, 10);
            if (!n || n === x.cupo) return;
            aviso("Cambiando cupo…");
            llamar("/boletos/puerta/cupo", { sesion: x.id, cupo: n }).then(function (r) { resultado(r, "Cupo de " + x.etiqueta + ": " + n); }).catch(sinRed);
          });
        }));
        caja.appendChild(acc);
        var lista = document.createElement("div"); lista.className = "sello-lista";
        var visibles = x.compras.filter(function (c) {
          if (!q) return true;
          return norm(c.nombre + " " + c.a_nombre_de).indexOf(q) >= 0 || norm(c.codigo).replace(/-/g, "").indexOf(q) >= 0 || (q.length === 4 && c.wa === q);
        });
        if (!visibles.length) lista.appendChild(txt("p", "mini", q ? "Nadie con esa búsqueda en esta sesión." : "Nadie todavía."));
        visibles.forEach(function (c) { lista.appendChild(fila(x, c)); });
        caja.appendChild(lista);
        cont.appendChild(caja);
      });
    };

    var fila = function (x, c) {
      var el = document.createElement("div");
      el.className = "sello-item" + (c.estado === "anulada" ? " anulada" : c.entraron >= c.cantidad ? " entro" : "");
      var izq = document.createElement("div");
      izq.appendChild(txt("div", "n", c.codigo + " · " + (c.a_nombre_de || c.nombre)));
      izq.appendChild(txt("div", "d", (c.estado === "anulada" ? "ANULADA · " : "") + c.entraron + " de " + c.cantidad + " entraron · "
        + (c.canal === "web" ? "en línea" : c.canal === "cortesia" ? "cortesía" : c.metodo) + (c.a_nombre_de ? " · compró " + c.nombre : "") + (c.email ? " · " + c.email : "") + (c.wa ? " · …" + c.wa : "")));
      el.appendChild(izq);
      if (c.estado === "anulada") return el;
      var der = document.createElement("div"); der.className = "puerta-acciones";
      var ocupar = function (on) { [].forEach.call(el.querySelectorAll("button"), function (b) { b.disabled = on; }); el.classList.toggle("trabajando", on); };
      var entrada = function (n) {
        ocupar(true);
        llamar("/boletos/puerta/entrada", { sesion: x.id, codigo: c.codigo, n: n, op: nuevaOp() }).then(function (r) {
          if (!r.ok) { ocupar(false); aviso(r.j.error || "No se pudo.", "error"); return; }
          x.entraron += r.j.entraron - c.entraron; c.entraron = r.j.entraron; pintar();
          aviso(c.codigo + ": " + r.j.entraron + " de " + r.j.cantidad + " adentro.", "ok");
        }).catch(function (e) { ocupar(false); sinRed(e); });
      };
      if (c.entraron < c.cantidad) der.appendChild(boton("Entró 1", function () { entrada(1); }, "entra"));
      if (c.entraron > 0) der.appendChild(boton("−1", function () { entrada(-1); }));
      var mas = document.createElement("details"); mas.className = "fila-mas";
      if (abiertos[c.codigo]) mas.open = true;
      mas.addEventListener("toggle", function () { if (mas.open) abiertos[c.codigo] = 1; else delete abiertos[c.codigo]; });
      mas.appendChild(txt("summary", "", "Más"));
      var cajaMas = document.createElement("div"); cajaMas.className = "puerta-acciones";
      cajaMas.appendChild(boton("A nombre de…", function () {
        dialogo({ texto: "¿A nombre de quién queda " + c.codigo + "?", campo: { valor: c.a_nombre_de || "", placeholder: "Nombre" }, si: "Guardar", no: "Cancelar" }).then(function (n) {
          if (n === null) return;
          aviso("Guardando…");
          llamar("/boletos/puerta/nombre", { sesion: x.id, codigo: c.codigo, nombre: n }).then(function (r) { resultado(r, "Listo: " + c.codigo + " a nombre de " + n + "."); }).catch(sinRed);
        });
      }));
      datos.sesiones.forEach(function (y) {
        if (y.id === x.id) return;
        cajaMas.appendChild(boton("Pasar a " + y.etiqueta, function () {
          dialogo({ texto: "¿Pasar " + c.codigo + " (" + c.nombre + ", " + c.cantidad + ") a la sesión de las " + y.etiqueta + "?", si: "Sí, pasarlo", no: "No" }).then(function (ok) {
            if (!ok) return;
            aviso("Moviendo…"); delete abiertos[c.codigo];
            llamar("/boletos/puerta/mover", { sesion: x.id, destino: y.id, codigo: c.codigo }).then(function (r) { resultado(r, c.codigo + " pasó a " + y.etiqueta + "."); }).catch(sinRed);
          });
        }));
      });
      cajaMas.appendChild(boton("Anular", function () {
        dialogo({ texto: "¿Anular " + c.codigo + " (" + c.nombre + ", " + c.cantidad + ")? Libera los lugares y deja de contar en la liquidación."
                    + (c.canal === "web" ? " El dinero se devuelve aparte, en Stripe." : ""),
                  campo: { placeholder: "Motivo (opcional)" }, si: "Sí, anular", no: "No, dejarlo", peligro: true }).then(function (motivo) {
          if (motivo === null) return;
          aviso("Anulando…"); delete abiertos[c.codigo];
          llamar("/boletos/puerta/anular", { sesion: x.id, codigo: c.codigo, motivo: motivo, op: nuevaOp() }).then(function (r) { resultado(r, c.codigo + " anulado."); }).catch(sinRed);
        });
      }, "peligro"));
      mas.appendChild(cajaMas);
      der.appendChild(mas);
      el.appendChild(der);
      return el;
    };

    fp.addEventListener("submit", function (ev) {
      ev.preventDefault();
      PIN = fp.pin.value.trim(); SHOW = fp.show.value;
      if (!PIN) { aviso("Pon el PIN.", "error"); return; }
      aviso("Abriendo…");
      llamar("/boletos/puerta/lista").then(function (r) {
        if (!r.ok) { aviso(r.j.error || "No se pudo abrir la lista.", "error"); return; }
        fp.pin.value = ""; fp.hidden = true; panel.hidden = false; aviso("");
        datos = r.j; ultima = new Date(); pintar();
        parar(); reloj = setInterval(function () { if (!document.hidden && PIN) cargar(); }, 30000);
      }).catch(function (e) { if (e.message !== "pin") aviso("Sin conexión con el API. Usa datos del celular.", "error"); });
    });
    $("p-refrescar").onclick = function () { aviso("Actualizando…"); cargar().then(function () { if (msg.textContent === "Actualizando…") aviso(""); }); };
    buscar.addEventListener("input", pintar);
    document.addEventListener("visibilitychange", function () { if (!document.hidden && PIN) cargar(); });

    var registrar = $("pv-registrar"), entran = $("pv-entran");
    var textoRegistrar = function () { registrar.textContent = entran.checked ? "Registrar y marcar entrada" : "Registrar (todavía no llega)"; };
    var porDefecto = function () {   // cortesías y transferencias se registran antes de que lleguen
      fv.metodo.disabled = fv.tipo.value === "cortesia";
      entran.checked = fv.tipo.value === "puerta" && fv.metodo.value !== "transferencia";
      textoRegistrar();
    };
    fv.tipo.addEventListener("change", porDefecto);
    fv.metodo.addEventListener("change", porDefecto);
    entran.addEventListener("change", textoRegistrar);
    fv.sesion.addEventListener("change", function () { fv.dataset.elegida = fv.sesion.value; });
    fv.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (registrar.disabled) return;
      var d = { sesion: fv.sesion.value, cantidad: parseInt(fv.cantidad.value, 10), tipo: fv.tipo.value, metodo: fv.metodo.value,
                nombre: fv.nombre.value.trim(), pidio: fv.pidio.value.trim(), entran: entran.checked, op: nuevaOp() };
      var desc = d.cantidad + (d.tipo === "cortesia" ? " cortesía(s)" : " en " + d.metodo + " (" + pesos(datos.precio * d.cantidad) + ")");
      registrar.disabled = true;
      dialogo({ texto: "¿Registrar " + desc + " para la sesión de las " + (fv.sesion.options[fv.sesion.selectedIndex] || {}).text + "?" + (d.entran ? " Quedan marcados como adentro." : ""), si: "Sí, registrar", no: "No" }).then(function (ok) {
        if (!ok) { registrar.disabled = false; return; }
        aviso("Registrando…");
        llamar("/boletos/puerta/venta", d).then(function (r) {
          registrar.disabled = false;
          if (!r.ok) { aviso(r.j.error || "No se pudo.", "error"); return; }
          aviso("Registrado: " + r.j.codigo + " · " + desc + ".", "ok"); fv.nombre.value = ""; fv.pidio.value = ""; cargar();
        }).catch(function (e) { registrar.disabled = false; sinRed(e); });
      });
    });

    [].forEach.call(document.querySelectorAll(".pag-puerta [data-accion]"), function (b) {
      b.addEventListener("click", function () {
        var a = b.getAttribute("data-accion");
        if (a === "pausa") {
          var pausar = !datos.pausada;
          dialogo({ texto: pausar ? "¿Pausar la venta en línea? La página dirá que está en pausa." : "¿Reanudar la venta en línea?", si: pausar ? "Sí, pausar" : "Sí, reanudar", no: "No" }).then(function (ok) {
            if (!ok) return;
            aviso(pausar ? "Pausando…" : "Reanudando…");
            llamar("/boletos/puerta/pausa", { pausada: pausar }).then(function (r) { resultado(r, pausar ? "Venta en pausa." : "Venta reanudada."); }).catch(sinRed);
          });
        } else if (a === "cortesias") {
          dialogo({ texto: "Tope de cortesías del show (ahora " + datos.cortesias_max + "):", campo: { valor: datos.cortesias_max, numero: true }, si: "Guardar", no: "Cancelar" }).then(function (v) {
            var n = parseInt(v, 10);
            if (v === null || isNaN(n)) return;
            aviso("Cambiando tope…");
            llamar("/boletos/puerta/cupo", { campo: "cortesias_max", cupo: n }).then(function (r) { resultado(r, "Tope de cortesías: " + n); }).catch(sinRed);
          });
        } else {
          aviso("Mandando…");
          llamar("/boletos/puerta/telegram", { que: a }).then(function (r) { aviso(r.ok ? "Mandado al Telegram de Pablo." : (r.j.error || "No se pudo."), r.ok ? "ok" : "error"); }).catch(sinRed);
        }
      });
    });
  }
})();
