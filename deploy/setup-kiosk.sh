#!/usr/bin/env bash
# Configura "liga e abre sozinho" (kiosk) detectando a versão/sessão do Raspberry Pi OS.
# Cobre: LXDE/Openbox (X11, Bullseye) e Wayfire/labwc (Wayland, Bookworm).
set -e

APP_DIR="/home/pi/cubagem-pi/python"
RUN="$APP_DIR/deploy/kiosk-run.sh"
chmod +x "$RUN" 2>/dev/null || true

# --- garante o navegador (tela cheia do kiosk) e utilitários ---
echo ">> Instalando o Chromium (navegador do kiosk)..."
sudo apt-get install -y chromium-browser 2>/dev/null || sudo apt-get install -y chromium 2>/dev/null || true
sudo apt-get install -y unclutter curl 2>/dev/null || true

# --- detectar compositor ---
if command -v wayfire >/dev/null 2>&1 || pgrep -x wayfire >/dev/null 2>&1; then
    COMPOSITOR="wayfire"
elif command -v labwc >/dev/null 2>&1 || pgrep -x labwc >/dev/null 2>&1; then
    COMPOSITOR="labwc"
else
    COMPOSITOR="x11"
fi
echo ">> Compositor detectado: $COMPOSITOR"

# --- login automático no desktop + sem protetor de tela ---
sudo raspi-config nonint do_boot_behaviour B4 2>/dev/null || true   # desktop autologin
sudo raspi-config nonint do_blanking 1        2>/dev/null || true   # desliga blanking (Bookworm)

# --- desabilita o serviço headless (evita conflito na porta 8080) ---
sudo systemctl disable cubagempi 2>/dev/null || true
sudo systemctl stop cubagempi    2>/dev/null || true

# --- 1) XDG autostart (LXDE/X11 e a maioria dos desktops) ---
mkdir -p /home/pi/.config/autostart
cat > /home/pi/.config/autostart/cubagem-kiosk.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Cubagem Kiosk
Exec=$RUN
X-GNOME-Autostart-enabled=true
EOF

# --- 2) Wayland / Wayfire (Bookworm em Pi 4) ---
if [ "$COMPOSITOR" = "wayfire" ]; then
    WF="/home/pi/.config/wayfire.ini"
    touch "$WF"
    grep -q "^\[autostart\]" "$WF" || printf "\n[autostart]\n" >> "$WF"
    grep -q "cubagem" "$WF" || echo "cubagem = $RUN" >> "$WF"
    echo ">> Autostart adicionado em $WF"
fi

# --- 3) Wayland / labwc (Bookworm em Pi 5) ---
if [ "$COMPOSITOR" = "labwc" ]; then
    mkdir -p /home/pi/.config/labwc
    AC="/home/pi/.config/labwc/autostart"
    grep -q "cubagem" "$AC" 2>/dev/null || echo "$RUN &" >> "$AC"
    chmod +x "$AC" 2>/dev/null || true
    echo ">> Autostart adicionado em $AC"
fi

sudo chown -R pi:pi /home/pi/.config 2>/dev/null || true

echo ">> Kiosk configurado. Após 'sudo reboot', basta LIGAR a energia que a tela do sistema abre sozinha."
echo ">> (Para sair do kiosk em manutenção: tecla ESC.)"
