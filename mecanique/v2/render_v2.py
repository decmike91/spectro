import numpy as np, math, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import spectro_v2 as S
P,_,D=S.parts()
col={"01_boitier":("#3a3f47",.30),"04_tete_fente":("#c0392b",1),"05_cassette_fente":("#f1c40f",1),"06_tiroir_filtre":("#27ae60",1),
 "07_chariot_coll":("#5d6d7e",1),"08_tube_coll":("#2980b9",1),"09_bride_coll":("#7f8c8d",1),
 "10_chariot_cam":("#5d6d7e",1),"11_tube_cam":("#2980b9",1),"12_bride_cam":("#7f8c8d",1),
 "13_plateau_equerre":("#8e44ad",1),"14_cadre_tilt":("#d35400",1),"15_disque_reseau":("#e67e22",1),
 "16_plaque_miroir":("#95a5a6",1),"17_plaque_capteur":("#16a085",1),"23_compartiment_batterie":("#34495e",.55),
 "reseau":("#00bcd4",1),"miroir":("#dfe6e9",1),"capteur":("#ecf0f1",1),"vis_coll":("#b7950b",1),"vis_cam":("#b7950b",1),"vis_lambda":("#b7950b",1),"accus":("#2ecc71",.8)}
allp={**P,**D}
def tris(wp,tol=0.4):
    v,t=wp.val().tessellate(tol,0.5); v=np.array([[p.x,p.y,p.z] for p in v]); return v[np.array(t)]
cache={k:(tris(allp[k]),c,a) for k,(c,a) in col.items()}
def rays():
    segs=[((-60,0),(0,0),"#ff5252"),((0,0),(S.SLIT_D-S.D_COLL,0),"#ffd54f"),((S.SLIT_D-S.D_COLL,0),S.G,"#ffd54f")]
    for k,c in zip((-1,0,1),("#7c4dff","#00e676","#ff1744")):
        th=math.atan(14.6/S.F_CAM)*k
        lp=S.add(S.add(S.G,S.U_CAM,S.D_CAM),S.N_CAM,S.D_CAM*math.tan(th))
        a=S.D_MIR; mp=S.add(S.add(S.G,S.U_CAM,a),S.N_CAM,S.D_CAM*math.tan(th)+(a-S.D_CAM)*(14.6*k/S.F_CAM - S.D_CAM*math.tan(th)/S.F_CAM))
        sp=S.add(S.S_PT,S.ang(S.A_OUT+90,1),-14.6*k)
        segs+=[(S.G,lp,c),(lp,mp,c),(mp,sp,c)]
    return segs
# vue de dessus
fig,ax=plt.subplots(figsize=(11,10))
for k,(T,c,a) in cache.items():
    if k in ("23_compartiment_batterie","accus"): continue
    for t in T: ax.fill(t[:,0],t[:,1],color=c,alpha=min(1,a*0.9),lw=0)
for a,b,c in rays(): ax.plot([a[0],b[0]],[a[1],b[1]],color=c,lw=1.6)
lab=[((-25,40),"Tête de fente\n(coulant 1,25\", tiroir filtre,\nfente inclinée)"),((-30,-70),"Port de\nguidage"),
     ((75,-48),"Collimateur f=75\nsur chariot (focus)"),((122,-50),"Réseau : λ + tilt + roll"),
     ((150,62),"Objectif f=100\nsur chariot (focus)"),((92,105),"Miroir plan 55×20"),((8,104),"TCD1304DG\n(facette)"),
     ((182,-29),"vis λ"),((182,-17),"focus coll."),((182,-4),"focus cam.")]
for (x,y),t in lab: ax.annotate(t,(x,y),fontsize=9,ha="center",bbox=dict(fc="white",alpha=0.85,ec="none"))
ax.set_aspect("equal"); ax.set_xlim(-70,200); ax.set_ylim(-110,120)
ax.set_title("Spectro v2 replié – vue de dessus (couvercle retiré), trajet optique"); ax.set_xlabel("mm")
plt.tight_layout(); plt.savefig("v2_dessus.png",dpi=115)
# iso
fig=plt.figure(figsize=(11,9)); ax=fig.add_subplot(111,projection="3d")
for k,(T,c,a) in cache.items():
    pc=Poly3DCollection(T,facecolor=c,edgecolor="none",alpha=a); ax.add_collection3d(pc)
for a,b,c in rays(): ax.plot([a[0],b[0]],[a[1],b[1]],[S.H,S.H],color=c,lw=1.4)
ax.set_xlim(-40,180); ax.set_ylim(-80,140); ax.set_zlim(-90,130); ax.view_init(elev=30,azim=-120)
ax.set_axis_off(); ax.set_box_aspect((1,1,1)); plt.subplots_adjust(0,0,1,0.95)
plt.title("Spectro v2 – assemblage avec compartiment batterie"); plt.savefig("v2_iso.png",dpi=125)
# zoom monture reseau
fig=plt.figure(figsize=(8,7)); ax=fig.add_subplot(111,projection="3d")
for k in ("13_plateau_equerre","14_cadre_tilt","15_disque_reseau","reseau"):
    T,c,a=cache[k]; ax.add_collection3d(Poly3DCollection(T,facecolor=c,edgecolor="#00000022",lw=0.1,alpha=1))
ax.set_xlim(100,160); ax.set_ylim(-30,30); ax.set_zlim(0,60); ax.view_init(elev=18,azim=-30); ax.set_axis_off()
plt.title("Monture du réseau : rotation λ, charnière de tilt, disque d'orientation"); plt.savefig("v2_monture_reseau.png",dpi=120)
print("ok")
