"""Génère le schéma électronique du spectrographe TCD1304DG (schemdraw)."""
import os
import schemdraw
import schemdraw.elements as elm
from schemdraw import logic
from schemdraw.elements import IcPin

schemdraw.config(fontsize=11, lw=1.3)

def tag(d, name, at, direction="right"):
    """Étiquette de réseau (connexion par nom)."""
    return d.add(elm.Tag(theta={"right": 0, "left": 180}[direction]).at(at).label(name, fontsize=10))

with schemdraw.Drawing(file=None, show=False) as d:
    d.config(unit=2.5)

    # ===================== BLOC 1 : RP2350-Zero ==============================
    d += elm.Label().at((-1, 10.6)).label("① RP2350-Zero (acquisition)", fontsize=13, halign="left")
    pico = d.add(elm.Ic(
        pins=[IcPin("GP2", side="right"),
              IcPin("GP3", side="right"),
              IcPin("GP4", side="right"),
              IcPin("GP26", side="right"),
              IcPin("5V", side="left"),
              IcPin("3V3", side="left"),
              IcPin("GND", side="left"),
              IcPin("USB-C", side="left")],
        edgepadW=1.0, pinspacing=0.9, w=5.0
    ).at((1.5, 3)))
    for p, n in (("GP2", "CLK_M"), ("GP3", "CLK_SH"), ("GP4", "CLK_ICG"), ("GP26", "ADC")):
        d += elm.Line().right(1.0).at(getattr(pico, p))
        tag(d, n, d.here)
    d += elm.Line().left(0.8).at(getattr(pico, "5V"))
    tag(d, "+5V", d.here, "left")
    d += elm.Line().left(0.8).at(getattr(pico, "3V3"))
    tag(d, "+3V3", d.here, "left")
    d += elm.Line().left(0.8).at(pico.GND); d += elm.Ground()
    d += elm.Line().left(0.8).at(getattr(pico, "USB-C"))
    d += elm.Line().up(1.6)
    d += elm.Label().label("USB-C  ⇄  câble micro-USB / USB-C  ⇄  port « USB » du\n"
                           "Raspberry Pi Zero (données + alimentation 5 V)\n"
                           "Broches repérées par leur nom sérigraphié ; GP16 = LED RGB",
                           fontsize=9, valign="bottom")

    # ===================== BLOC 2 : Alimentation analogique ===================
    d += elm.Label().at((-1, -4.0)).label("② Alimentation capteur (+5VA filtré)", fontsize=13, halign="left")
    tag(d, "+5V", (-0.5, -5.5), "left")
    d += elm.Line().right(0.5).at((-0.5, -5.5))
    d += elm.Inductor2(loops=2).right().label("FB1\nferrite 600Ω", fontsize=9)
    n5 = d.here
    d += elm.Capacitor(polar=True).down().label("C1\n47µF", loc="bottom", fontsize=9)
    d += elm.Ground()
    d += elm.Line().right(1.5).at(n5)
    d += elm.Capacitor().down().label("C2\n100nF", loc="bottom", fontsize=9)
    d += elm.Ground()
    d += elm.Line().right(1.5).at((n5[0] + 1.5, n5[1]))
    tag(d, "+5VA", d.here)

    # ===================== BLOC 3 : Tampons 74HCT04 ===========================
    X3 = 11
    d += elm.Label().at((X3, 9.5)).label("③ Tampons / adaptation 3,3 V → 5 V", fontsize=13, halign="left")
    for i, (nin, nout, a, y, lbl) in enumerate([
            ("CLK_M", "φM", "1→2", 7.5, "U2A"),
            ("CLK_SH", "SH", "3→4", 5.5, "U2B"),
            ("CLK_ICG", "ICG", "5→6", 3.5, "U2C")]):
        tag(d, nin, (X3, y), "left")
        d += elm.Line().right(0.6).at((X3, y))
        inv = d.add(logic.Not().right().label(lbl + "\n" + a, fontsize=8, loc="bottom"))
        d += elm.Line().right(0.6).at(inv.out)
        tag(d, nout, d.here)
    d += elm.Label().at((X3, 1.9)).label(
        "U2 = 74HCT04 : VCC (14) → +5VA, GND (7)\nC5 100 nF entre 14 et 7 au plus près\n"
        "Entrées inutilisées 9, 11, 13 → GND\nLe firmware inverse les GPIO (INVERT_OUT)",
        fontsize=9, halign="left", valign="top")

    # ===================== BLOC 4 : Capteur TCD1304DG =========================
    X4 = 11
    d += elm.Label().at((X4, -4.0)).label("④ Capteur CCD", fontsize=13, halign="left")
    ccd = d.add(elm.Ic(
        pins=[IcPin("VDD", pin="1", side="left"),
              IcPin("VAD", pin="2", side="left"),
              IcPin("ICG", pin="3", side="left"),
              IcPin("φM", pin="4", side="left"),
              IcPin("SH", pin="5", side="left"),
              IcPin("OS", pin="21", side="right"),
              IcPin("SS", pin="22", side="right"),
              IcPin("NC", pin="6…20", side="right")],
        edgepadW=0.8, pinspacing=0.9, w=4.6
    ).at((X4 + 2.5, -10.0)))
    d += elm.Label().at((ccd.center[0], ccd.center[1] + 2.9)).label("U1  TCD1304DG (DIP-22)", fontsize=11)
    for p in ("ICG", "φM", "SH"):
        d += elm.Line().left(0.8).at(getattr(ccd, p))
        tag(d, p, d.here, "left")
    d += elm.Line().left(0.8).at(ccd.VDD)
    tag(d, "+5VA", d.here, "left")
    d += elm.Line().left(0.8).at(ccd.VAD)
    tag(d, "+5VA", d.here, "left")
    d += elm.Line().right(0.8).at(ccd.SS); d += elm.Ground()
    d += elm.Line().right(0.8).at(ccd.NC); d += elm.Label().label("GND ou ouvert", fontsize=8, halign="left")
    d += elm.Line().right(0.8).at(ccd.OS)
    tag(d, "OS", d.here)
    d += elm.Label().at((X4, -11.4)).label(
        "C3 100 nF + C4 10 µF entre broches 1-2 et 22, au ras du boîtier.\n"
        "Fenêtre : manipuler sans la toucher (gants), protéger de la poussière.",
        fontsize=9, halign="left", valign="top")

    # ===================== BLOC 5 : Chaîne analogique =========================
    X5 = 22
    d += elm.Label().at((X5, 9.5)).label("⑤ Conditionnement du signal OS → ADC", fontsize=13, halign="left")
    # suiveur PNP
    tag(d, "OS", (X5, 4.0), "left")
    d += elm.Line().right(0.8).at((X5, 4.0))
    q1 = d.add(elm.BjtPnp(circle=True).anchor("base").label("Q1\n2SA1015\n(BC557)", loc="right", fontsize=9, ofst=(0.2, -0.6)))
    d += elm.Line().at(q1.collector).down(0.6); d += elm.Ground()
    d += elm.Resistor().at(q1.emitter).up(2.2).label("R1\n2,2k", loc="bottom", fontsize=9)
    tag(d, "+5VA", d.here)
    ve = q1.emitter
    d += elm.Dot().at(ve)
    d += elm.Line().right(1.4).at(ve)
    d += elm.Resistor().right().label("R3  4,7k", fontsize=9)
    nminus = d.here
    d += elm.Dot()
    # ampli op inverseur
    op = d.add(elm.Opamp(leads=True).anchor("in1").at((nminus[0] + 1.5, nminus[1])).label("U3 MCP6021", loc="bottom", ofst=(0, -0.3), fontsize=9))
    d += elm.Line().at(nminus).to(op.in1)
    # contre-réaction
    d += elm.Line().up(1.8).at(nminus)
    nfb = d.here
    d += elm.Resistor().right().tox(op.out[0]).label("R4  18k", fontsize=9)
    nfb2 = d.here
    d += elm.Line().down().toy(op.out)
    d += elm.Dot()
    d += elm.Line().up(1.4).at(nfb)
    d += elm.Capacitor().right().tox(op.out[0]).label("C7  10pF", fontsize=9)
    d += elm.Line().down().toy(nfb2)
    # résistance d'offset vers la masse
    d += elm.Resistor().down(2.6).at(nminus).label("R7\n18k", loc="bottom", fontsize=9)
    d += elm.Ground()
    # référence réglable sur IN+
    d += elm.Line().left(0.4).at(op.in2)
    d += elm.Line().down(2.4)
    nplus = d.here
    d += elm.Dot()
    d += elm.Capacitor().down().label("C8\n1µF", loc="bottom", fontsize=9)
    d += elm.Ground()
    d += elm.Resistor().left(5.6).at(nplus).label("R5  10k", fontsize=9)
    pot = d.add(elm.Potentiometer().down().anchor("tap").label("RV1\n10k\n(offset)", loc="bottom", fontsize=9, ofst=(0.3, 0)))
    d += elm.Line().at(pot.start).up(0.3)
    d += elm.Line().left(0.5)
    tag(d, "+3V3", d.here, "left")
    d += elm.Ground().at(pot.end)
    # alimentation ampli
    d += elm.Label().at((op.center[0] + 1.5, op.center[1] - 3.2)).label("U3 : VDD(7)=+3V3, VSS(4)=GND\nC6 100 nF", fontsize=8)
    # sortie vers ADC
    d += elm.Line().right(0.6).at(op.out)
    d += elm.Resistor().right().label("R6  100Ω", fontsize=9)
    nadc = d.here
    d += elm.Dot()
    d += elm.Capacitor().down().label("C9\n470pF", loc="bottom", fontsize=9)
    d += elm.Ground()
    d += elm.Line().right(0.8).at(nadc)
    tag(d, "ADC", d.here)

    d += elm.Label().at((X5, -4.0)).label(
        "Fonctionnement : Q1 tamponne OS (≈ 2,5–3,5 V, baisse avec la lumière).\n"
        "U3 inverse et amplifie (gain −3,8) : obscurité ≈ 0,2 V, saturation ≈ 2,6 V.\n"
        "Vout = Vref·(1 + R4/R3 + R4/R7) − (R4/R3)·V(E-Q1)\n"
        "U3 alimenté en 3,3 V : sa sortie ne peut pas dépasser la plage de l'ADC.\n\n"
        "Réglage : capteur dans le noir, tourner RV1 pour lire\n"
        "≈ 150 à 250 points ADC sur le « noir optique » de l'interface.",
        fontsize=9.5, halign="left", valign="top")

    here = os.path.dirname(os.path.abspath(__file__))
    d.save(os.path.join(here, "schema_tcd1304.svg"))
    d.save(os.path.join(here, "schema_tcd1304.png"), dpi=150)
print("ok")
