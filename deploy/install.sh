#!/usr/bin/env bash
# Instalador da cubadora — DETECTA a versão do Raspberry Pi/SO e configura do jeito certo.
# Funciona em Raspberry Pi OS Bullseye e Bookworm, em Pi 3/4/5 (X11 ou Wayland).
set -e

APP_DIR="/home/pi/cubagem-pi/python"

echo "==================================================================="
echo " Instalação da Cubadora (Python)"
echo "==================================================================="

# ----------------------------------------------------------- 1. DETECÇÃO
. /etc/os-release 2>/dev/null || true
CODENAME="${VERSION_CODENAME:-desconhecido}"
MODELO="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo desconhecido)"
SESSAO="${XDG_SESSION_TYPE:-x11}"
if command -v wayfire >/dev/null 2>&1 || pgrep -x wayfire >/dev/null 2>&1; then
    COMPOSITOR="wayfire"
elif command -v labwc >/dev/null 2>&1 || pgrep -x labwc >/dev/null 2>&1; then
    COMPOSITOR="labwc"
else
    COMPOSITOR="x11"
fi
echo ">> Dispositivo : $MODELO"
echo ">> SO          : $CODENAME"
echo ">> Sessão      : $SESSAO (compositor: $COMPOSITOR)"
echo ""

# ----------------------------------------------------------- 2. DEPENDÊNCIAS
echo ">> Instalando dependências do sistema..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip i2c-tools unclutter || true

echo ">> Instalando dependências Python..."
# Bookworm exige --break-system-packages (PEP 668); Bullseye não conhece a flag -> fallback.
if ! pip3 install --break-system-packages -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-pi.txt" 2>/dev/null; then
    pip3 install -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-pi.txt"
fi

# ----------------------------------------------------------- 3. INTERFACES
echo ">> Habilitando UART (serial) e I2C..."
sudo raspi-config nonint do_serial_hw 0    2>/dev/null || true   # libera a UART
sudo raspi-config nonint do_serial_cons 1  2>/dev/null || true   # desabilita console serial
sudo raspi-config nonint do_i2c 0          2>/dev/null || true   # habilita I2C

if [ -e /dev/serial0 ]; then PORTA="/dev/serial0"; else PORTA="/dev/ttyAMA0"; fi
echo ">> Porta serial detectada: $PORTA"

# ----------------------------------------------------------- 4. CONFIG
if [ ! -f "$APP_DIR/config.yaml" ]; then
    echo ">> Criando config.yaml a partir do exemplo..."
    cp "$APP_DIR/config.example.yaml" "$APP_DIR/config.yaml"
    # grava a porta serial detectada
    sed -i "s#serial_port:.*#serial_port: $PORTA#" "$APP_DIR/config.yaml" 2>/dev/null || true
fi

# ----------------------------------------------------------- 5. BACKEND (systemd) + TELA (navegador)
echo ">> Configurando o backend (systemd) e a tela local (navegador)..."
APP_DIR="$APP_DIR" bash "$APP_DIR/deploy/setup-kiosk.sh"

echo ""
echo "==================================================================="
echo " Instalação concluída."
echo " Ajuste $APP_DIR/config.yaml (modelo, sensores, ajustes) se preciso."
echo " O backend já roda como serviço (systemd) e sobe sozinho no boot."
echo " Reinicie para a tela local abrir no navegador:  sudo reboot"
echo "==================================================================="
