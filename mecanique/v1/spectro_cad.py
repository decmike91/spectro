"""
Spectroscope astro TCD1304DG - modele parametrique CadQuery
Geometrie en V a deviation fixe (angle inclus 50 deg), reseau plan en reflexion.
Repere monde : origine = axe de rotation du reseau (face du reseau), Z vers le haut,
plancher interieur a z=0, axe optique a z=H.
Lancer :  python3 spectro_cad.py   -> STL de chaque piece + STEP d'assemblage dans ./export
"""
import math, os
import cadquery as cq

# ------------------------------------------------------------------ parametres
H        = 30.0      # hauteur de l'axe optique au-dessus du plancher
H_INT    = 62.0      # hauteur interieure du boitier
WALL     = 3.0       # epaisseur parois
FLOOR    = 3.0
DEV      = 60.0      # angle inclus collimateur / camera (deg)
F_COLL   = 75.0      # focale collimateur
F_CAM    = 100.0     # focale objectif camera
D_COLL   = 55.0      # distance reseau -> collimateur
D_CAM    = 40.0      # distance reseau -> objectif camera (court = pas de vignettage)
SLIT_D   = D_COLL + F_COLL          # 130 : distance reseau -> fente
SENS_D   = D_CAM + F_CAM            # 140 : distance reseau -> capteur (nominale)
HEAD_BACK = 10.0     # la fente est 10 mm en avant de la face d'appui de la tete
COLL_WALL_OUT = SLIT_D - HEAD_BACK  # face exterieure paroi cote fente
CAM_WALL_OUT  = SENS_D - 3.0        # face ext. paroi capteur : plaque 4 mm + poche 2 mm + verre->puce ~1 mm
HW_COLL, HW_CAM = 32.0, 34.0        # demi-largeurs interieures des parois d'extremite
LENS_OD, LENS_D = 34.0, 25.4        # tube porte-lentille / lentille Ø1"
TUBE_L   = 16.0
CLR      = 0.25      # jeu d'impression FDM
INS_M3   = 4.0       # trou pour insert laiton M3 (a chaud)
SLIT_TILT = -30.0    # inclinaison fente (deg, autour de la verticale) -> renvoi a 60 deg vers guidage
NOSE_D   = 31.75     # coulant 1,25"

a1 = math.radians(180 - DEV/2)      # direction bras collimateur
a2 = math.radians(180 + DEV/2)      # direction bras camera
u = lambda a, d: (d*math.cos(a), d*math.sin(a))
n = lambda a, d: (-d*math.sin(a), d*math.cos(a))
def P(a, along, lat=0.0):
    x, y = u(a, along); nx, ny = n(a, lat); return (x+nx, y+ny)

def arm(shape, a):
    """Place une piece construite dans le repere 'bras' (X = distance au reseau) dans le monde."""
    return shape.rotate((0, 0, 0), (0, 0, 1), math.degrees(a))

# ------------------------------------------------------------------ contour
def hull(pts):
    pts = sorted(set(pts))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]

IN_PTS = hull([P(a1, COLL_WALL_OUT-WALL, HW_COLL), P(a1, COLL_WALL_OUT-WALL, -HW_COLL),
               P(a2, CAM_WALL_OUT-WALL,  HW_CAM),  P(a2, CAM_WALL_OUT-WALL,  -HW_CAM),
               (34.0, 66.0), (34.0, -36.0)])

def outline(off):
    return cq.Workplane("XY").polyline(IN_PTS).close().offset2D(off, "arc")

# ------------------------------------------------------------------ BOITIER
def end_pad(a, wall_out, hw, thick=7.0):
    """Renfort interieur sur paroi d'extremite (pour inserts)"""
    return arm(cq.Workplane("XY").box(thick, 2*hw, H_INT - 4.5, centered=(False, True, False))
               .translate((wall_out-WALL-thick, 0, 0)), a)

def cradle(a, along):
    c = (cq.Workplane("XY").box(TUBE_L - 6, 44, H, centered=(True, True, False))
         .cut(cq.Workplane("YZ").circle(LENS_OD/2+CLR).extrude(40, both=True).translate((0, 0, H))))
    for sx in (0,):
        for sy in (-19.5, 19.5):
            c = c.cut(cq.Workplane("XY").circle(INS_M3/2).extrude(8).translate((sx, sy, H-8)))
    return arm(c.translate((along, 0, 0)), a)

