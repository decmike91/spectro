import cadquery as cq, math, spectro_v2 as S
def loft_seg(p0, dirdeg, d0, w0, h0, d1, w1, h1):
    wp = (cq.Workplane("YZ").workplane(offset=d0).rect(w0, h0)
          .workplane(offset=d1-d0).rect(w1, h1).loft()).translate((0, 0, S.H))
    return S.place(wp, p0, dirdeg)
def cone(p0, dirdeg, d0, r0, d1, r1):
    s = cq.Solid.makeCone(r0, r1, d1-d0, cq.Vector(d0, 0, S.H), cq.Vector(1, 0, 0))
    return S.place(cq.Workplane("XY").add(s), p0, dirdeg)
B = 12.5; L = 29.2
def wcam(a):   # largeur horizontale du faisceau camera a la distance a du reseau (a >= D_CAM)
    t = (a - S.D_CAM)/S.F_CAM; return L*t + (B + 2*S.D_CAM*L/2/S.F_CAM)*(1 - t)
def hcam(a): return B*(1 - (a - S.D_CAM)/S.F_CAM)
lens_w = B + 2*S.D_CAM*L/2/S.F_CAM
d_after = S.SENS_D - S.D_MIR
BEAMS = {
 "fente->coll": cone((0, 0), 0, 1, 0.3, S.SLIT_D - S.D_COLL - 1, 6.4),
 "coll->reseau": cone((0, 0), 0, S.SLIT_D - S.D_COLL + 1, 6.4, S.SLIT_D - 3, 6.41),
 "reseau->obj": loft_seg(S.G, S.A_CAM, 6, B + 1, B + 0.5, S.D_CAM - S.TUBE_L/2 - 0.5, B + 2*(S.D_CAM - S.TUBE_L/2)*L/2/S.F_CAM, B + 0.5),
 "obj->miroir": loft_seg(S.G, S.A_CAM, S.D_CAM + S.TUBE_L/2 + 6, wcam(S.D_CAM + S.TUBE_L/2 + 6), hcam(S.D_CAM + S.TUBE_L/2 + 6), S.D_MIR - 14, wcam(S.D_MIR - 14), hcam(S.D_MIR - 14)),
 "miroir->capt": loft_seg(S.M_PT, S.A_OUT, 14, wcam(S.D_MIR + 14), hcam(S.D_MIR + 14), d_after - 1, L, 0.5),
}
