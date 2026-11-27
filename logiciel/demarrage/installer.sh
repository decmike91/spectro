#!/bin/bash
# Démarrage automatique du spectro sur le Raspberry Pi Zero.
#
#   cd ~/spectro && bash logiciel/demarrage/installer.sh              # serveur + interface
#   bash logiciel/demarrage/installer.sh --plein-ecran                # interface en plein écran
#   bash logiciel/demarrage/installer.sh --sans-interface             # serveur seul (Pi sans écran)
#   bash logiciel/demarrage/installer.sh --desinstaller
#
# Au démarrage du Pi :
#   1. le service systemd « spectro » lance le serveur (l'appli Android s'y connecte) ;
#      il redémarre tout seul s'il s'arrête, ou si le Pico est branché après coup ;
#   2. avahi annonce le Pi sur le Wi-Fi (l'appli le trouve sans adresse IP) ;
#   3. à l'ouverture du bureau (connexion automatique activée), l'interface PyQt
#      s'ouvre et affiche le spectre en direct, en passant par le serveur.
set -e

DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
UTIL="$(id -un)"
MAISON="$HOME"
OPTIONS=""
INTERFACE=1

for a in "$@"; do
  case "$a" in
    --plein-ecran) OPTIONS="--fullscreen" ;;
    --sans-interface) INTERFACE=0 ;;
    --desinstaller)
      sudo systemctl disable --now spectro 2>/dev/null || true
      sudo rm -f /etc/systemd/system/spectro.service /etc/avahi/services/spectro.service
      rm -f "$MAISON/.config/autostart/spectro-gui.desktop"
      sudo systemctl daemon-reload
      echo "Démarrage automatique supprimé."
      exit 0 ;;
    *) echo "Option inconnue : $a"; exit 1 ;;
  esac
done

if [ "$UTIL" = "root" ]; then
  echo "Lancez ce script avec votre utilisateur habituel (pas avec sudo) : il appelle sudo lui-même."
  exit 1
fi

echo "== Dépôt : $DEPOT  —  utilisateur : $UTIL"

echo "== Paquets"
PAQUETS="python3-aiohttp python3-numpy python3-serial python3-gpiozero avahi-daemon"
[ $INTERFACE = 1 ] && PAQUETS="$PAQUETS python3-pyqt5 python3-pyqtgraph"
sudo apt-get install -y $PAQUETS

echo "== Accès au port série du Pico et aux GPIO (ventilateur)"
sudo usermod -aG dialout,gpio "$UTIL" || true

echo "== Service du serveur"
sed -e "s#^User=.*#User=$UTIL#" \
    -e "s#/home/pi/spectro#$DEPOT#g" \
    "$DEPOT/logiciel/serveur/spectro.service" | sudo tee /etc/systemd/system/spectro.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable spectro
sudo systemctl restart spectro

echo "== Annonce sur le réseau (avahi)"
sudo mkdir -p /etc/avahi/services
sudo cp "$DEPOT/logiciel/serveur/avahi-spectro.service" /etc/avahi/services/spectro.service
sudo systemctl enable --now avahi-daemon
sudo systemctl reload avahi-daemon 2>/dev/null || true

if [ $INTERFACE = 1 ]; then
  echo "== Lancement de l'interface à l'ouverture du bureau"
  mkdir -p "$MAISON/.config/autostart"
  sed -e "s#@DEPOT@#$DEPOT#g" -e "s#@OPTIONS@#$OPTIONS#" \
      "$DEPOT/logiciel/demarrage/spectro-gui.desktop" > "$MAISON/.config/autostart/spectro-gui.desktop"
  # Wayfire (anciennes versions de Raspberry Pi OS Bookworm) ignore ~/.config/autostart
  if [ -f "$MAISON/.config/wayfire.ini" ] && ! grep -q spectro_gui "$MAISON/.config/wayfire.ini"; then
    grep -q '^\[autostart\]' "$MAISON/.config/wayfire.ini" || printf '\n[autostart]\n' >> "$MAISON/.config/wayfire.ini"
    sed -i "/^\[autostart\]/a spectro = /usr/bin/python3 $DEPOT/logiciel/rpi/spectro_gui.py --server http://127.0.0.1:8080 --run $OPTIONS" \
        "$MAISON/.config/wayfire.ini"
  fi
  if command -v raspi-config > /dev/null; then
    echo "== Connexion automatique au bureau (sans mot de passe)"
    sudo raspi-config nonint do_boot_behaviour B4 || true
  else
    echo "!! Activez la connexion automatique au bureau pour que l'interface s'ouvre seule."
  fi
fi

sleep 3
echo
if systemctl is-active --quiet spectro; then
  echo "Serveur démarré : http://$(hostname).local:8080   (journal : journalctl -u spectro -f)"
else
  echo "!! Le serveur ne tourne pas encore. Journal : journalctl -u spectro -e"
  echo "   (Pico non branché ? Le service réessaie toutes les 3 secondes.)"
fi
echo "Redémarrez le Pi pour vérifier : sudo reboot"
