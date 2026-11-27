# Démarrage automatique sur le Raspberry Pi Zero

Une seule commande installe tout :

```bash
git clone https://github.com/decmike91/spectro.git ~/spectro
cd ~/spectro
bash logiciel/demarrage/installer.sh                  # serveur + interface à l'écran
sudo reboot
```

Variantes :

| Commande | Effet |
| --- | --- |
| `bash logiciel/demarrage/installer.sh --plein-ecran` | interface en plein écran (petit écran tactile) |
| `bash logiciel/demarrage/installer.sh --sans-interface` | serveur seul, Pi sans écran (appli Android uniquement) |
| `bash logiciel/demarrage/installer.sh --desinstaller` | supprime le démarrage automatique |

## Ce qui se passe au démarrage du Pi

1. **Le serveur** (`serveur/spectro_server.py`) démarre comme service systemd `spectro`. Il redémarre tout seul toutes les 3 s s'il s'arrête, par exemple si le Pico n'est pas encore branché.
2. **avahi** annonce le Pi sur le Wi-Fi : l'appli Android le trouve sans adresse IP.
3. **L'interface PyQt** (`rpi/spectro_gui.py`) s'ouvre à l'arrivée sur le bureau et affiche le spectre en direct. Le script active la connexion automatique au bureau avec `raspi-config`.

L'interface est lancée avec `--server` : elle ne prend pas le port série, elle lit les spectres du serveur. **L'écran du Pi et l'appli Android fonctionnent donc en même temps.** Ils partagent le temps de pose, le noir soustrait en direct et l'étalonnage : un réglage fait sur l'un se retrouve sur l'autre. Pendant une séquence lancée depuis le téléphone, l'interface attend la fin de la séquence pour reprendre le direct.

Le script installe :

- `/etc/systemd/system/spectro.service`, copie de `serveur/spectro.service` avec votre utilisateur et le chemin du dépôt ;
- `/etc/avahi/services/spectro.service` ;
- `~/.config/autostart/spectro-gui.desktop`, copie de `spectro-gui.desktop`, plus une ligne dans `~/.config/wayfire.ini` si ce bureau est utilisé.

Il ajoute aussi l'utilisateur aux groupes `dialout` (port série du Pico) et `gpio` (ventilateur).

## Commandes utiles

```bash
systemctl status spectro          # état du serveur
journalctl -u spectro -f          # journal en direct
sudo systemctl restart spectro    # après une mise à jour : cd ~/spectro && git pull
sudo systemctl disable spectro    # ne plus démarrer le serveur au boot
```

Pour lancer l'interface à la main sur un PC du réseau, en même temps que le Pi :

```bash
python3 logiciel/rpi/spectro_gui.py --server raspberrypi.local
```

Sur un Pi Zero de première génération (un seul cœur), le bureau et l'interface ralentissent le direct. Le Pi Zero 2 W est plus confortable. Sinon, utilisez `--sans-interface` et seulement l'appli Android.