def base():
    shell = outline(WALL).extrude(H_INT + FLOOR).translate((0, 0, -FLOOR))
    shell = shell.cut(outline(0).extrude(H_INT + 1))
    # renforts d'extremite
    shell = shell.union(end_pad(a1, COLL_WALL_OUT, HW_COLL)).union(end_pad(a2, CAM_WALL_OUT, HW_CAM))
    # passage lumiere cote fente + 4 inserts de fixation de la tete
    cut1 = cq.Workplane("YZ").circle(11).extrude(30).translate((COLL_WALL_OUT-20, 0, H))
    for y, z in [(-24, -22), (24, -22), (-24, 22), (24, 22)]:
        cut1 = cut1.union(cq.Workplane("YZ").circle(INS_M3/2).extrude(8)
                          .translate((COLL_WALL_OUT-8, y, H+z)))
    shell = shell.cut(arm(cut1, a1))
    # fenetre capteur + 3 inserts de reglage tip/tilt/focus
    cut2 = cq.Workplane("XY").box(30, 36, 14).translate((CAM_WALL_OUT-10, 0, H))
    for y, z in [(-27, 0), (27, 11), (27, -11)]:
        cut2 = cut2.union(cq.Workplane("YZ").circle(INS_M3/2).extrude(8)
                          .translate((CAM_WALL_OUT-8, y, H+z)))
    shell = shell.cut(arm(cut2, a2))
    # berceaux des tubes de lentilles
    shell = shell.union(cradle(a1, D_COLL)).union(cradle(a2, D_CAM))
    # pivot du reseau (vis M4 par dessous, tete noyee)
    shell = shell.union(cq.Workplane("XY").circle(8).extrude(9))
    shell = shell.cut(cq.Workplane("XY").circle(2.2).extrude(20).translate((0, 0, -5)))
    shell = shell.cut(cq.Workplane("XY").circle(4.2).extrude(3.2).translate((0, 0, -FLOOR-0.01)))
    # bossage de la vis micrometrique (M3 x 50, insert depuis l'exterieur) + poteau ressort
    boss = cq.Workplane("XY").box(10, 12, 18, centered=(False, True, False)).translate((34-10, 54, 0))
    shell = shell.union(boss)
    shell = shell.cut(cq.Workplane("YZ").circle(INS_M3/2).extrude(20).translate((22, 54, 11.5)))
    shell = shell.union(cq.Workplane("XY").circle(2.5).extrude(16).translate((20, 34, 0)))
    # cloison anti-lumiere parasite entre les deux bras
    xs = min(p[0] for p in IN_PTS) - 1
    shell = shell.union(cq.Workplane("XY").box(-70 - xs, 2, H_INT - 4.5, centered=(False, True, False))
                        .translate((xs, 0, 0)))
    shell = shell.intersect(outline(WALL).extrude(H_INT + FLOOR).translate((0, 0, -FLOOR)))
    # colonnettes de fixation du couvercle aux sommets
    cx = sum(p[0] for p in IN_PTS)/len(IN_PTS); cy = sum(p[1] for p in IN_PTS)/len(IN_PTS)
    global LID_PTS
    LID_PTS = []
    for (x, y) in IN_PTS:
        d = math.hypot(cx-x, cy-y); px, py = x+(cx-x)/d*5, y+(cy-y)/d*5
        LID_PTS.append((px, py))
        shell = shell.union(cq.Workplane("XY").circle(5).extrude(H_INT).translate((px, py, 0)))
        shell = shell.cut(cq.Workplane("XY").circle(INS_M3/2).extrude(8).translate((px, py, H_INT-8)))
    return shell

HATCH = (-25, 25, -20, 32)   # trappe d'acces au reseau (xmin, xmax, ymin, ymax)

def couvercle():
    lid = outline(WALL).extrude(3).translate((0, 0, H_INT))
    x0, x1, y0, y1 = HATCH
    lid = lid.cut(cq.Workplane("XY").box(x1-x0, y1-y0, 10).translate(((x0+x1)/2, (y0+y1)/2, H_INT)))
    for (x, y) in LID_PTS:
        lid = lid.cut(cq.Workplane("XY").circle(1.7).extrude(10).translate((x, y, H_INT-1)))
    # aimants 6x2 aux coins de la trappe
    for x in (x0-5, x1+5):
        for y in (y0+6, y1-6):
            lid = lid.cut(cq.Workplane("XY").circle(3.1).extrude(2.2).translate((x, y, H_INT+3-2.2)))
    # levre anti-lumiere
    lip = outline(-0.4).extrude(4).translate((0, 0, H_INT-4)).cut(outline(-2.4).extrude(4).translate((0, 0, H_INT-4)))
    for (x, y) in LID_PTS:
        lip = lip.cut(cq.Workplane("XY").circle(5.6).extrude(6).translate((x, y, H_INT-5)))
    return lid.union(lip)

