#!/usr/bin/env python3
"""
Interface graphique du spectrographe TCD1304DG.

    python3 spectro_gui.py                 # matériel sur /dev/ttyACM0
    python3 spectro_gui.py --port COM5     # sous Windows
    python3 spectro_gui.py --sim           # simulateur, sans matériel

Dépendances (Raspberry Pi OS) :
    sudo apt install python3-pyqt5 python3-pyqtgraph python3-numpy python3-serial

Le code est organisé pour être modifié facilement :
  * CONFIG              : réglages par défaut, couleurs, fichiers
  * process_spectrum()  : toute la chaîne de traitement (un seul endroit)
  * AcqWorker           : thread d'acquisition
  * MainWindow._build_* : construction de l'interface, un bloc par panneau
"""
import argparse
import csv
import json
import os
import sys
import time

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, QtWidgets

from tcd1304 import TCD1304, TCD1304Simulator, ADC_MAX, NPIX

# =============================================================================
#  CONFIGURATION (à adapter)
# =============================================================================
CONFIG = {
    "port": "/dev/ttyACM0",
    "tint_ms": 10.0,            # temps d'intégration initial
    "averages": 1,
    "smooth": 1,                # largeur du lissage (pixels, 1 = aucun)
    "calib_file": os.path.expanduser("~/.tcd1304_calib.json"),
    "save_dir": os.path.expanduser("~/spectres"),
    "saturation": 3900,         # seuil d'alerte (ADC 12 bits)
    "peak_threshold": 0.10,     # fraction du max pour détecter un pic
    "peak_max": 12,
    "curve_color": "#1f77b4",
    "ref_color": "#999999",
    "background": "w",
    "foreground": "k",
    # calibration par défaut λ(pixel) = c0 + c1·p + c2·p² + c3·p³   (nm)
    "calib_coeffs": [350.0, 0.135, -2.0e-6, 0.0],
}


# =============================================================================
#  TRAITEMENT DU SPECTRE
# =============================================================================
def smooth(y, n):
    if n <= 1:
        return y
    k = np.ones(int(n)) / int(n)
    return np.convolve(y, k, mode="same")


def find_peaks(y, threshold, max_peaks, min_dist=8):
    """Maxima locaux simples (sans scipy)."""
    if y.size < 3:
        return np.array([], dtype=int)
    thr = y.min() + threshold * (y.max() - y.min())
    idx = np.where((y[1:-1] > y[:-2]) & (y[1:-1] >= y[2:]) & (y[1:-1] > thr))[0] + 1
    idx = idx[np.argsort(y[idx])[::-1]]
    kept = []
    for i in idx:
        if all(abs(i - j) >= min_dist for j in kept):
            kept.append(i)
        if len(kept) >= max_peaks:
            break
    return np.array(sorted(kept), dtype=int)


def process_spectrum(frame_avg, state):
    """frame_avg : trame brute moyennée (3694 valeurs, float).
    state : dict de réglages courants. Retourne le spectre utile (3648)."""
    y = frame_avg[32:32 + 3648].astype(float)
    if state["sub_black"]:
        y = y - frame_avg[16:29].mean()          # noir optique (pixels masqués)
    if state["dark"] is not None:
        y = y - state["dark"]                    # fond enregistré
    y = smooth(y, state["smooth"])
    mode = state["mode"]
    if mode in ("Transmission %", "Absorbance") and state["ref"] is not None:
        ref = np.where(np.abs(state["ref"]) < 1e-3, 1e-3, state["ref"])
        t = y / ref
        if mode == "Transmission %":
            y = 100.0 * t
        else:
            y = -np.log10(np.clip(t, 1e-4, None))
    return y


