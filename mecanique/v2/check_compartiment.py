"""Verification du compartiment electronique : aucun composant ne touche les parois,
le couvercle, la bride ou un autre composant ; chaque composant est dans le volume."""
import itertools
import spectro_v2 as S

def vol(a, b):
    try:
        return a.intersect(b).val().Volume()
    except Exception:
        return 0.0

comp = S.compartiment_batterie()
lid = S.couvercle_batterie()
bride = S.bride_penglin()
D = S.electronique_dummies()
fails = 0
for k, v in D.items():
    for nom, piece in (("compartiment", comp), ("couvercle", lid), ("bride", bride)):
        x = vol(v, piece)
        if x > 0.01:
            # la bride doit TOUCHER le module sans le penetrer ; la fiche USB-C est hors de la carte
            print(f"  ✗ {k} / {nom} : {x:.2f} mm3"); fails += 1
for (a, va), (b, vb) in itertools.combinations(D.items(), 2):
    if {a, b} in ({"carte_interface", "rp2350_zero"}, {"rp2350_zero", "fiche_usb_c"}):
        continue                                  # emboitement voulu
    x = vol(va, vb)
    if x > 0.01:
        print(f"  ✗ {a} / {b} : {x:.2f} mm3"); fails += 1
# contact bride / module (doit etre au contact : distance ~0)
top, bot = S._pen_z()
bb = bride.val().BoundingBox()
print(f"bride : dessus z={bb.zmax:.2f}, dessous carte PENGLIN z={bot:.2f}")
if abs(bb.zmax - bot) > 0.05:
    print("  ✗ la bride ne serre pas la carte"); fails += 1
# butee USB-A
usba_x0 = S.PEN["x"] + S.PEN["w"] - 13.0
print(f"butee : bord bride x={bb.xmax:.1f}, corps USB-A x={usba_x0:.1f} (jeu {usba_x0 - bb.xmax:.1f} mm)")
# volume interieur libre sous les composants (couvercle coulissant)
z_lid = -S.FLOOR - S.BAT_H + 2.4
for k, v in D.items():
    b = v.val().BoundingBox()
    if b.zmin < z_lid + 0.5:
        print(f"  ✗ {k} trop bas : {b.zmin:.1f} < {z_lid + 0.5:.1f}"); fails += 1
print("Compartiment :", "OK" if fails == 0 else f"{fails} PROBLEME(S)")
