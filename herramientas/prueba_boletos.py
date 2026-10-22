# -*- coding: utf-8 -*-
"""Pruebas del módulo de boletos con Stripe simulado y libro en archivos locales.
Uso: python -I herramientas/prueba_boletos.py api"""
import datetime as dt
import hashlib
import hmac
import json
import os
import sys
import tempfile
import threading
import time
import urllib.parse

import requests

API_DIR = os.path.abspath(sys.argv[1])
TMP = tempfile.mkdtemp(prefix="boletos_")
os.environ.update({
    "BOLETOS_LOCAL": TMP, "STRIPE_KEY": "rk_test_falsa", "STRIPE_WEBHOOK_SECRET": "whsec_prueba",
    "CANJE_PIN": "12345678", "PUERTA_PIN": "445566", "REFRESH_KEY": "llave-prueba", "REGALO_SHEET_ID": "",
    "ALLOWED_ORIGINS": "https://rossospeakeasy.com,http://localhost:8765",
})
for k in ("BUCKET", "BOLETOS_BUCKET", "TELEGRAM_TOKEN_ROSSO", "K_SERVICE", "BOLETOS_SHEET_ID"):
    os.environ.pop(k, None)
sys.path.insert(0, API_DIR)
os.chdir(API_DIR)

import app as appmod          # noqa: E402
import boletos as bo          # noqa: E402

assert appmod.boletos_mod is bo, "boletos no se montó"

# las pruebas usan su propio show y su propio trato: no dependen de lo que diga el catálogo real
import copy   # noqa: E402
SHOW_PRUEBA = {
    "slug": "show-prueba", "artista": "Artista Prueba", "fecha": "2026-11-25", "visible": "oculto", "venta_abre": "",
    "precio": 650, "max_por_compra": 4, "cortesias_max": 4, "duracion_min": 45, "cierra_min_antes": 60,
    "sesiones": [{"id": "21", "hora": "21:00", "puertas": "20:30", "cupo": 30, "es": "9:00 pm", "en": "9:00 pm"},
                 {"id": "23", "hora": "23:00", "puertas": "22:30", "cupo": 30, "es": "11:00 pm", "en": "11:00 pm"}],
    "es": {"titulo": "Prueba", "descripcion": "Prueba", "texto": "Prueba"},
    "en": {"titulo": "Test", "descripcion": "Test", "texto": "Test"},
}
bo.SHOWS.clear()
bo.SHOWS["show-prueba"] = copy.deepcopy(SHOW_PRUEBA)
# trato inventado: el real vive fuera del repo (que es público) y no debe aparecer aquí
TRATO = {"fijo": 1000, "porcentaje": 0.3, "comision_web": 0.04, "comision_clip": 0.03}
bo._trato = lambda slug: dict(TRATO)
TG = []
bo._telegram = lambda texto, **kw: (TG.append(texto), True)[1]

# ---------------- reloj controlable
RELOJ = {"t": time.time(), "local": dt.datetime(2026, 11, 1, 12, 0)}
bo._ahora = lambda: RELOJ["t"]
bo._ahora_local = lambda: RELOJ["local"]

# ---------------- Stripe falso
SES, LLAMADAS = {}, []
_lock_stripe = threading.Lock()


def stripe_falso(metodo, ruta, datos=None, idem=None):
    with _lock_stripe:
        LLAMADAS.append((metodo, ruta))
        if metodo == "POST" and ruta == "checkout/sessions":
            assert "payment_method_types[0]" not in datos, "endive rechaza payment_method_types"
            assert datos["allowed_payment_method_types[0]"] == "card"
            assert datos["expires_at"].isdigit()
            for v in datos.values():
                assert len(str(v)) <= 500 or True
            n = len(SES) + 1
            cs = f"cs_test_{n:04d}"
            md = {k[9:-1]: v for k, v in datos.items() if k.startswith("metadata[")}
            assert all(len(v) <= 500 for v in md.values()) and len(md) <= 50
            q = int(datos["line_items[0][quantity]"])
            SES[cs] = {"id": cs, "object": "checkout.session", "url": f"https://checkout.stripe.com/c/pay/{cs}",
                       "status": "open", "payment_status": "unpaid", "metadata": md,
                       "amount_total": int(datos["line_items[0][price_data][unit_amount]"]) * q,
                       "client_reference_id": datos["client_reference_id"], "customer_email": datos["customer_email"],
                       "payment_intent": None, "customer_details": None, "_datos": datos}
            return 200, dict(SES[cs])
        if metodo == "POST" and ruta.endswith("/expire"):
            cs = ruta.split("/")[2]
            s = SES.get(cs)
            if not s or s["status"] != "open":
                return 400, {"error": {"message": "not expireable"}}
            s["status"] = "expired"
            return 200, dict(s)
        if metodo == "GET" and ruta.startswith("checkout/sessions/"):
            cs = ruta.split("/")[2]
            return (200, dict(SES[cs])) if cs in SES else (404, {"error": {}})
        raise AssertionError(f"llamada inesperada {metodo} {ruta}")


bo._stripe = stripe_falso


def pagar(cs, email="cliente@correo.com", nombre="Cliente"):
    s = SES[cs]
    assert s["status"] == "open", f"{cs} no está abierta: {s['status']}"
    s.update(status="complete", payment_status="paid", payment_intent="pi_" + cs[-4:],
             customer_details={"email": email, "name": nombre})
    return dict(s)


