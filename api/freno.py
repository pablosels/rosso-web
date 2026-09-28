# -*- coding: utf-8 -*-
"""Freno de intentos fallidos del PIN de barra (canje de tarjetas de regalo y Sello ROSSO).

Cuenta los PIN equivocados por IP, en memoria: 10 fallos dentro de 15 minutos bloquean esa IP
15 minutos (HTTP 429), aunque después mande el PIN bueno. Un PIN bueno borra los fallos de su
IP. Cada bloqueo manda un aviso por Telegram (uno por IP y por ventana, y a lo más 5 avisos por
ventana en total, para que un ataque desde muchas IPs no inunde el chat).

Es un freno parcial, a propósito sin base de datos:
- vive en la memoria de cada instancia de Cloud Run y hay hasta 2 (max-instances 2): en el peor
  caso son ~20 intentos por ventana, dos avisos por el mismo bloqueo, y un reinicio, un
  despliegue o un escalado a cero lo pone en ceros;
- quien tenga muchas IPs distintas no queda frenado, sólo avisado (una IPv6 cuenta por su /64
  para que no baste con rotar la dirección dentro de la misma conexión);
- toda la barra sale a internet por la misma IP: si alguien en el WiFi del bar se equivoca 10
  veces, la barra también espera 15 min (o usa datos del celular).
Con el PIN de 8 dígitos (10^8 combinaciones) y ~1,900 intentos al día por IP, adivinarlo desde
una sola IP tomaría décadas.
"""
import datetime as dt
import html
import ipaddress
import math
import threading
import time

MAX_FALLOS = 10
VENTANA = 15 * 60          # segundos
MAX_AVISOS = 5             # avisos de Telegram por ventana, sumando todas las IPs
BARRER_DESDE = 2000        # con más IPs anotadas que esto, se tiran las que ya caducaron


def clave_ip(xff, remota):
    """IP del cliente según el frontal de Google. Cloud Run AGREGA la IP real al final de
    X-Forwarded-For; lo que venga antes lo pudo escribir el propio cliente, así que se toma
    la última. Las IPv6 se agrupan por /64."""
    ip = (xff or "").split(",")[-1].strip() or (remota or "").strip()
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return ip[:64] or "?"
    if a.version == 6:
        if a.ipv4_mapped:
            return str(a.ipv4_mapped)
        return str(ipaddress.ip_network(f"{a}/64", strict=False))
    return str(a)


class Freno:
    def __init__(self, avisar=None, max_fallos=MAX_FALLOS, ventana=VENTANA, max_avisos=MAX_AVISOS,
                 reloj=time.monotonic):
        self.avisar = avisar      # función(texto) que manda el Telegram
        self.max_fallos, self.ventana, self.max_avisos, self.reloj = max_fallos, ventana, max_avisos, reloj
        self._fallos = {}         # ip -> [(momento, ruta), ...] dentro de la ventana
        self._bloqueos = {}       # ip -> momento en que se levanta
        self._avisos = []         # momentos de los avisos mandados
        self._lock = threading.Lock()

    def espera(self, ip):
        """Segundos que le faltan a esa IP para poder volver a intentar; 0 si puede."""
        with self._lock:
            hasta = self._bloqueos.get(ip)
            if hasta is None:
                return 0
            falta = hasta - self.reloj()
            if falta > 0:
                return math.ceil(falta)
            del self._bloqueos[ip]
            return 0

    def acierto(self, ip):
        with self._lock:
            self._fallos.pop(ip, None)

    def fallo(self, ip, ruta):
        """Anota un PIN equivocado. Devuelve True si con este la IP quedó bloqueada."""
        with self._lock:
            ahora = self.reloj()
            self._barrer(ahora)
            marcas = [m for m in self._fallos.get(ip, []) if ahora - m[0] < self.ventana]
            marcas.append((ahora, ruta))
            if len(marcas) < self.max_fallos:
                self._fallos[ip] = marcas
                print(f"freno pin: fallo {len(marcas)}/{self.max_fallos} de {ip} ({ruta})")
                return False
            self._fallos.pop(ip, None)
            self._bloqueos[ip] = ahora + self.ventana
            self._avisos = [t for t in self._avisos if ahora - t < self.ventana]
            n_aviso = 0
            if len(self._avisos) < self.max_avisos:
                self._avisos.append(ahora)
                n_aviso = len(self._avisos)
        rutas = ", ".join(sorted({r for _, r in marcas}))
        print(f"freno pin: bloqueada {ip} por {self.ventana // 60} min tras {len(marcas)} fallos ({rutas})")
        if n_aviso and self.avisar:
            hasta = (dt.datetime.now() + dt.timedelta(seconds=self.ventana)).strftime("%H:%M")
            texto = (f"🔒 <b>PIN de barra</b>: {len(marcas)} intentos con PIN equivocado desde la IP "
                     f"<code>{html.escape(ip)}</code> en menos de {self.ventana // 60} min ({html.escape(rutas)}). "
                     f"Queda bloqueada hasta las {hasta}.\nSi no fue alguien de la barra, alguien está "
                     "tratando de adivinar el PIN; si se repite, rótalo (ver api/DESPLEGAR.md).")
            if n_aviso == self.max_avisos:
                texto += (f"\n\n⚠️ Van {n_aviso} IPs bloqueadas en {self.ventana // 60} min; no aviso de más "
                          "hasta que pase la ventana (quedan en el log de Cloud Run como «freno pin»).")
            try:
                self.avisar(texto)
            except Exception as e:
                print("freno pin: telegram fallo:", e)
        return True

    def _barrer(self, ahora):
        if len(self._fallos) > BARRER_DESDE:
            for ip in [ip for ip, m in self._fallos.items() if ahora - m[-1][0] >= self.ventana]:
                del self._fallos[ip]
        if len(self._bloqueos) > BARRER_DESDE:
            for ip in [ip for ip, hasta in self._bloqueos.items() if hasta <= ahora]:
                del self._bloqueos[ip]
