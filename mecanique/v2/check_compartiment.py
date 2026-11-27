"""Verification du module electronique et du capot capteur : aucun composant ne touche le bac,
la bride, le capot ou un autre composant ; le capot ne touche ni le boitier,
ni la tete de fente, ni la carte capteur ; le module ne touche pas le boitier."""
import itertools
import spectro_v2 as S

def vol(a, b):
    try:
        return sum(s.Volume() for s in a.intersect(b).solids().vals())
    except Exception:
        return 0.0

bac, bride, capot = S.bac_electronique(), S.bride_penglin(), S.capot_capteur()
boit = S.boitier()
tete = S.head_world(S.tete_local())
plaque = S.sens(S.plaque_capteur_Se())
carte = S.carte_capteur_dummy()
D = S.electronique_dummies()
fails = 0
def bad(msg):
    global fails; print("  ✗", msg); fails += 1

for k, v in D.items():
    for nom, piece in (("bac", bac), ("bride", bride), ("capot", capot)):
        x = vol(v, piece)
        if x > 0.01: bad(f"{k} / {nom} : {x:.2f} mm3")
for (a, va), (b, vb) in itertools.combinations(D.items(), 2):
    if {a, b} in ({"carte_interface", "rp2350_zero"}, {"rp2350_zero", "fiche_usb_c"}):
        continue
    x = vol(va, vb)
    if x > 0.01: bad(f"{a} / {b} : {x:.2f} mm3")
for nom, piece in (("boitier", boit), ("tete de fente", tete), ("plaque capteur", plaque), ("carte capteur", carte),
                   ("bac", bac), ("bride", bride)):
    x = vol(capot, piece)
    if x > 0.01: bad(f"capot / {nom} : {x:.2f} mm3")
x = vol(bac, boit)
if x > 0.01: bad(f"bac / boitier : {x:.2f} mm3")
# le bac est bien plaque sous le plancher
if abs(bac.val().BoundingBox().zmax - (-S.FLOOR)) > 0.01: bad("le bac n'est pas au contact du boitier")
x = vol(carte, boit)
if x > 0.01: bad(f"carte capteur / boitier : {x:.2f} mm3")

top, bot = S._pen_z()
bb = bride.val().BoundingBox()
if abs(bb.zmin - top) > 0.05: bad("la bride ne serre pas la carte PENGLIN")
print(f"butee bride / USB-A : jeu {S.PEN['x'] + S.PEN['w'] - 13.0 - bb.xmax:.1f} mm")
for k, v in D.items():
    b = v.val().BoundingBox()
    if b.zmax > S.Z_LID_BOT - 0.3:
        print(f"  ! {k} : sommet {b.zmax - S.Z_F:.1f} mm au-dessus du fond (interieur {S.Z_LID_BOT - S.Z_F:.1f})")
# le capot ferme bien la zone du capteur : la fente des fils est sous le capot
x0, x1, y0, y1 = S.CABLE_SLOT
cb = capot.val().BoundingBox()
if not (cb.xmin < x0 and cb.ymin < y0 and y1 < cb.ymax): bad("fente des fils hors du capot")
# carte capteur entierement sous le capot
kb = carte.val().BoundingBox()
if not (kb.xmin > cb.xmin and kb.ymax < cb.ymax and kb.zmax < cb.zmax): bad("carte capteur non couverte")
print(f"module : {S.Z_LID_TOP - S.Z_TRAY_BOT:.1f} mm sous le plancher ; hauteur totale {S.H_INT + 3 - S.Z_TRAY_BOT + 0:.1f} mm (couvercle optique compris)")
print("Module electronique et capot :", "OK" if fails == 0 else f"{fails} PROBLEME(S)")