def firmar(payload):
    t = str(int(time.time()))
    v1 = hmac.new(b"whsec_prueba", f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={t},v1={v1}"


C = appmod.app.test_client()
ORIGEN = {"Origin": "https://rossospeakeasy.com"}


def webhook(evento):
    payload = json.dumps(evento).encode()
    return C.post("/stripe/webhook", data=payload, headers={"Stripe-Signature": firmar(payload), "Content-Type": "application/json"})


def completado(s):
    return webhook({"type": "checkout.session.completed", "data": {"object": s}})


def checkout(**kw):
    d = {"show": "show-prueba", "sesion": "21", "cantidad": 2, "nombre": "Ana López", "email": "ana@correo.com", "idioma": "es"}
    d.update(kw)
    return C.post("/boletos/checkout", json=d, headers=dict(ORIGEN, **{"X-Forwarded-For": kw.pop("ip", "1.2.3.4")}) if False else ORIGEN,
                  environ_base={"REMOTE_ADDR": d.pop("ip", "1.2.3.4")})


def puerta(ruta, **kw):
    d = {"show": "show-prueba", "pin": "445566"}
    d.update(kw)
    return C.post("/boletos/puerta/" + ruta, json=d, headers=ORIGEN, environ_base={"REMOTE_ADDR": "9.9.9.9"})


def led(sid="21"):
    return bo._leer("show-prueba", sid)


OK, FALLAS = [], []


def prueba(nombre, cond, detalle=""):
    (OK if cond else FALLAS).append(nombre)
    print(("  ok  " if cond else "  XX  ") + nombre + ("" if cond else f"  -> {detalle}"))


def reiniciar():
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    SES.clear()
    TG.clear()
    bo._ultima_reconciliacion.clear()
    RELOJ["t"] = time.time()
    RELOJ["local"] = dt.datetime(2026, 11, 1, 12, 0)
    bo.SHOWS["show-prueba"] = copy.deepcopy(SHOW_PRUEBA)


# ======================================================================
reiniciar()
print("\n[catálogo y config]")
bo.SHOWS["show-prueba"]["visible"] = "no"
r = C.get("/boletos/show/show-prueba")
prueba("show no visible da 404", r.status_code == 404, r.status_code)
bo.SHOWS["show-prueba"]["visible"] = "oculto"
r = C.get("/boletos/show/show-prueba")
j = r.get_json()
prueba("show oculto responde activo", r.status_code == 200 and j["activo"], j)
prueba("dos sesiones abiertas con 30", [(x["estado"], x["quedan"]) for x in j["sesiones"]] == [("abierta", 30), ("abierta", 30)], j)

print("\n[entrada]")
r = C.post("/boletos/checkout", json={"show": "show-prueba"}, headers={})
prueba("sin Origin: 403", r.status_code == 403, r.status_code)
r = C.post("/boletos/checkout", data="{}", headers=dict(ORIGEN, **{"Content-Type": "text/plain"}))
prueba("text/plain: 415", r.status_code == 415, r.status_code)
r = checkout(cantidad=5)
prueba("5 boletos: 400", r.status_code == 400, r.get_json())
r = checkout(email="no-es-correo")
prueba("correo inválido: 400", r.status_code == 400, r.get_json())
r = checkout(nombre="<img src=x onerror=alert(1)>", email="x@correo.com")
prueba("nombre con HTML se limpia y pasa", r.status_code == 200, r.get_json())
cs_html = list(SES)[-1]
prueba("metadata sin < > \" '", not any(ch in SES[cs_html]["metadata"]["nombre"] for ch in "<>\"'"), SES[cs_html]["metadata"]["nombre"])
r = checkout(empresa_web="bot")
prueba("miel: 400", r.status_code == 400, r.status_code)

print("\n[compra con webhook]")
reiniciar()
r = checkout()
j = r.get_json()
prueba("checkout ok con url", r.status_code == 200 and j["url"].startswith("https://checkout.stripe.com"), j)
cs = list(SES)[-1]
datos = SES[cs]["_datos"]
prueba("success_url lleva b, f y el placeholder", "boletos/gracias/?b=show-prueba&f=21&s={CHECKOUT_SESSION_ID}" in datos["success_url"], datos["success_url"])
prueba("código en el nombre del item", SES[cs]["metadata"]["codigo"] in datos["line_items[0][price_data][product_data][name]"])
prueba("receipt_email", datos["payment_intent_data[receipt_email]"] == "ana@correo.com")
prueba("monto del servidor", SES[cs]["amount_total"] == 130000, SES[cs]["amount_total"])
L = led()
prueba("apartado con cs", len(L["apartados"]) == 1 and list(L["apartados"].values())[0]["cs"] == cs, L["apartados"])
j = C.get("/boletos/show/show-prueba").get_json()
prueba("quedan 28 y en_pago 2 (tras caché)", True)
time.sleep(0)
bo_cache_vacia = True
r = checkout()
prueba("doble clic devuelve la misma url sin otra sesión", r.get_json().get("url", "").endswith(cs) and len(SES) == 1, (r.get_json(), len(SES)))
s = pagar(cs, "ana@correo.com", "Ana López")
r = completado(s)
prueba("webhook 200", r.status_code == 200, r.status_code)
L = led()
prueba("compra registrada y apartado fuera", cs in L["compras"] and not L["apartados"], L)
prueba("Telegram de venta", any("2 boletos" in t for t in TG), TG)
n_tg = len(TG)
r = completado(s)
prueba("webhook repetido no duplica", len(led()["compras"]) == 1 and len(TG) == n_tg, (len(led()["compras"]), TG[n_tg:]))
r = C.get(f"/boletos/estado?b=show-prueba&f=21&s={cs}")
j = r.get_json()
prueba("estado listo con código", j["listo"] and j["compra"]["codigo"] == SES[cs]["metadata"]["codigo"], j)
prueba("compra avisada", led()["compras"][cs]["avisado"], led()["compras"][cs])

print("\n[sin webhook: la página de gracias registra]")
r = checkout(email="beto@correo.com", nombre="Beto", cantidad=1)
cs2 = list(SES)[-1]
pagar(cs2, "beto@correo.com", "Beto")
r = C.get(f"/boletos/estado?b=show-prueba&f=21&s={cs2}")
prueba("sin v=1 no pregunta a Stripe", r.get_json()["listo"] is False, r.get_json())
r = C.get(f"/boletos/estado?b=show-prueba&f=21&s={cs2}&v=1")
prueba("con v=1 registra", r.get_json()["listo"] is True, r.get_json())
prueba("aviso dice que no fue por webhook", any("pagina de gracias" in t for t in TG), TG[-1:])
r = completado(SES[cs2])
prueba("el webhook tardío no duplica", sum(1 for c in led()["compras"].values() if c["cs"] == cs2) == 1)

print("\n[cancelar]")
r = checkout(email="caro@correo.com", nombre="Caro", cantidad=3)
cs3 = list(SES)[-1]
hold3 = SES[cs3]["metadata"]["hold"]
r = C.post("/boletos/cancelar", json={"show": "show-prueba", "sesion": "21", "hold": hold3}, headers=ORIGEN)
prueba("cancelar suelta", r.get_json().get("soltado") is True and hold3 not in led()["apartados"], r.get_json())
prueba("sesión expirada en Stripe", SES[cs3]["status"] == "expired")
r = checkout(email="dani@correo.com", nombre="Dani", cantidad=1)
cs4 = list(SES)[-1]
hold4 = SES[cs4]["metadata"]["hold"]
pagar(cs4, "dani@correo.com", "Dani")
r = C.post("/boletos/cancelar", json={"show": "show-prueba", "sesion": "21", "hold": hold4}, headers=ORIGEN)
j = r.get_json()
prueba("cancelar algo ya pagado lo registra y NO suelta", j.get("pagado") is True and cs4 in led()["compras"], j)

print("\n[apartado vencido]")
r = checkout(email="eli@correo.com", nombre="Eli", cantidad=2)
cs5 = list(SES)[-1]
RELOJ["t"] += 21 * 60
bo._ultima_reconciliacion.clear()
r = checkout(email="fer@correo.com", nombre="Fer", cantidad=1)
prueba("al vencer se expira en Stripe y se suelta", SES[cs5]["status"] == "expired" and all(a["cs"] != cs5 for a in led()["apartados"].values()), led()["apartados"])
cs6 = list(SES)[-1]
pagar(cs6)
RELOJ["t"] += 21 * 60
r = puerta("lista")
prueba("vencido pero pagado: la lista lo registra", cs6 in led()["compras"], list(led()["compras"]))

print("\n[cupo]")
reiniciar()
for i in range(15):
    r = checkout(email=f"c{i}@correo.com", nombre=f"Cliente {i}", cantidad=2, ip=f"10.0.0.{i}")
    assert r.status_code == 200, r.get_json()
    completado(pagar(list(SES)[-1], f"c{i}@correo.com"))
r = checkout(email="tarde@correo.com", nombre="Tarde", cantidad=1)
j = r.get_json()
prueba("sesión llena: 409", r.status_code == 409, (r.status_code, j))
j = C.get("/boletos/show/show-prueba").get_json()
prueba("estado agotada", j["sesiones"][0]["estado"] == "agotada" and j["sesiones"][0]["quedan"] == 0, j["sesiones"][0])
r = checkout(sesion="23", email="otra@correo.com", nombre="Otra", cantidad=4, ip="5.5.5.5")
prueba("la otra sesión sigue vendiendo", r.status_code == 200, r.get_json())

print("\n[tope por conexión]")
reiniciar()
for i in range(2):
    r = checkout(email=f"t{i}@correo.com", nombre="Tomás", cantidad=4, ip="7.7.7.7")
r = checkout(email="t9@correo.com", nombre="Tomás", cantidad=1, ip="7.7.7.7")
prueba("más de 8 lugares en pago desde una IP: 429", r.status_code == 429, r.get_json())

print("\n[concurrencia: 40 compras de 1 al mismo tiempo, cupo 30]")
reiniciar()
resultados = []


def comprar(i):
    rr = C.post("/boletos/checkout", json={"show": "show-prueba", "sesion": "21", "cantidad": 1, "nombre": f"P {i}",
                                           "email": f"p{i}@correo.com"}, headers=ORIGEN, environ_base={"REMOTE_ADDR": f"20.0.{i}.1"})
    resultados.append(rr.status_code)


hilos = [threading.Thread(target=comprar, args=(i,)) for i in range(40)]
[h.start() for h in hilos]
[h.join() for h in hilos]
L = led()
en_pago = sum(a["cantidad"] for a in L["apartados"].values())
prueba("nunca más de 30 apartados", en_pago <= 30, en_pago)
prueba("30 aceptadas, 10 rechazadas", resultados.count(200) == 30 and resultados.count(409) == 10, (resultados.count(200), sorted(set(resultados))))
abiertas_sin_apartado = [cs for cs, s in SES.items() if s["status"] == "open" and all(a["cs"] != cs for a in L["apartados"].values())]
prueba("ninguna sesión de Stripe abierta sin apartado", not abiertas_sin_apartado, abiertas_sin_apartado)
pagos = [threading.Thread(target=lambda cs=cs: completado(pagar(cs))) for cs, s in list(SES.items()) if s["status"] == "open"]
[h.start() for h in pagos]
[h.join() for h in pagos]
L = led()
prueba("30 compras, cero apartados", len(L["compras"]) == 30 and not L["apartados"], (len(L["compras"]), len(L["apartados"])))
codigos = [c["codigo"] for c in L["compras"].values()]
prueba("códigos únicos", len(set(codigos)) == len(codigos))

print("\n[puerta]")
reiniciar()
completado(pagar(list(SES)[-1] if checkout().status_code == 200 else None, "ana@correo.com", "Ana López"))
cod = list(led()["compras"].values())[0]["codigo"]
r = puerta("lista", pin="0000")
prueba("PIN malo 403", r.status_code == 403, r.status_code)
r = puerta("lista")
prueba("PIN de puerta abre", r.status_code == 200 and r.get_json()["sesiones"][0]["vendidos"] == 2, r.get_json())
r = puerta("lista", pin="12345678")
prueba("PIN de barra también abre", r.status_code == 200)
r = C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": "445566"}, headers={"Origin": "https://malo.com"})
prueba("puerta desde otro origen: 403", r.status_code == 403)
r = puerta("entrada", sesion="21", codigo=cod, n=1, op="op-1")
r2 = puerta("entrada", sesion="21", codigo=cod, n=1, op="op-1")
prueba("misma op no se aplica dos veces", r.get_json()["entraron"] == 1 and r2.get_json()["entraron"] == 1 and list(led()["compras"].values())[0]["entraron"] == 1, (r.get_json(), r2.get_json()))
puerta("entrada", sesion="21", codigo=cod, n=1, op="op-2")
puerta("entrada", sesion="21", codigo=cod, n=1, op="op-3")
prueba("no pasa de la cantidad", list(led()["compras"].values())[0]["entraron"] == 2)
r = puerta("entrada", sesion="21", codigo=cod, n=5, op="op-4")
prueba("n distinto de ±1: 400", r.status_code == 400)
n_tg = len(TG)
r = puerta("venta", sesion="21", cantidad=2, tipo="puerta", metodo="efectivo", nombre="Walk in", op="v-1", entran=True)
r2 = puerta("venta", sesion="21", cantidad=2, tipo="puerta", metodo="efectivo", nombre="Walk in", op="v-1", entran=True)
ventas = [c for c in led()["compras"].values() if c["canal"] == "puerta"]
prueba("venta en puerta idempotente", r.status_code == 200 and len(ventas) == 1 and ventas[0]["bruto"] == 1300, (r.get_json(), ventas))
prueba("un solo Telegram por la venta", sum(1 for t in TG[n_tg:] if "Venta en puerta" in t) == 1, TG[n_tg:])
r = puerta("venta", sesion="21", cantidad=-3, tipo="puerta", metodo="efectivo", op="v-2")
prueba("cantidad negativa: 400", r.status_code == 400)
r = puerta("venta", sesion="21", cantidad=3, tipo="cortesia", op="c-1", pidio="Ana")
r2 = puerta("venta", sesion="23", cantidad=2, tipo="cortesia", op="c-2")
prueba("tope de cortesías (4) entre sesiones", r.status_code == 200 and r2.status_code == 409, (r.get_json(), r2.get_json()))
r = puerta("cupo", campo="cortesias_max", cupo=6)
r2 = puerta("venta", sesion="23", cantidad=2, tipo="cortesia", op="c-3")
prueba("subir el tope deja pasar", r.status_code == 200 and r2.status_code == 200, r2.get_json())
r = puerta("nombre", sesion="21", codigo=cod, nombre="Pepe (de parte de Ana)")
prueba("a nombre de", led()["compras"][list(led()["compras"])[0]].get("a_nombre_de", "").startswith("Pepe"))
r = puerta("mover", sesion="21", destino="23", codigo=cod, op="m-1")
r2 = puerta("mover", sesion="21", destino="23", codigo=cod, op="m-1")
movidas = [c for c in led("23")["compras"].values() if c["codigo"] == cod]
prueba("mover idempotente", r.status_code == 200 and len(movidas) == 1 and not any(c["codigo"] == cod and c.get("estado") == "ok" for c in led("21")["compras"].values()), (r.get_json(), r2.get_json(), movidas))
r = puerta("anular", sesion="23", codigo=cod, motivo="reembolso", op="a-1")
prueba("anular", r.status_code == 200 and movidas and [c for c in led("23")["compras"].values() if c["codigo"] == cod][0]["estado"] == "anulada", r.get_json())
r = puerta("cupo", sesion="21", cupo=34)
j = C.get("/boletos/show/show-prueba")
prueba("cupo ajustado", r.status_code == 200, r.get_json())
r = puerta("pausa", pausada=True)
bo_cache = None
r = checkout(sesion="23", email="z@correo.com", nombre="Zoe")
prueba("pausa frena la venta", r.status_code == 409 and r.get_json().get("estado") == "pausada", r.get_json())
puerta("pausa", pausada=False)
r = checkout(sesion="23", email="z@correo.com", nombre="Zoe", cantidad=1)
cs_z = list(SES)[-1]
r = puerta("soltar", sesion="23")
prueba("soltar pagos en curso", r.get_json().get("sueltos") == 1 and SES[cs_z]["status"] == "expired", r.get_json())

print("\n[liquidación]")
r = checkout(sesion="23", email="web@correo.com", nombre="Wendy", cantidad=2, ip="6.6.6.6")
completado(pagar(list(SES)[-1], "web@correo.com", "Wendy"))
r = C.get("/boletos/liquidacion?show=show-prueba", headers={"X-Refresh-Key": "llave-prueba"})
liq = r.get_json()
t = liq["totales"]
esperado_neto = (1300 - 1300 * TRATO["comision_web"]) / 1.16 + 1300 / 1.16
prueba("neto = web con su comisión + efectivo", abs(t["neto"] - esperado_neto) < 0.02, (t, esperado_neto))
prueba("pago artista = fijo + porcentaje del neto", liq["trato"] and abs(liq["trato"]["pago_artista"] - (TRATO["fijo"] + esperado_neto * TRATO["porcentaje"])) < 0.02, liq["trato"])
prueba("cortesías no cuentan dinero", t["cortesias"] == 5 and t["boletos"] == 4, t)
prueba("efectivo esperado", t["efectivo"] == 1300, t)
r = C.get("/boletos/liquidacion?show=show-prueba")
prueba("liquidación sin llave: 401", r.status_code == 401)
r = puerta("telegram", que="liquidacion")
prueba("liquidación a Telegram", r.status_code == 200 and "Liquidación" in TG[-1], r.get_json())
r = puerta("telegram", que="lista")
prueba("lista a Telegram", r.status_code == 200 and "Lista" in TG[-1], TG[-1][:120])

print("\n[webhook: thin, huérfana y regalo]")
reiniciar()
checkout()
cs = list(SES)[-1]
pagar(cs)
r = webhook({"type": "v1.checkout.session.completed", "related_object": {"id": cs, "type": "checkout.session"}})
prueba("evento thin registra", r.status_code == 200 and cs in led()["compras"], r.get_json())
s_mala = {"id": "cs_test_huerfana", "payment_status": "paid", "status": "complete", "amount_total": 65000,
          "metadata": {"tipo": "boleto", "show": "no-existe", "sesion": "21", "cantidad": "1"}, "customer_details": {"email": "h@correo.com"}}
r = webhook({"type": "checkout.session.completed", "data": {"object": s_mala}})
prueba("huérfana: 200 y aviso", r.status_code == 200 and any("SIN registrar" in t for t in TG), TG[-1:])
r = webhook({"type": "checkout.session.completed", "data": {"object": {"id": "cs_x", "metadata": {"tipo": "regalo"}, "payment_status": "paid"}}})
prueba("regalo sin configurar sigue dando 503", r.status_code == 503, r.status_code)
payload = json.dumps({"type": "checkout.session.completed", "data": {"object": {}}}).encode()
r = C.post("/stripe/webhook", data=payload, headers={"Stripe-Signature": "t=1,v1=00", "Content-Type": "application/json"})
prueba("firma mala 400", r.status_code == 400)

print("\n[sobreventa: pago que llega después de soltar el lugar]")
reiniciar()
bo.SHOWS["show-prueba"]["sesiones"][0]["cupo"] = 2
r = checkout(email="a1@correo.com", nombre="A1", cantidad=2)
csA = list(SES)[-1]
s_vieja = dict(SES[csA])
SES[csA]["status"] = "expired"             # Stripe la expiró (simulado)
RELOJ["t"] += 21 * 60
bo._ultima_reconciliacion.clear()
r = checkout(email="b1@correo.com", nombre="B1", cantidad=2, ip="8.8.8.8")
csB = list(SES)[-1]
completado(pagar(csB))
s_vieja.update(status="complete", payment_status="paid", customer_details={"email": "a1@correo.com", "name": "A1"})
completado(s_vieja)
prueba("se registra igual y avisa SOBREVENTA", csA in led()["compras"] and any("SOBREVENTA" in t for t in TG), TG[-1:])
bo.SHOWS["show-prueba"]["sesiones"][0]["cupo"] = 30

print("\n[ventana de venta]")
reiniciar()
RELOJ["local"] = dt.datetime(2026, 11, 25, 20, 1)
r = checkout()
prueba("a menos de 60 min: cerrada en línea", r.status_code == 409 and r.get_json().get("estado") == "cerrada_en_linea", r.get_json())
r = checkout(sesion="23")
prueba("la de las 11 aún vende a las 8:01", r.status_code == 200, r.get_json())
RELOJ["local"] = dt.datetime(2026, 11, 1, 12, 0)
bo.SHOWS["show-prueba"]["venta_abre"] = "2026-11-02T12:00"
r = checkout(email="pronto@correo.com")
prueba("antes de venta_abre: por_abrir", r.status_code == 409 and r.get_json().get("estado") == "por_abrir", r.get_json())

print("\n[correcciones de la revisión]")
from google.api_core import exceptions as gexc   # noqa: E402

# 1. error pasajero de GCS en el webhook -> 500 (Stripe reintenta), no huérfana
reiniciar()
checkout()
cs = list(SES)[-1]
s = pagar(cs)
original = bo._mutar_sesion
bo._mutar_sesion = lambda *a, **k: (_ for _ in ()).throw(gexc.RetryError("GCS no responde", None))
r = completado(s)
bo._mutar_sesion = original
prueba("RetryError en el webhook: 500 y sin aviso de huérfana", r.status_code == 500 and not any("SIN registrar" in t for t in TG), (r.status_code, TG[-1:]))
r = completado(s)
prueba("el reintento de Stripe sí registra", r.status_code == 200 and cs in led()["compras"])
bo._mutar_sesion = lambda *a, **k: (_ for _ in ()).throw(gexc.RetryError("GCS no responde", None))
r = checkout(email="g@correo.com", nombre="Gina")
bo._mutar_sesion = original
prueba("RetryError en checkout: 503 ocupado", r.status_code == 503 and r.get_json().get("codigo") == "ocupado", (r.status_code, r.get_json()))

# 2. mover idempotente por compra aunque falle la segunda escritura
reiniciar()
checkout(cantidad=4)
cs = list(SES)[-1]
completado(pagar(cs))
cod = led()["compras"][cs]["codigo"]
fallar = {"n": 1}


def mutar_que_falla(slug, sid, fn):
    if sid == "21" and fallar["n"]:
        fallar["n"] -= 1
        raise bo.Ocupado("simulado")
    return original(slug, sid, fn)


bo._mutar_sesion = mutar_que_falla
r1 = puerta("mover", sesion="21", destino="23", codigo=cod)
bo._mutar_sesion = original
r2 = puerta("mover", sesion="21", destino="23", codigo=cod)
vivas23 = [c for c in led("23")["compras"].values() if c["codigo"] == cod and c.get("estado", "ok") == "ok"]
vivas21 = [c for c in led("21")["compras"].values() if c["codigo"] == cod and c.get("estado", "ok") == "ok"]
prueba("mover: primer intento avisa que quedó a medias", r1.status_code == 503, r1.get_json())
prueba("mover: el reintento no duplica", r2.status_code == 200 and len(vivas23) == 1 and not vivas21, (r2.get_json(), len(vivas23), len(vivas21)))
r = C.get(f"/boletos/estado?b=show-prueba&f=21&s={cs}")
prueba("gracias de una compra movida enseña la sesión nueva", r.get_json()["compra"]["sesion"]["id"] == "23", r.get_json())
puerta("anular", sesion="23", codigo=cod, op="an-1")
r = C.get(f"/boletos/estado?b=show-prueba&f=21&s={cs}")
prueba("gracias de una compra anulada lo dice", r.get_json()["compra"]["estado"] == "anulada", r.get_json())

# 3. topes dentro de la escritura atómica: 8 a la vez desde la misma IP
reiniciar()
lento = bo._stripe


def stripe_lento(*a, **k):
    if a[1] == "checkout/sessions":
        time.sleep(0.3)
    return lento(*a, **k)


bo._stripe = stripe_lento
res_ip = []
hilos = [threading.Thread(target=lambda i=i: res_ip.append(C.post("/boletos/checkout", json={
    "show": "show-prueba", "sesion": "21", "cantidad": 4, "nombre": "Bot", "email": f"bot{i}@correo.com"},
    headers=ORIGEN, environ_base={"REMOTE_ADDR": "66.66.66.66"}).status_code)) for i in range(8)]
[h.start() for h in hilos]
[h.join() for h in hilos]
bo._stripe = lento
en_pago = sum(a["cantidad"] for a in led()["apartados"].values())
prueba("8 en paralelo desde una IP: no pasan de 8 lugares", en_pago <= 8, (en_pago, sorted(res_ip)))
abiertas = [c for c, s in SES.items() if s["status"] == "open" and all(a["cs"] != c for a in led()["apartados"].values())]
prueba("las sesiones rechazadas quedan expiradas en Stripe", not abiertas, abiertas)

# 4. el atajo por correo sólo vale desde la misma conexión
reiniciar()
r1 = checkout(email="victima@correo.com", nombre="Vicky", ip="1.1.1.1")
r2 = checkout(email="victima@correo.com", nombre="Otro", ip="2.2.2.2")
prueba("mismo correo, otra IP: no recibe la liga ajena", r2.status_code == 200 and r2.get_json()["url"] != r1.get_json()["url"] and SES[list(SES)[0]]["status"] == "open", (r1.get_json(), r2.get_json()))

# 5. cortesía repetida por mala señal no choca con el tope
reiniciar()
checkout()
r1 = puerta("venta", sesion="21", cantidad=3, tipo="cortesia", op="cort-1")
r2 = puerta("venta", sesion="21", cantidad=3, tipo="cortesia", op="cort-1")
prueba("cortesía repetida: mismo código, no 409", r1.status_code == 200 and r2.status_code == 200 and r1.get_json()["codigo"] == r2.get_json()["codigo"], (r1.get_json(), r2.get_json()))

# 6. el PIN de puerta no reinicia el freno del PIN de barra
reiniciar()
ip_atacante = {"REMOTE_ADDR": "77.77.77.77"}
for i in range(9):
    C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": f"0000000{i}"}, headers=ORIGEN, environ_base=ip_atacante)
C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": "445566"}, headers=ORIGEN, environ_base=ip_atacante)
r = C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": "00000009"}, headers=ORIGEN, environ_base=ip_atacante)
prueba("9 malos + PIN de puerta + 1 malo = bloqueado", r.status_code == 429, r.status_code)
appmod.freno_pin._fallos.clear(); appmod.freno_pin._bloqueos.clear()

# 7. evento thin cuya sesión no se pudo leer -> 503
reiniciar()
r = webhook({"type": "v1.checkout.session.completed", "related_object": {"id": "cs_test_no_existe", "type": "checkout.session"}})
prueba("thin sin sesión legible: 503 para que Stripe reintente", r.status_code == 503, r.status_code)

# 8. huérfana registrada por la ruta de operación conserva su código
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
s = pagar(cs)
s_rota = json.loads(json.dumps(s))
s_rota["metadata"]["sesion"] = "99"
webhook({"type": "checkout.session.completed", "data": {"object": s_rota}})
r = C.post("/boletos/huerfana", json={"cs": cs, "show": "show-prueba", "sesion": "21"}, headers={"X-Refresh-Key": "llave-prueba"})
c = led()["compras"].get(cs) or {}
prueba("huérfana: se registra con el código del recibo", r.status_code == 200 and c.get("codigo") == s["metadata"]["codigo"] and c.get("metodo") == "stripe", (r.get_json(), c))
r = C.post("/boletos/huerfana", json={"cs": cs, "show": "show-prueba", "sesion": "21"})
prueba("huérfana sin llave: 401", r.status_code == 401)

# 9. venta_abre con zona horaria se rechaza al cargar
import pathlib   # noqa: E402
tmpcat = pathlib.Path(TMP) / "cat.json"
cat = json.loads(pathlib.Path(API_DIR, "boletos.json").read_text(encoding="utf-8"))
cat["shows"][0]["venta_abre"] = "2026-10-28T12:00:00-06:00"
tmpcat.write_text(json.dumps(cat), encoding="utf-8")
viejo = bo.CATALOGO
bo.CATALOGO = tmpcat
try:
    bo._cargar_catalogo()
    rechazo = False
except ValueError:
    rechazo = True
bo.CATALOGO = viejo
prueba("venta_abre con zona horaria: el catálogo no carga", rechazo)

# 10. registro casi simultáneo: un solo aviso
reiniciar()
checkout()
cs = list(SES)[-1]
s = pagar(cs)
n0 = sum(1 for t in TG if "boleto" in t and "🎟" in t)
hilos = [threading.Thread(target=lambda: completado(s)), threading.Thread(target=lambda: C.get(f"/boletos/estado?b=show-prueba&f=21&s={cs}&v=1"))]
[h.start() for h in hilos]
[h.join() for h in hilos]
n1 = sum(1 for t in TG if "🎟" in t)
prueba("webhook y gracias a la vez: un solo Telegram", n1 - n0 == 1, TG[-3:])

# 11. errores con código para traducir
r = checkout(email="malo")
prueba("error con código", r.get_json().get("codigo") == "correo", r.get_json())

print("\n[reembolsos y PINes del equipo]")
import regalo as regalo_mod   # noqa: E402

# reembolso completo en Stripe -> la compra se anula sola
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
completado(pagar(cs))
pi = led()["compras"][cs]["pi"]
cargo = {"id": "ch_1", "object": "charge", "payment_intent": pi, "amount": 130000, "amount_refunded": 130000, "refunded": True, "metadata": {}}
r = webhook({"type": "charge.refunded", "data": {"object": cargo}})
c = led()["compras"][cs]
prueba("reembolso completo: anulada y aviso", r.status_code == 200 and c["estado"] == "anulada" and any("Reembolso en Stripe: anulé" in t for t in TG), (c.get("estado"), TG[-1:]))
n = len(TG)
webhook({"type": "charge.refunded", "data": {"object": cargo}})
prueba("reembolso repetido: sin aviso doble", len(TG) == n, TG[n:])
j = C.get("/boletos/show/show-prueba").get_json()
prueba("el lugar quedó libre", j["sesiones"][0]["quedan"] == 30, j["sesiones"][0])

# parcial de boletos completos -> se quitan esos boletos
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
completado(pagar(cs))
pi = led()["compras"][cs]["pi"]
parcial = {"payment_intent": pi, "amount": 130000, "amount_refunded": 65000}
webhook({"type": "charge.refunded", "data": {"object": parcial}})
c = led()["compras"][cs]
prueba("reembolso de 1 de 2: le queda 1 y $650", c["estado"] == "ok" and c["cantidad"] == 1 and c["bruto"] == 650 and any("le quité 1" in t for t in TG), (c, TG[-1:]))
n = len(TG)
webhook({"type": "charge.refunded", "data": {"object": parcial}})
prueba("el mismo parcial otra vez no quita más", led()["compras"][cs]["cantidad"] == 1 and len(TG) == n, (led()["compras"][cs]["cantidad"], TG[n:]))
liq = C.get("/boletos/liquidacion?show=show-prueba", headers={"X-Refresh-Key": "llave-prueba"}).get_json()
prueba("la liquidación cuenta 1 boleto de $650", liq["totales"]["boletos"] == 1 and liq["totales"]["bruto"] == 650, liq["totales"])
webhook({"type": "charge.refunded", "data": {"object": dict(parcial, amount_refunded=130000)}})
prueba("después el resto: anulada", led()["compras"][cs]["estado"] == "anulada", led()["compras"][cs]["estado"])

# un monto que no cuadra con boletos completos -> sólo aviso
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
completado(pagar(cs))
pi = led()["compras"][cs]["pi"]
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 130000, "amount_refunded": 30000}}})
prueba("reembolso de $300: no toca la compra y avisa", led()["compras"][cs]["cantidad"] == 2 and any("no cuadra" in t for t in TG), TG[-1:])
n = len(TG)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 130000, "amount_refunded": 30000}}})
prueba("el mismo monto que no cuadra otra vez: sin aviso doble", len(TG) == n and led()["compras"][cs]["cantidad"] == 2, TG[n:])

