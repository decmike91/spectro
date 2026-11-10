"""
Spectroscope astro TCD1304DG - VERSION 2 (compacte, repliee par un miroir)
Modele parametrique CadQuery.

Repere monde : fente a l'origine, axe du telescope = +X (sens de la lumiere), Z vers le haut,
plancher interieur a z=0, axe optique a z=H.
Chemin : fente -> collimateur (sur l'axe) -> reseau (G) -> objectif camera (bras a 120 deg)
         -> miroir plan de renvoi -> capteur TCD1304 sur une facette de la face avant.

Reglages :
  * focus collimateur : chariot + vis M3 (bouton face arriere), ressort de rappel
  * focus objectif    : chariot + vis M3 (bouton face laterale), ressort de rappel
  * reseau            : rotation lambda (levier + vis M3 face arriere)
                        tilt (charniere horizontale + vis M3 tirante + ressort)
                        orientation des traits / roll (disque porte-reseau tournant + vis M3 + ressort)
  * miroir            : 3 vis M3 + ressorts depuis l'exterieur (tip / tilt / piston)
  * capteur           : 3 vis M3 + ressorts depuis l'exterieur (focus fin / tip / tilt)
Lancer : python3 spectro_v2.py  -> export_v2/*.stl + spectro_v2_assemblage.step
"""
import math, os
import cadquery as cq

# ------------------------------------------------------------------ parametres
H        = 31.0      # axe optique au-dessus du plancher
H_INT    = 62.0      # hauteur interieure
WALL, FLOOR = 3.0, 3.0
CLR      = 0.25      # jeu FDM
INS_M3   = 4.0       # trou insert laiton M3
F_COLL, F_CAM = 75.0, 100.0
SLIT_D   = 130.0     # fente -> reseau (collimateur a 75 de la fente, 55 du reseau)
GX       = SLIT_D    # position du reseau sur l'axe
D_COLL   = 55.0      # reseau -> collimateur
D_CAM    = 34.0      # reseau -> objectif camera
A_CAM    = 120.0     # direction du bras camera vu du reseau (deg) -> angle inclus 60 deg
D_MIR    = 76.0      # reseau -> miroir (le long du bras camera)
A_OUT    = 180.0     # direction apres le miroir (vers la face avant)
SENS_D   = D_CAM + F_CAM      # 134 : chemin reseau -> capteur
HEAD_BACK = 10.0     # face d'appui de la tete de fente a x = 10
X_FRONT  = HEAD_BACK # face exterieure avant
X_BACK_IN = 163.0    # face interieure arriere
Y_MIN_IN = -36.0
LENS_OD, LENS_D, TUBE_L = 34.0, 25.4, 16.0
SLED_L   = 20.0
TRAVEL   = 5.0       # course de focus +/- (mm)
SLIT_TILT = 30.0
NOSE_D   = 31.75
PHI_NOM  = 6.0       # rotation reseau pour l'assemblage (300 t/mm)
SCREW_Z  = 5.0       # hauteur des vis de focus (sous les faisceaux et sous le plateau)

G = (GX, 0.0)
rad = math.radians
def ang(a, d): return (d*math.cos(rad(a)), d*math.sin(rad(a)))
def add(p, q, k=1.0): return (p[0]+k*q[0], p[1]+k*q[1])
U_CAM = ang(A_CAM, 1); N_CAM = ang(A_CAM+90, 1)      # +Y du repere bras camera
M_PT  = add(G, U_CAM, D_MIR)                          # point de reflexion du miroir
U_OUT = ang(A_OUT, 1)
S_PT  = add(M_PT, U_OUT, SENS_D - D_MIR)              # puce du capteur
MIR_N = math.degrees(math.atan2(-U_CAM[1]+U_OUT[1], -U_CAM[0]+U_OUT[0]))  # normale face miroir
MIR_BACK = MIR_N + 180                                 # dos du miroir

def place(shape, origin, a_deg, z=0.0):
    return shape.rotate((0, 0, 0), (0, 0, 1), a_deg).translate((origin[0], origin[1], z))

def W(): return cq.Workplane("XY")
def cyl_x(r, l, x0=0, y=0, z=0):       # cylindre le long de +X
    return cq.Workplane("YZ").circle(r).extrude(l).translate((x0, y, z))
def cyl_y(r, l, y0=0, x=0, z=0):       # cylindre le long de +Y
    return W().add(cq.Solid.makeCylinder(r, l, cq.Vector(x, y0, z), cq.Vector(0, 1, 0)))

# ------------------------------------------------------------------ contour du boitier
O_SENS = add(S_PT, U_OUT, -3.0)         # face ext. de la facette capteur (puce 3 mm au-dela)
I_SENS = add(O_SENS, U_OUT, -WALL)      # face int.
T_SENS = ang(A_OUT - 90, 1)             # le long de la facette
FAC_HL = 32.0
C_PT = add(I_SENS, T_SENS, FAC_HL)      # bas de facette (cote axe)
D_PT = add(I_SENS, T_SENS, -FAC_HL)     # haut de facette
if C_PT[1] > D_PT[1]: C_PT, D_PT = D_PT, C_PT
IN_PTS = [(X_FRONT + WALL, Y_MIN_IN), (X_BACK_IN, Y_MIN_IN), (X_BACK_IN, 36.0),
          (132.0, 78.0), (84.0, 100.0), D_PT, C_PT, (X_FRONT + WALL, C_PT[1] - 2)]

def outline(off):
    return W().polyline(IN_PTS).close().offset2D(off, "arc")

def shell_solid():
    return outline(WALL).extrude(H_INT + FLOOR).translate((0, 0, -FLOOR))

# ------------------------------------------------------------------ chariots de focus
def rails(L, x0):
    """Clavette de guidage centrale (le chariot a une rainure de 10 mm), repere bras"""
    return W().box(L, 10 - 2*CLR, 5, centered=(False, True, False)).translate((x0, 0, 0))

