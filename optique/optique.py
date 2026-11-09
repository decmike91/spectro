"""Bilan optique du spectro TCD1304 - geometrie a deviation fixe (V), reseau plan en reflexion."""
import numpy as np, json
# --- Parametres (modifiables) ---
D_tel, F_tel = 80.0, 480.0          # lunette 80/480 (f/6)
f_coll, f_cam = 75.0, 100.0         # achromats Ø25.4
Dv = np.radians(50.0)               # angle inclus collimateur/camera
pix, npix = 8e-3, 3648              # TCD1304 : 8 µm, 3648 px utiles
tilt_slit = np.radians(30.0)        # fente inclinee (reflexion vers guidage)
seeing = 3.0                        # arcsec FWHM
L = pix*npix
beam = f_coll/(F_tel/D_tel)
reseaux = {300:600, 600:550, 1200:590, 1200.1:656}   # l/mm : lambda centrale (nm)
fentes = [15, 25, 35, 50, 100]      # µm
out = {"faisceau_mm": round(beam,1), "echelle_fente_arcsec_par_um": round(206265e-3/F_tel,3),
       "etoile_fwhm_um": round(seeing/206265*F_tel*1e3,1), "reseaux": []}
for N, lc in reseaux.items():
    n = N*1e-6                                   # traits/nm
    s = n*lc/(2*np.cos(Dv/2)); phi = np.arcsin(s)
    a, b = phi+Dv/2, phi-Dv/2
    def lam(x): return (np.sin(a)+np.sin(b-np.arctan(x/f_cam)))/n
    l1, l2 = sorted([lam(-L/2), lam(L/2)])
    disp = np.cos(b)/(n*f_cam)                   # nm/mm
    anam = np.cos(a)/np.cos(b)
    row = {"N":N,"lambda_c":lc,"rotation_reseau_deg":round(np.degrees(phi),2),
           "alpha":round(np.degrees(a),1),"beta":round(np.degrees(b),1),
           "plage_nm":[round(l1),round(l2)],"nm_par_px":round(disp*pix,4),"fentes":[]}
    for w in fentes:
        wimg = w*1e-3*np.cos(tilt_slit)*f_cam/f_coll*anam
        fwhm = max(wimg, 2*pix)*disp
        row["fentes"].append({"w_um":w,"image_px":round(wimg/pix,1),"dl_nm":round(fwhm,3),"R":int(lc/fwhm)})
    out["reseaux"].append(row)
json.dump(out, open("bilan_optique.json","w"), indent=1)
print(f"Faisceau collimate: {beam:.1f} mm | etoile: {out['etoile_fwhm_um']} µm | 1 µm fente = {out['echelle_fente_arcsec_par_um']}\"")
for r in out["reseaux"]:
    print(f"\n{r['N']} t/mm  lc={r['lambda_c']}  rot={r['rotation_reseau_deg']}°  plage {r['plage_nm']} nm  {r['nm_par_px']} nm/px")
    for f in r["fentes"]: print(f"   fente {f['w_um']:>3} µm -> {f['image_px']:>4} px  Δλ={f['dl_nm']:.3f} nm  R={f['R']}")
# empreinte du faisceau sur l'objectif camera (vignettage)
for d in (42,):
    print(f"empreinte objectif camera a {d} mm du reseau: {beam+2*d*np.tan(np.arctan(L/2/f_cam)):.1f} mm")
# empreinte du faisceau sur le reseau 25 mm
for r in out["reseaux"]:
    print(f"{r['N']:.0f} t/mm @ {r['lambda_c']} nm : empreinte reseau {beam/np.cos(np.radians(r['alpha'])):.1f} mm, ordre 0 a {2*r['rotation_reseau_deg']:.1f}° de l'axe camera")