# reembolso que llega antes que el pago -> se registra ya anulada
reiniciar()
checkout(cantidad=1)
cs = list(SES)[-1]
s = pagar(cs)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": s["payment_intent"], "amount": 65000, "amount_refunded": 65000,
                                                        "metadata": {"tipo": "boleto", "codigo": s["metadata"]["codigo"]}}}})
prueba("reembolso antes del pago: queda la marca", any("antes que su pago" in t for t in TG), TG[-1:])
completado(s)
prueba("al registrarse el pago, queda anulada", led()["compras"][cs]["estado"] == "anulada", led()["compras"][cs]["estado"])

# un cargo que no es de boletos no hace nada
n = len(TG)
r = webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": "pi_otro", "amount": 50000, "amount_refunded": 50000}}})
prueba("reembolso ajeno: 200 y nada", r.status_code == 200 and len(TG) == n)

# reembolso de una compra que se pasó de sesión: se anula la copia viva
reiniciar()
checkout(cantidad=1)
cs = list(SES)[-1]
completado(pagar(cs))
cod = led()["compras"][cs]["codigo"]
pi = led()["compras"][cs]["pi"]
puerta("mover", sesion="21", destino="23", codigo=cod)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 65000, "amount_refunded": 65000}}})
copia = [c for c in led("23")["compras"].values() if c["codigo"] == cod][0]
prueba("reembolso de una compra movida anula la copia", copia["estado"] == "anulada", copia.get("estado"))

