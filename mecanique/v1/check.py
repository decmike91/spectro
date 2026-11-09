import itertools, cadquery as cq, glob, os
fs=[f for f in sorted(glob.glob("export/*.stl"))]
import spectro_cad as S
B=S.base()
parts={"boitier":B,"couv":S.couvercle(),"trappe":S.trappe(),
 "tete":S.arm(S.to_coll_arm(S.tete_local()),S.a1),
 "cass_fente":S.arm(S.to_coll_arm(S.cassette_fente()),S.a1),
 "tiroir":S.arm(S.to_coll_arm(S.tiroir_filtre()),S.a1),
 "tubeC":S.arm(S.tube_lentille().translate((S.D_COLL,0,0)),S.a1),
 "tubeK":S.arm(S.tube_lentille().translate((S.D_CAM,0,0)),S.a2),
 "brideC":S.arm(S.bride_tube().translate((S.D_COLL,0,0)),S.a1),
 "brideK":S.arm(S.bride_tube().translate((S.D_CAM,0,0)),S.a2),
 "plaque":S.arm(S.plaque_capteur(),S.a2),"masque":S.arm(S.masque_capteur(),S.a2)}
for phi in (0,6,26,32):
    parts[f"plat{phi}"]=S.plateau_reseau().rotate((0,0,0),(0,0,1),-phi)
    parts[f"cassR{phi}"]=S.cassette_reseau().rotate((0,0,0),(0,0,1),-90-phi)
for a,b in itertools.combinations(parts,2):
    if a[:4]==b[:4] and a.startswith(("plat","cass")) : continue
    if ("plat" in a and "cassR" in b) or ("cassR" in a and "plat" in b):
        if a[-2:].strip("tR")!=b[-2:].strip("tR"): continue
    try:
        v=parts[a].intersect(parts[b]).val().Volume()
    except Exception: v=0
    if v>0.5: print(f"{a:12s} x {b:12s}: {v:.1f} mm3")
