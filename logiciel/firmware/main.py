# =============================================================================
#  Firmware d'acquisition TCD1304DG pour Raspberry Pi Pico (RP2040) - MicroPython
#  -----------------------------------------------------------------------------
#  Rôle : générer les horloges du capteur (φM, SH, ICG) avec les PIO, et
#  numériser la sortie OS avec l'ADC interne, déclenché pixel par pixel par la
#  PIO via DMA (échantillonnage synchrone, sans aucune gigue logicielle).
#  La trame (3694 valeurs 12 bits) est envoyée au Raspberry Pi Zero par USB.
#
#  MicroPython >= 1.23 requis (classe rp2.DMA).
#  Copier ce fichier sous le nom main.py sur le Pico (Thonny ou mpremote).
#
#  Protocole (USB CDC, lignes texte terminées par \n) :
#     I            -> "TCD1304 fw=1.0 npix=3694 fm=1000000 tint_us=10000\n"
#     T <µs>       -> règle le temps d'intégration -> "OK tint_us=<réel>\n"
#     R            -> lit une trame -> b"FRM:" + 3694 x uint16 little-endian
#     P            -> "PONG\n"
#  En cas d'erreur : "ERR <message>\n"
# =============================================================================

import sys
import machine
import rp2
import array
from machine import Pin, mem32
from micropython import const

# -----------------------------------------------------------------------------
#  PARAMÈTRES MODIFIABLES
# -----------------------------------------------------------------------------
FM_HZ      = 1_000_000   # horloge maître φM : 1_000_000, 1_250_000 ou 1_500_000
TINT_US    = 10_000      # temps d'intégration au démarrage (µs, >= 10)
ADC_PHASE  = 6           # retard (0..12 cycles PIO) de l'instant d'échantillonnage
                         # dans le pixel : à ajuster à l'oscilloscope si besoin
INVERT_OUT = True        # True si étage 74HCT04 (inverseur) entre Pico et capteur

PIN_FM  = 2              # GP2  -> 74HCT04 -> φM  (broche 4 du capteur)
PIN_SH  = 3              # GP3  -> 74HCT04 -> SH  (broche 5)
PIN_ICG = 4              # GP4  -> 74HCT04 -> ICG (broche 3)  (doit être PIN_SH+1)
ADC_CH  = 0              # GP26 = ADC0 <- sortie de l'ampli

NPIX = const(3694)       # 16 dummy + 13 masqués + 3 dummy + 3648 utiles + 14 dummy

# -----------------------------------------------------------------------------
#  Registres RP2040
# -----------------------------------------------------------------------------
SYS_HZ     = const(120_000_000)       # diviseurs PIO entiers pour 1 / 1.25 / 1.5 MHz
PIO0_BASE  = const(0x50200000)
PIO0_CTRL  = const(0x50200000)
PIO0_RXF2  = const(0x50200028)        # FIFO RX de la SM2 (déclencheur ADC)
ADC_BASE   = const(0x4004C000)
ADC_CS     = const(0x4004C000)
ADC_FCS    = const(0x4004C008)
ADC_FIFO   = const(0x4004C00C)
ADC_DIV    = const(0x4004C010)
IO_BANK0   = const(0x40014000)
DREQ_PIO0_RX2 = const(6)
DREQ_ADC      = const(36)


# -----------------------------------------------------------------------------
#  Programmes PIO  (1 cycle PIO = 1/(4·fM) ; un pixel = 4 φM = 16 cycles)
#  Les niveaux écrits sont ceux vus par le capteur (l'inversion éventuelle du
#  74HCT04 est compensée par l'option OUTOVER des GPIO).
# -----------------------------------------------------------------------------
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def pio_phim():
    # φM : 2 cycles haut, 2 cycles bas -> fM = fPIO/4 ; haut aux cycles 0,1 mod 4
    wrap_target()
    set(pins, 1)[1]
    set(pins, 0)[1]
    wrap()


