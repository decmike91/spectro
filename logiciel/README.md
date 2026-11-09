# Spectrographe à capteur linéaire TCD1304DG — Raspberry Pi Zero

## Architecture

```
TCD1304DG ──OS──► Q1 + U3 (conditionnement) ──► ADC du Pico (12 bits, 250 kéch/s)
    ▲  φM / SH / ICG                                   │
    └── 74HCT04 (3,3 V → 5 V) ◄── PIO du Pico ─────────┘
                                         │ USB (série CDC)
                                 Raspberry Pi Zero : tcd1304.py + spectro_gui.py
```

**Pourquoi un Pico entre le capteur et le Pi Zero ?** Le capteur sort un pixel toutes
les 4 µs et chaque pixel doit être numérisé en phase exacte avec φM. Le Pi Zero n'a pas
d'ADC, et Linux n'est pas temps réel : sa gigue (dizaines de µs) mélangerait les pixels.
Le RP2040 (environ 5 €) génère les horloges avec ses PIO et déclenche chaque conversion
ADC par DMA, sans aucune intervention logicielle. Le Pi Zero ne fait que l'affichage
et le traitement. La même interface tourne aussi sur un PC avec le Pico branché directement.

## Fichiers

| Fichier | Rôle |
|---|---|
| `schema/schema_tcd1304.svg / .png` | Schéma électronique |
| `schema/schema.py` | Source du schéma (schemdraw), modifiable |
| `firmware/main.py` | Firmware MicroPython du Pico (PIO + DMA + protocole USB) |
| `rpi/tcd1304.py` | Pilote Python + simulateur |
| `rpi/spectro_gui.py` | Interface graphique (PyQt5 + pyqtgraph) |

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
| — | Raspberry Pi Pico (ou Pico W) | |
| — | Raspberry Pi Zero / Zero W / Zero 2 W | |
| — | Câble micro-USB OTG (Pico ↔ port « USB » du Zero) | |

## Brochage

**TCD1304DG** : 1 VDD, 2 VAD, 3 ICG, 4 φM, 5 SH, 21 OS, 22 SS (masse), 6 à 20 NC.
VDD = VAD = 5 V (plage autorisée 3,0 à 5,5 V). Le niveau haut des horloges ne doit
jamais dépasser VDD : c'est pour ça que le 74HCT04 est alimenté par le même +5VA.

| Pico | → | 74HCT04 | → | TCD1304DG |
|---|---|---|---|---|
| GP2 (broche 4) | | 1 → 2 | | φM (4) |
| GP3 (broche 5) | | 3 → 4 | | SH (5) |
| GP4 (broche 6) | | 5 → 6 | | ICG (3) |
| GP26/ADC0 (broche 31) | ← R6 ← U3 sortie | | | |
| VBUS (40) | → FB1 → +5VA | | | |
| 3V3(OUT) (36) | → U3, RV1 | | | |
| GND / AGND (38 / 33) | masse commune | | | |

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

### 1. Pico
1. Flasher MicroPython **≥ 1.23** (fichier .uf2 depuis micropython.org, en maintenant BOOTSEL).
2. Copier `firmware/main.py` sur le Pico : `mpremote cp firmware/main.py :main.py`, ou via Thonny.
3. Débrancher puis rebrancher le Pico : il démarre l'acquisition tout seul.

### 2. Raspberry Pi Zero (Raspberry Pi OS avec bureau)
```bash
sudo apt install python3-pyqt5 python3-pyqtgraph python3-numpy python3-serial
sudo usermod -aG dialout $USER        # accès à /dev/ttyACM0, puis se reconnecter
python3 rpi/tcd1304.py                # test en ligne de commande
python3 rpi/spectro_gui.py            # interface graphique
python3 rpi/spectro_gui.py --sim      # interface sans matériel (simulateur)
```
Sur un Pi Zero sans écran, l'interface s'utilise via VNC. On peut aussi brancher le Pico
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
