#!/usr/bin/env python3
"""
Serveur réseau du spectrographe TCD1304DG (Raspberry Pi Zero).

Il pilote le capteur (via le Pico, pilote ../rpi/tcd1304.py) et expose :
  * une API HTTP JSON  (réglages, acquisitions, séquences, bibliothèque de spectres,
                        étalonnage, ventilateur, export CSV / FITS)
  * un WebSocket /ws    (spectre en direct, état, progression des séquences)

C'est ce serveur qu'utilise l'application Android. Il est annoncé sur le réseau
local en mDNS (_spectro._tcp) par avahi (voir README).

    python3 spectro_server.py                 # capteur réel sur /dev/ttyACM0
    python3 spectro_server.py --sim           # simulateur, sans matériel
    python3 spectro_server.py --port 8080 --data ~/spectro_data

Dépendances : aiohttp, numpy, pyserial (+ gpiozero pour le ventilateur, facultatif).
"""
import argparse
import asyncio
import datetime as dt
import json
import os
import re
import shutil
import struct
import sys
import threading
import time
import traceback

import numpy as np
from aiohttp import web, WSMsgType

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rpi"))
from tcd1304 import TCD1304, TCD1304Simulator, ADC_MAX  # noqa: E402

VERSION = "1.0"
NACT = 3648
SATURATION = 3900                # seuil d'alerte (ADC 12 bits)
DEFAULT_CALIB = [350.0, 0.135, -2.0e-6, 0.0]


def now_iso():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def slug(text):
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip())[:40].strip("_")
    return s or "spectre"


# =============================================================================
#  ÉTALONNAGE (même fichier que l'interface PyQt : ~/.tcd1304_calib.json)
# =============================================================================
class Calibration:
    def __init__(self, path):
        self.path = path
        self.coeffs = list(DEFAULT_CALIB)
        self.points = []
        self.rms = None
        self.date = None
        try:
            with open(path) as f:
                d = json.load(f)
            self.coeffs = [float(c) for c in d["coeffs"]]
            self.points = [list(p) for p in d.get("points", [])]
            self.rms = d.get("rms")
            self.date = d.get("date")
        except (OSError, ValueError, KeyError):
            pass

    def nm(self, px):
        px = np.asarray(px, float)
        return sum(c * px ** i for i, c in enumerate(self.coeffs))

    def to_dict(self):
        return {"coeffs": self.coeffs, "points": self.points, "rms": self.rms, "date": self.date}

    def update(self, d):
        coeffs = [float(c) for c in d["coeffs"]]
        if len(coeffs) < 2:
            raise ValueError("au moins 2 coefficients")
        self.coeffs = coeffs
        self.points = [[float(a), float(b)] for a, b in d.get("points", [])]
        self.rms = d.get("rms")
        self.date = now_iso()
        with open(self.path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)


# =============================================================================
#  BIBLIOTHÈQUE DE SPECTRES (un fichier JSON par spectre)
# =============================================================================
META_KEYS = ("id", "name", "kind", "date", "tint_us", "averages", "n_frames", "combine",
             "temp_c", "dark_id", "black", "max_raw", "saturated", "calib", "notes",
             "history", "unit")
KINDS = ("light", "dark", "flat", "lamp", "ref", "result")


class Store:
    def __init__(self, folder):
        self.folder = os.path.expanduser(folder)
        os.makedirs(self.folder, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, sid):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", sid or ""):
            raise KeyError(sid)
        return os.path.join(self.folder, sid + ".json")

    def new_id(self, name):
        base = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + slug(name)
        sid, i = base, 1
        while os.path.exists(self._path(sid)):
            i += 1
            sid = "%s-%d" % (base, i)
        return sid

    def save(self, spec):
        spec = dict(spec)
        spec.setdefault("id", self.new_id(spec.get("name", "spectre")))
        spec.setdefault("date", now_iso())
        spec.setdefault("kind", "light")
        spec.setdefault("history", [])
        spec["values"] = [round(float(v), 3) for v in spec["values"]]
        with self.lock, open(self._path(spec["id"]), "w") as f:
            json.dump(spec, f)
        return spec

    def get(self, sid):
        with open(self._path(sid)) as f:
            return json.load(f)

    def delete(self, sid):
        os.remove(self._path(sid))

    def rename(self, sid, name=None, notes=None, kind=None):
        s = self.get(sid)
        if name is not None:
            s["name"] = name
        if notes is not None:
            s["notes"] = notes
        if kind is not None:
            s["kind"] = kind
        with self.lock, open(self._path(sid), "w") as f:
            json.dump(s, f)
        return s

    def list(self):
        out = []
        for fn in sorted(os.listdir(self.folder), reverse=True):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.folder, fn)) as f:
                    d = json.load(f)
                out.append({k: d.get(k) for k in META_KEYS if k in d})
            except (OSError, ValueError):
                continue
        return out