W_OUT, W_IN = 22.0, 18.5
def chariot(lug_y=None, outer=+1, insert_face=-1):
    """Chariot porte-tube (repere bras, centre a X=0). lug_y : position laterale de la vis de focus.
    insert_face : -1 = l'insert de la vis est sur la face X- ; +1 = sur la face X+ (patte)."""
    y0, y1 = sorted((outer*W_OUT, -outer*W_IN))
    s = W().box(SLED_L, y1 - y0, H, centered=(True, False, False)).translate((0, y0, 0))
    yj = -outer*W_IN if outer < 0 else -W_IN      # joue sur le cote interieur, epaisseur 2.5 vers l'axe
    yj = (W_IN - 2.5) if outer < 0 else (-W_IN)
    s = s.union(W().box(SLED_L, 2.5, 10, centered=(True, False, False)).translate((0, yj, H)))
    s = s.cut(cyl_x(LENS_OD/2 + CLR, 40, -20, 0, H))
    s = s.cut(W().circle(INS_M3/2).extrude(8).translate((0, outer*19.5, H - 8)))
    s = s.cut(W().box(SLED_L + 2, 10, 6).translate((0, 0, 3)))        # rainure de guidage
    if lug_y is not None:
        if abs(lug_y) > 20:   # patte deportee
            ya, yb = sorted((lug_y + (4 if lug_y > 0 else -4), 16 if lug_y > 0 else -16))
            s = s.union(W().box(8, yb - ya, 10, centered=(False, False, False))
                        .translate((insert_face*SLED_L/2 - (8 if insert_face > 0 else 0), ya, 0)))
        s = s.cut(cyl_x(INS_M3/2, 8, insert_face*(SLED_L/2) - (8 if insert_face > 0 else 0), lug_y, SCREW_Z))
    return s

def butee(lug_y, x0):
    """Butee de ressort fixe au plancher (repere bras)"""
    b = W().box(6, 10, 10, centered=(False, True, False)).translate((x0, lug_y, 0))
    return b.cut(cyl_x(1.8, 10, x0 - 1, lug_y, SCREW_Z))

def tube_lentille():
    t = cq.Workplane("YZ").circle(LENS_OD/2).circle(LENS_D/2 + 0.15).extrude(TUBE_L)
    t = t.union(cq.Workplane("YZ").circle(LENS_D/2 + 0.2).circle(11).extrude(1.5))
    return t.translate((-TUBE_L/2, 0, H))

def bride(outer=+1):
    """Bride : vissee cote exterieur, crochet pose sur la joue interieure"""
    y0, y1 = sorted((outer*W_OUT, -outer*(W_IN + 0.5)))
    b = W().box(8, y1 - y0, LENS_OD/2 + 4, centered=(True, False, False)).translate((0, y0, H))
    b = b.cut(cyl_x(LENS_OD/2 + CLR, 20, -10, 0, H))
    yj = (W_IN - 2.5 - CLR) if outer < 0 else (-W_IN - 0.5)
    ji = W().box(10, 3.5, 10.3, centered=(True, False, False)).translate((0, yj, H))
    b = b.cut(ji)
    return b.cut(W().circle(1.7).extrude(30).translate((0, outer*19.5, H)))

# repere collimateur : origine G, X vers la fente (180 deg)
COLL_LUG_Y = 17.5     # Y du repere coll (= -y monde)
def coll(shape): return place(shape, G, 180)
# repere camera : origine G, X le long du bras camera
CAM_LUG_Y = -26.0
def cam(shape): return place(shape, G, A_CAM)

# ------------------------------------------------------------------ monture du reseau (repere local L)
# L : origine sur l'axe de pivot, face gravee dans le plan y=0, normale = -y, traits verticaux (z)
DISC_D, DISC_T = 38.0, 8.0
Z_PLAT = 8.0                        # dessus du pied de pivot
def plateau_L():
    p = W().circle(18).extrude(3).translate((0, 0, Z_PLAT))                     # disque z 8..11
    lev = (W().box(8, 30, 4, centered=(True, False, False)).translate((0, 0, Z_PLAT))
           .rotate((0, 0, 0), (0, 0, 1), 45 - 90))                               # levier a 45 deg (local)
    p = p.union(lev)
    tip = ang(45, 27)
    p = p.cut(W().circle(1.2).extrude(10).translate((tip[0], tip[1], Z_PLAT - 1)))  # accroche ressort
    # equerre (berceau d'inclinaison) solidaire
    p = p.union(W().box(48, 7.5, 2.5, centered=(True, False, False)).translate((0, 11.5, Z_PLAT + 3)))
    p = p.union(W().box(44, 4, 44, centered=(True, False, False)).translate((0, 14, Z_PLAT + 3)))
    for sx in (-1, 1):   # oreilles de charniere
        p = p.union(W().box(3.5, 8, 6, centered=(True, False, False)).translate((sx*26.25, 4, Z_PLAT + 3)))
        p = p.union(W().box(3.4, 3, 2.5, centered=(True, False, False)).translate((sx*26.3, 9.5, Z_PLAT + 3)))
    p = p.cut(cyl_x(1.6, 60, -30, 7, Z_PLAT + 6.5))                            # axe de charniere O3
    p = p.cut(W().circle(2.2).extrude(20).translate((0, 0, Z_PLAT - 2)))        # pivot M4
    # vis tirante du tilt : traverse l'equerre en haut
    p = p.cut(cyl_y(1.7, 10, 12, 0, H + 18))
    p = p.cut(cyl_y(3.0, 2, 13.99, 0, H + 18))                                  # logement ressort
    return p