def trappe():
    x0, x1, y0, y1 = HATCH
    t = cq.Workplane("XY").box(x1-x0+20, y1-y0, 3).translate(((x0+x1)/2, (y0+y1)/2, H_INT+4.5))
    t = t.union(cq.Workplane("XY").box(x1-x0-2*CLR, y1-y0-2*CLR, 3).translate(((x0+x1)/2, (y0+y1)/2, H_INT+1.5)))
    t = t.cut(cq.Workplane("XY").box(x1-x0-6, y1-y0-6, 3).translate(((x0+x1)/2, (y0+y1)/2, H_INT+1.5)))
    for x in (x0-5, x1+5):
        for y in (y0+6, y1-6):
            t = t.cut(cq.Workplane("XY").circle(3.1).extrude(2.2).translate((x, y, H_INT+3)))
    return t

# ------------------------------------------------------------------ TETE DE FENTE
# repere local : lumiere selon +Z, fente a l'origine, Y = verticale, X = lateral
def tete_local():
    HB = HEAD_BACK
    body = cq.Workplane("XY").box(50, 50, 24 + HB).translate((0, 0, (HB - 24)/2))  # z -24..HB
    body = body.union(cq.Workplane("XY").box(60, 56, 6).translate((0, 0, HB - 3)))  # bride
    body = body.union(cq.Workplane("XY").circle(NOSE_D/2 - 0.1).extrude(32).translate((0, 0, -56)))
    # port de guidage (renvoi par la fente inclinee a 60 deg)
    t = math.radians(2*abs(SLIT_TILT))
    pdir = cq.Vector(math.sin(t), 0, -math.cos(t))
    port = cq.Solid.makeCylinder(19, 74, cq.Vector(0, 0, 0) + pdir*18, pdir)
    port = cq.Workplane("XY").add(port).intersect(cq.Workplane("XY").box(300, 300, 150).translate((0, 0, -75)))
    body = body.union(port)
    # alesages
    body = body.cut(cq.Workplane("XY").circle(13.5).extrude(52).translate((0, 0, -57)))    # avant fente
    body = body.cut(cq.Workplane("XY").circle(6).extrude(HB + 1).translate((0, 0, 0)))    # apres fente
    body = body.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(8, 30, cq.Vector(0, 0, 0), pdir)))
    body = body.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(15.9 + CLR, 70, cq.Vector(0, 0, 0)+pdir*24, pdir)))
    # tiroir filtre 1,25" (z -19..-11), ouvert par le haut
    body = body.cut(cq.Workplane("XY").box(34 + 2*CLR, 45, 8 + 2*CLR).translate((0, 25 - 22.5 + 3, -17)))
    # glissiere cassette de fente, inclinee
    slot = cq.Workplane("XY").box(24 + 2*CLR, 46, 4 + 2*CLR).translate((0, 25 - 23 + 4, 0))
    body = body.cut(slot.rotate((0, 0, 0), (0, 1, 0), SLIT_TILT))
    # fixations sur boitier
    for x, y in [(-24, -22), (24, -22), (-24, 22), (24, 22)]:
        body = body.cut(cq.Workplane("XY").circle(1.7).extrude(10).translate((x, y, HB - 8)))
    # vis pointeau M3 pour serrer coulant guidage
    body = body.cut(cq.Workplane("XY").add(cq.Solid.makeCylinder(INS_M3/2, 30,
                    cq.Vector(0, 0, 0)+pdir*60, cq.Vector(0, 1, 0))))
    return body

def to_coll_arm(shape_local):
    """local (Xl,Yl,Zl) -> bras collimateur (X=SLIT_D-Zl, Y=-Xl, Z=H+Yl)"""
    return (shape_local.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), -90)
            .translate((SLIT_D, 0, H)))

def cassette_fente():
    c = cq.Workplane("XY").box(24, 44.5, 4).translate((0, 5.75, 0))          # y -20..28 (local tete)
    c = c.union(cq.Workplane("XY").box(24, 4, 6).translate((0, 30, 0)))   # poignee/capot
    c = c.cut(cq.Workplane("XY").box(18, 20, 2).translate((0, 0, -1)))     # logement lame/feuillard (cote telescope)
    c = c.cut(cq.Workplane("XY").box(4, 14, 10))                          # fenetre
    c = c.cut(cq.Workplane("XY").box(10, 2, 10).translate((0, 31.5, 0)))     # etiquette largeur (grave)
    return c.rotate((0, 0, 0), (0, 1, 0), SLIT_TILT)

