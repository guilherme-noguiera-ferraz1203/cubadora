#!/usr/bin/env bash
# Instalador da cubadora — DETECTA a versão do Raspberry Pi/SO e configura do jeito certo.
# Funciona em Raspberry Pi OS Bullseye, Bookworm e Trixie, em Pi 3/4/5 (X11 ou Wayland).
#
# NUNCA usa 'set -e' cego: cada etapa loga e trata erro nao-fatal. So aborta em erro real.

APP_DIR="/home/pi/cubagem-pi/python"

# Quem e o usuario alvo (dono do desktop). Quando o bootstrap roda o instalador via
#   sudo -u pi bash install.sh   -> id -un = pi
# Quando o usuario roda manualmente
#   sudo bash install.sh         -> id -un = root, mas SUDO_USER=pi
# Por isso preferimos SUDO_USER.
USER_ALVO="${USER_ALVO:-${SUDO_USER:-$(id -un)}}"
if [ "$USER_ALVO" = "root" ]; then
    id pi >/dev/null 2>&1 && USER_ALVO="pi"
fi
export USER_ALVO   # para o setup-kiosk.sh reusar

echo "==================================================================="
echo " Instalação da Cubadora (Python)"
echo "==================================================================="

# ----------------------------------------------------------- 1. DETECÇÃO
. /etc/os-release 2>/dev/null || true
CODENAME="${VERSION_CODENAME:-desconhecido}"
MODELO="$(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo desconhecido)"
SESSAO="${XDG_SESSION_TYPE:-tty}"

echo ">> Dispositivo : $MODELO"
echo ">> SO          : $CODENAME"
echo ">> Sessão      : $SESSAO"
echo ">> Usuario     : $USER_ALVO"
echo ""

# ----------------------------------------------------------- 2. DEPENDÊNCIAS
echo ">> Instalando dependências do sistema..."
if ! sudo apt-get update; then
    echo "   AVISO: apt-get update falhou; tentando seguir com cache atual."
fi
sudo apt-get install -y python3 python3-pip i2c-tools unclutter || \
    echo "   AVISO: algum pacote nao foi instalado (segue mesmo assim)."

echo ">> Instalando dependências Python..."
# Bookworm/Trixie exigem --break-system-packages (PEP 668); Bullseye nao conhece a flag -> fallback.
if ! pip3 install --break-system-packages -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-pi.txt" 2>/dev/null; then
    pip3 install -r "$APP_DIR/requirements.txt" -r "$APP_DIR/requirements-pi.txt" || {
        echo "   ERRO: pip falhou em ambos os modos. Abortando." >&2
        exit 1
    }
fi

# ----------------------------------------------------------- 3. INTERFACES
echo ">> Habilitando UART (serial) e I2C..."
if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_serial_hw 0    2>/dev/null || true   # libera a UART
    sudo raspi-config nonint do_serial_cons 1  2>/dev/null || true   # desabilita console serial
    sudo raspi-config nonint do_i2c 0          2>/dev/null || true   # habilita I2C
else
    echo "   raspi-config nao encontrado; pulando (config UART/I2C manual via /boot/firmware/config.txt)."
fi

if [ -e /dev/serial0 ]; then PORTA="/dev/serial0"; else PORTA="/dev/ttyAMA0"; fi
echo ">> Porta serial detectada: $PORTA"

# ----------------------------------------------------------- 4. CONFIG
if [ ! -f "$APP_DIR/config.yaml" ]; then
    echo ">> Criando config.yaml a partir do exemplo..."
    cp "$APP_DIR/config.example.yaml" "$APP_DIR/config.yaml"
    sed -i "s#serial_port:.*#serial_port: $PORTA#" "$APP_DIR/config.yaml" 2>/dev/null || true
    chown "$USER_ALVO":"$USER_ALVO" "$APP_DIR/config.yaml" 2>/dev/null || true
fi

# ----------------------------------------------------------- 5. SUDOERS (controle remoto sem senha)
# O backend roda como servico systemd (sem TTY); 'sudo' interativo trava em prompt invisivel
# e os comandos remotos (reiniciar/desligar/restart_servico) falham SILENCIOSAMENTE.
# Liberamos NOPASSWD apenas para os binarios estritamente necessarios.
echo ">> Configurando sudoers (NOPASSWD para reboot/poweroff/systemctl) p/ $USER_ALVO..."
SUDOERS_TMP="$(mktemp)"
cat > "$SUDOERS_TMP" <<EOF
$USER_ALVO ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff, /sbin/halt, /sbin/shutdown, /bin/systemctl, /usr/bin/systemctl
EOF
if sudo visudo -cf "$SUDOERS_TMP" >/dev/null 2>&1; then
    sudo install -m 440 "$SUDOERS_TMP" /etc/sudoers.d/cubagempi-nopasswd
    echo "   ok (/etc/sudoers.d/cubagempi-nopasswd)"
else
    echo "   AVISO: validacao do sudoers falhou; deixe NOPASSWD manualmente."
fi
rm -f "$SUDOERS_TMP"

# ----------------------------------------------------------- 6. BACKEND (systemd) + TELA (navegador)
echo ">> Configurando o backend (systemd) e a tela local (navegador)..."
APP_DIR="$APP_DIR" USER_ALVO="$USER_ALVO" bash "$APP_DIR/deploy/setup-kiosk.sh"
KIOSK_RC=$?
if [ "$KIOSK_RC" -ne 0 ]; then
    echo "   AVISO: setup-kiosk.sh saiu com codigo $KIOSK_RC."
    echo "          Veja as mensagens acima para identificar a etapa que falhou."
fi

echo ""
echo "==================================================================="
echo " Instalação concluída."
echo " Ajuste $APP_DIR/config.yaml (modelo, sensores, ajustes) se preciso."
echo " O backend já roda como serviço (systemd) e sobe sozinho no boot."
echo " Reinicie para a tela local abrir no navegador:  sudo reboot"
echo "==================================================================="