def cadre_L():
    """Cadre basculant : siege du disque porte-reseau, charniere en bas, vis tirante en haut."""
    f = W().box(48, 6, H + 22 - (Z_PLAT + 5.5), centered=(True, False, False)).translate((0, 5, Z_PLAT + 5.5))
    f = f.cut(cyl_y(DISC_D/2 + 0.3, 3.05, 4.99, 0, H))                                        # siege O38.6 prof. 3
    f = f.cut(cyl_y(12, 10, 4, 0, H))                                                       # allegement
    for sx in (-22.5, 22.5):                                                                # charnieres
        f = f.union(W().box(4, 6, 6, centered=(True, False, False)).translate((sx, 5, Z_PLAT + 3.5)))
    f = f.cut(cyl_x(1.6, 60, -30, 7, Z_PLAT + 6.5))
    for sx in (-9, 9):                                                                      # aimants 6x2
        f = f.cut(cyl_y(3.1, 2.2, 7.9, sx, H - 9))
    f = f.cut(cyl_y(INS_M3/2, 6, 5.5, 0, H + 18))                                           # insert vis tilt
    # bossage roll (cote +x) : insert vertical en haut, logement ressort en bas
    f = f.union(W().box(8, 5, 26, centered=(True, False, False)).translate((25, 0.5, H - 13)))
    f = f.cut(W().box(9, 6, 8).translate((25, 3, H)))                                       # passage patte
    f = f.cut(W().circle(INS_M3/2).extrude(9).translate((25.5, 3, H + 4)))
    f = f.cut(W().circle(2.6).extrude(5).translate((25.5, 3, H - 13 + 1)))
    return f

def disque_reseau_L():
    """Porte-reseau interchangeable (1 par reseau). Face du reseau affleurante a y=0."""
    d = cyl_y(DISC_D/2, DISC_T, 0, 0, H)
    d = d.cut(W().box(25.4 + 2*CLR, 6.3, 25.4 + 2*CLR, centered=(True, False, True)).translate((0, -0.01, H)))
    d = d.union(W().box(10, 4, 4, centered=(False, False, True)).translate((DISC_D/2 - 1, 0.3, H)))  # patte roll
    for sx in (-9, 9):
        d = d.cut(cyl_y(3.1, 2.2, DISC_T - 2.2 + 0.01, sx, H - 9))
    d = d.cut(W().box(3, 4, 2).translate((0, 4, H + DISC_D/2 - 0.5)))                         # repere
    return d

def reseau_dummy_L():
    return W().box(25.4, 6, 25.4, centered=(True, False, True)).translate((0, 0, H))

def L_to_world(shape, phi):
    return place(shape, G, 240 - phi)

def pied_pivot():
    p = W().circle(8).extrude(Z_PLAT).translate((G[0], G[1], 0))
    return p

# ------------------------------------------------------------------ miroir (repere Mi : X = dos du miroir)
MIR_W, MIR_H, MIR_T = 55.0, 20.0, 2.0   # incidence 60 deg : miroir allonge
MIR_PW = 59.0
MIR_HOLES = [(-22, -6), (22, -6), (0, 8)]
def miroir_plaque_Mi():
    p = W().box(5, MIR_PW, 24, centered=(False, True, True)).translate((MIR_T, 0, H))
    p = p.cut(W().box(0.6, MIR_W + 0.4, MIR_H + 0.4, centered=(False, True, True)).translate((MIR_T - 0.01, 0, H)))
    for y, z in MIR_HOLES:
        p = p.cut(cyl_x(INS_M3/2, 5, MIR_T + 1, y, H + z))
    return p
def miroir_dummy_Mi():
    return W().box(MIR_T, MIR_W, MIR_H, centered=(False, True, True)).translate((0, 0, H))
def mir(shape): return place(shape, M_PT, MIR_BACK)

# ------------------------------------------------------------------ capteur (repere Se : X = sens de la lumiere sortante)
SENS_HOLES = [(-23, 0), (23, 11), (23, -11)]
def sens(shape): return place(shape, O_SENS, A_OUT)
def plaque_capteur_Se():
    p = W().box(4, 58, 36, centered=(False, True, True)).translate((0, 0, H))
    p = p.cut(W().box(10, 34, 6).translate((0, 0, H)))
    for y, z in SENS_HOLES:
        p = p.cut(cyl_x(1.7, 10, -1, y, H + z))
    for y in (-26, 26):
        for z in (-14, 14):
            p = p.cut(cyl_x(1.25, 10, -1, y, H + z))
    p = p.cut(W().box(2, 44, 12).translate((4, 0, H)))
    return p
def masque_Se():
    m = W().box(1.2, 40, 12).translate((-WALL - 7 - 0.6, 0, H))
    return m.cut(W().box(4, 33, 3.5).translate((-WALL - 7 - 0.6, 0, H)))
def capteur_dummy_Se():
    return W().box(3.5, 41.6, 10.2, centered=(False, True, True)).translate((2.0, 0, H))