def tiroir_filtre():
    d = cq.Workplane("XY").box(34, 44, 8).translate((0, 6.5, -17))
    d = d.union(cq.Workplane("XY").box(44, 4, 10).translate((0, 30.5, -17)))
    d = d.cut(cq.Workplane("XY").circle(15.4 + CLR).extrude(5.5).translate((0, 0, -21.01)))   # cellule filtre
    d = d.cut(cq.Workplane("XY").circle(13).extrude(10).translate((0, 0, -22)))
    return d

def porte_relais():
    """Insert coulissant dans le port de guidage : lentille relais Ø12,7 f=25 (grandissement 1)."""
    r = cq.Workplane("XY").circle(15.9 - CLR).circle(6.0).extrude(12)
    r = r.cut(cq.Workplane("XY").circle(6.35 + 0.15).extrude(3.5).translate((0, 0, 8.5)))
    return r

def capuchon_source():
    """Se coiffe sur le coulant : LED blanche / halogene + diffuseur, pour courbes de filtres et flats."""
    c = cq.Workplane("XY").circle(NOSE_D/2 + 3).extrude(40)
    c = c.cut(cq.Workplane("XY").circle(NOSE_D/2 + 0.3).extrude(26).translate((0, 0, 14)))
    c = c.cut(cq.Workplane("XY").circle(12.6).extrude(2).translate((0, 0, 12)))   # diffuseur Ø25
    c = c.cut(cq.Workplane("XY").circle(5.2).extrude(13))                        # LED 10 mm / ampoule
    return c

# ------------------------------------------------------------------ OPTIQUE INTERNE
def tube_lentille():
    t = cq.Workplane("YZ").circle(LENS_OD/2).circle(LENS_D/2 + 0.15).extrude(TUBE_L)
    t = t.union(cq.Workplane("YZ").circle(LENS_D/2 + 0.2).circle(11).extrude(1.5))   # epaulement
    # epaulement cote fente (collimateur) / cote capteur (camera) : le tube est retourne
    return t.translate((-TUBE_L/2, 0, H)).rotate((0, 0, 0), (0, 0, 1), 180)

def bague_lentille():
    return cq.Workplane("YZ").circle(LENS_D/2 + 0.1).circle(11).extrude(3)

def bride_tube():
    b = cq.Workplane("XY").box(8, 44, LENS_OD/2 + 4, centered=(True, True, False)).translate((0, 0, H))
    b = b.cut(cq.Workplane("YZ").circle(LENS_OD/2 + CLR).extrude(20, both=True).translate((0, 0, H)))
    for sy in (-19.5, 19.5):
        b = b.cut(cq.Workplane("XY").circle(1.7).extrude(30).translate((0, sy, H)))
    return b

def plateau_reseau():
    p = cq.Workplane("XY").circle(18).extrude(3).translate((0, 0, 9))
    arm_ang = math.radians(16)
    L = 60
    bar = (cq.Workplane("XY").box(8, L, 3, centered=(True, False, False)).translate((0, 0, 9))
           .union(cq.Workplane("XY").box(8, L - 24, 5, centered=(True, False, False)).translate((0, 24, 9)))
           .rotate((0, 0, 0), (0, 0, 1), 16))
    p = p.union(bar)
    tip = (-math.sin(arm_ang)*(L-4), math.cos(arm_ang)*(L-4))
    p = p.cut(cq.Workplane("XY").circle(1.2).extrude(10).translate((tip[0], tip[1], 8)))  # accroche ressort
    p = p.cut(cq.Workplane("XY").circle(2.2).extrude(10).translate((0, 0, 8)))
    for x in (-11, 11):
        p = p.cut(cq.Workplane("XY").circle(1.45).extrude(4).translate((9, x, 9.5)))    # piges Ø3
    p = p.cut(cq.Workplane("XY").circle(4.1).extrude(3.1).translate((9, 0, 12 - 3.1 + 0.01)))  # aimant 8x3
    return p

def cassette_reseau():
    """Reseau 25 x 25 x 6 (type Thorlabs GR25-xxxx), face gravee dans le plan de l'axe de pivot (y=0)."""
    g = cq.Workplane("XY").box(32, 13, 3, centered=(True, False, False)).translate((0, 0, 12))
    g = g.union(cq.Workplane("XY").box(32, 4, 30, centered=(True, False, False)).translate((0, 6 + CLR, 15)))
    g = g.union(cq.Workplane("XY").box(32, 6.5, 2.3, centered=(True, False, False)).translate((0, 0, 15)))
    for x in (-15, 15):   # joues laterales
        g = g.union(cq.Workplane("XY").box(2, 6.5, 30, centered=(True, False, False)).translate((x, 0.3, 15)))
    g = g.cut(cq.Workplane("XY").box(25.4 + 2*CLR, 6.1 + CLR, 40, centered=(True, False, False)).translate((0, 0, 17.3)))
    for x in (-11, 11):
        g = g.cut(cq.Workplane("XY").circle(1.6).extrude(4).translate((x, 9, 11.5)))
    g = g.cut(cq.Workplane("XY").circle(4.1).extrude(1.6).translate((0, 9, 11.99)))
    # fenetre de visee arriere supprimee : dos plein = piege a lumiere
    return g

