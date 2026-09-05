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
  function medir(tipo) {
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
  if (location.pathname.indexOf("/carta") === 0) medir("carta");
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest && ev.target.closest("a[href*='wa.me'], a[href*='opentable.com']");
    if (!a) return;
    medir(a.href.indexOf("wa.me") >= 0 ? "whatsapp" : "opentable");
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
    reserva.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = document.getElementById("r-fecha").value, h = document.getElementById("r-hora").value, p = document.getElementById("r-personas").value;
      if (!f) return;
      var url = "https://www.opentable.com.mx/restref/client/?rid=1498843&restref=1498843&lang=" + (EN ? "en-US" : "es-MX") + "&datetime=" + encodeURIComponent(f + "T" + h) + "&covers=" + p + "&otSource=Restaurant%20website";
      medir("reservar");
      window.open(url, "_blank", "noopener");
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
        if (res.ok && res.j.ok) { forma.reset(); msg.textContent = tt("Listo. Te escribimos por WhatsApp en menos de 24 horas (folio " + res.j.folio + ").", "Done. We will message you on WhatsApp within 24 hours (ref. " + res.j.folio + ")."); msg.classList.add("ok"); }
        else { msg.textContent = (res.j && res.j.error) || tt("No se pudo enviar. Inténtalo otra vez.", "Could not send. Try again."); msg.classList.add("error"); }
      })
      .catch(function () { msg.textContent = tt("No se pudo enviar. Inténtalo otra vez o escríbenos por WhatsApp.", "Could not send. Try again or message us on WhatsApp."); msg.classList.add("error"); })
      .finally(function () { boton.disabled = false; });
  });
})();
