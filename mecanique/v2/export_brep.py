"""Exporte la géométrie exacte (BREP) de chaque pièce pour la génération des fichiers FreeCAD :
  <dossier>/pieces/<nom>.brep      pièce posée sur le plateau (comme les STL)
  <dossier>/assemblage/<nom>.brep  pièce à sa place dans l'assemblage (+ composants factices)
Usage : python3 export_brep.py /tmp/brep"""
import os, sys
import spectro_v2 as S

out = sys.argv[1] if len(sys.argv) > 1 else "brep"
for d in ("pieces", "assemblage"):
    os.makedirs(os.path.join(out, d), exist_ok=True)
P, extra, dummies = S.parts()
for k, v in {**P, **extra}.items():
    S.pose_impression(v).val().exportBrep(os.path.join(out, "pieces", k + ".brep"))
    if k in P:
        v.val().exportBrep(os.path.join(out, "assemblage", k + ".brep"))
    print("ok", k)
for k, v in dummies.items():
    v.val().exportBrep(os.path.join(out, "assemblage", "composant_" + k + ".brep"))
    print("ok composant", k)