def reseau_dummy():
    return cq.Workplane("XY").box(25.4, 6, 25.4, centered=(True, False, False)).translate((0, 0, 17.3))

def plaque_capteur():
    """Plaque exterieure : recoit le PCB driver TCD1304, reglee par 3 vis M3 + ressorts (focus, tip, tilt)."""
    p = cq.Workplane("XY").box(4, 70, 40, centered=(False, True, True)).translate((0, 0, H))
    p = p.cut(cq.Workplane("XY").box(10, 34, 6).translate((0, 0, H)))            # fenetre zone active 29,2 mm
    for y, z in [(-27, 0), (27, 11), (27, -11)]:
        p = p.cut(cq.Workplane("YZ").circle(1.7).extrude(10).translate((-1, y, H + z)))
    for y in (-30, 30):                                                             # 4 trous PCB (a adapter)
        for z in (-15, 15):
            p = p.cut(cq.Workplane("YZ").circle(1.25).extrude(10).translate((-1, y, H + z)))
    p = p.cut(cq.Workplane("XY").box(2, 44, 12).translate((4, 0, H)))               # logement boitier CERDIP
    return p.translate((CAM_WALL_OUT, 0, 0))

def masque_capteur():
    m = cq.Workplane("XY").box(1.2, 40, 12).translate((0, 0, H))
    m = m.cut(cq.Workplane("XY").box(4, 33.0, 3.5).translate((0, 0, H)))
    return m.translate((CAM_WALL_OUT - WALL - 7.0 - 0.6, 0, 0))

def capteur_dummy():
    return (cq.Workplane("XY").box(3.5, 41.6, 10.2, centered=(False, True, True))
            .translate((CAM_WALL_OUT + 4 - 0.5, 0, H)))

# ------------------------------------------------------------------ export
if __name__ == "__main__":
    os.makedirs("export", exist_ok=True)
    B = base()
    parts = {
        "01_boitier": B,
        "02_couvercle": couvercle(),
        "03_trappe_reseau": trappe(),
        "04_tete_fente": arm(to_coll_arm(tete_local()), a1),
        "05_cassette_fente": arm(to_coll_arm(cassette_fente()), a1),
        "06_tiroir_filtre": arm(to_coll_arm(tiroir_filtre()), a1),
        "07_tube_collimateur": arm(tube_lentille().translate((D_COLL, 0, 0)), a1),
        "08_tube_camera": arm(tube_lentille().translate((D_CAM, 0, 0)), a2),
        "09_bride_coll": arm(bride_tube().translate((D_COLL, 0, 0)), a1),
        "10_bride_cam": arm(bride_tube().translate((D_CAM, 0, 0)), a2),
        "11_plateau_reseau": plateau_reseau().rotate((0, 0, 0), (0, 0, 1), -6),
        "12_cassette_reseau": cassette_reseau().rotate((0, 0, 0), (0, 0, 1), -90-6),
        "13_plaque_capteur": arm(plaque_capteur(), a2),
        "14_masque_capteur": arm(masque_capteur(), a2),
        "15_capuchon_source": capuchon_source(),
        "16_porte_relais": porte_relais(),
        "17_bague_lentille": bague_lentille(),
    }
    dummies = {"reseau": reseau_dummy().rotate((0, 0, 0), (0, 0, 1), -90-6),
               "capteur": arm(capteur_dummy(), a2)}
    asm = cq.Assembly()
    for k, v in parts.items():
        if k in ("15_capuchon_source", "16_porte_relais", "17_bague_lentille"):
            pass
        else:
            asm.add(v, name=k)
        cq.exporters.export(v, f"export/{k}.stl", tolerance=0.05, angularTolerance=0.2)
        print("ok", k)
    for k, v in dummies.items():
        asm.add(v, name="dummy_" + k)
        cq.exporters.export(v, f"export/dummy_{k}.stl")
    asm.save("export/spectro_assemblage.step")
    bb = B.val().BoundingBox()
    print(f"Boitier : {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm")