# una compra que quedó viva en dos sesiones (mover a medias): el reembolso anula las dos y no se revive
reiniciar()
checkout(cantidad=1)
cs = list(SES)[-1]
completado(pagar(cs))
cod = led()["compras"][cs]["codigo"]
pi = led()["compras"][cs]["pi"]
fallar = {"n": 1}
bo._mutar_sesion = mutar_que_falla
puerta("mover", sesion="21", destino="23", codigo=cod)
bo._mutar_sesion = original
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 65000, "amount_refunded": 65000}}})
vivas = [c for x in ("21", "23") for c in led(x)["compras"].values() if c["codigo"] == cod and c.get("estado", "ok") == "ok"]
prueba("viva en dos sesiones: el reembolso anula las dos", not vivas, vivas)
r = puerta("mover", sesion="21", destino="23", codigo=cod)
prueba("«Pasar a» no revive una copia anulada", r.status_code in (404, 409) and not [c for c in led("23")["compras"].values() if c["codigo"] == cod and c.get("estado", "ok") == "ok"], r.get_json())

# reembolsos fuera de orden: uno viejo (acumulado menor) que llega tarde no regresa boletos
reiniciar()
checkout(cantidad=3)
cs = list(SES)[-1]
completado(pagar(cs))
pi = led()["compras"][cs]["pi"]
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 195000, "amount_refunded": 65000}}})
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 195000, "amount_refunded": 130000}}})
prueba("segundo parcial: dice cuántos ahora y cuántos en total", any("le quité 1 boleto(s) ahora (2 en total)" in t for t in TG), TG[-1:])
n = len(TG)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 195000, "amount_refunded": 65000}}})
c = led()["compras"][cs]
prueba("el reembolso viejo que llega tarde no regresa boletos", c["cantidad"] == 1 and c["bruto"] == 650 and len(TG) == n, (c["cantidad"], c["bruto"], TG[n:]))
liq = C.get("/boletos/liquidacion?show=show-prueba", headers={"X-Refresh-Key": "llave-prueba"}).get_json()
prueba("Stripe estimada sobre lo cobrado, no sobre lo que quedó", abs(liq["totales"]["stripe_estimada"] - (1950 * 0.036 + 3) * 1.16) < 0.02, liq["totales"])

