import cadquery as cq, spectro_cad as S
def frustum(a, d0, r0, d1, r1):
    s = cq.Solid.makeCone(r0, r1, d1-d0, cq.Vector(d0, 0, S.H), cq.Vector(1, 0, 0))
    return S.arm(cq.Workplane("XY").add(s), a)
b_slit = frustum(S.a1, S.D_COLL+1, 6.4, S.SLIT_D-1, 0.3)
b_coll = frustum(S.a1, 3, 6.4, S.D_COLL, 6.41)
b_cam1 = frustum(S.a2, 3, 6.4, S.D_CAM, 12.3)
loft = (cq.Workplane("YZ").workplane(offset=S.D_CAM+8).circle(12.0)
        .workplane(offset=S.SENS_D-S.D_CAM-10).rect(30, 0.5).loft()).translate((0,0,S.H))
b_cam2 = S.arm(loft, S.a2)
BEAMS = {"fente->coll":b_slit,"coll->reseau":b_coll,"reseau->cam":b_cam1,"cam->capteur":b_cam2}
if __name__=="__main__":
    import check  # reuse parts dict
