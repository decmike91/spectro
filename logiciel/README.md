# Spectrographe à capteur linéaire TCD1304DG — Raspberry Pi Zero

## Architecture

```
TCD1304DG ──OS──► Q1 + U3 (conditionnement) ──► ADC de la RP2350-Zero (12 bits)
    ▲  φM / SH / ICG                                   │
    └── 74HCT04 (3,3 V → 5 V) ◄── PIO de la RP2350 ────────┘
                                         │ USB-C (série CDC)
                                 Raspberry Pi Zero : tcd1304.py + spectro_gui.py
```

**Pourquoi un microcontrôleur RP2350 (ou RP2040) entre le capteur et le Pi Zero ?** Le capteur sort un pixel toutes
les 4 µs et chaque pixel doit être numérisé en phase exacte avec φM. Le Pi Zero n'a pas
d'ADC, et Linux n'est pas temps réel : sa gigue (dizaines de µs) mélangerait les pixels.
La RP2350-Zero (environ 8 €, 23,5 × 18 mm) génère les horloges avec ses PIO et déclenche chaque conversion
ADC par DMA, sans aucune intervention logicielle. Le Pi Zero ne fait que l'affichage
et le traitement. La même interface tourne aussi sur un PC avec la carte branchée directement.

Le firmware détecte la puce : il fonctionne tel quel sur une **RP2350-Zero** (montage actuel),
une Pico 2 / Pico 2 W ou une Pico d'origine (RP2040). Seul `LED_RGB` est à régler en tête de fichier.

## Fichiers

| Fichier | Rôle |
|---|---|
| `schema/schema_tcd1304.svg / .png` | Schéma électronique |
| `schema/schema.py` | Source du schéma (schemdraw), modifiable |
| `firmware/main.py` | Firmware MicroPython de la RP2350-Zero / Pico (PIO + DMA + protocole USB) |
| `rpi/tcd1304.py` | Pilote Python + simulateur |
| `rpi/spectro_gui.py` | Interface graphique (PyQt5 + pyqtgraph) ; `--server` pour passer par le serveur |
| `serveur/` | Serveur réseau pour l'appli Android |
| `demarrage/installer.sh` | Démarrage automatique du serveur et de l'interface |

## Nomenclature

| Réf. | Composant | Remarque |
|---|---|---|
| U1 | TCD1304DG | DIP-22, support tulipe conseillé |
| U2 | 74HCT04 | **HCT** (seuils TTL, accepte le 3,3 V), alim 5 V |
| U3 | MCP6021 (DIP-8) | AOP rail-à-rail 10 MHz ; alternative : OPA350, AD8031 |
| Q1 | 2SA1015 ou BC557 / 2N3906 | PNP, suiveur d'émetteur |
| R1 | 2,2 kΩ | |
| R3 | 4,7 kΩ 1 % | |
| R4, R7 | 18 kΩ 1 % | |
| R5 | 10 kΩ | |
| R6 | 100 Ω | |
| RV1 | 10 kΩ multitours | réglage du zéro |
| C1 | 47 µF électrolytique | |
| C2, C3, C5, C6 | 100 nF céramique | découplage au plus près de chaque CI |
| C4 | 10 µF | |
| C7 | 10 pF C0G | |
| C8 | 1 µF | |
| C9 | 470 pF C0G | |
| FB1 | Ferrite 600 Ω @ 100 MHz | |
| — | RP2350-Zero (Waveshare ou compatible, barrettes soudées) | ou Pico 2 / Pico (même firmware) |
| — | Plaque à pastilles 50 × 30 mm + 2 barrettes femelles 9 broches | carte d'interface, 4 trous Ø 2,2 aux coins |
| — | Raspberry Pi Zero / Zero W / Zero 2 W | |
| — | Câble court micro-USB (OTG) ↔ USB-C, 10 à 15 cm | RP2350-Zero ↔ port « USB » du Zero |

## Brochage

**TCD1304DG** : 1 VDD, 2 VAD, 3 ICG, 4 φM, 5 SH, 21 OS, 22 SS (masse), 6 à 20 NC.
VDD = VAD = 5 V (plage autorisée 3,0 à 5,5 V). Le niveau haut des horloges ne doit
jamais dépasser VDD : c'est pour ça que le 74HCT04 est alimenté par le même +5VA.

| RP2350-Zero | → | 74HCT04 | → | TCD1304DG |
|---|---|---|---|---|
| GP2 | | 1 → 2 | | φM (4) |
| GP3 | | 3 → 4 | | SH (5) |
| GP4 | | 5 → 6 | | ICG (3) |
| GP26 (ADC0) | ← R6 ← U3 sortie | | | |
| 5V | → FB1 → +5VA | | | |
| 3V3 | → U3, RV1 | | | |
| GND | masse commune | | | |

Les broches de la RP2350-Zero se repèrent à leur nom sérigraphié (GP2, GP3, GP4, GP26, 5V, 3V3, GND).
Sa LED RGB (GP16) passe au bleu pendant chaque lecture et reste vert faible au repos.
La RP2350-Zero n'a pas de broche AGND ni ADC_VREF séparée : soigner le découplage
(C1, C2) et garder le fil OS → GP26 court et torsadé avec une masse.