# =============================================================================
#  VENTILATEUR (GPIO + MOSFET ; facultatif)
# =============================================================================
class Fan:
    """mode 'auto' : coupé pendant les acquisitions (vibrations), sinon allumé
    au-dessus de t_on et éteint en dessous de t_off. 'on' / 'off' : forcé."""

    def __init__(self, pin=18, t_on=60.0, t_off=52.0):
        self.mode, self.t_on, self.t_off = "auto", t_on, t_off
        self.running = False
        self.dev = None
        try:
            from gpiozero import OutputDevice
            self.dev = OutputDevice(pin)
        except Exception:
            self.dev = None          # pas de GPIO (PC, simulateur) : état logique seulement

    def _set(self, on):
        self.running = bool(on)
        if self.dev is not None:
            self.dev.on() if on else self.dev.off()

    def update(self, busy):
        t = cpu_temp()
        if self.mode == "on":
            self._set(True)
        elif self.mode == "off":
            self._set(False)
        elif busy:
            self._set(False)
        elif t is not None:
            if t >= self.t_on:
                self._set(True)
            elif t <= self.t_off:
                self._set(False)

    def to_dict(self):
        return {"mode": self.mode, "running": self.running, "t_on": self.t_on,
                "t_off": self.t_off, "gpio": self.dev is not None}


