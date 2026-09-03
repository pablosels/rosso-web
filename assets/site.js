/* rossospeakeasy.com — menú móvil, carta viva y formulario de eventos. */
(function () {
  var API = document.body.dataset.api || "";

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
      var d = it.descripcion ? '<span class="desc">' + esc(it.descripcion) + "</span>" : "";
      return '<li><span class="nombre">' + esc(it.nombre) + d + '</span><span class="puntos" aria-hidden="true"></span><span class="precio">' + Number(it.precio).toLocaleString("es-MX") + "</span></li>";
    }).join("") + "</ul>";
  }
  var MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

  // carta viva: si la API responde, reemplaza el snapshot embebido
  var carta = document.getElementById("carta");
  if (carta && API) {
    fetch(API + "/carta", { mode: "cors" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (data) {
      if (!data || !data.secciones || !data.secciones.length) return;
      carta.innerHTML = data.secciones.map(function (s) {
        var inner = s.items && s.items.length ? items(s.items) : "";
        (s.subsecciones || []).forEach(function (sub) { inner += '<h3 class="sub">' + esc(sub.titulo) + "</h3>" + items(sub.items); });
        return '<section class="bloque" id="' + slug(s.titulo) + '"><h2>' + esc(s.titulo) + "</h2>" + inner + "</section>";
      }).join("");
      var nota = document.getElementById("carta-nota");
      if (nota && data.generada) {
        var d = new Date(data.generada);
        if (!isNaN(d)) nota.textContent = "Precios en pesos, IVA incluido. Actualizada desde nuestro punto de venta el " + d.getDate() + " de " + MESES[d.getMonth()] + " de " + d.getFullYear() + ".";
      }
    }).catch(function () { /* se queda el snapshot */ });
  }

  // reservar: arma el link de OpenTable con fecha, hora y personas (tope = opciones del select)
  var reserva = document.getElementById("forma-reserva");
  if (reserva) {
    reserva.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var f = document.getElementById("r-fecha").value, h = document.getElementById("r-hora").value, p = document.getElementById("r-personas").value;
      if (!f) return;
      var url = "https://www.opentable.com.mx/restref/client/?rid=1498843&restref=1498843&lang=es-MX&datetime=" + encodeURIComponent(f + "T" + h) + "&covers=" + p + "&otSource=Restaurant%20website";
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
      if (!datos.nombre || !datos.whatsapp || !datos.fecha || !datos.hora) { msg.textContent = "Nos faltan nombre, WhatsApp, fecha y hora."; msg.classList.add("error"); return; }
      if (pax < 5) { msg.innerHTML = 'Para 4 personas o menos reserva directo <a href="' + document.body.dataset.base + '/reservar/">aquí</a>.'; msg.classList.add("error"); return; }
      if (!API) { msg.textContent = "El formulario todavía no está conectado; escríbenos por WhatsApp."; msg.classList.add("error"); return; }
      var boton = forma.querySelector("button[type=submit]");
      boton.disabled = true; msg.textContent = "Enviando…";
      fetch(API + "/eventos", { method: "POST", mode: "cors", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok && res.j.ok) {
            forma.reset();
            msg.textContent = "Listo. Te escribimos por WhatsApp en menos de 24 horas con la propuesta (folio " + res.j.folio + ").";
            msg.classList.add("ok");
          } else {
            msg.textContent = (res.j && res.j.error) || "No se pudo enviar. Inténtalo otra vez o escríbenos por WhatsApp.";
            msg.classList.add("error");
          }
        })
        .catch(function () { msg.textContent = "No se pudo enviar. Inténtalo otra vez o escríbenos por WhatsApp."; msg.classList.add("error"); })
        .finally(function () { boton.disabled = false; });
    });
  }
})();
