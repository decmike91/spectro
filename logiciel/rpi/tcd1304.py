"""
Pilote Python du spectrographe TCD1304DG (côté Raspberry Pi Zero ou PC).

Le Pico (firmware/main.py) est vu comme un port série USB (/dev/ttyACM0).

    from tcd1304 import TCD1304
    ccd = TCD1304("/dev/ttyACM0")
    ccd.set_integration_us(20000)
    frame = ccd.read_frame()          # numpy uint16, 3694 valeurs brutes
    spectre = ccd.active(frame)       # 3648 pixels utiles

Un simulateur (TCD1304Simulator) offre la même API pour tester sans matériel.
"""
import struct
import time
import numpy as np

NPIX = 3694
ACTIVE = slice(32, 32 + 3648)       # pixels utiles S1..S3648
SHIELDED = slice(16, 29)            # pixels masqués (noir optique)
ADC_MAX = 4095


class TCD1304:
    def __init__(self, port="/dev/ttyACM0", timeout=3.0):
        import serial  # pyserial
        self.ser = serial.Serial(port, 115200, timeout=timeout)
        time.sleep(0.2)
        self.ser.reset_input_buffer()
        self.tint_us = None
        self.info = self.get_info()

    # --- bas niveau -------------------------------------------------------
    def _cmd(self, text):
        self.ser.write((text + "\n").encode())

    def _line(self):
        line = self.ser.readline().decode(errors="replace").strip()
        if not line:
            raise TimeoutError("pas de réponse du Pico")
        if line.startswith("ERR"):
            raise RuntimeError(line)
        return line

    # --- API --------------------------------------------------------------
    def get_info(self):
        self.ser.reset_input_buffer()
        self._cmd("I")
        line = self._line()
        info = dict(kv.split("=") for kv in line.split()[1:] if "=" in kv)
        self.tint_us = int(info.get("tint_us", 0))
        return info

    def set_integration_us(self, tint_us):
        self._cmd("T %d" % int(tint_us))
        line = self._line()
        self.tint_us = int(line.split("=")[1])
        return self.tint_us

    def read_frame(self):
        self._cmd("R")
        hdr = self.ser.read_until(b"FRM:")
        if not hdr.endswith(b"FRM:"):
            rest = hdr.decode(errors="replace").strip()
            raise RuntimeError("trame invalide : " + (rest or "timeout"))
        raw = self.ser.read(2 * NPIX)
        if len(raw) != 2 * NPIX:
            raise TimeoutError("trame incomplète")
        return np.frombuffer(raw, dtype="<u2") & 0x0FFF

    def close(self):
        self.ser.close()

    # --- utilitaires ------------------------------------------------------
    @staticmethod
    def active(frame):
        return np.asarray(frame)[ACTIVE]

    @staticmethod
    def optical_black(frame):
        return float(np.mean(np.asarray(frame)[SHIELDED]))


class TCD1304Simulator:
    """Faux capteur : raies d'une lampe Hg/Ar + continuum + bruit."""
    LINES_NM = [(404.66, .35), (435.83, 1.0), (546.07, .9), (576.96, .3),
                (579.07, .3), (696.54, .15), (763.51, .25), (811.53, .2)]

    def __init__(self, *a, **k):
        self.tint_us = 10000
        self.info = {"npix": str(NPIX), "fm": "1000000", "tint_us": "10000", "sim": "1"}
        px = np.arange(3648)
        self._nm = 350 + 0.135 * px - 2.0e-6 * px ** 2   # pseudo-calibration
        self._rng = np.random.default_rng()

    def get_info(self):
        return self.info

    def set_integration_us(self, tint_us):
        self.tint_us = max(10, int(tint_us))
        return self.tint_us

    def read_frame(self):
        time.sleep(max(0.015, self.tint_us / 1e6))
        sig = 80 * np.exp(-((self._nm - 600) / 150) ** 2)
        for c, a in self.LINES_NM:
            sig += 3000 * a * np.exp(-0.5 * ((self._nm - c) / 0.6) ** 2)
        sig *= self.tint_us / 10000.0
        frame = np.full(NPIX, 120.0)
        frame[ACTIVE] += sig
        frame += self._rng.normal(0, 4, NPIX)
        return np.clip(frame, 0, ADC_MAX).astype(np.uint16)

    def close(self):
        pass

    active = staticmethod(TCD1304.active)
    optical_black = staticmethod(TCD1304.optical_black)