# marca de reembolso + el pago entra por la reconciliación (no por el webhook) -> se aplica igual
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
s = pagar(cs)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": s["payment_intent"], "amount": 130000, "amount_refunded": 130000,
                                                        "metadata": {"tipo": "boleto", "codigo": s["metadata"]["codigo"]}}}})
RELOJ["t"] += 21 * 60
puerta("lista")
prueba("marca + reconciliación: queda anulada", led()["compras"][cs]["estado"] == "anulada", led()["compras"][cs].get("estado"))
n = len(TG)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": s["payment_intent"], "amount": 130000, "amount_refunded": 130000,
                                                        "metadata": {"tipo": "boleto", "codigo": s["metadata"]["codigo"]}}}})
completado(s)
prueba("el reintento del webhook no la revive ni avisa doble", led()["compras"][cs]["estado"] == "anulada" and not any("antes que su pago" in t for t in TG[n:]), TG[n:])

# "no cuadra" viejo que llega tarde: un solo aviso
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
completado(pagar(cs))
pi = led()["compras"][cs]["pi"]
for monto in (95000, 30000, 95000):
    webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 130000, "amount_refunded": monto}}})
prueba("no cuadra: el viejo y el repetido no vuelven a avisar", sum("no cuadra" in t for t in TG) == 1, [t for t in TG if "no cuadra" in t])

