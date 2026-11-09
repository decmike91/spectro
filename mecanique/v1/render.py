import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import spectro_cad as S, math
B=S.base()
P={"boitier":(B,"#3a3f47",0.35),
 "tete":(S.arm(S.to_coll_arm(S.tete_local()),S.a1),"#c0392b",1),
 "cass_fente":(S.arm(S.to_coll_arm(S.cassette_fente()),S.a1),"#f1c40f",1),
 "tiroir":(S.arm(S.to_coll_arm(S.tiroir_filtre()),S.a1),"#27ae60",1),
 "tubeC":(S.arm(S.tube_lentille().translate((S.D_COLL,0,0)),S.a1),"#2980b9",1),
 "tubeK":(S.arm(S.tube_lentille().translate((S.D_CAM,0,0)),S.a2),"#2980b9",1),
 "brideC":(S.arm(S.bride_tube().translate((S.D_COLL,0,0)),S.a1),"#7f8c8d",1),
 "brideK":(S.arm(S.bride_tube().translate((S.D_CAM,0,0)),S.a2),"#7f8c8d",1),
 "plateau":(S.plateau_reseau().rotate((0,0,0),(0,0,1),-6),"#8e44ad",1),
 "cassR":(S.cassette_reseau().rotate((0,0,0),(0,0,1),-96),"#e67e22",1),
 "reseau":(S.reseau_dummy().rotate((0,0,0),(0,0,1),-96),"#00bcd4",1),
 "plaque":(S.arm(S.plaque_capteur(),S.a2),"#16a085",1),
 "capteur":(S.arm(S.capteur_dummy(),S.a2),"#ecf0f1",1)}
def tris(wp,tol=0.4):
    v,t=wp.val().tessellate(tol,0.5); v=np.array([[p.x,p.y,p.z] for p in v]); return v[np.array(t)]
cache={k:(tris(w),c,a) for k,(w,c,a) in P.items()}
def rays(ax3=None, ax2=None):
    sl=np.array(S.P(S.a1,S.SLIT_D)); co=np.array(S.P(S.a1,S.D_COLL)); g=np.zeros(2)
    ca=np.array(S.P(S.a2,S.D_CAM)); se=[np.array(S.P(S.a2,S.SENS_D,l)) for l in (-14.6,0,14.6)]
    nose=np.array(S.P(S.a1,S.SLIT_D+60))
    segs=[(nose,sl,"#ff5252"),(sl,co,"#ffd54f"),(co,g,"#ffd54f")]
    for th,c in zip((-math.atan(14.6/S.F_CAM),0,math.atan(14.6/S.F_CAM)),("#7c4dff","#00e676","#ff1744")):
        lp=np.array(S.P(S.a2,S.D_CAM, S.D_CAM*math.tan(th))); sp=np.array(S.P(S.a2,S.SENS_D,S.F_CAM*math.tan(th)))
        segs+= [(g,lp,c),(lp,sp,c)]
    for a,b,c in segs:
        if ax3 is not None: ax3.plot([a[0],b[0]],[a[1],b[1]],[S.H,S.H],color=c,lw=1.6)
        if ax2 is not None: ax2.plot([a[0],b[0]],[a[1],b[1]],color=c,lw=1.6)
fig=plt.figure(figsize=(11,10),facecolor="white")
ax=fig.add_subplot(111,projection="3d")
for k,(T,c,a) in cache.items():
    pc=Poly3DCollection(T,facecolor=c,edgecolor="none",alpha=a); pc.set_sort_zpos(None); ax.add_collection3d(pc)
rays(ax3=ax)
ax.set_xlim(-170,40); ax.set_ylim(-110,100); ax.set_zlim(-60,150)
ax.view_init(elev=42,azim=-125); ax.set_axis_off(); ax.set_box_aspect((1,1,1))
plt.title("Spectro TCD1304 – assemblage (couvercle retiré)",fontsize=14)
plt.subplots_adjust(0,0,1,0.95); plt.savefig("vue_iso.png",dpi=130)
# vue de dessus
fig,ax=plt.subplots(figsize=(11,10))
for k,(T,c,a) in cache.items():
    for t in T[::1]:
        ax.fill(t[:,0],t[:,1],color=c,alpha=min(1,a*0.9),lw=0)
rays(ax2=ax)
lab=[(S.P(S.a1,S.SLIT_D+25),"Tête de fente\n(coulant 1,25\", tiroir filtre,\nfente inclinée, port guidage)"),
     (S.P(S.a1,S.D_COLL,-38),"Collimateur f=75"),(S.P(S.a2,S.D_CAM,38),"Objectif caméra f=100"),
     ((10,-25),"Réseau sur\nplateau rotatif"),(S.P(S.a2,S.SENS_D+22),"TCD1304DG\n+ driver"),((40,58),"Vis de\nréglage λ")]
for (x,y),t in lab: ax.annotate(t,(x,y),fontsize=9,ha="center",bbox=dict(fc="white",alpha=0.8,ec="none"))
ax.set_aspect("equal"); ax.set_title("Vue de dessus – trajet optique (bleu 1er bord / vert centre / rouge 2e bord du capteur)")
ax.set_xlabel("mm"); plt.tight_layout(); plt.savefig("vue_dessus.png",dpi=120)
print("ok")