@rp2.asm_pio(set_init=(rp2.PIO.OUT_LOW, rp2.PIO.OUT_HIGH))
def pio_seq():
    # set pins : bit0 = SH, bit1 = ICG
    # Une "période" = temps d'intégration P = D + 30 cycles (P multiple de 4).
    # Chaque période commence par une impulsion SH (obturateur électronique).
    # Si le CPU a déposé un jeton dans la FIFO TX, la période est une période de
    # lecture : ICG descend, SH pulse, ICG remonte (φM haut), puis IRQ0 lance
    # la SM de déclenchement ADC.
    pull(block)                # OSR = D
    mov(isr, osr)              # ISR conserve D
    set(pins, 0b10)[1]         # ICG=1, SH=0 ; 4 cycles d'init -> S ≡ 0 mod 4
    wrap_target()
    set(x, 0)                  # c0
    pull(noblock)              # c1   OSR = jeton, ou X(=0) si FIFO vide
    mov(y, osr)                # c2
    jmp(not_y, "normal")       # c3
    # ---- période de lecture (24 cycles) ----
    set(pins, 0b00)[1]         # c4  ICG ↓            t2 = 2 cyc (0,5 µs @1 MHz)
    set(pins, 0b01)[7]         # c6  SH ↑             t3 = 8 cyc (2 µs)
    set(pins, 0b00)[10]        # c14 SH ↓             t1 = 11 cyc (2,75 µs)
    set(pins, 0b10)            # c25 ICG ↑ (≡1 mod 4 : φM est haut)
    irq(0)                     # c26 démarre la lecture
    jmp("tail")                # c27
    # ---- période normale (24 cycles) ----
    label("normal")
    nop()[1]                   # c4
    set(pins, 0b11)[7]         # c6  SH ↑ (ICG haut)
    set(pins, 0b10)[13]        # c14 SH ↓
    # ---- attente : 1 + (D+1) cycles ----
    label("tail")
    mov(y, isr)                # c28
    label("dly")
    jmp(y_dec, "dly")
    wrap()


def make_pio_trig(phase):
    @rp2.asm_pio(in_shiftdir=rp2.PIO.SHIFT_RIGHT)
    def pio_trig():
        # Pousse NPIX fois la valeur 7 (ADC_CS : EN|TS_EN|START_ONCE) dans la
        # FIFO RX, une fois par pixel (16 cycles). Un canal DMA recopie chaque
        # mot vers ADC_CS -> une conversion par pixel, synchrone de φM.
        pull(block)                    # OSR = NPIX-1
        wrap_target()
        wait(1, irq, 0)
        mov(x, osr)
        nop()[phase]
        label("pix")
        mov(isr, invert(null))         # ISR = 0xFFFFFFFF
        in_(null, 29)                  # ISR = 0x00000007
        push(noblock)[12]
        jmp(x_dec, "pix")              # boucle = 16 cycles = 1 pixel
        wrap()
    return pio_trig