# =============================================================================
#  MOTEUR D'ACQUISITION (un seul thread parle au Pico)
# =============================================================================
class Engine(threading.Thread):
    def __init__(self, dev, store, fan, publish):
        super().__init__(daemon=True)
        self.dev, self.store, self.fan, self.publish = dev, store, fan, publish
        self.cond = threading.Condition()
        self.tint_us = int(getattr(dev, "tint_us", None) or 10000)
        self.averages = 1
        self.sub_black = True
        self.live = False
        self.live_dark_id = None
        self._live_dark = None
        self.jobs = []
        self.job = None              # job en cours (dict d'état publié)
        self.stop_job = False
        self.last = None             # dernier spectre en direct
        self.error = None
        self.frames = 0
        self._dev_tint = None

    # ---- capteur ------------------------------------------------------------
    def _set_tint(self, tint_us):
        tint_us = int(max(10, min(60_000_000, tint_us)))
        if tint_us != self._dev_tint:
            self._dev_tint = self.dev.set_integration_us(tint_us)
            self.dev.read_frame()   # la 1re trame après changement est intégrée avec l'ancien temps
        return self._dev_tint

    def _read(self, tint_us, n):
        """Lit n trames et renvoie (spectre utile moyen, noir optique, max brut)."""
        self._set_tint(tint_us)
        acc = np.zeros(NACT)
        blacks, maxraw = [], 0
        for _ in range(max(1, int(n))):
            if self.stop_job and self.job:
                break
            fr = self.dev.read_frame().astype(float)
            act = self.dev.active(fr)
            b = self.dev.optical_black(fr)
            maxraw = max(maxraw, int(act.max()))
            acc += act - (b if self.sub_black else 0.0)
            blacks.append(b)
            self.frames += 1
        k = max(1, len(blacks))
        return acc / k, float(np.mean(blacks)) if blacks else 0.0, maxraw

    # ---- file de travaux ------------------------------------------------------
    def submit(self, job):
        with self.cond:
            if self.job is not None or self.jobs:
                raise RuntimeError("une acquisition est déjà en cours")
            job.update({"state": "queued", "index": 0, "results": [], "error": None,
                        "started": None, "progress": 0.0})
            self.jobs.append(job)
            self.cond.notify()
        return job

    def set_live(self, on, dark_id=None):
        with self.cond:
            self.live = bool(on)
            self.live_dark_id = dark_id or None
            self._live_dark = None
            if dark_id:
                try:
                    self._live_dark = np.asarray(self.store.get(dark_id)["values"], float)
                except (OSError, KeyError, ValueError):
                    self.live_dark_id = None
            self.cond.notify()

    def run(self):
        while True:
            with self.cond:
                while not self.jobs and not self.live:
                    self.fan.update(busy=False)
                    self.cond.wait(timeout=2.0)
                job = self.jobs.pop(0) if self.jobs else None
            try:
                if job:
                    self._run_job(job)
                else:
                    self._live_step()
                self.error = None
            except Exception as e:  # le serveur ne doit jamais s'arrêter
                self.error = str(e)
                traceback.print_exc()
                if job:
                    job["state"], job["error"] = "error", str(e)
                    self.job = None
                    self.publish({"type": "job", "job": job})
                time.sleep(1.0)

    def _live_step(self):
        self.fan.update(busy=False)
        y, black, maxraw = self._read(self.tint_us, self.averages)
        if self._live_dark is not None and len(self._live_dark) == NACT:
            y = y - self._live_dark
        self.last = {"t": time.time(), "tint_us": self._dev_tint, "averages": self.averages,
                     "black": round(black, 1), "max_raw": maxraw,
                     "saturated": maxraw >= SATURATION, "dark_id": self.live_dark_id,
                     "values": y}
        self.publish({"type": "frame", **self.last})

    # ---- acquisitions et séquences ----------------------------------------------
    def _run_job(self, job):
        self.job, self.stop_job = job, False
        job["state"], job["started"] = "running", now_iso()
        self.fan.update(busy=True)
        self.publish({"type": "job", "job": job})
        count = int(job.get("count", 1))
        tint = int(job.get("tint_us", self.tint_us))
        avg = int(job.get("averages", 1))
        interval = float(job.get("interval_s", 0.0))
        dark = None
        if job.get("dark_id"):
            dark = np.asarray(self.store.get(job["dark_id"])["values"], float)
        frames, temps = [], []
        t_next = time.time()
        for i in range(count):
            if self.stop_job:
                job["state"] = "stopped"
                break
            delay = t_next - time.time()
            while delay > 0 and not self.stop_job:      # attente interruptible
                time.sleep(min(delay, 0.2))
                delay = t_next - time.time()
            t_next = time.time() + interval
            y, black, maxraw = self._read(tint, avg)
            if dark is not None:
                y = y - dark
            frames.append(y)
            temps.append(cpu_temp())
            job["index"] = i + 1
            job["progress"] = (i + 1) / count
            info = {"tint_us": tint, "averages": avg, "black": round(black, 1), "max_raw": maxraw,
                    "saturated": maxraw >= SATURATION, "dark_id": job.get("dark_id")}
            self.publish({"type": "frame", "t": time.time(), **info, "values": y})
            if job.get("save_individual") or job.get("combine", "none") == "none":
                s = self.store.save({"name": "%s_%03d" % (job["name"], i + 1), "kind": job["kind"],
                                     "n_frames": avg, "temp_c": temps[-1], **info,
                                     "values": y.tolist(), "history": ["acquisition"]})
                job["results"].append(s["id"])
            self.publish({"type": "job", "job": job})
        if frames and job.get("combine", "none") != "none":
            st = np.vstack(frames)
            comb = job["combine"]
            y = {"sum": st.sum(0), "mean": st.mean(0), "median": np.median(st, 0)}[comb]
            s = self.store.save({"name": job["name"], "kind": job["kind"], "tint_us": tint,
                                 "averages": avg, "n_frames": len(frames) * avg, "combine": comb,
                                 "temp_c": temps[-1], "dark_id": job.get("dark_id"),
                                 "values": y.tolist(),
                                 "history": ["séquence %d × %d ms, %s" % (len(frames), tint // 1000, comb)]})
            job["results"].append(s["id"])
        if job["state"] == "running":
            job["state"] = "done"
        job["progress"] = 1.0 if job["state"] == "done" else job["progress"]
        self.job = None
        self.fan.update(busy=False)
        self.publish({"type": "job", "job": job})


# =============================================================================
#  EXPORTS
# =============================================================================
def to_csv(spec, calib):
    y = np.asarray(spec["values"], float)
    px = np.arange(len(y))
    coeffs = (spec.get("calib") or {}).get("coeffs") or (calib.coeffs if calib else None)
    lines = ["# %s (%s) %s tint_us=%s" % (spec.get("name"), spec.get("kind"), spec.get("date"),
                                         spec.get("tint_us"))]
    if coeffs:
        lam = sum(c * px ** i for i, c in enumerate(coeffs))
        lines.append("pixel;lambda_nm;intensite")
        lines += ["%d;%.4f;%.3f" % (p, l, v) for p, l, v in zip(px, lam, y)]
    else:
        lines.append("pixel;intensite")
        lines += ["%d;%.3f" % (p, v) for p, v in zip(px, y)]
    return "\n".join(lines) + "\n"


def to_fits(spec, calib):
    """FITS 1D (BITPIX -32). Étalonné : rééchantillonné sur une grille linéaire en Å
    (CRVAL1/CDELT1), format lu par ISIS, BASS, SpcAudace, VisualSpec."""
    y = np.asarray(spec["values"], float)
    px = np.arange(len(y))
    coeffs = (spec.get("calib") or {}).get("coeffs") or (calib.coeffs if calib else None)
    cards = [("SIMPLE", True), ("BITPIX", -32), ("NAXIS", 1), ("NAXIS1", len(y))]
    if coeffs:
        lam = 10.0 * sum(c * px ** i for i, c in enumerate(coeffs))     # Å
        order = np.argsort(lam)
        lam, y = lam[order], y[order]
        step = (lam[-1] - lam[0]) / (len(lam) - 1)
        grid = lam[0] + step * np.arange(len(lam))
        y = np.interp(grid, lam, y)
        cards += [("CRPIX1", 1.0), ("CRVAL1", float(lam[0])), ("CDELT1", float(step)),
                  ("CTYPE1", "WAVE"), ("CUNIT1", "Angstrom")]
    else:
        cards += [("CRPIX1", 1.0), ("CRVAL1", 0.0), ("CDELT1", 1.0), ("CTYPE1", "PIXEL")]
    cards += [("OBJECT", str(spec.get("name", ""))[:60]), ("DATE-OBS", str(spec.get("date", ""))[:19]),
              ("EXPTIME", (spec.get("tint_us") or 0) / 1e6 * (spec.get("n_frames") or 1)),
              ("IMAGETYP", str(spec.get("kind", ""))), ("INSTRUME", "TCD1304DG spectro"),
              ("ORIGIN", "spectro_server %s" % VERSION)]

    def card(k, v):
        if isinstance(v, bool):
            val = "%20s" % ("T" if v else "F")
        elif isinstance(v, int):
            val = "%20d" % v
        elif isinstance(v, float):
            val = "%20s" % ("%.10G" % v)
        else:
            val = "'%-8s'" % v.replace("'", "''")
        return ("%-8s= %s" % (k, val))[:80].ljust(80)

    hdr = "".join(card(k, v) for k, v in cards) + "END".ljust(80)
    hdr += " " * (-len(hdr) % 2880)
    data = np.asarray(y, ">f4").tobytes()
    data += b"\0" * (-len(data) % 2880)
    return hdr.encode("ascii") + data


# =============================================================================
#  APPLICATION WEB
# =============================================================================
def json_ok(data=None, **kw):
    return web.json_response({"ok": True, **({"data": data} if data is not None else {}), **kw})


def json_err(msg, status=400):
    return web.json_response({"ok": False, "error": msg}, status=status)


def make_app(dev, data_dir, calib_path, sim=False):
    store = Store(data_dir)
    calib = Calibration(calib_path)
    fan = Fan()
    app = web.Application(client_max_size=8 * 1024 * 1024)
    clients = set()
    loop_holder = {}

    def encode(msg):
        if "values" in msg:
            msg = dict(msg)
            msg["values"] = [round(float(v), 1) for v in msg["values"]]
        return json.dumps(msg)

    def publish(msg):
        loop = loop_holder.get("loop")
        if loop is None or not clients:
            return
        text = encode(msg)

        async def send():
            for ws in list(clients):
                try:
                    await ws.send_str(text)
                except Exception:
                    clients.discard(ws)
        asyncio.run_coroutine_threadsafe(send(), loop)

    engine = Engine(dev, store, fan, publish)

    def status():
        st = shutil.disk_usage(store.folder)
        return {"version": VERSION, "sim": sim, "device": getattr(dev, "info", {}),
                "tint_us": engine.tint_us, "averages": engine.averages,
                "sub_black": engine.sub_black, "live": engine.live,
                "live_dark_id": engine.live_dark_id, "job": engine.job,
                "temp_c": cpu_temp(), "fan": fan.to_dict(), "calib": calib.to_dict(),
                "error": engine.error, "frames": engine.frames,
                "disk_free_mb": st.free // (1024 * 1024), "time": now_iso()}

    async def body(request):
        try:
            return await request.json()
        except Exception:
            return {}

    # --- état et réglages -----------------------------------------------------------
    async def h_status(request):
        return json_ok(status())

    async def h_config(request):
        d = await body(request)
        if "tint_us" in d:
            engine.tint_us = int(max(10, min(60_000_000, int(d["tint_us"]))))
        if "averages" in d:
            engine.averages = int(max(1, min(1000, int(d["averages"]))))
        if "sub_black" in d:
            engine.sub_black = bool(d["sub_black"])
        return json_ok(status())

    async def h_live(request):
        d = await body(request)
        engine.set_live(d.get("on", True), d.get("dark_id"))
        return json_ok(status())

    async def h_last(request):
        if engine.last is None:
            return json_err("pas encore de spectre", 404)
        m = dict(engine.last)
        m["values"] = [round(float(v), 1) for v in m["values"]]
        return json_ok(m)

    # --- acquisitions -----------------------------------------------------------------
    async def h_acquire(request):
        d = await body(request)
        job = {"type": "acquire", "name": d.get("name") or d.get("kind", "light"),
               "kind": d.get("kind", "light") if d.get("kind") in KINDS else "light",
               "count": 1, "tint_us": int(d.get("tint_us", engine.tint_us)),
               "averages": int(d.get("averages", engine.averages)), "interval_s": 0,
               "combine": "mean", "dark_id": d.get("dark_id"), "save_individual": False}
        try:
            engine.submit(job)
        except RuntimeError as e:
            return json_err(str(e), 409)
        return json_ok(job)

    async def h_seq_start(request):
        d = await body(request)
        try:
            job = {"type": "sequence", "name": d.get("name") or "sequence",
                   "kind": d.get("kind", "light") if d.get("kind") in KINDS else "light",
                   "count": int(max(1, min(10000, int(d.get("count", 10))))),
                   "tint_us": int(d.get("tint_us", engine.tint_us)),
                   "averages": int(max(1, int(d.get("averages", 1)))),
                   "interval_s": float(max(0.0, float(d.get("interval_s", 0)))),
                   "combine": d.get("combine", "mean") if d.get("combine") in ("none", "sum", "mean", "median") else "mean",
                   "dark_id": d.get("dark_id") or None,
                   "save_individual": bool(d.get("save_individual", False))}
            if job["dark_id"]:
                store.get(job["dark_id"])
            engine.submit(job)
        except (ValueError, TypeError) as e:
            return json_err("paramètre invalide : %s" % e)
        except (KeyError, OSError):
            return json_err("noir introuvable", 404)
        except RuntimeError as e:
            return json_err(str(e), 409)
        return json_ok(job)

    async def h_seq_stop(request):
        engine.stop_job = True
        return json_ok(status())

    async def h_job(request):
        return json_ok(engine.job)

    # --- bibliothèque ------------------------------------------------------------------
    async def h_list(request):
        kind = request.query.get("kind")
        items = store.list()
        if kind:
            items = [i for i in items if i.get("kind") == kind]
        return json_ok(items)

    async def h_get(request):
        try:
            return json_ok(store.get(request.match_info["sid"]))
        except (KeyError, OSError):
            return json_err("spectre introuvable", 404)

    async def h_put(request):
        d = await body(request)
        vals = d.get("values")
        if not isinstance(vals, list) or not vals:
            return json_err("'values' manquant")
        spec = {k: d[k] for k in META_KEYS if k in d and k != "id"}
        spec["values"] = vals
        spec.setdefault("kind", "result")
        spec.setdefault("name", "resultat")
        return json_ok(store.save(spec))

    async def h_patch(request):
        d = await body(request)
        try:
            s = store.rename(request.match_info["sid"], d.get("name"), d.get("notes"),
                             d.get("kind") if d.get("kind") in KINDS else None)
        except (KeyError, OSError):
            return json_err("spectre introuvable", 404)
        return json_ok({k: s.get(k) for k in META_KEYS})

    async def h_delete(request):
        try:
            store.delete(request.match_info["sid"])
        except (KeyError, OSError):
            return json_err("spectre introuvable", 404)
        return json_ok()

    async def h_export(request):
        sid, fmt = request.match_info["sid"], request.match_info["fmt"]
        try:
            spec = store.get(sid)
        except (KeyError, OSError):
            return json_err("spectre introuvable", 404)
        if fmt == "csv":
            return web.Response(text=to_csv(spec, calib), content_type="text/csv",
                                headers={"Content-Disposition": 'attachment; filename="%s.csv"' % sid})
        if fmt == "fits":
            return web.Response(body=to_fits(spec, calib), content_type="application/fits",
                                headers={"Content-Disposition": 'attachment; filename="%s.fits"' % sid})
        return json_err("format inconnu (csv ou fits)", 404)

    # --- étalonnage / ventilateur ----------------------------------------------------------
    async def h_calib_get(request):
        return json_ok(calib.to_dict())

    async def h_calib_put(request):
        try:
            calib.update(await body(request))
        except (KeyError, ValueError, TypeError) as e:
            return json_err("étalonnage invalide : %s" % e)
        publish({"type": "status", "status": status()})
        return json_ok(calib.to_dict())

    async def h_fan(request):
        d = await body(request)
        if d.get("mode") in ("auto", "on", "off"):
            fan.mode = d["mode"]
        for k in ("t_on", "t_off"):
            if k in d:
                setattr(fan, k, float(d[k]))
        fan.update(busy=engine.job is not None)
        return json_ok(fan.to_dict())

    # --- WebSocket --------------------------------------------------------------------------
    async def h_ws(request):
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=0)
        await ws.prepare(request)
        clients.add(ws)
        await ws.send_str(json.dumps({"type": "status", "status": status()}))
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT and msg.data == "status":
                    await ws.send_str(json.dumps({"type": "status", "status": status()}))
                elif msg.type == WSMsgType.ERROR:
                    break
        finally:
            clients.discard(ws)
        return ws

    async def h_index(request):
        return web.Response(text="Spectro TCD1304 - serveur %s\nAPI : /api/status\n" % VERSION)

    async def status_pusher(app_):
        async def loop():
            while True:
                await asyncio.sleep(2.0)
                if clients:
                    publish({"type": "status", "status": status()})
        app_["pusher"] = asyncio.create_task(loop())

    async def on_startup(app_):
        loop_holder["loop"] = asyncio.get_running_loop()
        engine.start()
        await status_pusher(app_)

    app.on_startup.append(on_startup)
    r = app.router
    r.add_get("/", h_index)
    r.add_get("/api/status", h_status)
    r.add_post("/api/config", h_config)
    r.add_post("/api/live", h_live)
    r.add_get("/api/live/last", h_last)
    r.add_post("/api/acquire", h_acquire)
    r.add_post("/api/sequence", h_seq_start)
    r.add_post("/api/sequence/stop", h_seq_stop)
    r.add_get("/api/job", h_job)
    r.add_get("/api/spectra", h_list)
    r.add_post("/api/spectra", h_put)
    r.add_get("/api/spectra/{sid}", h_get)
    r.add_patch("/api/spectra/{sid}", h_patch)
    r.add_delete("/api/spectra/{sid}", h_delete)
    r.add_get("/api/spectra/{sid}/{fmt}", h_export)
    r.add_get("/api/calibration", h_calib_get)
    r.add_put("/api/calibration", h_calib_put)
    r.add_post("/api/fan", h_fan)
    r.add_get("/ws", h_ws)
    app["engine"], app["store"], app["calib"], app["fan"] = engine, store, calib, fan
    return app


def main():
    ap = argparse.ArgumentParser(description="Serveur du spectro TCD1304DG")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--serial", default="/dev/ttyACM0")
    ap.add_argument("--data", default="~/spectro_data")
    ap.add_argument("--calib", default="~/.tcd1304_calib.json")
    ap.add_argument("--sim", action="store_true", help="simulateur, sans matériel")
    a = ap.parse_args()
    dev = TCD1304Simulator() if a.sim else TCD1304(a.serial)
    app = make_app(dev, a.data, os.path.expanduser(a.calib), sim=a.sim)
    print("Spectro : http://0.0.0.0:%d  (données : %s)" % (a.port, os.path.expanduser(a.data)))
    web.run_app(app, port=a.port, print=None)


if __name__ == "__main__":
    main()
