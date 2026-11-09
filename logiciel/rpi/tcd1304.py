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


if __name__ == "__main__":
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyACM0"
    ccd = TCD1304(port)
    print("Info :", ccd.info)
    t0 = time.time()
    f = ccd.read_frame()
    print("Trame lue en %.1f ms, min=%d max=%d noir optique=%.1f"
          % (1e3 * (time.time() - t0), f.min(), f.max(), ccd.optical_black(f)))
