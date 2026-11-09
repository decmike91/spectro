# Appli Android « Spectro »

Appli native (Kotlin, Jetpack Compose) qui se connecte au serveur du Pi Zero (`logiciel/serveur`) par le Wi-Fi.

## Installer

1. Sur le téléphone, ouvrir la page [Releases du dépôt](https://github.com/decmike91/spectro/releases/tag/apk-latest) et télécharger `spectro.apk`. Il est recompilé automatiquement à chaque modification de `main`.
2. Ouvrir le fichier et autoriser l'installation d'applications de cette source.
3. Le téléphone et le Pi doivent être sur le même réseau Wi-Fi (ou le téléphone connecté au point d'accès du Pi).
4. Au premier lancement, l'icône Wi-Fi en haut ouvre la connexion : le Pi annoncé par avahi apparaît tout seul, sinon taper son adresse (`192.168.x.y:8080`).

Android 8.0 ou plus récent.

## Fonctions

**Direct**
- Spectre en direct avec zoom à deux doigts, déplacement, curseur (λ et intensité), axe en pixels ou en nm.
- Temps de pose (boutons ×2 et ÷2), moyennes, soustraction du noir optique et d'un noir enregistré.
- Alerte de saturation, niveau de noir, cadence.
- Superposition d'un spectre de référence.
- Acquisition unique enregistrée sur le Pi, ou « figer » le direct dans le téléphone.

**Séquences** (exécutées par le Pi)
- N poses × temps de pose, lectures moyennées par pose, intervalle entre poses.
- Combinaison par moyenne, médiane ou somme, ou toutes les poses gardées.
- Soustraction d'un noir à chaque pose.
- Progression et temps restant, arrêt en cours de route.
- Raccourcis pour une série de noirs, de lampe ou de flats.

**Spectres** (bibliothèque du Pi)
- Liste filtrable par type (objet, noir, flat, lampe, référence, résultat).
- Chargement dans l'espace de travail, export CSV ou FITS vers une autre appli (mail, Drive…), renommage, suppression.

**Traitement** (dans le téléphone, sur l'espace de travail)
- Addition, soustraction, division, multiplication ou décalage par une constante.
- Moyenne, médiane ou somme de plusieurs spectres.
- Transmission (%) et absorbance d'un filtre.
- Normalisation (au maximum ou sur une zone).
- Lissages : moyenne glissante, Savitzky-Golay.
- Continuum (polynôme avec rejet des raies) : division ou soustraction.
- Correction de réponse instrumentale : A ÷ B × Planck(T), B étant une étoile de référence de température T.
- Mesure d'une raie dans une zone :
  - centre et largeur à mi-hauteur ;
  - pouvoir de résolution λ/Δλ ;
  - profondeur, flux, largeur équivalente (Å) ;
  - rapport signal/bruit ;
  - vitesse radiale par rapport à une raie de référence.
- Détection des raies avec identification (Balmer, He, Na, Mg, Ca, [O III], [N II], [S II], raies telluriques…) et repères des raies de référence.
- Les résultats peuvent être enregistrés sur le Pi ou partagés en CSV ou FITS.

**Étalonnage**
- Lampes au néon, mercure, argon, fluocompacte, ou raies stellaires.
- Identification automatique robuste (rejet des raies mélangées et des points aberrants), ajout et suppression manuels.
- Polynôme d'ordre 1 à 3, résidus point par point, écart RMS, dispersion.
- L'étalonnage est enregistré sur le Pi et sert à tous les affichages et exports.

**Divers**
- Mode nuit rouge pour garder l'adaptation à l'obscurité.
- Écran maintenu allumé.
- Ventilateur : auto, marche ou arrêt.

## Compiler soi-même

Ouvrir le dossier `android/` dans Android Studio, ou :

```bash
cd android
./gradlew assembleRelease          # app/build/outputs/apk/release/app-release.apk
./gradlew testDebugUnitTest        # tests du moteur de calcul
```

Le moteur de calcul (`math/`) est en Kotlin pur et couvert par les tests unitaires. L'APK de release est signé avec la clé de débogage : il s'installe directement, mais ne peut pas être publié sur le Play Store tel quel.
