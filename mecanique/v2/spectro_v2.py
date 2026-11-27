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
Lancer : python3 spectro_v2.py  -> export_v2/*.stl (posés sur le plateau) + spectro_v2_assemblage.step
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
        # pont reliant l'oreille a l'equerre (sans lui, l'oreille etait detachee de 0,5 mm) ;
        # y >= 11,5 : 0,5 mm de jeu avec les charnieres du cadre basculant (y <= 11)
        p = p.union(W().box(5, 1.5, 2.5, centered=(True, False, False)).translate((sx*25.5, 11.5, Z_PLAT + 3)))
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
    # module electronique : bossages bas aux coins arriere, inserts par dessous (vis M3 x 35)
    for x, y in BACK_BOSSES:
        b = b.union(W().circle(4.5).extrude(6).translate((x, y, -0.01)))
    # capot capteur : 2 bossages sur la facette (au-dessus de la plaque capteur), inserts M3
    for y in HOOD_Y:
        b = b.union(W().box(O_SENS[0] + 0.5 - 28.0, 8, 8, centered=(False, True, True)).translate((28.0, y, HOOD_Z)))
        late_cuts.append(cyl_x(INS_M3/2, 8, 27.99, y, HOOD_Z))
    for c in late_cuts: b = b.cut(c)
    # colonnettes de couvercle
    global LID_PTS
    LID_PTS = lid_pts()
    for px, py in LID_PTS:
        b = b.union(W().circle(4.5).extrude(H_INT).translate((px, py, 0)))
        b = b.cut(W().circle(INS_M3/2).extrude(8).translate((px, py, H_INT - 8)))
    for x, y in mod_pts():                        # inserts du module electronique (par dessous)
        b = b.cut(W().circle(INS_M3/2).extrude(8).translate((x, y, -FLOOR - 0.01)))
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

# ------------------------------------------------------------------ MODULE ELECTRONIQUE (sous le boitier, dans son prolongement)
# Bac (23) dont le contour prolonge celui du boitier optique (zone du capteur comprise), plaque
# directement sous le plancher du boitier (pas de couvercle : le plancher le ferme) ; composants
# vissés sur son fond. Fixe par 8 vis M3 x 30 introduites PAR DESSOUS (inserts dans les colonnettes
# du boitier) : l'electronique se demonte sans ouvrir l'optique.
# Capot du capteur (25) : ferme la zone du capteur (facette avant), de son fond (pose sur le bac)
# jusqu'au dessus du boitier ; les fils capteur -> electronique descendent dans le bac par une fente
# de ce fond et sont proteges sur toute leur longueur.
#   Bac, cote -y : support 2 x 18650 en PARALLELE (1S2P ~7 Ah) tenu par 2 sangles, carte BMS 1S 6 A,
#   interrupteur a bascule ; face arriere : module PENGLIN (USB-C charge, USB-A sortie 5 V) et
#   ventilateur 25 mm en extraction ; cote +y : carte d'interface (RP2350-Zero) sous la fente des
#   fils, Raspberry Pi Zero ; entrees d'air sur la face avant.
LID_T, TRAY_H, TRAY_FLOOR = 0.0, 30.0, 2.5     # LID_T = 0 : bac plaque sous le plancher
Z_LID_TOP = -FLOOR                        # dessous du plancher du boitier
Z_LID_BOT = Z_LID_TOP - LID_T
Z_TRAY_BOT = Z_LID_BOT - TRAY_H
Z_F = Z_TRAY_BOT + TRAY_FLOOR             # dessus du fond du bac
T_IN = [(X_FRONT + WALL, Y_MIN_IN), (X_BACK_IN, Y_MIN_IN), (X_BACK_IN, 36.0), (132.0, 78.0),
        (84.0, 100.0), (X_FRONT + WALL, 100.0)]
def t_outline(off):
    return W().polyline(T_IN).close().offset2D(off, "arc")
def lid_pts():
    """colonnettes du boitier (couvercle optique en haut, module electronique en bas)"""
    cx = sum(p[0] for p in IN_PTS)/len(IN_PTS); cy = sum(p[1] for p in IN_PTS)/len(IN_PTS)
    pts = []
    for i, (x, y) in enumerate(IN_PTS):
        if i in (1, 2): continue      # coins arriere : passage des vis lambda / focus
        d = math.hypot(cx - x, cy - y)
        pts.append((x + (cx - x)/d*5, y + (cy - y)/d*5))
    return pts
BACK_BOSSES = [(157.0, -30.0), (155.0, 33.0)]            # bossages bas (coins arriere)
def mod_pts(): return lid_pts() + BACK_BOSSES
HOOD_Y, HOOD_Z = (42.0, 90.0), 55.0                       # vis du capot capteur (M3 x 25)
HOOD_FLOOR = 2.0                                          # fond du capot (ferme le bac sous la zone capteur)
CB_DEPTH = 5.0                                            # lamage des vis M3 x 30 sous le bac
HOLDER = dict(x=24.0, y=-31.0, w=77.0, d=41.0, h=20.0)    # support 2 x 18650
STRAPS = (52.0, 92.0)                                     # x des sangles
BMS = dict(x=105.0, y=-12.0, w=20.0, d=8.0, h=3.5)
PEN = dict(x=137.0, y=-24.0, w=25.0, d=20.0, bz=6.0)      # PENGLIN, composants VERS LE BAS, carte a bz du fond
PEN_RAIL = 5.3
IFB = dict(x=16, y=56, w=50, d=30, holes=[(3, 3), (47, 3), (3, 27), (47, 27)], drill=1.0)    # M2
RPZ = dict(x=19.0, y=62.0, w=23.5, d=18.0)                # RP2350-Zero (USB-C vers +x)
PIZ = dict(x=70, y=38, w=65, d=30, holes=[(3.5, 3.5), (61.5, 3.5), (3.5, 26.5), (61.5, 26.5)], drill=1.1)  # M2.5
FAN = dict(x=X_BACK_IN - 10, yc=14.5, s=25.0, hole=20.0, zc=14.0)
STANDOFF = 4.0
SW_X = 110.0                                               # interrupteur (decoupe 19,5 x 13,5, cote -y)
CABLE_SLOT = (17.0, 31.0, 66.0, 72.0)                     # fente des fils dans le fond du capot

def _pen_z():
    """(z dessus, z dessous) de la carte PENGLIN"""
    bot = Z_F + PEN["bz"]
    return bot + 1.6, bot
def pen_screws():
    return [(PEN["x"] + 5, PEN["y"] - PEN_RAIL/2 - 0.15), (PEN["x"] + 5, PEN["y"] + PEN["d"] + PEN_RAIL/2 + 0.15)]

def bac_electronique():
    zt = Z_LID_BOT
    b = t_outline(WALL).extrude(TRAY_H).translate((0, 0, Z_TRAY_BOT))
    b = b.cut(t_outline(0).extrude(TRAY_H).translate((0, 0, Z_F)))
    # colonnes de fixation (vis M3 x 30 par dessous, tete noyee)
    for x, y in mod_pts():
        b = b.union(W().circle(4.5).extrude(zt - Z_F + 0.01).translate((x, y, Z_F - 0.01)))
    # sangles du support d'accus : montants avec fente au-dessus du support
    H_ = HOLDER; zh = Z_F + H_["h"]
    for xs in STRAPS:
        for y0, y1 in ((Y_MIN_IN - 0.5, H_["y"] - 0.5), (H_["y"] + H_["d"] + 0.5, H_["y"] + H_["d"] + 4.5)):
            post = W().box(16, y1 - y0, H_["h"] + 4.5, centered=(True, False, False)).translate((xs, y0, Z_F - 0.01))
            post = post.cut(W().box(12, y1 - y0 + 2, 2.5, centered=(True, False, False)).translate((xs, y0 - 1, zh + 0.7)))
            b = b.union(post)
    # berceau du module PENGLIN (composants vers le bas) : rebords de 0,8 mm sous la carte,
    # bride 24 vissee par dessus ; son bord bute contre le corps de l'USB-A
    top, bot = _pen_z()
    for y_outer, y_ledge in (((PEN["y"] - PEN_RAIL, PEN["y"] - 0.3), (PEN["y"] - 0.3, PEN["y"] + 0.8)),
                             ((PEN["y"] + PEN["d"] + 0.3, PEN["y"] + PEN["d"] + PEN_RAIL), (PEN["y"] + PEN["d"] - 0.8, PEN["y"] + PEN["d"] + 0.3))):
        b = b.union(W().box(PEN["w"] + 1, y_outer[1] - y_outer[0], top - Z_F + 0.01, centered=False).translate((PEN["x"] - 1, y_outer[0], Z_F - 0.01)))
        b = b.union(W().box(PEN["w"] + 1, y_ledge[1] - y_ledge[0], bot - Z_F + 0.01, centered=False).translate((PEN["x"] - 1, y_ledge[0], Z_F - 0.01)))
    for x, y in pen_screws():
        b = b.cut(W().circle(0.8).extrude(6).translate((x, y, top - 6 + 0.01)))      # M2 autotaraudeuse
    # fenetre USB-C (charge, sous la carte) + USB-A (sortie 5 V, dessus) dans la face arriere
    yc = PEN["y"] + PEN["d"]/2
    b = b.cut(W().box(10, 13.5, 7.5, centered=(False, True, True)).translate((X_BACK_IN - 2, yc, bot - 1.6)))
    b = b.cut(W().box(10, 16.5, 9.5, centered=(False, True, True)).translate((X_BACK_IN - 2, yc, top + 3.5)))
    # entretoises carte d'interface et Pi Zero
    for B_ in (IFB, PIZ):
        for hx, hy in B_["holes"]:
            b = b.union(W().circle(2.6).extrude(STANDOFF + 0.01).translate((B_["x"] + hx, B_["y"] + hy, Z_F - 0.01)))
            b = b.cut(W().circle(B_["drill"]).extrude(STANDOFF + 2).translate((B_["x"] + hx, B_["y"] + hy, Z_F - 1)))
    # ventilateur : 4 vis + grille dans la face arriere (extraction)
    zf = Z_F + FAN["zc"]
    for dy in (-1, 1):
        for dz in (-1, 1):
            b = b.cut(cyl_x(1.3, 8, X_BACK_IN - 2, FAN["yc"] + dy*FAN["hole"]/2, zf + dz*FAN["hole"]/2))
    grille = cyl_x(11.5, 8, X_BACK_IN - 2, FAN["yc"], zf)
    for a_ in (0, 90):
        grille = grille.cut(W().box(10, 24, 2).rotate((0, 0, 0), (1, 0, 0), a_).translate((X_BACK_IN + 1.5, FAN["yc"], zf)))
    b = b.cut(grille.cut(cyl_x(3, 8, X_BACK_IN - 2, FAN["yc"], zf)))
    # entrees d'air (face avant, cote electronique)
    for i in range(4):
        b = b.cut(W().box(10, 24, 2.2).translate((X_FRONT + 1.5, 78, Z_F + 6 + i*5)))
    # interrupteur a bascule (face -y)
    b = b.cut(W().box(19.5, 10, 13.5).translate((SW_X + 9.75, Y_MIN_IN - 1.5, Z_F + 14)))
    # trous de fixation (apres les unions)
    for x, y in mod_pts():
        b = b.cut(W().circle(1.7).extrude(TRAY_H + 2).translate((x, y, Z_TRAY_BOT - 1)))
        b = b.cut(W().circle(3.1).extrude(CB_DEPTH).translate((x, y, Z_TRAY_BOT - 0.01)))
    return b

def bride_penglin():
    """Piece 24 : bride sur le module PENGLIN (2 vis M2 x 6). Son bord +x bute contre l'USB-A."""
    top, bot = _pen_z()
    x1 = PEN["x"] + PEN["w"] - 14.5
    b = W().box(x1 - PEN["x"] + 1, PEN["d"] + 2*PEN_RAIL, 2.0, centered=False).translate((PEN["x"] - 1, PEN["y"] - PEN_RAIL, top))
    for x, y in pen_screws():
        b = b.cut(W().circle(1.1).extrude(4).translate((x, y, top - 1)))
    return b.cut(W().box(x1 - PEN["x"] - 8, PEN["d"] - 6, 4, centered=False).translate((PEN["x"] + 9, PEN["y"] + 3, top - 1)))

def capot_capteur():
    """Piece 25 : capot de la zone capteur, pose sur le bac electronique, jusqu'au dessus du boitier.
    Fixe par 2 vis M3 x 25 (face avant) dans les bossages de la facette. Son fond ferme le bac sous
    la zone du capteur ; les fils y passent par une fente (a garnir de mousse : lumiere des LED)."""
    z0, z1 = Z_LID_TOP, H_INT + 3
    c = t_outline(WALL).extrude(z1 - z0).translate((0, 0, z0))
    c = c.intersect(W().box(O_SENS[0] + 3 - X_FRONT, 90, 200, centered=False).translate((X_FRONT, 20, -50)))
    c = c.cut(outline(WALL + CLR).extrude(200).translate((0, 0, -50)))
    c = c.cut(W().box(60, 100.5 - 20, z1 - 2.5 - z0 - HOOD_FLOOR, centered=False).translate((X_FRONT + 2.5, 20, z0 + HOOD_FLOOR)))
    for y in HOOD_Y:
        c = c.cut(cyl_x(1.7, 10, X_FRONT - 1, y, HOOD_Z))
    x0, x1, y0, y1 = CABLE_SLOT
    return c.cut(W().box(x1 - x0, y1 - y0, 10, centered=False).translate((x0, y0, z0 - 5)))

def electronique_dummies():
    """Volumes des composants (verification des interferences et rendus)."""
    H_ = HOLDER
    top, bot = _pen_z()
    zi = Z_F + STANDOFF + 1.6                        # dessus de la carte d'interface
    zr = zi + 8.5                                    # dessous de la RP2350-Zero (sur barrettes)
    return {
        "accus": W().box(H_["w"], H_["d"], H_["h"], centered=False).translate((H_["x"], H_["y"], Z_F)),
        "bms": W().box(BMS["w"], BMS["d"], BMS["h"], centered=False).translate((BMS["x"], BMS["y"], Z_F)),
        "penglin": W().box(PEN["w"], PEN["d"], 1.6, centered=False).translate((PEN["x"], PEN["y"], bot))
                   .union(W().box(7.5, 9.0, 3.2, centered=False).translate((PEN["x"] + PEN["w"] - 6.5, PEN["y"] + PEN["d"]/2 - 4.5, bot - 3.2)))
                   .union(W().box(14.0, 13.1, 7.0, centered=False).translate((PEN["x"] + PEN["w"] - 13.0, PEN["y"] + PEN["d"]/2 - 6.55, top)))
                   .union(W().box(6.0, 6.0, 3.0, centered=False).translate((PEN["x"] + 4, PEN["y"] + 3, bot - 3.0))),
        "carte_interface": W().box(IFB["w"], IFB["d"], 1.6, centered=False).translate((IFB["x"], IFB["y"], zi - 1.6))
                   .union(W().box(23.0, 2.6, 8.5, centered=False).translate((RPZ["x"] + 0.25, RPZ["y"] - 0.2, zi)))
                   .union(W().box(23.0, 2.6, 8.5, centered=False).translate((RPZ["x"] + 0.25, RPZ["y"] + RPZ["d"] - 2.4, zi))),
        "rp2350_zero": W().box(RPZ["w"], RPZ["d"], 4.1, centered=False).translate((RPZ["x"], RPZ["y"], zr))
                   .union(W().box(7.5, 9.0, 3.2, centered=False).translate((RPZ["x"] + RPZ["w"] - 6.5, RPZ["y"] + RPZ["d"]/2 - 4.5, zr + 4.1))),
        "fiche_usb_c": W().box(22.0, 12.0, 7.0, centered=False).translate((RPZ["x"] + RPZ["w"] + 0.5, RPZ["y"] + RPZ["d"]/2 - 6, zr + 4.1 - 1.9)),
        "pi_zero": W().box(PIZ["w"], PIZ["d"], 5, centered=False).translate((PIZ["x"], PIZ["y"], Z_F + STANDOFF)),
        "ventilateur": W().box(10, FAN["s"], FAN["s"], centered=(False, True, True)).translate((FAN["x"], FAN["yc"], Z_F + FAN["zc"])),
        "interrupteur": W().box(19.0, 16.0, 13.0, centered=False).translate((SW_X + 0.25, Y_MIN_IN, Z_F + 7.75)),
    }

def carte_capteur_dummy():
    """carte du capteur (TCD1304 + 74HCT04 + ampli) vissee sur la plaque 17, composants compris"""
    return W().box(10, 58, 34, centered=False).translate((O_SENS[0] - 4 - 10, S_PT[1] - 29, H - 17))

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
        "23_bac_electronique": bac_electronique(),
        "24_bride_penglin": bride_penglin(),
        "25_capot_capteur": capot_capteur(),
    }
    extra = {"19_capuchon_source": capuchon_source(), "20_porte_relais": porte_relais(),
             "21_bague_lentille": bague_lentille(), "22_bouton_x3": bouton()}
    dummies = {"reseau": L_to_world(reseau_dummy_L(), phi), "miroir": mir(miroir_dummy_Mi()),
               "capteur": sens(capteur_dummy_Se()), "accus": accus_dummy(),
               "vis_coll": vis_coll(), "vis_cam": vis_cam(), "vis_lambda": vis_lambda(phi)}
    return P, extra, dummies

def pose_impression(wp):
    """Pose une piece pour l'impression : essaie les 6 faces de l'enveloppe comme face
    du dessous, garde celle qui offre la plus grande surface plane au contact du plateau
    (a egalite, la moins haute), puis centre la piece en X/Y et la pose sur Z = 0.
    Les fichiers STL ont ainsi un sens pour un trancheur ; le STEP garde l'assemblage."""
    rots = [((1, 0, 0), 0), ((1, 0, 0), 180), ((1, 0, 0), 90), ((1, 0, 0), -90),
            ((0, 1, 0), 90), ((0, 1, 0), -90)]
    best = None
    for ax, ang in rots:
        r = wp.rotate((0, 0, 0), ax, ang) if ang else wp
        bb = r.val().BoundingBox()
        contact = 0.0
        for f in r.faces().vals():
            if f.geomType() != "PLANE":
                continue
            fb = f.BoundingBox()
            if fb.zlen < 1e-3 and abs(fb.zmin - bb.zmin) < 1e-3:
                contact += f.Area()
        key = (round(contact, 1), -bb.zlen)
        if best is None or key > best[0]:
            best = (key, r)
    r = best[1]
    bb = r.val().BoundingBox()
    return r.translate((-bb.center.x, -bb.center.y, -bb.zmin))

if __name__ == "__main__":
    os.makedirs("export_v2", exist_ok=True)
    P, extra, dummies = parts()
    asm = cq.Assembly()
    for k, v in {**P, **extra}.items():
        cq.exporters.export(pose_impression(v), f"export_v2/{k}.stl", tolerance=0.05, angularTolerance=0.2)
        if k in P: asm.add(v, name=k)
        print("ok", k)
    for k, v in dummies.items():
        asm.add(v, name="dummy_" + k)
    asm.export("export_v2/spectro_v2_assemblage.step")
    bb = P["01_boitier"].val().BoundingBox()
    area = outline(WALL).val().Area() if hasattr(outline(WALL).val(), "Area") else 0
    print(f"Boitier v2 : {bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm")
    print("M", M_PT, "S", S_PT, "normale miroir", MIR_N)
