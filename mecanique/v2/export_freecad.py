"""Construit les documents FreeCAD (atelier Part) a partir des BREP de export_brep.py.

  python3 export_brep.py brep
  BREP=brep SORTIE=freecad QT_QPA_PLATFORM=offscreen freecad export_freecad.py

Avec l interface graphique (meme hors ecran), les couleurs et la vue cadree sont enregistrees ;
avec freecadcmd, seulement la geometrie."""
import os, sys, glob
import FreeCAD as App, Part
SRC = os.environ.get("BREP", "brep")
OUT = os.environ.get("SORTIE", "freecad")
try:
    import FreeCADGui as Gui
    GUI = Gui.getMainWindow() is not None
except Exception:
    GUI = False
print("GUI:", GUI)

NOIR = (0.18, 0.18, 0.20)
COUL = {"composant_accus": (0.18, 0.75, 0.40), "composant_capteur": (0.55, 0.35, 0.75),
        "composant_miroir": (0.80, 0.85, 0.90), "composant_reseau": (0.30, 0.60, 0.95),
        "composant_vis_coll": (0.75, 0.75, 0.75), "composant_vis_cam": (0.75, 0.75, 0.75),
        "composant_vis_lambda": (0.75, 0.75, 0.75)}

def label(nom):
    n = nom.split("_", 1)
    return nom if not n[0].isdigit() else n[0] + " " + n[1].replace("_", " ")

def ajoute(doc, chemin, nom, couleur=NOIR):
    sh = Part.Shape(); sh.read(chemin)
    o = doc.addObject("Part::Feature", "".join(c if c.isalnum() else "_" for c in nom))
    o.Shape = sh; o.Label = label(nom)
    if GUI:
        o.ViewObject.ShapeColor = couleur
        if nom.startswith("02_") or nom.startswith("24_"):
            o.ViewObject.Transparency = 60
    return o

def finit(doc, fichier):
    doc.recompute()
    if GUI:
        Gui.ActiveDocument = Gui.getDocument(doc.Name)
        v = Gui.ActiveDocument.ActiveView
        v.viewIsometric(); v.fitAll()
    doc.saveAs(fichier)
    App.closeDocument(doc.Name)

# une pièce par fichier (posée sur le plateau)
os.makedirs(os.path.join(OUT, "pieces"), exist_ok=True)
for f in sorted(glob.glob(os.path.join(SRC, "pieces", "*.brep"))):
    nom = os.path.basename(f)[:-5]
    doc = App.newDocument("P" + nom.split("_")[0])
    doc.Label = label(nom)
    ajoute(doc, f, nom, (0.25, 0.27, 0.30))
    finit(doc, os.path.join(OUT, "pieces", nom + ".FCStd"))
    print("ok", nom)

# assemblage complet
doc = App.newDocument("Assemblage")
doc.Label = "Spectrographe v2 - assemblage"
g_p = doc.addObject("App::DocumentObjectGroup", "Pieces"); g_p.Label = "Pièces imprimées"
g_c = doc.addObject("App::DocumentObjectGroup", "Composants"); g_c.Label = "Composants (optique, capteur, accus, vis)"
for f in sorted(glob.glob(os.path.join(SRC, "assemblage", "*.brep"))):
    nom = os.path.basename(f)[:-5]
    o = ajoute(doc, f, nom, COUL.get(nom, NOIR))
    (g_c if nom.startswith("composant_") else g_p).addObject(o)
finit(doc, os.path.join(OUT, "spectro_v2_assemblage.FCStd"))
print("ok assemblage")
if GUI:
    Gui.getMainWindow().close()
import os as _o; _o._exit(0)