# ------------------------------------------------------------------ BOITIER
def boitier():
    b = shell_solid().cut(outline(0).extrude(H_INT + 1))
    # pied de pivot (vis M4 par dessous)
    b = b.union(pied_pivot())
    b = b.cut(W().circle(2.2).extrude(30).translate((G[0], G[1], -5)))
    b = b.cut(W().circle(4.2).extrude(3.2).translate((G[0], G[1], -FLOOR - 0.01)))
    # renfort face avant (tete de fente) : passage lumiere + 4 inserts
    pad = W().box(7, 46, H_INT - 4.5, centered=(False, True, False)).translate((X_FRONT + WALL, 0, 0))
    b = b.union(pad)
    b = b.cut(cyl_x(11, 30, 0, 0, H))
    for y, z in [(-18, -22), (18, -22), (-18, 22), (18, 22)]:
        b = b.cut(cyl_x(INS_M3/2, 8, X_FRONT - 0.01, y, H + z))
    # facette capteur : renfort + fenetre + 3 inserts
    fpad = W().box(7, 2*FAC_HL, H_INT - 4.5, centered=(False, True, False)).translate((-WALL - 7, 0, 0))
    b = b.union(sens(fpad))
    fcut = W().box(30, 36, 14).translate((-10, 0, H))
    for y, z in SENS_HOLES:
        fcut = fcut.union(cyl_x(INS_M3/2, 8, -8, y, H + z))
    b = b.cut(sens(fcut))
    # rails + butees des chariots
    b = b.union(coll(rails(SLED_L + 2*TRAVEL + 6, D_COLL - SLED_L/2 - TRAVEL - 3)))
    b = b.union(cam(rails(SLED_L + 2*TRAVEL + 6, D_CAM - SLED_L/2 - TRAVEL - 3)))
    b = b.union(coll(butee(COLL_LUG_Y, D_COLL - SLED_L/2 - TRAVEL - 14)))
    # passages des vis de focus a travers les parois (+ bossages exterieurs perpendiculaires)
    #   collimateur : vis le long de +X monde, sortie face arriere
    b = b.union(W().box(10, 12, 10).translate((X_BACK_IN + WALL + 3, -COLL_LUG_Y, SCREW_Z)))
    late_cuts = [cyl_x(1.7, 60, X_BACK_IN - 20, -COLL_LUG_Y, SCREW_Z)]
    #   camera : vis le long du bras camera, sortie paroi laterale
    xe = cam_back_X()
    cam_boss = W().box(14, 12, 10).translate((xe - 4, CAM_LUG_Y, SCREW_Z))
    b = b.union(cam(cam_boss))
    late_cuts.append(cam(cyl_x(1.7, 40, xe - 20, CAM_LUG_Y, SCREW_Z)))
    b = b.union(cam(butee(CAM_LUG_Y, D_CAM - SLED_L/2 - TRAVEL - 12)
                    .intersect(W().box(400, 400, 7, centered=(True, True, False)))))
    #   lambda : vis le long de -X monde, face arriere, sur le levier
    b = b.union(W().box(10, 12, 12).translate((X_BACK_IN + WALL + 3, -29, Z_PLAT + 2)))
    late_cuts.append(cyl_x(INS_M3/2, 20, X_BACK_IN - 4, -29, Z_PLAT + 1.5))
    b = b.union(W().circle(2.5).extrude(16).translate((158, -24.5, 0)))     # poteau ressort lambda
    # bossage du miroir : 3 vis depuis l'exterieur
    mb = W().box(30, 62, 30, centered=(False, True, True)).translate((13, 0, H))
    for y, z in MIR_HOLES:
        mb = mb.cut(cyl_x(1.7, 40, 0, y, H + z)).cut(cyl_x(3.0, 3, 13, y, H + z))
    b = b.union(mir(mb).intersect(shell_solid()))
    for y, z in MIR_HOLES:
        b = b.cut(mir(cyl_x(1.7, 40, 0, y, H + z))).cut(mir(cyl_x(3.0, 3, 13, y, H + z)))
        b = b.cut(mir(cyl_x(3.6, 30, 25, y, H + z)))                       # lamages exterieurs
    for x, y in BAT_SCREWS:                                           # fixation du compartiment batterie
        late_cuts.append(W().circle(1.7).extrude(10).translate((x, y, -FLOOR - 1)))
    for c in late_cuts: b = b.cut(c)
    # colonnettes de couvercle
    global LID_PTS
    LID_PTS = []
    cx = sum(p[0] for p in IN_PTS)/len(IN_PTS); cy = sum(p[1] for p in IN_PTS)/len(IN_PTS)
    for i, (x, y) in enumerate(IN_PTS):
        if i in (1, 2): continue      # coins arriere : passage des vis lambda / focus
        d = math.hypot(cx - x, cy - y); px, py = x + (cx - x)/d*5, y + (cy - y)/d*5
        LID_PTS.append((px, py))
        b = b.union(W().circle(4.5).extrude(H_INT).translate((px, py, 0)))
        b = b.cut(W().circle(INS_M3/2).extrude(8).translate((px, py, H_INT - 8)))
    return b

HATCH = (100, 158, -30, 24)
def couvercle():
    lid = outline(WALL).extrude(3).translate((0, 0, H_INT))
    x0, x1, y0, y1 = HATCH
    lid = lid.cut(W().box(x1 - x0, y1 - y0, 10).translate(((x0 + x1)/2, (y0 + y1)/2, H_INT)))
    for (x, y) in LID_PTS:
        lid = lid.cut(W().circle(1.7).extrude(10).translate((x, y, H_INT - 1)))
    for x in (x0 - 5,):
        for y in (y0 + 6, y1 - 6):
            lid = lid.cut(W().circle(3.1).extrude(2.2).translate((x, y, H_INT + 0.8)))
    lip = outline(-0.4).extrude(3).translate((0, 0, H_INT - 3)).cut(outline(-2.4).extrude(3).translate((0, 0, H_INT - 3)))
    for (x, y) in LID_PTS:
        lip = lip.cut(W().circle(5.6).extrude(6).translate((x, y, H_INT - 5)))
    return lid.union(lip)

def trappe():
    x0, x1, y0, y1 = HATCH
    t = W().box(x1 - x0 + 12, y1 - y0, 2.5).translate(((x0 + x1)/2 - 6, (y0 + y1)/2, H_INT + 3 + 1.25))
    t = t.union(W().box(x1 - x0 - 2*CLR, y1 - y0 - 2*CLR, 3).translate(((x0 + x1)/2, (y0 + y1)/2, H_INT + 1.5)))
    t = t.cut(W().box(x1 - x0 - 6, y1 - y0 - 6, 3).translate(((x0 + x1)/2, (y0 + y1)/2, H_INT + 1.5)))
    for y in (y0 + 6, y1 - 6):
        t = t.cut(W().circle(3.1).extrude(2.2).translate((x0 - 5, y, H_INT + 3)))
    return t

