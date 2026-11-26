import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import spectro_v2 as S
def tris(wp,tol=0.3):
    v,t=wp.val().tessellate(tol,0.5); v=np.array([[p.x,p.y,p.z] for p in v]); return v[np.array(t)]
D=S.electronique_dummies()
comps=[("accus","Support 2×18650\nen parallèle","#2ecc71"),("bms","BMS","#00b894"),
 ("penglin","PENGLIN","#f39c12"),("interrupteur","inter.","#b2bec3"),
 ("carte_interface","carte\nd'interface","#a29bfe"),("rp2350_zero","RP2350\nZero","#e84393"),
 ("pi_zero","Pi Zero 2 W","#0984e3"),("ventilateur","ventilo","#636e72")]
bac=S.bac_electronique(); capot=S.capot_capteur(); bride=S.bride_penglin()
# --- vue de dessus du bac
fig,ax=plt.subplots(figsize=(10,9))
for t in tris(bac): ax.fill(t[:,0],t[:,1],color="#34495e",alpha=0.10,lw=0)
xs=[p[0] for p in S.IN_PTS]+[S.IN_PTS[0][0]]; ys=[p[1] for p in S.IN_PTS]+[S.IN_PTS[0][1]]
ax.plot(xs,ys,"--",color="#999",lw=1,label="boîtier optique (au-dessus)")
cb=capot.val().BoundingBox()
ax.add_patch(plt.Rectangle((cb.xmin,cb.ymin),cb.xlen,cb.ylen,fill=False,ec="#e17055",lw=2,ls="-.",label="capot capteur (au-dessus)"))
x0,x1,y0,y1=S.CABLE_SLOT; ax.add_patch(plt.Rectangle((x0,y0),x1-x0,y1-y0,color="#e17055")); ax.text(x1+1,y1+1,"fente\ndes fils",fontsize=7,color="#e17055")
for t in tris(bride): ax.fill(t[:,0],t[:,1],color="#d35400",alpha=0.5,lw=0)
for k,name,c in comps:
    bb=D[k].val().BoundingBox()
    ax.add_patch(plt.Rectangle((bb.xmin,bb.ymin),bb.xlen,bb.ylen,color=c,alpha=0.85))
    tx,ty=(bb.xmax-11,bb.ymax-6) if k=="carte_interface" else (bb.center.x,bb.center.y)
    ax.text(tx,ty,name,ha="center",va="center",fontsize=8,color="white",weight="bold")
for x,y in S.mod_pts(): ax.plot(x,y,"o",color="#d63031",ms=6)
ax.annotate("USB-C charge\nUSB-A 5 V",(166,-14),(170,-40),fontsize=8,arrowprops=dict(arrowstyle="->"))
ax.annotate("extraction",(166,S.FAN["yc"]),(172,20),fontsize=8,arrowprops=dict(arrowstyle="->"))
ax.annotate("entrées d'air",(10,78),(-30,70),fontsize=8,arrowprops=dict(arrowstyle="->"))
ax.annotate("interrupteur",(120,-39),(100,-55),fontsize=8,arrowprops=dict(arrowstyle="->"))
ax.set_aspect("equal"); ax.set_xlim(-35,205); ax.set_ylim(-62,112); ax.legend(loc="upper right",fontsize=8)
ax.set_title("Module électronique sous le boîtier (vu de dessus, couvercle retiré)\npoints rouges : 8 vis M3 × 35 de fixation au boîtier, par dessous",fontsize=10)
plt.tight_layout(); plt.savefig("v2_compartiment.png",dpi=110); plt.close()
# --- vue 3D de l'ensemble
P,extra,dum=S.parts()
fig=plt.figure(figsize=(11,9)); ax=fig.add_subplot(111,projection="3d")
def add(wp,c,a,tol=0.5):
    ax.add_collection3d(Poly3DCollection(tris(wp,tol),facecolor=c,alpha=a,edgecolor=(0,0,0,0.03),lw=0.1))
add(P["01_boitier"],"#4a4f57",0.55)
add(P["04_tete_fente"],"#7f8c8d",0.6)
add(P["17_plaque_capteur"],"#16a085",1)
add(P["23_bac_electronique"],"#2d3436",0.35)
add(P["24_couvercle_electronique"],"#636e72",0.25)
add(P["26_capot_capteur"],"#e17055",0.85)
for k,name,c in comps: add(D[k],c,0.95)
ax.set_xlim(-40,170); ax.set_ylim(-60,150); ax.set_zlim(-40,80)
ax.view_init(elev=28,azim=-140); ax.set_box_aspect((210,210,120),zoom=1.05); ax.axis("off")
ax.set_title("Spectro v2 : module électronique dans le prolongement du boîtier\net capot du capteur (orange), couvercle optique retiré",fontsize=10)
plt.tight_layout(); plt.savefig("v2_compartiment_3d.png",dpi=110); print("ok")
