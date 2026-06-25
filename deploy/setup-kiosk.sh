#!/usr/bin/env bash
# Configura: (1) o BACKEND como servico systemd (sobe sempre no boot, independente do desktop) e
# (2) a TELA LOCAL (kiosk) = SO o navegador em tela cheia. Detecta a sessao do Raspberry Pi OS.
#
# DESIGN: NUNCA usar 'set -e' cego. Cada etapa loga o que esta fazendo, e falhas
# nao-fatais (apt sem chromium, raspi-config inexistente, autostart de compositor ausente)
# avancam com aviso em vez de abortar. So aborta se uma etapa REALMENTE fatal falhar.

APP_DIR="${APP_DIR:-/home/pi/cubagem-pi/python}"
RUN="$APP_DIR/deploy/kiosk-run.sh"

# Quem e o "dono" do desktop. Se chamado via sudo, usa o usuario original.
# Cai pra 'pi' se nem SUDO_USER nem id retornarem algo util.
USER_ALVO="${USER_ALVO:-${SUDO_USER:-$(id -un)}}"
if [ "$USER_ALVO" = "root" ]; then
    id pi >/dev/null 2>&1 && USER_ALVO="pi"
fi
HOME_ALVO="$(getent passwd "$USER_ALVO" 2>/dev/null | cut -d: -f6)"
[ -n "$HOME_ALVO" ] || HOME_ALVO="/home/$USER_ALVO"

echo ">> setup-kiosk: USER_ALVO=$USER_ALVO  HOME_ALVO=$HOME_ALVO  APP_DIR=$APP_DIR"
chmod +x "$RUN" 2>/dev/null || true

# --- navegador + utilitarios ---
echo ">> [1/6] Instalando o Chromium (navegador do kiosk)..."
if sudo apt-get install -y chromium-browser >/dev/null 2>&1; then
    echo "   ok (chromium-browser)"
elif sudo apt-get install -y chromium >/dev/null 2>&1; then
    echo "   ok (chromium)"
else
    echo "   AVISO: nao consegui instalar chromium/chromium-browser via apt."
    echo "          O backend vai subir, mas a tela local nao vai abrir ate isso ser resolvido."
fi
sudo apt-get install -y unclutter curl >/dev/null 2>&1 || true

# --- BACKEND como servico systemd (confiavel; NAO depende do desktop) ---
echo ">> [2/6] Instalando o backend como servico systemd (cubagempi, User=$USER_ALVO)..."
SVC_TMP="$(mktemp)"
sed -e "s#^User=.*#User=$USER_ALVO#" \
    -e "s#^WorkingDirectory=.*#WorkingDirectory=$APP_DIR#" \
    -e "s#--config [^ ]*#--config $APP_DIR/config.yaml#" \
    "$APP_DIR/deploy/cubagempi.service" > "$SVC_TMP"
if ! sudo install -m 644 "$SVC_TMP" /etc/systemd/system/cubagempi.service; then
    echo "   ERRO FATAL: nao consegui gravar /etc/systemd/system/cubagempi.service" >&2
    rm -f "$SVC_TMP"
    exit 1
fi
rm -f "$SVC_TMP"
sudo systemctl daemon-reload
if sudo systemctl enable --now cubagempi >/dev/null 2>&1; then
    echo "   ok (cubagempi enabled + started)"
elif sudo systemctl enable cubagempi >/dev/null 2>&1; then
    echo "   ok (cubagempi enabled; start tentativa abaixo)"
    sudo systemctl start cubagempi >/dev/null 2>&1 || \
        echo "   AVISO: cubagempi nao subiu agora; verifique 'journalctl -u cubagempi -n 50'"
else
    echo "   AVISO: 'systemctl enable cubagempi' falhou; verifique 'systemctl status cubagempi'"
fi

# --- detectar compositor (para o autostart do navegador) ---
# IMPORTANTE: nao usar 'pgrep -x' pra detectar (matcha lixo de sessoes anteriores).
# So olha se o binario do compositor existe E qual e a sessao reportada.
echo ">> [3/6] Detectando ambiente grafico..."
if [ -n "${SUDO_USER:-}" ]; then
    SESSAO="$(sudo -u "$USER_ALVO" sh -c 'echo "${XDG_SESSION_TYPE:-}"' 2>/dev/null)"
