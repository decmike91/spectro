import spectro_v2 as S, beams_v2 as BM
P,_,D = S.parts(S.PHI_NOM, 0)
for bn,b in BM.BEAMS.items():
    for pn,p in {**P, **D}.items():
        if pn in ("dummy_miroir","miroir") and bn in ("obj->miroir","miroir->capt"): continue
        try:
            i=p.intersect(b); v=sum(s.Volume() for s in i.solids().vals())
        except Exception: v=-1
        if v>0.05: print(f"{bn:14s} bloque par {pn}: {v:.2f} mm3")
for phi in (0,15,30):
    P,_,D = S.parts(phi, 0)
    for pn in ("13_plateau_equerre","14_cadre_tilt","15_disque_reseau"):
        for bn in ("coll->reseau","reseau->obj"):
            i=P[pn].intersect(BM.BEAMS[bn]); v=sum(s.Volume() for s in i.solids().vals())
            if v>0.05: print(f"phi={phi} {bn} bloque par {pn}: {v:.2f}")
print("faisceaux ok")