# ------------------------------------------------------------------ TETE DE FENTE (identique v1, bride 52 mm, guidage cote -y)
def tete_local():
    HB = HEAD_BACK
    body = W().box(50, 50, 24 + HB).translate((0, 0, (HB - 24)/2))
    body = body.union(W().box(52, 56, 6).translate((0, 0, HB - 3)))
    body = body.union(W().circle(NOSE_D/2 - 0.1).extrude(32).translate((0, 0, -56)))
    t = rad(2*SLIT_TILT)
    pdir = cq.Vector(-math.sin(t), 0, -math.cos(t))
    port = cq.Solid.makeCylinder(19, 60, cq.Vector(0, 0, 0) + pdir*18, pdir)
    port = W().add(port).intersect(W().box(300, 300, 150).translate((0, 0, -75)))
    body = body.union(port)
    body = body.cut(W().circle(13.5).extrude(52).translate((0, 0, -57)))
    body = body.cut(W().circle(6).extrude(HB + 1))
    body = body.cut(W().add(cq.Solid.makeCylinder(8, 30, cq.Vector(0, 0, 0), pdir)))
    body = body.cut(W().add(cq.Solid.makeCylinder(15.9 + CLR, 60, cq.Vector(0, 0, 0) + pdir*24, pdir)))
    body = body.cut(W().box(34 + 2*CLR, 45, 8 + 2*CLR).translate((0, 5.5, -17)))
    slot = W().box(24 + 2*CLR, 46, 4 + 2*CLR).translate((0, 6, 0))
    body = body.cut(slot.rotate((0, 0, 0), (0, 1, 0), SLIT_TILT))
    for x, y in [(-18, -22), (18, -22), (-18, 22), (18, 22)]:
        body = body.cut(W().circle(1.7).extrude(10).translate((x, y, HB - 8)))
    body = body.cut(W().add(cq.Solid.makeCylinder(INS_M3/2, 30, cq.Vector(0, 0, 0) + pdir*50, cq.Vector(0, 1, 0))))
    return body

def cassette_fente():
    c = W().box(24, 44.5, 4).translate((0, 5.75, 0))
    c = c.union(W().box(24, 4, 6).translate((0, 30, 0)))
    c = c.cut(W().box(18, 20, 2).translate((0, 0, -1)))
    c = c.cut(W().box(4, 14, 10))
    c = c.cut(W().box(10, 2, 10).translate((0, 31.5, 0)))
    return c.rotate((0, 0, 0), (0, 1, 0), SLIT_TILT)

def tiroir_filtre():
    d = W().box(34, 44, 8).translate((0, 6.5, -17))
    d = d.union(W().box(44, 4, 10).translate((0, 30.5, -17)))
    d = d.cut(W().circle(15.4 + CLR).extrude(5.5).translate((0, 0, -21.01)))
    d = d.cut(W().circle(13).extrude(10).translate((0, 0, -22)))
    return d

def head_world(shape_local):
    """local tete (lumiere +Z, Y vertical) -> monde (lumiere +X)"""
    return (shape_local.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), -90)
            .rotate((0, 0, 0), (0, 0, 1), 180).translate((0, 0, H)))

def porte_relais():
    r = W().circle(15.9 - CLR).circle(6.0).extrude(12)
    return r.cut(W().circle(6.35 + 0.15).extrude(3.5).translate((0, 0, 8.5)))

def capuchon_source():
    c = W().circle(NOSE_D/2 + 3).extrude(40)
    c = c.cut(W().circle(NOSE_D/2 + 0.3).extrude(26).translate((0, 0, 14)))
    c = c.cut(W().circle(12.6).extrude(2).translate((0, 0, 12)))
    return c.cut(W().circle(5.2).extrude(13))

def bague_lentille():
    return cq.Workplane("YZ").circle(LENS_D/2 + 0.1).circle(11).extrude(3)

def bouton():
    """Bouton moletable pour vis M3 (tete de vis noyee + ecrou)"""
    k = W().polygon(12, 16).extrude(8)
    k = k.cut(W().polygon(6, 6.4).extrude(3.2).translate((0, 0, 8 - 3.2)))
    return k.cut(W().circle(1.7).extrude(10))

# ------------------------------------------------------------------ vis (pour verification)
def vis_coll(off=0):
    x0 = GX - (D_COLL - SLED_L/2) + off
    return cyl_x(1.5, X_BACK_IN + WALL + 8 - x0 + 2, x0 - 2, -COLL_LUG_Y, SCREW_Z)
def vis_cam(off=0):
    x1 = D_CAM - SLED_L/2 + off
    x0 = cam_back_X() - 9
    return cam(cyl_x(1.5, x1 - x0, x0, CAM_LUG_Y, SCREW_Z))
def vis_lambda(phi=PHI_NOM):
    th = rad(285 - phi)
    r = -29/math.sin(th); xc = GX + r*math.cos(th) + 4/abs(math.sin(th)) + 0.3
    return cyl_x(1.5, X_BACK_IN + WALL + 8 - xc, xc, -29, Z_PLAT + 1.5)

