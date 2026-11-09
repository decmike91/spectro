# Serveur du spectro (Raspberry Pi Zero)

`spectro_server.py` tourne sur le Pi Zero. Il pilote le capteur TCD1304DG à travers le Pico (pilote `../rpi/tcd1304.py`) et met tout à disposition de l'appli Android par le Wi-Fi :

- **API HTTP JSON** : réglages, acquisitions, séquences, bibliothèque de spectres, étalonnage, ventilateur, export CSV et FITS ;
- **WebSocket `/ws`** : spectre en direct (environ 20 spectres/s en simulation), état et progression des séquences.

Les séquences tournent sur le Pi : elles continuent si le téléphone se met en veille ou se déconnecte.

## Installation sur le Pi Zero

```bash
sudo apt install python3-aiohttp python3-numpy python3-serial python3-gpiozero avahi-daemon
git clone https://github.com/decmike91/spectro.git ~/spectro

# test sans matériel
python3 ~/spectro/logiciel/serveur/spectro_server.py --sim

# démarrage automatique
sudo cp ~/spectro/logiciel/serveur/spectro.service /etc/systemd/system/
sudo systemctl enable --now spectro

# annonce sur le réseau : l'appli trouve le Pi toute seule
sudo cp ~/spectro/logiciel/serveur/avahi-spectro.service /etc/avahi/services/spectro.service
```

Le service suppose l'utilisateur `pi` et le dépôt dans `/home/pi/spectro` : adaptez `spectro.service` sinon.

Options : `--port 8080`, `--serial /dev/ttyACM0`, `--data ~/spectro_data` (dossier des spectres), `--calib ~/.tcd1304_calib.json` (étalonnage partagé avec l'interface PyQt `../rpi/spectro_gui.py`), `--sim` (simulateur).

Le serveur et l'interface PyQt utilisent le même port série : n'en lancez qu'un à la fois.

## Ventilateur

Le ventilateur 5 V est commandé par le GPIO18 à travers un MOSFET logique :

- GPIO18 → résistance de 100 Ω → grille d'un AO3400 (ou 2N7000) ;
- résistance de 100 kΩ entre la grille et la masse ;
- source à la masse, drain vers le fil − du ventilateur, fil + au 5 V ;
- diode Schottky (1N5819) en parallèle sur le ventilateur, cathode côté 5 V.

En mode « auto », le ventilateur est **coupé pendant les acquisitions et les séquences** pour ne pas faire vibrer la fente. Le reste du temps, il démarre au-dessus de 60 °C et s'arrête sous 52 °C. Les modes « marche » et « arrêt » le forcent.

## API

| Méthode | Chemin | Rôle |
| --- | --- | --- |
| GET | `/api/status` | État : pose, moyennes, direct, séquence en cours, température, ventilateur, étalonnage |
| POST | `/api/config` | `{tint_us, averages, sub_black}` |
| POST | `/api/live` | `{on, dark_id}` : direct marche/arrêt, noir soustrait |
| GET | `/api/live/last` | Dernier spectre en direct |
| POST | `/api/acquire` | `{name, kind, tint_us, averages, dark_id}` : une acquisition enregistrée |
| POST | `/api/sequence` | `{name, kind, count, tint_us, averages, interval_s, combine, dark_id, save_individual}` |
| POST | `/api/sequence/stop` | Arrête la séquence (le résultat partiel est gardé) |
| GET | `/api/job` | Séquence en cours |
| GET / POST | `/api/spectra` | Liste / enregistre un spectre (`values` + métadonnées) |
| GET / PATCH / DELETE | `/api/spectra/{id}` | Lit, renomme, supprime |
| GET | `/api/spectra/{id}/csv` · `/fits` | Export (FITS 1D linéaire en Å si étalonné : ISIS, BASS, VisualSpec) |
| GET / PUT | `/api/calibration` | Étalonnage λ(pixel) = c0 + c1·p + c2·p² + … |
| POST | `/api/fan` | `{mode: auto/on/off, t_on, t_off}` |
| WS | `/ws` | Messages `frame`, `status`, `job` |

`kind` vaut `light` (objet), `dark` (noir), `flat`, `lamp` (lampe d'étalonnage), `ref` (référence) ou `result`. `combine` vaut `mean`, `median`, `sum` ou `none`.
