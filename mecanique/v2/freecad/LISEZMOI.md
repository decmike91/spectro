# Fichiers FreeCAD (atelier Part)

Ouvrir avec FreeCAD 1.0 ou plus récent.

| Fichier | Contenu |
| --- | --- |
| `spectro_v2_assemblage.FCStd` | Assemblage complet : pièces imprimées (groupe « Pièces imprimées ») et composants factices (réseau, miroir, capteur, électronique, vis) à leur place. Couvercles transparents. |
| `pieces/01_boitier.FCStd` … `pieces/26_capot_capteur.FCStd` | Une pièce par fichier, posée sur le plateau et centrée, comme les STL. |

Chaque pièce est un solide exact (`Part::Feature`, géométrie B-rep, pas un maillage) : on peut la
mesurer, la couper (Part → Booléen), y ajouter des formes, ou l'exporter en STEP / STL depuis FreeCAD.
Ce ne sont pas des pièces paramétriques : les cotes se changent dans `../spectro_v2.py` (CadQuery),
puis on régénère ces fichiers :

```bash
python3 spectro_v2.py                 # STL + STEP
python3 export_brep.py brep           # géométrie exacte
BREP=brep SORTIE=freecad QT_QPA_PLATFORM=offscreen freecad export_freecad.py
```

Si une pièce n'apparaît pas à l'ouverture : menu Affichage → Vues standard → Tout afficher (touche V, F).