def in_poly(p, poly):
    x, y = p; c = False
    for i in range(len(poly)):
        x1, y1 = poly[i]; x2, y2 = poly[(i+1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2-x1)*(y-y1)/(y2-y1) + x1: c = not c
    return c
def cam_back_X():
    """X (repere camera) ou la vis de focus camera traverse la face arriere"""
    X = D_CAM - SLED_L/2
    while in_poly(add(add(G, U_CAM, X), N_CAM, CAM_LUG_Y), IN_PTS): X -= 0.5
    return X

# ------------------------------------------------------------------ COMPARTIMENT ELECTRONIQUE (sous le plancher)
# Baie A (y < cloison) : 2 x 18650 en PARALLELE (1S2P, ~7 Ah) dans un support 2 x 18650 (~77x41x20),
#   tenu par 2 sangles velcro / colliers passant dans les montants ; carte BMS 1S 3 A (DW01A+FS8205A) ;
#   module PENGLIN chargeur/boost 5 V 2 A (carte 25x20, USB-C dessus, USB-A dessous) glisse dans
#   un berceau, connecteurs contre la face arriere : USB-C = charge, USB-A = sortie 5 V auxiliaire
#   (resistance chauffante anti-buee). Interrupteur a bascule sur le cote -y (coupe le 5 V interne).
# Baie B : carte d'interface (plaque a pastilles 50x30) portant la RP2350-Zero sur barrettes femelles,
#   le MOSFET du ventilateur et le depart du cable vers la carte capteur ; Raspberry Pi Zero (65x30) ;
#   ventilateur 25x25x10 5 V en extraction sur la face arriere, entrees d'air sur la face avant.
# Tout est suspendu au plafond du compartiment ; le fond est un couvercle coulissant.
BAT_X0, BAT_X1, BAT_Y0, BAT_Y1 = 24.0, 166.0, -36.0, 60.0
BAT_H, BAT_TOP = 31.0, 2.5
Y_CLOISON = 16.0
BAT_SCREWS = [(30, -30), (161, -32), (30, 12), (161, 12), (60, 55), (130, 55)]
HOLDER = dict(x=35.5, y=-29.5, w=77.0, d=41.0, h=20.0)        # support 2 x 18650
STRAPS = (52.0, 96.0)                                          # x des sangles de maintien
BMS = dict(x=114.0, y=-12.0, w=20.0, d=8.0, h=3.5)             # carte BMS 1S (collee)
PEN = dict(x=137.0, y=-18.0, w=25.0, d=20.0, zb=-6.0)          # module PENGLIN (zb : dessus carte / plafond)
IFB = dict(x=30, y=20, w=50, d=30, holes=[(3, 3), (47, 3), (3, 27), (47, 27)], drill=1.0)    # M2, plaque a pastilles
RPZ = dict(x=33.0, y=26.0, w=23.5, d=18.0)                     # RP2350-Zero (USB-C vers +x)
PIZ  = dict(x=86, y=20, w=65, d=30, holes=[(3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)], drill=1.1)  # M2.5
FAN  = dict(x=163 - 10, yc=36.5, s=25.0, hole=20.0)
IFB_STANDOFF = 4.0
SW_X = 115.0                                                   # interrupteur a bascule (decoupe 19,5 x 13,5)
PEN_RAIL = 5.3                                                 # largeur des rails du berceau PENGLIN
def pen_screws():
    return [(PEN["x"] + 5, PEN["y"] - PEN_RAIL/2 - 0.15), (PEN["x"] + 5, PEN["y"] + PEN["d"] + PEN_RAIL/2 + 0.15)]
def _ztop(): return -FLOOR - BAT_TOP
def _pen_z():
    """(z dessus carte, z dessous carte) du module PENGLIN"""
    zt = _ztop(); top = zt + PEN["zb"]
    return top, top - 1.6
def compartiment_batterie():
    w, d = BAT_X1 - BAT_X0, BAT_Y1 - BAT_Y0
    cx, cy = (BAT_X0 + BAT_X1)/2, (BAT_Y0 + BAT_Y1)/2
    z0 = -FLOOR - BAT_H
    c = W().box(w, d, BAT_H, centered=(True, True, False)).translate((cx, cy, z0))
    c = c.cut(W().box(w - 6, d - 6, BAT_H - BAT_TOP, centered=(True, True, False)).translate((cx, cy, z0)))
    # rainures du couvercle coulissant (sort par l'arriere)
    c = c.cut(W().box(w - 3, d - 3.4, 1.8, centered=(True, True, False)).translate((cx + 1.5, cy, z0 + 0.6)))
    c = c.cut(W().box(w - 3, d - 6, 2.5, centered=(True, True, False)).translate((cx + 1.5, cy, z0)))
    zt = _ztop()
    # cloison baie accus / baie electronique, avec passage de fils
    c = c.union(W().box(w - 6, 2, BAT_H - BAT_TOP - 3, centered=(True, False, False)).translate((cx, Y_CLOISON, z0 + 3)))
    c = c.cut(W().box(12, 4, 6).translate((112, Y_CLOISON + 1, zt - 3)))
    # bossages des inserts de fixation au plancher
    for x, y in BAT_SCREWS:
        c = c.union(W().circle(4.5).extrude(10).translate((x, y, zt - 10 + 0.01)))
        c = c.cut(W().circle(INS_M3/2).extrude(8).translate((x, y, -FLOOR - 8)))
    # --- baie A : montants des sangles du support d'accus (fente 12 x 2,5 sous le support)
    H = HOLDER
    zh = zt - H["h"]                                   # dessous du support
    for xs in STRAPS:
        for y0, y1 in ((BAT_Y0 + 3, H["y"] - 0.5), (H["y"] + H["d"] + 0.5, Y_CLOISON)):
            post = W().box(16, y1 - y0, H["h"] + 4.5, centered=(True, False, False)).translate((xs, y0, zh - 4.5))
            post = post.cut(W().box(12, y1 - y0 + 2, 2.5, centered=(True, False, False)).translate((xs, y0 - 1, zh - 3.2)))
            c = c.union(post)
    # --- baie A : berceau du module PENGLIN : deux rails (rebord de 0,8 mm sur la carte, guidage
    #     lateral), la bride 25 serree par 2 vis M2 plaque la carte contre les rebords et bute
    #     contre le corps de l'USB-A quand on enfiche une fiche (aucun recul possible).
    top, bot = _pen_z()
    for y_outer, y_ledge in (((PEN["y"] - PEN_RAIL, PEN["y"] - 0.3), (PEN["y"] - 0.3, PEN["y"] + 0.8)),
                             ((PEN["y"] + PEN["d"] + 0.3, PEN["y"] + PEN["d"] + PEN_RAIL), (PEN["y"] + PEN["d"] - 0.8, PEN["y"] + PEN["d"] + 0.3))):
        rail = W().box(PEN["w"] + 1, y_outer[1] - y_outer[0], zt - bot + 0.01, centered=False).translate((PEN["x"] - 1, y_outer[0], bot))
        rail = rail.union(W().box(PEN["w"] + 1, y_ledge[1] - y_ledge[0], zt - top + 0.01, centered=False).translate((PEN["x"] - 1, y_ledge[0], top)))
        c = c.union(rail)
    for x, y in pen_screws():
        c = c.cut(W().circle(0.8).extrude(6).translate((x, y, bot - 0.01)))          # M2 autotaraudeuse
    # fenetre USB-C (charge) + USB-A (sortie 5 V) dans la face arriere
    zc = top + 1.6                                     # axe USB-C (3,2 mm au-dessus de la carte)
    za = bot - 3.5                                     # axe USB-A (7 mm sous la carte)
    yc = PEN["y"] + PEN["d"]/2
    c = c.cut(W().box(10, 13.5, 7.5, centered=(False, True, True)).translate((BAT_X1 - 5, yc, zc)))
    c = c.cut(W().box(10, 16.5, 9.5, centered=(False, True, True)).translate((BAT_X1 - 5, yc, za)))
    # --- baie B : entretoises de la carte d'interface et du Pi Zero
    for B_, hs in ((IFB, IFB_STANDOFF), (PIZ, 4.0)):
        for hx, hy in B_["holes"]:
            c = c.union(W().circle(2.6).extrude(hs).translate((B_["x"] + hx, B_["y"] + hy, zt - hs + 0.01)))
            c = c.cut(W().circle(B_["drill"]).extrude(hs + 2).translate((B_["x"] + hx, B_["y"] + hy, zt - hs - 1)))
    # ventilateur : 4 vis + grille dans la face arriere (extraction)
    zf = zt - FAN["s"]/2 - 0.5
    for dy in (-1, 1):
        for dz in (-1, 1):
            c = c.cut(cyl_x(1.3, 8, BAT_X1 - 5, FAN["yc"] + dy*FAN["hole"]/2, zf + dz*FAN["hole"]/2))
    grille = cyl_x(11.5, 8, BAT_X1 - 5, FAN["yc"], zf)
    for a in (0, 90):
        grille = grille.cut(W().box(10, 24, 2).rotate((0, 0, 0), (1, 0, 0), a).translate((BAT_X1 - 1.5, FAN["yc"], zf)))
    c = c.cut(grille.cut(cyl_x(3, 8, BAT_X1 - 5, FAN["yc"], zf)))
    # entrees d'air (face avant, baie electronique) + sortie cable vers la carte capteur
    for i in range(4):
        c = c.cut(W().box(10, 26, 2.2).translate((BAT_X0, 32, zt - 6 - i*5)))
    c = c.cut(cyl_x(3.2, 10, BAT_X0 - 5, 52, zt - 8))
    # interrupteur a bascule (cote -y, baie A)
    c = c.cut(W().box(19.5, 10, 13.5).translate((SW_X, BAT_Y0 + 1.5, z0 + 15)))
    return c

def couvercle_batterie():
    w, d = BAT_X1 - BAT_X0, BAT_Y1 - BAT_Y0
    cx, cy = (BAT_X0 + BAT_X1)/2, (BAT_Y0 + BAT_Y1)/2
    z0 = -FLOOR - BAT_H
    t = W().box(w - 3 - CLR, d - 3.4 - 2*CLR, 1.8 - 2*CLR, centered=(True, True, False)).translate((cx + 1.5, cy, z0 + 0.6 + CLR))
    t = t.union(W().box(w - 3 - CLR, d - 6 - 2*CLR, 0.6 + CLR, centered=(True, True, False)).translate((cx + 1.5, cy, z0)))
    t = t.union(W().box(4, d - 10, 4, centered=(True, True, False)).translate((BAT_X1 - 2, cy, z0 - 4 + 0.6)))  # tirette
    for x in (40, 52, 64, 76):                     # entrees d'air sous la carte d'interface
        t = t.cut(W().box(2.2, 20, 10).translate((x, 37, z0)))
    return t

def bride_penglin():
    """Piece 25 : bride sous le module PENGLIN (2 vis M2 x 6). Son bord +x bute contre l'USB-A."""
    top, bot = _pen_z()
    x1 = PEN["x"] + PEN["w"] - 14.5
    b = W().box(x1 - PEN["x"] + 1, PEN["d"] + 2*PEN_RAIL, 2.0, centered=False).translate((PEN["x"] - 1, PEN["y"] - PEN_RAIL, bot - 2.0))
    for x, y in pen_screws():
        b = b.cut(W().circle(1.1).extrude(4).translate((x, y, bot - 3)))
    b = b.cut(W().box(x1 - PEN["x"] - 8, PEN["d"] - 6, 4, centered=False).translate((PEN["x"] + 9, PEN["y"] + 3, bot - 3)))  # allegement
    return b

def electronique_dummies():
    """Volumes des composants (verification des interferences et rendus)."""
    zt = _ztop(); H = HOLDER
    top, bot = _pen_z()
    zi = zt - IFB_STANDOFF                         # dessus de la carte d'interface
    d = {
        "accus": W().box(H["w"], H["d"], H["h"], centered=False).translate((H["x"], H["y"], zt - H["h"])),
        "bms": W().box(BMS["w"], BMS["d"], BMS["h"], centered=False).translate((BMS["x"], BMS["y"], zt - BMS["h"])),
        "penglin": W().box(PEN["w"], PEN["d"], 1.6, centered=False).translate((PEN["x"], PEN["y"], bot))
                   .union(W().box(7.5, 9.0, 3.2, centered=False).translate((PEN["x"] + PEN["w"] - 6.5, PEN["y"] + PEN["d"]/2 - 4.5, top)))
                   .union(W().box(14.0, 13.1, 7.0, centered=False).translate((PEN["x"] + PEN["w"] - 13.0, PEN["y"] + PEN["d"]/2 - 6.55, bot - 7.0)))
                   .union(W().box(6.0, 6.0, 3.0, centered=False).translate((PEN["x"] + 4, PEN["y"] + 3, top))),   # self 2R2
        "carte_interface": W().box(IFB["w"], IFB["d"], 1.6, centered=False).translate((IFB["x"], IFB["y"], zi - 1.6))
                   .union(W().box(23.0, 2.6, 8.5, centered=False).translate((RPZ["x"] + 0.25, RPZ["y"] - 0.2, zi - 1.6 - 8.5)))
                   .union(W().box(23.0, 2.6, 8.5, centered=False).translate((RPZ["x"] + 0.25, RPZ["y"] + RPZ["d"] - 2.4, zi - 1.6 - 8.5))),
        "rp2350_zero": W().box(RPZ["w"], RPZ["d"], 1.6 + 2.5, centered=False).translate((RPZ["x"], RPZ["y"], zi - 1.6 - 8.5 - 4.1))
                   .union(W().box(7.5, 9.0, 3.2, centered=False).translate((RPZ["x"] + RPZ["w"] - 6.5, RPZ["y"] + RPZ["d"]/2 - 4.5, zi - 1.6 - 8.5 - 4.1 - 3.2))),
        "fiche_usb_c": W().box(22.0, 12.0, 7.0, centered=False).translate((RPZ["x"] + RPZ["w"] + 0.5, RPZ["y"] + RPZ["d"]/2 - 6, zi - 1.6 - 8.5 - 4.1 - 3.2 - 1.9)),
        "pi_zero": W().box(PIZ["w"], PIZ["d"], 5, centered=False).translate((PIZ["x"], PIZ["y"], zt - 4 - 5)),
        "ventilateur": W().box(10, FAN["s"], FAN["s"], centered=(False, True, True)).translate((FAN["x"], FAN["yc"], zt - FAN["s"]/2 - 0.5)),
        "interrupteur": W().box(19.0, 16.0, 13.0, centered=False).translate((SW_X + 0.25, BAT_Y0 + 3, -FLOOR - BAT_H + 15.25)),
    }
    return d

def accus_dummy():
    r = None
    for v in electronique_dummies().values():
        r = v if r is None else r.union(v)
    return r

# ------------------------------------------------------------------ assemblage
def parts(phi=PHI_NOM, focus=0.0):
    B = boitier()
    P = {
        "01_boitier": B,
        "02_couvercle": couvercle(),
        "03_trappe": trappe(),
        "04_tete_fente": head_world(tete_local()),
        "05_cassette_fente": head_world(cassette_fente()),
        "06_tiroir_filtre": head_world(tiroir_filtre()),
        "07_chariot_coll": coll(chariot(COLL_LUG_Y, outer=+1, insert_face=-1).translate((D_COLL + focus, 0, 0))),
        "08_tube_coll": coll(tube_lentille().rotate((0, 0, 0), (0, 0, 1), 180).translate((D_COLL + focus, 0, 0))),
        "09_bride_coll": coll(bride(+1).translate((D_COLL + focus, 0, 0))),
        "10_chariot_cam": cam(chariot(CAM_LUG_Y, outer=-1, insert_face=-1).translate((D_CAM + focus, 0, 0))),
        "11_tube_cam": cam(tube_lentille().rotate((0, 0, 0), (0, 0, 1), 180).translate((D_CAM + focus, 0, 0))),
        "12_bride_cam": cam(bride(-1).translate((D_CAM + focus, 0, 0))),
        "13_plateau_equerre": L_to_world(plateau_L(), phi),
        "14_cadre_tilt": L_to_world(cadre_L(), phi),
        "15_disque_reseau": L_to_world(disque_reseau_L(), phi),
        "16_plaque_miroir": mir(miroir_plaque_Mi()),
        "17_plaque_capteur": sens(plaque_capteur_Se()),
        "18_masque_capteur": sens(masque_Se()),
        "23_compartiment_batterie": compartiment_batterie(),
        "24_couvercle_batterie": couvercle_batterie(),
        "25_bride_penglin": bride_penglin(),
    }
    extra = {"19_capuchon_source": capuchon_source(), "20_porte_relais": porte_relais(),
             "21_bague_lentille": bague_lentille(), "22_bouton_x3": bouton()}
    dummies = {"reseau": L_to_world(reseau_dummy_L(), phi), "miroir": mir(miroir_dummy_Mi()),
               "capteur": sens(capteur_dummy_Se()), "accus": accus_dummy(),
               "vis_coll": vis_coll(), "vis_cam": vis_cam(), "vis_lambda": vis_lambda(phi)}
    return P, extra, dummies

if __name__ == "__main__":
    os.makedirs("export_v2", exist_ok=True)
    P, extra, dummies = parts()
    asm = cq.Assembly()
    for k, v in {**P, **extra}.items():
        cq.exporters.export(v, f"export_v2/{k}.stl", tolerance=0.05, angularTolerance=0.2)
        if k in P: asm.add(v, name=k)
        print("ok", k)
    for k, v in dummies.items():
        asm.add(v, name="dummy_" + k)
    asm.export("export_v2/spectro_v2_assemblage.step")
    bb = P["01_boitier"].val().BoundingBox()
    area = outline(WALL).val().Area() if hasattr(outline(WALL).val(), "Area") else 0
    print(f"Boitier v2 : {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm")
    print("M", M_PT, "S", S_PT, "normale miroir", MIR_N)