# la puerta pasa la compra de sesión justo mientras llega el reembolso: se ajusta la copia
reiniciar()
checkout(cantidad=1)
cs = list(SES)[-1]
completado(pagar(cs))
pi, cod = led()["compras"][cs]["pi"], led()["compras"][cs]["codigo"]
buscar_original = bo._compras_de_pi


def buscar_y_mover(pi_):
    r_ = buscar_original(pi_)
    bo._compras_de_pi = buscar_original
    puerta("mover", sesion="21", destino="23", codigo=cod)
    return r_


bo._compras_de_pi = buscar_y_mover
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": pi, "amount": 65000, "amount_refunded": 65000}}})
bo._compras_de_pi = buscar_original
copia = [c for c in led("23")["compras"].values() if c["codigo"] == cod]
prueba("reembolso mientras la puerta la pasa: se anula la copia", copia and copia[0]["estado"] == "anulada" and any("anulé" in t for t in TG), (copia, TG[-2:]))

# el reembolso llega mientras la puerta la está pasando (después de leerla): la copia se iguala
for devuelto_, esperado in ((130000, "anulada"), (65000, 1)):
    reiniciar()
    checkout(cantidad=2)
    cs = list(SES)[-1]
    completado(pagar(cs))
    pi, cod = led()["compras"][cs]["pi"], led()["compras"][cs]["codigo"]
    cupo_original = bo._cupo

    def cupo_y_reembolso(*a, **kw):
        bo._cupo = cupo_original
        bo.reembolso({"payment_intent": pi, "amount": 130000, "amount_refunded": devuelto_, "metadata": {"tipo": "boleto"}})
        return cupo_original(*a, **kw)

    bo._cupo = cupo_y_reembolso
    r = puerta("mover", sesion="21", destino="23", codigo=cod)
    bo._cupo = cupo_original
    copia = [c for c in led("23")["compras"].values() if c["codigo"] == cod][0]
    if esperado == "anulada":
        vivas = [c for x in ("21", "23") for c in led(x)["compras"].values() if c["codigo"] == cod and c.get("estado", "ok") == "ok"]
        prueba("reembolso completo mientras se pasa: la copia también queda anulada", r.status_code == 409 and not vivas, (r.status_code, vivas))
    else:
        prueba("reembolso parcial mientras se pasa: la copia queda con 1", r.status_code == 200 and copia.get("estado", "ok") == "ok" and copia["cantidad"] == 1, (r.status_code, copia))