# =============================================================================
#  CALIBRATION EN LONGUEUR D'ONDE
# =============================================================================
class Calibration:
    def __init__(self, path, default):
        self.path = path
        self.coeffs = list(default)
        self.points = []            # [(pixel, nm), ...]
        self.load()

    def nm(self, px):
        c = self.coeffs
        return c[0] + c[1] * px + c[2] * px ** 2 + c[3] * px ** 3

    def fit(self, degree):
        p = np.array([q[0] for q in self.points], float)
        l = np.array([q[1] for q in self.points], float)
        degree = min(degree, len(p) - 1)
        if degree < 1:
            raise ValueError("Il faut au moins 2 points de calibration")
        c = np.polyfit(p, l, degree)[::-1]
        self.coeffs = list(c) + [0.0] * (4 - len(c))
        resid = l - self.nm(p)
        return float(np.sqrt(np.mean(resid ** 2)))

    def load(self):
        try:
            with open(self.path) as f:
                d = json.load(f)
            self.coeffs = d["coeffs"]
            self.points = [tuple(x) for x in d.get("points", [])]
        except (OSError, ValueError, KeyError):
            pass

    def save(self):
        with open(self.path, "w") as f:
            json.dump({"coeffs": self.coeffs, "points": self.points}, f, indent=2)


class CalibDialog(QtWidgets.QDialog):
    REF_LINES = "Hg : 404.66 435.83 546.07 576.96 579.07 | Ar : 696.54 763.51 811.53 | " \
                "Ne : 585.25 640.22 | laser : 405 532 650"

    def __init__(self, calib, peaks_px, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calibration en longueur d'onde")
        self.calib = calib
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel(
            "Associez des pixels (pics détectés) à des longueurs d'onde connues.\n"
            + self.REF_LINES))
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Pixel", "λ (nm)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table)
        for p, l in calib.points:
            self._add_row(p, l)
        for p in peaks_px:
            if not any(abs(p - q[0]) < 3 for q in calib.points):
                self._add_row(p, "")
        row = QtWidgets.QHBoxLayout()
        b_add = QtWidgets.QPushButton("+ ligne")
        b_add.clicked.connect(lambda: self._add_row("", ""))
        b_del = QtWidgets.QPushButton("− ligne")
        b_del.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()))
        self.deg = QtWidgets.QSpinBox()
        self.deg.setRange(1, 3)
        self.deg.setValue(2)
        row.addWidget(b_add)
        row.addWidget(b_del)
        row.addStretch()
        row.addWidget(QtWidgets.QLabel("Degré du polynôme"))
        row.addWidget(self.deg)
        lay.addLayout(row)
        self.result = QtWidgets.QLabel(self._coeff_text())
        lay.addWidget(self.result)
        bb = QtWidgets.QDialogButtonBox()
        b_fit = bb.addButton("Ajuster", QtWidgets.QDialogButtonBox.ActionRole)
        b_fit.clicked.connect(self.do_fit)
        bb.addButton(QtWidgets.QDialogButtonBox.Save).clicked.connect(self.do_save)
        bb.addButton(QtWidgets.QDialogButtonBox.Close).clicked.connect(self.reject)
        lay.addWidget(bb)
        self.resize(460, 460)

    def _add_row(self, p, l):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(p)))
        self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(l)))

    def _coeff_text(self):
        return "λ = " + " + ".join("%.6g·p^%d" % (c, i) for i, c in enumerate(self.calib.coeffs))

    def _read_points(self):
        pts = []
        for r in range(self.table.rowCount()):
            try:
                p = float(self.table.item(r, 0).text())
                l = float(self.table.item(r, 1).text())
                pts.append((p, l))
            except (AttributeError, ValueError):
                continue
        return pts

    def do_fit(self):
        self.calib.points = self._read_points()
        try:
            rms = self.calib.fit(self.deg.value())
            self.result.setText(self._coeff_text() + "\nrésidu RMS = %.3f nm" % rms)
        except Exception as e:
            self.result.setText("Erreur : %s" % e)

    def do_save(self):
        self.do_fit()
        self.calib.save()
        self.accept()


# =============================================================================
#  THREAD D'ACQUISITION
# =============================================================================
class AcqWorker(QtCore.QThread):
    frame_ready = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(self, dev):
        super().__init__()
        self.dev = dev
        self.running = False
        self.single = False
        self.averages = 1
        self.pending_tint_us = None
        self._mutex = QtCore.QMutex()

    def request_tint(self, us):
        with QtCore.QMutexLocker(self._mutex):
            self.pending_tint_us = us

    def run(self):
        while not self.isInterruptionRequested():
            with QtCore.QMutexLocker(self._mutex):
                tint, self.pending_tint_us = self.pending_tint_us, None
            try:
                if tint is not None:
                    self.dev.set_integration_us(tint)
                if not (self.running or self.single):
                    self.msleep(30)
                    continue
                acc = np.zeros(NPIX)
                n = max(1, self.averages)
                for _ in range(n):
                    acc += self.dev.read_frame()
                self.single = False
                self.frame_ready.emit(acc / n)
            except Exception as e:
                self.running = self.single = False
                self.error.emit(str(e))
                self.msleep(500)


