import itertools, sys, cadquery as cq, spectro_v2 as S
res=[]
def inter(a,b):
    try:
        i=a.intersect(b); return sum(s.Volume() for s in i.solids().vals())
    except Exception as e: return -1
for phi in (0, 6, 15, 27, 30):
  for focus in (-S.TRAVEL, S.TRAVEL):
    P,_,D=S.parts(phi, focus)
    P={**P, **{k:v for k,v in D.items() if k.startswith("vis")}, "reseau":D["reseau"], "miroir":D["miroir"]}
    if phi!=0 or focus!=-S.TRAVEL:  # pieces fixes testees une seule fois
        keys=[k for k in P if k in ("13_plateau_equerre","14_cadre_tilt","15_disque_reseau","reseau","vis_lambda","07_chariot_coll","08_tube_coll","09_bride_coll","10_chariot_cam","11_tube_cam","12_bride_cam","vis_coll","vis_cam")]
    else: keys=list(P)
    for a in keys:
        for b in P:
            if a>=b and b in keys: continue
            if a==b: continue
            v=inter(P[a],P[b])
            if v>0.3: res.append((phi,focus,a,b,round(v,1)))
seen=set()
for r in res:
    k=(min(r[2],r[3]),max(r[2],r[3]))
    if k in seen: continue
    seen.add(k); print(r)
print("fin", len(res))
