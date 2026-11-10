import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import spectro_v2 as S
def tris(wp,tol=0.3):
    v,t=wp.val().tessellate(tol,0.5); v=np.array([[p.x,p.y,p.z] for p in v]); return v[np.array(t)]
D=S.electronique_dummies()
comps=[("accus","Support 2×18650\nen parallèle","#2ecc71"),("bms","BMS 1S","#00b894"),
 ("penglin","PENGLIN\n5 V 2 A","#f39c12"),("interrupteur","inter.","#b2bec3"),
 ("carte_interface","carte\nd'interface","#a29bfe"),("rp2350_zero","RP2350\nZero","#e84393"),
 ("pi_zero","Pi Zero 2 W","#0984e3"),("ventilateur","ventilo\n25","#636e72")]
fig,ax=plt.subplots(figsize=(11,8))
xs=[p[0] for p in S.IN_PTS]+[S.IN_PTS[0][0]]; ys=[p[1] for p in S.IN_PTS]+[S.IN_PTS[0][1]]
ax.plot(xs,ys,"--",color="#999",lw=1,label="emprise du spectro")
for t in tris(S.compartiment_batterie()): ax.fill(t[:,0],t[:,1],color="#34495e",alpha=0.12,lw=0)
for t in tris(S.bride_penglin()): ax.fill(t[:,0],t[:,1],color="#d35400",alpha=0.35,lw=0)
for k,name,c in comps:
    bb=D[k].val().BoundingBox()
    ax.add_patch(plt.Rectangle((bb.xmin,bb.ymin),bb.xlen,bb.ylen,color=c,alpha=0.8))
    tx,ty=(bb.xmax-11,bb.ymax-6) if k=="carte_interface" else (bb.center.x,bb.center.y)
    ax.text(tx,ty,name,ha="center",va="center",fontsize=8,color="white",weight="bold")
for xs_ in S.STRAPS: ax.add_patch(plt.Rectangle((xs_-6,S.BAT_Y0+3),12,S.Y_CLOISON-S.BAT_Y0-3,fill=False,ls=":",ec="#2d3436"))
for x,y in S.BAT_SCREWS: ax.plot(x,y,"o",color="#d63031",ms=5)
ax.annotate("air →",(167,36),fontsize=9); ax.annotate("← air + câble capteur",(-30,40),fontsize=9)
ax.annotate("USB-C : charge\nUSB-A : sortie 5 V\n(anti-buée)",(168,-16),fontsize=9)
ax.annotate("interrupteur",(112,-46),fontsize=9)
ax.annotate("sangles velcro",(40,-48),fontsize=9)
ax.plot([S.BAT_X0+3,S.BAT_X1-3],[S.Y_CLOISON+1]*2,color="#2d3436",lw=2)
ax.set_aspect("equal"); ax.set_xlim(-35,210); ax.set_ylim(-55,110); ax.legend(loc="upper left",fontsize=8)
ax.set_title("Compartiment électronique sous le plancher (vu de dessus, 142 × 96 × 31 mm)\n"
             "points rouges : vis de fixation au spectro ; orange : bride du module PENGLIN")
plt.tight_layout(); plt.savefig("v2_compartiment.png",dpi=115); print("ok")

# --- vue 3D par dessous, couvercle retire
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
fig=plt.figure(figsize=(11,8)); ax=fig.add_subplot(111,projection="3d")
def add(wp,c,a,tol=0.4):
    T=tris(wp,tol); ax.add_collection3d(Poly3DCollection(T,facecolor=c,alpha=a,edgecolor=(0,0,0,0.04),lw=0.1))
add(S.compartiment_batterie(),"#34495e",0.18)
add(S.bride_penglin(),"#d35400",0.9)
for k,name,c in comps: add(D[k],c,0.95)
add(D["fiche_usb_c"],"#2d3436",0.9)
ax.set_xlim(20,170); ax.set_ylim(-50,75); ax.set_zlim(-60,20)
ax.view_init(elev=-38,azim=-58); ax.set_box_aspect((150,125,80)); ax.axis("off")
ax.set_title("Compartiment vu par dessous, couvercle retiré")
plt.tight_layout(); plt.savefig("v2_compartiment_3d.png",dpi=115); print("ok 3d")