# =============================================================================
#  FENÊTRE PRINCIPALE
# =============================================================================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, dev):
        super().__init__()
        self.setWindowTitle("Spectrographe TCD1304DG")
        self.dev = dev
        self.calib = Calibration(CONFIG["calib_file"], CONFIG["calib_coeffs"])
        self.state = {"sub_black": True, "dark": None, "ref": None,
                      "smooth": CONFIG["smooth"], "mode": "Intensité"}
        self.last_frame = None
        self.last_y = None
        self.peaks = np.array([], dtype=int)
        self._t_last = time.time()
        self._fps = 0.0

        pg.setConfigOptions(antialias=False, background=CONFIG["background"],
                            foreground=CONFIG["foreground"])
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        lay = QtWidgets.QHBoxLayout(central)
        lay.addWidget(self._build_plot(), 1)
        lay.addWidget(self._build_controls())
        self.status = self.statusBar()

        self.worker = AcqWorker(dev)
        self.worker.frame_ready.connect(self.on_frame)
        self.worker.error.connect(lambda m: self.status.showMessage("Erreur : " + m, 5000))
        self.worker.start()
        self.on_tint_changed()

    # ---------------------------------------------------------------- tracé
    def _build_plot(self):
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.curve = self.plot.plot(pen=pg.mkPen(CONFIG["curve_color"], width=1))
        self.ref_curve = self.plot.plot(pen=pg.mkPen(CONFIG["ref_color"], style=QtCore.Qt.DashLine))
        self.peak_items = []
        self.vline = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#d62728"))
        self.plot.addItem(self.vline, ignoreBounds=True)
        self.cursor_lbl = pg.TextItem(anchor=(0, 1), color="#d62728")
        self.plot.addItem(self.cursor_lbl, ignoreBounds=True)
        self.plot.scene().sigMouseMoved.connect(self.on_mouse)
        return self.plot

    # ------------------------------------------------------------- commandes
    def _build_controls(self):
        w = QtWidgets.QWidget()
        w.setFixedWidth(250)
        v = QtWidgets.QVBoxLayout(w)

        g = QtWidgets.QGroupBox("Acquisition")
        f = QtWidgets.QFormLayout(g)
        self.b_run = QtWidgets.QPushButton("▶ Démarrer")
        self.b_run.setCheckable(True)
        self.b_run.toggled.connect(self.on_run)
        b_single = QtWidgets.QPushButton("Mesure unique")
        b_single.clicked.connect(self.on_single)
        self.sp_tint = QtWidgets.QDoubleSpinBox()
        self.sp_tint.setRange(0.01, 60000)
        self.sp_tint.setDecimals(2)
        self.sp_tint.setSuffix(" ms")
        self.sp_tint.setValue(CONFIG["tint_ms"])
        self.sp_tint.setKeyboardTracking(False)
        self.sp_tint.valueChanged.connect(self.on_tint_changed)
        self.sp_avg = QtWidgets.QSpinBox()
        self.sp_avg.setRange(1, 1000)
        self.sp_avg.setValue(CONFIG["averages"])
        self.sp_avg.valueChanged.connect(lambda n: setattr(self.worker, "averages", n))
        f.addRow(self.b_run)
        f.addRow(b_single)
        f.addRow("Intégration", self.sp_tint)
        f.addRow("Moyennes", self.sp_avg)
        v.addWidget(g)

        g = QtWidgets.QGroupBox("Traitement")
        f = QtWidgets.QFormLayout(g)
        self.cb_black = QtWidgets.QCheckBox("Soustraire noir optique")
        self.cb_black.setChecked(True)
        self.cb_black.toggled.connect(lambda b: self.state.update(sub_black=b))
        self.sp_smooth = QtWidgets.QSpinBox()
        self.sp_smooth.setRange(1, 51)
        self.sp_smooth.setValue(CONFIG["smooth"])
        self.sp_smooth.valueChanged.connect(lambda n: self.state.update(smooth=n))
        b_dark = QtWidgets.QPushButton("Enregistrer le fond")
        b_dark.clicked.connect(self.on_dark)
        b_dark_clr = QtWidgets.QPushButton("Effacer le fond")
        b_dark_clr.clicked.connect(lambda: self.state.update(dark=None))
        b_ref = QtWidgets.QPushButton("Enregistrer la référence")
        b_ref.clicked.connect(self.on_ref)
        self.cmb_mode = QtWidgets.QComboBox()
        self.cmb_mode.addItems(["Intensité", "Transmission %", "Absorbance"])
        self.cmb_mode.currentTextChanged.connect(lambda m: self.state.update(mode=m))
        f.addRow(self.cb_black)
        f.addRow("Lissage", self.sp_smooth)
        f.addRow(b_dark)
        f.addRow(b_dark_clr)
        f.addRow(b_ref)
        f.addRow("Mode", self.cmb_mode)
        v.addWidget(g)

        g = QtWidgets.QGroupBox("Affichage")
        f = QtWidgets.QFormLayout(g)
        self.cb_nm = QtWidgets.QCheckBox("Axe en nm")
        self.cb_nm.setChecked(True)
        self.cb_peaks = QtWidgets.QCheckBox("Repérer les pics")
        self.cb_peaks.setChecked(True)
        self.cb_ref = QtWidgets.QCheckBox("Afficher la référence")
        self.cb_auto = QtWidgets.QCheckBox("Échelle Y auto")
        self.cb_auto.setChecked(True)
        self.cb_auto.toggled.connect(lambda b: self.plot.enableAutoRange(axis="y", enable=b))
        b_cal = QtWidgets.QPushButton("Calibration λ…")
        b_cal.clicked.connect(self.on_calib)
        for wd in (self.cb_nm, self.cb_peaks, self.cb_ref, self.cb_auto, b_cal):
            f.addRow(wd)
        v.addWidget(g)

        g = QtWidgets.QGroupBox("Fichiers")
        f = QtWidgets.QFormLayout(g)
        b_csv = QtWidgets.QPushButton("Enregistrer CSV")
        b_csv.clicked.connect(self.on_save_csv)
        b_png = QtWidgets.QPushButton("Enregistrer image PNG")
        b_png.clicked.connect(self.on_save_png)
        f.addRow(b_csv)
        f.addRow(b_png)
        v.addWidget(g)

        self.lbl_info = QtWidgets.QLabel("")
        self.lbl_info.setWordWrap(True)
        v.addWidget(self.lbl_info)
        v.addStretch()
        return w

    # -------------------------------------------------------------- actions
    def on_run(self, on):
        self.worker.running = on
        self.b_run.setText("■ Arrêter" if on else "▶ Démarrer")

    def on_single(self):
        self.worker.single = True

    def on_tint_changed(self, *_):
        self.worker.request_tint(int(round(self.sp_tint.value() * 1000)))

    def _raw_active(self):
        """Spectre utile courant, avant mode transmission/absorbance."""
        if self.last_frame is None:
            return None
        st = dict(self.state, mode="Intensité", dark=None)
        return process_spectrum(self.last_frame, st)

    def on_dark(self):
        y = self._raw_active()
        if y is not None:
            self.state["dark"] = y
            self.status.showMessage("Fond enregistré", 3000)

    def on_ref(self):
        if self.last_frame is None:
            return
        st = dict(self.state, mode="Intensité")
        self.state["ref"] = process_spectrum(self.last_frame, st)
        self.status.showMessage("Référence enregistrée", 3000)

    def on_calib(self):
        CalibDialog(self.calib, list(self.peaks), self).exec()

    def x_axis(self):
        px = np.arange(3648)
        return self.calib.nm(px) if self.cb_nm.isChecked() else px

    # ----------------------------------------------------- nouvelle trame
    def on_frame(self, frame):
        self.last_frame = frame
        y = process_spectrum(frame, self.state)
        self.last_y = y
        x = self.x_axis()
        self.curve.setData(x, y)
        if self.cb_ref.isChecked() and self.state["ref"] is not None \
                and self.state["mode"] == "Intensité":
            self.ref_curve.setData(x, self.state["ref"])
        else:
            self.ref_curve.setData([], [])
        self.plot.setLabel("bottom", "Longueur d'onde (nm)" if self.cb_nm.isChecked() else "Pixel")
        self.plot.setLabel("left", self.state["mode"])
        self._draw_peaks(x, y)

        now = time.time()
        self._fps = 0.8 * self._fps + 0.2 / max(1e-3, now - self._t_last)
        self._t_last = now
        raw_max = frame[32:3680].max()
        sat = raw_max >= CONFIG["saturation"]
        self.lbl_info.setText(
            "<b>%.1f trames/s</b><br>max brut : %d / %d%s<br>noir optique : %.1f"
            % (self._fps, raw_max, ADC_MAX,
               " <span style='color:red'><b>SATURATION</b></span>" if sat else "",
               frame[16:29].mean()))

    def _draw_peaks(self, x, y):
        for it in self.peak_items:
            self.plot.removeItem(it)
        self.peak_items = []
        if not self.cb_peaks.isChecked():
            self.peaks = np.array([], dtype=int)
            return
        self.peaks = find_peaks(y, CONFIG["peak_threshold"], CONFIG["peak_max"])
        for i in self.peaks:
            lbl = "%.1f" % x[i] if self.cb_nm.isChecked() else "%d" % i
            t = pg.TextItem(lbl, anchor=(0.5, 1.2), color="#2ca02c")
            t.setPos(x[i], y[i])
            self.plot.addItem(t)
            self.peak_items.append(t)

    def on_mouse(self, pos):
        if not self.plot.sceneBoundingRect().contains(pos) or self.last_y is None:
            return
        p = self.plot.getPlotItem().vb.mapSceneToView(pos)
        x = self.x_axis()
        i = int(np.clip(np.searchsorted(x, p.x()), 0, len(x) - 1))
        self.vline.setPos(x[i])
        self.cursor_lbl.setText("px %d  λ %.2f nm  y %.3g" % (i, self.calib.nm(i), self.last_y[i]))
        self.cursor_lbl.setPos(x[i], self.last_y[i])

    # ---------------------------------------------------------- fichiers
    def _default_name(self, ext):
        os.makedirs(CONFIG["save_dir"], exist_ok=True)
        return os.path.join(CONFIG["save_dir"], time.strftime("spectre_%Y%m%d_%H%M%S") + ext)

    def on_save_csv(self):
        if self.last_y is None:
            return
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV", self._default_name(".csv"), "CSV (*.csv)")
        if not fn:
            return
        px = np.arange(3648)
        with open(fn, "w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["# tint_ms=%.3f" % self.sp_tint.value(), "moyennes=%d" % self.sp_avg.value(),
                        "mode=%s" % self.state["mode"], "calib=%s" % self.calib.coeffs])
            w.writerow(["pixel", "lambda_nm", "valeur"])
            for i in px:
                w.writerow([i, "%.3f" % self.calib.nm(i), "%.4f" % self.last_y[i]])
        self.status.showMessage("Enregistré : " + fn, 4000)

    def on_save_png(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "PNG", self._default_name(".png"), "PNG (*.png)")
        if fn:
            import pyqtgraph.exporters
            pyqtgraph.exporters.ImageExporter(self.plot.plotItem).export(fn)

    def closeEvent(self, ev):
        self.worker.requestInterruption()
        self.worker.wait(3000)
        self.dev.close()
        super().closeEvent(ev)


def main():
    ap = argparse.ArgumentParser(description="Spectrographe TCD1304DG")
    ap.add_argument("--port", default=CONFIG["port"])
    ap.add_argument("--sim", action="store_true", help="simulateur sans matériel")
    args = ap.parse_args()
    app = QtWidgets.QApplication(sys.argv)
    dev = TCD1304Simulator() if args.sim else TCD1304(args.port)
    win = MainWindow(dev)
    win.resize(1100, 650)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
