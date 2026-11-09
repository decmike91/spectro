import numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import spectro_v2 as S
def tris(wp,tol=0.3):
    v,t=wp.val().tessellate(tol,0.5); v=np.array([[p.x,p.y,p.z] for p in v]); return v[np.array(t)]
zt=S._ztop()
comps=[("Accus 2×18650",S.W().box(77,41,20,centered=False).translate((35.5,-32,zt-20)),"#2ecc71"),
 ("Chargeur 5 V\nUSB-C",S.W().box(45,28,10,centered=False).translate((116,-21,zt-10)),"#f39c12"),
 ("Pico",S.W().box(51,21,4,centered=False).translate((S.PICO['x'],S.PICO['y'],zt-8)),"#e84393"),
 ("Pi Zero 2 W",S.W().box(65,30,5,centered=False).translate((S.PIZ['x'],S.PIZ['y'],zt-9)),"#0984e3"),
 ("Ventilo\n25 mm",S.W().box(10,25,25,centered=(False,True,True)).translate((S.FAN['x'],S.FAN['yc'],zt-13)),"#636e72")]
fig,ax=plt.subplots(figsize=(11,8))
# contour du boitier au-dessus
xs=[p[0] for p in S.IN_PTS]+[S.IN_PTS[0][0]]; ys=[p[1] for p in S.IN_PTS]+[S.IN_PTS[0][1]]
ax.plot(xs,ys,"--",color="#999",lw=1,label="emprise du spectro")
for t in tris(S.compartiment_batterie()): ax.fill(t[:,0],t[:,1],color="#34495e",alpha=0.12,lw=0)
for name,w,c in comps:
    bb=w.val().BoundingBox()
    ax.add_patch(plt.Rectangle((bb.xmin,bb.ymin),bb.xlen,bb.ylen,color=c,alpha=0.85))
    ax.text(bb.center.x,bb.center.y,name,ha="center",va="center",fontsize=9,color="white",weight="bold")
for x,y in S.BAT_SCREWS: ax.plot(x,y,"o",color="#d63031",ms=5)
ax.annotate("air →",(167,36),fontsize=9); ax.annotate("← air + câble capteur",(-30,40),fontsize=9)
ax.annotate("USB-C charge",(168,-7),fontsize=9); ax.annotate("interrupteur",(125,-44),fontsize=9)
ax.axhline(S.Y_CLOISON+1,xmin=0,xmax=0,color="k")
ax.plot([S.BAT_X0+3,S.BAT_X1-3],[S.Y_CLOISON+1]*2,color="#2d3436",lw=2)
ax.set_aspect("equal"); ax.set_xlim(-35,205); ax.set_ylim(-55,110); ax.legend(loc="upper left",fontsize=8)
ax.set_title("Compartiment électronique sous le plancher (vu de dessus, 142 × 96 × 31 mm)\npoints rouges : vis de fixation au spectro")
plt.tight_layout(); plt.savefig("v2_compartiment.png",dpi=115); print("ok")