# -----------------------------------------------------------------------------
#  Classe d'acquisition
# -----------------------------------------------------------------------------
class TCD1304:
    def __init__(self, fm_hz=FM_HZ, tint_us=TINT_US):
        machine.freq(SYS_HZ)
        if SYS_HZ % (4 * fm_hz):
            raise ValueError("fM doit diviser 30 MHz (1, 1.25 ou 1.5 MHz)")
        self.fm = fm_hz
        self.buf = array.array("H", bytes(2 * NPIX))
        self._trig_word = array.array("I", [0])
        self.adc = machine.ADC(ADC_CH)          # configure GP26 en analogique
        mem32[ADC_DIV] = 0                      # pas de conversion libre
        mem32[ADC_FCS] = (1 << 0) | (1 << 3) | (1 << 24) | (3 << 10)  # EN, DREQ, THRESH=1
        mem32[ADC_CS] = 0x1 | (ADC_CH << 12)
        self.dma_trig = rp2.DMA()
        self.dma_adc = rp2.DMA()
        self.sms = []
        self.tint_us = 0
        self.set_tint(tint_us)

    # -- (re)démarrage synchrone des 3 machines d'état
    def _start(self, d):
        for sm in self.sms:
            sm.active(0)
        rp2.PIO(0).remove_program()
        f = 4 * self.fm
        sm0 = rp2.StateMachine(0, pio_phim, freq=f, set_base=Pin(PIN_FM))
        sm1 = rp2.StateMachine(1, pio_seq, freq=f, set_base=Pin(PIN_SH))
        sm2 = rp2.StateMachine(2, make_pio_trig(ADC_PHASE), freq=f)
        self.sms = [sm0, sm1, sm2]
        for p in (PIN_FM, PIN_SH, PIN_ICG):     # inversion matérielle des sorties
            reg = IO_BANK0 + 8 * p + 4
            v = mem32[reg] & ~(0x3 << 8)
            if INVERT_OUT:
                v |= 0x1 << 8
            mem32[reg] = v
        sm1.put(d)
        sm2.put(NPIX - 1)
        # SM_ENABLE (bits 0-2) + CLKDIV_RESTART (bits 8-10) dans la même écriture
        mem32[PIO0_CTRL] = 0x7 | (0x7 << 8)

    def set_tint(self, tint_us):
        tint_us = max(10, int(tint_us))
        n = max(1, round(tint_us * self.fm / 1_000_000))   # nb de périodes φM
        p = 4 * n                                         # cycles PIO
        if p < 40:
            p = 40
        self._start(p - 30)
        self.tint_us = p * 1_000_000 // (4 * self.fm)
        self.read()          # première trame jetée (intégration indéterminée)
        return self.tint_us

    def _drain(self):
        sm2 = self.sms[2]
        while sm2.rx_fifo():
            sm2.get()
        while (mem32[ADC_FCS] >> 16) & 0xF:
            mem32[ADC_FIFO]
        mem32[ADC_FCS] |= (3 << 10)             # efface OVER/UNDER

    def read(self, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = 2 * self.tint_us // 1000 + 100
        self._drain()
        self.dma_adc.config(
            read=ADC_FIFO, write=self.buf, count=NPIX,
            ctrl=self.dma_adc.pack_ctrl(size=1, inc_read=False, inc_write=True,
                                        treq_sel=DREQ_ADC),
            trigger=True)
        self.dma_trig.config(
            read=PIO0_RXF2, write=ADC_CS, count=NPIX,
            ctrl=self.dma_trig.pack_ctrl(size=2, inc_read=False, inc_write=False,
                                         treq_sel=DREQ_PIO0_RX2),
            trigger=True)
        self.sms[1].put(1)                       # jeton : prochaine période = lecture
        import time
        t0 = time.ticks_ms()
        while self.dma_adc.active():
            if time.ticks_diff(time.ticks_ms(), t0) > timeout_ms:
                self.dma_trig.active(0)
                self.dma_adc.active(0)
                return False
        return True


# -----------------------------------------------------------------------------
#  Boucle de commande USB
# -----------------------------------------------------------------------------
def main():
    out = sys.stdout.buffer
    led = Pin("LED", Pin.OUT)
    ccd = TCD1304()
    while True:
        line = sys.stdin.readline()
        if not line:
            continue
        cmd = line.strip().split()
        if not cmd:
            continue
        c = cmd[0].upper()
        try:
            if c == "R":
                led.on()
                ok = ccd.read()
                led.off()
                if ok:
                    out.write(b"FRM:")
                    out.write(ccd.buf)
                else:
                    out.write(b"ERR timeout\n")
            elif c == "T":
                t = ccd.set_tint(int(cmd[1]))
                out.write(b"OK tint_us=%d\n" % t)
            elif c == "I":
                out.write(b"TCD1304 fw=1.0 npix=%d fm=%d tint_us=%d\n"
                          % (NPIX, ccd.fm, ccd.tint_us))
            elif c == "P":
                out.write(b"PONG\n")
            else:
                out.write(b"ERR commande inconnue\n")
        except Exception as e:
            out.write(b"ERR %s\n" % str(e).encode())


main()