class TCD1304Remote:
    """Même API que TCD1304, mais passe par le serveur (serveur/spectro_server.py)
    au lieu d'ouvrir le port série.

    Le port série ne peut être ouvert que par un seul programme : avec ce pilote,
    l'interface PyQt et le serveur (donc l'appli Android) tournent en même temps
    et partagent le capteur. Le temps de pose et le noir soustrait en direct sont
    alors communs à l'écran du Pi et au téléphone.

    Si le serveur n'est pas encore prêt (démarrage du Pi), les lectures attendent
    au lieu d'échouer.
    """
    remote = True

    def __init__(self, url="http://127.0.0.1:8080", timeout=5.0, wait_s=60.0):
        url = url.strip().rstrip("/")
        self.url = url if "://" in url else "http://" + url
        if self.url.count(":") < 2:                    # port par défaut
            self.url += ":8080"
        self.timeout = timeout
        self.tint_us = None
        self.info = {"remote": self.url}
        self.calib = None
        self._last_t = 0.0          # horodatage (horloge du serveur) du dernier spectre lu
        self._want_tint = None      # temps de pose demandé, pas encore vu dans un spectre
        self._t_change = 0.0
        self._t_check = 0.0
        self._closed = False
        t_end = time.time() + wait_s
        while True:
            try:
                self.get_info()
                break
            except OSError:
                if time.time() > t_end:
                    break           # on continue : les lectures attendront le serveur
                time.sleep(1.0)

    # --- HTTP -------------------------------------------------------------
    def _call(self, method, path, data=None):
        import json
        import urllib.request
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(self.url + path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            d = json.loads(r.read().decode())
        if not d.get("ok"):
            raise RuntimeError(d.get("error", "erreur du serveur"))
        return d.get("data")

    # --- API --------------------------------------------------------------
    def get_info(self):
        st = self._call("GET", "/api/status")
        self.info = dict(st.get("device") or {}, remote=self.url)
        self.tint_us = int(st.get("tint_us") or 0) or None
        self.calib = st.get("calib")
        return self.info

    def set_integration_us(self, tint_us):
        while True:
            try:
                st = self._call("POST", "/api/config", {"tint_us": int(tint_us)})
                break
            except OSError:
                if self._closed:
                    raise RuntimeError("pilote fermé")
                time.sleep(1.0)
        self.tint_us = int(st["tint_us"])
        self._want_tint, self._t_change = self.tint_us, time.time()
        return self.tint_us

    def _ensure_live(self):
        """Allume le direct du serveur s'il est éteint (sans changer le noir choisi
        depuis le téléphone). Vérifié toutes les 2 s : le téléphone peut l'éteindre."""
        if time.time() - self._t_check < 2.0:
            return
        self._t_check = time.time()
        st = self._call("GET", "/api/status")
        self.calib = st.get("calib")
        if not st.get("live"):
            self._call("POST", "/api/live", {"on": True, "dark_id": st.get("live_dark_id")})

    def read_frame(self):
        import urllib.error
        while True:
            if self._closed:
                raise RuntimeError("pilote fermé")
            try:
                self._ensure_live()
                m = self._call("GET", "/api/live/last")
            except urllib.error.HTTPError as e:
                if e.code != 404:   # 404 : pas encore de spectre
                    raise
                m = None
            except OSError:         # serveur arrêté ou en cours de démarrage
                time.sleep(1.0)
                continue
            if m and m["t"] > self._last_t:
                tint_ok = (self._want_tint is None
                           or abs(m.get("tint_us", 0) - self._want_tint) <= max(2, 0.05 * self._want_tint)
                           or time.time() - self._t_change > 2.0 + self._want_tint / 1e6)
                self._last_t = m["t"]
                if tint_ok:
                    self._want_tint = None
                    return self._to_frame(m)
            time.sleep(0.02)

    @staticmethod
    def _to_frame(m):
        """Reconstitue une trame brute (3694 valeurs) à partir du spectre utile du serveur."""
        black = float(m.get("black", 0.0))
        vals = np.asarray(m["values"], float)
        if m.get("sub_black", True):
            vals = vals + black
        frame = np.full(NPIX, black)
        frame[ACTIVE] = vals
        return frame

    def put_calibration(self, coeffs, points):
        self._call("PUT", "/api/calibration",
                   {"coeffs": [float(c) for c in coeffs], "points": [list(p) for p in points]})

    def close(self):
        self._closed = True

    active = staticmethod(TCD1304.active)
    optical_black = staticmethod(TCD1304.optical_black)


if __name__ == "__main__":
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    ccd = TCD1304(port)
    print("Info :", ccd.info)
    t0 = time.time()
    f = ccd.read_frame()
    print("Trame lue en %.1f ms, min=%d max=%d noir optique=%.1f"
          % (1e3 * (time.time() - t0), f.min(), f.max(), ccd.optical_black(f)))