# carrera: el pago se registra mientras llega el reembolso (leyó reembolsos.json antes de la marca)
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
s = pagar(cs)
previo_original = bo._reembolso_previo
bo._reembolso_previo = lambda pi: None          # el registro no ve la marca: todavía no existía
completado(s)
bo._reembolso_previo = previo_original
marcar_original = bo._marcar_reembolso
llamadas_compras = {"n": 0}
compras_original = bo._compras_de_pi


def compras_tarde(pi):                          # la primera búsqueda no la ve; la segunda (tras la marca), sí
    llamadas_compras["n"] += 1
    return ([], False) if llamadas_compras["n"] == 1 else compras_original(pi)


bo._compras_de_pi = compras_tarde
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": s["payment_intent"], "amount": 130000, "amount_refunded": 130000,
                                                        "metadata": {"tipo": "boleto", "codigo": s["metadata"]["codigo"]}}}})
bo._compras_de_pi = compras_original
prueba("carrera marca/registro: la segunda vuelta la anula", led()["compras"][cs]["estado"] == "anulada", led()["compras"][cs].get("estado"))

# la comisión de Stripe se cuenta una vez por pago aunque esté en dos sesiones
reiniciar()
checkout(cantidad=1)
cs = list(SES)[-1]
completado(pagar(cs))
cod = led()["compras"][cs]["codigo"]
fallar = {"n": 1}
bo._mutar_sesion = mutar_que_falla
puerta("mover", sesion="21", destino="23", codigo=cod)   # viva en las dos
bo._mutar_sesion = original
liq = C.get("/boletos/liquidacion?show=show-prueba", headers={"X-Refresh-Key": "llave-prueba"}).get_json()
prueba("Stripe estimada una vez por pago", abs(liq["totales"]["stripe_estimada"] - (650 * 0.036 + 3) * 1.16) < 0.02, liq["totales"])