else
    SESSAO="${XDG_SESSION_TYPE:-}"
fi
HAS_LABWC=0; command -v labwc   >/dev/null 2>&1 && HAS_LABWC=1
HAS_WAYFIRE=0; command -v wayfire >/dev/null 2>&1 && HAS_WAYFIRE=1
echo "   SESSAO=$SESSAO  labwc=$HAS_LABWC  wayfire=$HAS_WAYFIRE"

# --- login automatico no desktop + sem protetor de tela (best-effort) ---
echo ">> [4/6] Configurando autologin do desktop e desligando o blanking..."
if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_boot_behaviour B4 >/dev/null 2>&1 \
        && echo "   ok (autologin do desktop)" \
        || echo "   AVISO: raspi-config nao aceitou do_boot_behaviour B4"
    sudo raspi-config nonint do_blanking 1 >/dev/null 2>&1 \
        && echo "   ok (blanking desativado)" \
        || echo "   AVISO: raspi-config nao aceitou do_blanking"
else
    echo "   raspi-config nao encontrado; pulando (ok no Trixie minimal)."
fi

# --- 1) XDG autostart (LXDE/X11 e a maioria dos desktops) ---
echo ">> [5/6] Gravando autostart do kiosk (XDG, labwc, wayfire)..."
sudo -u "$USER_ALVO" mkdir -p "$HOME_ALVO/.config/autostart" 2>/dev/null || \
    mkdir -p "$HOME_ALVO/.config/autostart"
DESK_TMP="$(mktemp)"
cat > "$DESK_TMP" <<EOF
[Desktop Entry]
Type=Application
Name=Cubagem Kiosk
Exec=$RUN
X-GNOME-Autostart-enabled=true
EOF
install -o "$USER_ALVO" -g "$USER_ALVO" -m 644 "$DESK_TMP" \
    "$HOME_ALVO/.config/autostart/cubagem-kiosk.desktop"
rm -f "$DESK_TMP"
echo "   ok (XDG: $HOME_ALVO/.config/autostart/cubagem-kiosk.desktop)"

# --- 2) Wayland / Wayfire (Bookworm em Pi 4) ---
if [ "$HAS_WAYFIRE" = "1" ]; then
    WF="$HOME_ALVO/.config/wayfire.ini"
    sudo -u "$USER_ALVO" touch "$WF" 2>/dev/null || touch "$WF"
    grep -q "^\[autostart\]" "$WF" 2>/dev/null || printf "\n[autostart]\n" >> "$WF"
    grep -q "cubagem" "$WF" 2>/dev/null || echo "cubagem = $RUN" >> "$WF"
    chown "$USER_ALVO":"$USER_ALVO" "$WF" 2>/dev/null || true
    echo "   ok (wayfire: $WF)"
fi

# --- 3) Wayland / labwc (Bookworm/Trixie em Pi 4/5) ---
if [ "$HAS_LABWC" = "1" ]; then
    sudo -u "$USER_ALVO" mkdir -p "$HOME_ALVO/.config/labwc" 2>/dev/null || \
        mkdir -p "$HOME_ALVO/.config/labwc"
    AC="$HOME_ALVO/.config/labwc/autostart"
    if ! grep -q "cubagem" "$AC" 2>/dev/null; then
        echo "$RUN &" >> "$AC"
    fi
    chmod +x "$AC" 2>/dev/null || true
    chown "$USER_ALVO":"$USER_ALVO" "$AC" 2>/dev/null || true
    echo "   ok (labwc: $AC)"
fi

# Garante que TODO o ~/.config pertence ao usuario (caso algum mkdir tenha rodado como root).
sudo chown -R "$USER_ALVO":"$USER_ALVO" "$HOME_ALVO/.config" 2>/dev/null || true

echo ">> [6/6] Pronto: backend por systemd + tela local pelo navegador."
echo "   - Backend ja esta no ar e sobe sozinho a cada boot."
echo "   - A tela local abre apos 'sudo reboot' (se houver desktop instalado)."
