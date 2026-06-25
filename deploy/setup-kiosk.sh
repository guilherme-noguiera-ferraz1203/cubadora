#!/usr/bin/env bash
# Configura: (1) o BACKEND como servico systemd (sobe sempre no boot, independente do desktop) e
# (2) a TELA LOCAL (kiosk) = SO o navegador em tela cheia. Detecta a sessao do Raspberry Pi OS.
set -e

APP_DIR="${APP_DIR:-/home/pi/cubagem-pi/python}"
RUN="$APP_DIR/deploy/kiosk-run.sh"
USER_ALVO="$(id -un)"
HOME_ALVO="$(getent passwd "$USER_ALVO" | cut -d: -f6)"; [ -n "$HOME_ALVO" ] || HOME_ALVO="$HOME"
chmod +x "$RUN" 2>/dev/null || true

# --- navegador + utilitarios ---
echo ">> Instalando o Chromium (navegador do kiosk)..."
sudo apt-get install -y chromium-browser 2>/dev/null || sudo apt-get install -y chromium 2>/dev/null || true
sudo apt-get install -y unclutter curl 2>/dev/null || true

# --- BACKEND como servico systemd (confiavel; NAO depende do desktop) ---
echo ">> Instalando o backend como servico systemd (cubagempi)..."
sudo sed -e "s#^User=.*#User=$USER_ALVO#" \
         -e "s#^WorkingDirectory=.*#WorkingDirectory=$APP_DIR#" \
         -e "s#--config [^ ]*#--config $APP_DIR/config.yaml#" \
         "$APP_DIR/deploy/cubagempi.service" | sudo tee /etc/systemd/system/cubagempi.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now cubagempi 2>/dev/null || sudo systemctl enable cubagempi

# --- detectar compositor (para o autostart do navegador) ---
if command -v wayfire >/dev/null 2>&1 || pgrep -x wayfire >/dev/null 2>&1; then
    COMPOSITOR="wayfire"
elif command -v labwc >/dev/null 2>&1 || pgrep -x labwc >/dev/null 2>&1; then
    COMPOSITOR="labwc"
else
    COMPOSITOR="x11"
fi
echo ">> Compositor detectado: $COMPOSITOR"

# --- login automatico no desktop + sem protetor de tela ---
sudo raspi-config nonint do_boot_behaviour B4 2>/dev/null || true   # desktop autologin
sudo raspi-config nonint do_blanking 1        2>/dev/null || true   # desliga blanking (Bookworm)

# --- 1) XDG autostart (LXDE/X11 e a maioria dos desktops) ---
mkdir -p "$HOME_ALVO/.config/autostart"
cat > "$HOME_ALVO/.config/autostart/cubagem-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Cubagem Kiosk
Exec=$RUN
X-GNOME-Autostart-enabled=true
EOF

# --- 2) Wayland / Wayfire (Bookworm em Pi 4) ---
if [ "$COMPOSITOR" = "wayfire" ]; then
    WF="$HOME_ALVO/.config/wayfire.ini"; touch "$WF"
    grep -q "^\[autostart\]" "$WF" || printf "\n[autostart]\n" >> "$WF"
    grep -q "cubagem" "$WF" || echo "cubagem = $RUN" >> "$WF"
    echo ">> Autostart (navegador) adicionado em $WF"
fi

# --- 3) Wayland / labwc (Bookworm em Pi 5) ---
if [ "$COMPOSITOR" = "labwc" ]; then
    mkdir -p "$HOME_ALVO/.config/labwc"; AC="$HOME_ALVO/.config/labwc/autostart"
    grep -q "cubagem" "$AC" 2>/dev/null || echo "$RUN &" >> "$AC"
    chmod +x "$AC" 2>/dev/null || true
    echo ">> Autostart (navegador) adicionado em $AC"
fi

sudo chown -R "$USER_ALVO":"$USER_ALVO" "$HOME_ALVO/.config" 2>/dev/null || true

echo ">> Pronto: backend por systemd + tela local pelo navegador."
echo ">> O backend ja esta no ar e sobe sozinho a cada boot; a tela abre apos 'sudo reboot'."