Le câble entre la carte d'interface (compartiment) et la carte capteur porte 7 fils :
φM/CLK_M, CLK_SH, CLK_ICG, ADC, +5V, +3V3, GND. Il passe par le trou Ø 6,4 de la face avant.

Conseils de câblage : un plan de masse, des fils d'horloge courts, et la partie
analogique (Q1, U3) collée au capteur. SH présente 600 pF et ICG 250 pF : le 74HCT04
doit être à moins de 5 cm du capteur.

## Chronogrammes générés (fM = 1 MHz)

Les chronogrammes ont été vérifiés dans un émulateur PIO, avec les exigences de la fiche technique :

| Paramètre | Fiche technique | Firmware |
|---|---|---|
| t2 : ICG↓ → SH↑ | 100 à 1000 ns | 500 ns |
| t3 : largeur de SH | ≥ 1000 ns | 2000 ns |
| t1 : SH↓ → ICG↑ | ≥ 1000 ns | 2750 ns |
| t4 : ICG↑ pendant φM haut | φM maintenu haut | ICG monte 250 ns après φM↑ |
| tINT (obturateur électronique) | ≥ 10 µs | 10 µs à 60 s, par pas de 1 µs |

Une trame fait 3694 éléments : 16 dummy, puis 13 pixels masqués (noir optique, indices
16 à 28), puis 3 dummy, puis les **3648 pixels utiles** (indices 32 à 3679), puis 14 dummy.
La lecture dure 14,8 ms. On obtient environ 30 à 60 trames/s avec des intégrations courtes.

## Installation

### 1. RP2350-Zero
1. Flasher MicroPython **≥ 1.24** pour RP2350 : fichier .uf2 « RPI_PICO2 » (micropython.org/download/RPI_PICO2).
   Maintenir BOOT en branchant l'USB-C, puis copier le .uf2 sur le disque qui apparaît.
2. Copier `firmware/main.py` sur la carte : `mpremote cp firmware/main.py :main.py`, ou via Thonny.
3. Débrancher puis rebrancher : la LED passe au vert faible, l'acquisition est prête.
   (Sur une Pico, mettre `LED_RGB = False` en tête de `main.py`.)

### 2. Raspberry Pi Zero (Raspberry Pi OS avec bureau)
```bash
sudo apt install python3-pyqt5 python3-pyqtgraph python3-numpy python3-serial
sudo usermod -aG dialout $USER        # accès à /dev/ttyACM0, puis se reconnecter
python3 rpi/tcd1304.py                # test en ligne de commande
python3 rpi/spectro_gui.py            # interface graphique
python3 rpi/spectro_gui.py --sim      # interface sans matériel (simulateur)
```
Sur un Pi Zero sans écran, l'interface s'utilise via VNC. On peut aussi brancher la RP2350-Zero
sur un PC (`--port COM5` sous Windows).

## Mise en service
1. Vérifier à l'oscilloscope φM (1 MHz), SH (impulsion de 2 µs toutes les tINT) et ICG sur les broches du capteur.
2. Observer OS : on doit voir un palier pendant environ 15 ms après chaque ICG.
3. Capteur dans le noir : régler **RV1** pour que le « noir optique » affiché par l'interface soit vers 150 à 250.
4. Éclairer avec une lampe fluorescente (raies Hg 404,7 / 435,8 / 546,1 / 577 / 579 nm),
   puis lancer *Calibration λ…*. Les pics détectés sont pré-remplis : saisir les λ, cliquer
   *Ajuster* puis *Enregistrer*. La calibration est gardée dans `~/.tcd1304_calib.json`.
5. Si le spectre paraît bruité ou décalé d'un pixel, ajuster `ADC_PHASE` (de 0 à 12) dans
   `main.py` : c'est l'instant d'échantillonnage dans le pixel. Choisir la valeur qui donne
   les raies les plus fines et le bruit le plus faible.

## Personnaliser
- **Firmware** : `FM_HZ` (1, 1,25 ou 1,5 MHz), `INVERT_OUT` (False si le tampon n'inverse pas, par exemple un 74HCT244), choix des broches.
- **Interface** : dictionnaire `CONFIG` (couleurs, seuils, dossiers). Tout le traitement est
  regroupé dans `process_spectrum()` : c'est là qu'on ajoute un filtre ou une correction de
  réponse spectrale. Chaque panneau de commandes est construit dans `_build_controls()`.
- **Fonctions** : acquisition continue ou unique, moyennes, lissage, soustraction du noir
  optique et d'un fond, modes Intensité / Transmission % / Absorbance, pics étiquetés,
  curseur pixel/λ, export CSV et PNG.

## Limites connues
- L'ADC du RP2040 a environ 9 bits effectifs et des non-linéarités connues vers les codes
  512, 1536, 2560 et 3584. C'est suffisant pour un spectro pédagogique. Pour de la
  photométrie fine, on peut remplacer l'ADC par un AD7980 (16 bits) sur SPI, déclenché par la même PIO.
- Le firmware et le schéma ont été vérifiés par émulation et par calcul, pas encore sur un
  montage réel : les premiers essais doivent se faire à l'oscilloscope.