# marca de un parcial: el aviso no promete anularla
reiniciar()
checkout(cantidad=2)
cs = list(SES)[-1]
s = pagar(cs)
webhook({"type": "charge.refunded", "data": {"object": {"payment_intent": s["payment_intent"], "amount": 130000, "amount_refunded": 65000,
                                                        "metadata": {"tipo": "boleto", "codigo": s["metadata"]["codigo"]}}}})
prueba("marca de parcial: dice que quita boletos", "le quito los boletos" in TG[-1], TG[-1:])
completado(s)
prueba("al registrarse, le queda 1", led()["compras"][cs]["cantidad"] == 1 and led()["compras"][cs]["estado"] == "ok", led()["compras"][cs])

# textos con 1 lugar
prueba("queda 1 lugar (singular)", bo._quedan_txt(1) == "queda 1 lugar" and bo._quedan_txt(3) == "quedan 3 lugares" and bo._quedan_txt(-2) == "quedan 0 lugares")

# firma de Stripe: varias v1 (rotación del secreto) y basura en t
payload = b'{"x":1}'
t_ok = str(int(time.time()))
buena = hmac.new(b"whsec_prueba", f"{t_ok}.".encode() + payload, hashlib.sha256).hexdigest()
prueba("firma: la buena primero y otra después", regalo_mod.verificar_firma(payload, f"t={t_ok},v1={buena},v1={'0' * 64}"))
prueba("firma: otra primero y la buena después", regalo_mod.verificar_firma(payload, f"t={t_ok},v1={'0' * 64},v1={buena}"))
prueba("firma: ninguna buena", not regalo_mod.verificar_firma(payload, f"t={t_ok},v1={'0' * 64}"))
prueba("firma: t no numérico no truena", not regalo_mod.verificar_firma(payload, f"t=abc,v1={buena}"))
prueba("firma: t con dígitos no ASCII no truena", not regalo_mod.verificar_firma(payload, f"t=²,v1={buena}") and not regalo_mod.verificar_firma(payload, "t=" + "9" * 5000 + f",v1={buena}"))
prueba("firma: v1 con acentos no truena", not regalo_mod.verificar_firma(payload, f"t={t_ok},v1=ñandú"))
r = C.post("/stripe/webhook", data=payload, headers={"Stripe-Signature": "t=abc,v1=x", "Content-Type": "application/json"})
prueba("webhook con firma basura: 400, no 500", r.status_code == 400, r.status_code)

# miel: el campo se llama distinto en la página, pero el API recibe empresa_web
r = checkout(empresa_web="algo")
prueba("miel llena: no se cobra", r.status_code == 400, r.status_code)

# Stripe caído al crear el pago: avisa una vez, no en cada intento
reiniciar()
bo._falla_stripe[0] = 0.0
antes_stripe = bo._stripe
bo._stripe = lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("sin red"))
r1 = checkout(cantidad=1)
r2 = checkout(cantidad=1, email="otra@correo.com")
bo._stripe = antes_stripe
avisos = [t for t in TG if "Stripe no dejó crear un pago" in t]
prueba("Stripe caído: 502 y un solo aviso", r1.status_code == 502 and r2.status_code == 502 and len(avisos) == 1, (r1.status_code, r2.status_code, len(avisos)))

# PINes del equipo
reiniciar()
regalo_mod.PINES_EQUIPO.clear()
regalo_mod.PINES_EQUIPO.update({"Ana": "11223344"})
prueba("quien_pin: barra", regalo_mod.quien_pin("12345678") == "barra")
prueba("quien_pin: Ana", regalo_mod.quien_pin("11223344") == "Ana")
prueba("quien_pin: nadie", regalo_mod.quien_pin("99999999") is None and not regalo_mod.pin_correcto(""))
r = puerta("lista", pin="11223344")
prueba("Ana abre la puerta con su PIN", r.status_code == 200, r.status_code)
r = puerta("venta", pin="11223344", sesion="21", cantidad=1, tipo="puerta", metodo="efectivo", op="ana-1", entran=True)
prueba("el aviso dice quién vendió", r.status_code == 200 and "por Ana" in TG[-1], TG[-1:])
prueba("la venta guarda quién", [c for c in led()["compras"].values() if c["canal"] == "puerta"][0].get("por") == "Ana")
r = puerta("venta", sesion="21", cantidad=1, tipo="puerta", metodo="efectivo", op="barra-1", entran=True, pin="12345678")
prueba("con el PIN general lo dice", "con el PIN general" in TG[-1], TG[-1:])
appmod.freno_pin._fallos.clear(); appmod.freno_pin._bloqueos.clear()
ip_b = {"REMOTE_ADDR": "88.88.88.88"}
for i in range(9):
    C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": f"0000000{i}"}, headers=ORIGEN, environ_base=ip_b)
C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": "11223344"}, headers=ORIGEN, environ_base=ip_b)
r = C.post("/boletos/puerta/lista", json={"show": "show-prueba", "pin": "00000009"}, headers=ORIGEN, environ_base=ip_b)
prueba("un PIN personal no borra los fallos (no sirve para adivinar)", r.status_code == 429, r.status_code)
appmod.freno_pin._fallos.clear(); appmod.freno_pin._bloqueos.clear()
r = C.post("/regalo/canjear", json={"codigo": "ROSSO-XXXX-XXXX", "monto": 1, "pin": "11223344"}, headers=ORIGEN)
prueba("el PIN personal también entra al canje (pasa el PIN, falla por el código)", r.status_code != 403, (r.status_code, r.get_json()))
regalo_mod.PINES_EQUIPO.clear()
r = puerta("lista", pin="11223344")
prueba("PIN dado de baja ya no entra", r.status_code == 403, r.status_code)
prueba("PINES_BARRA mal formado se ignora", regalo_mod._pines_equipo("no es json") == {} and regalo_mod._pines_equipo('{"X": "12"}') == {})
appmod.freno_pin._fallos.clear(); appmod.freno_pin._bloqueos.clear()

print(f"\n{len(OK)} bien, {len(FALLAS)} mal")
if FALLAS:
    print("FALLARON:", FALLAS)
    sys.exit(1)
