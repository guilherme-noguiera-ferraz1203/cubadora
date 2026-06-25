#!/usr/bin/env bash
# Inicia a cubadora em modo kiosk: backend (headless) + navegador em TELA CHEIA.
# Funciona em X11 e Wayland (Bullseye/Bookworm), Pi 3/4/5.

# Instância única: o autostart pode disparar em mais de um lugar (XDG .desktop + labwc/wayfire).
# Sem isto, dois backends sobem ao mesmo tempo e brigam pela serial (GPIO busy) e pela porta 8080
# -> tela piscando. O flock garante que só o primeiro kiosk-run.sh siga adiante.
exec 9>/tmp/cubagem-kiosk.lock
flock -n 9 || { echo "[kiosk] ja em execucao; saindo."; exit 0; }

APP="/home/pi/cubagem-pi/python"
CFG="$APP/config.yaml"
export DISPLAY="${DISPLAY:-:0}"

# Em X11, desliga o protetor de tela (no Wayland é via raspi-config do-blanking)
if [ "${XDG_SESSION_TYPE:-x11}" = "x11" ]; then
    xset s off -dpms s noblank 2>/dev/null || true
fi

# 1) Backend (serve o painel web + máquina), com auto-reinício se cair
(
  cd "$APP"
  while true; do
    python3 scripts/run.py --config "$CFG" --real --no-gui
    echo "[kiosk] backend caiu; reiniciando em 3s..."; sleep 3
  done
) &

# 2) Espera o painel web responder
for i in $(seq 1 60); do
    curl -s http://localhost:8080/api/status >/dev/null 2>&1 && break
    sleep 0.5
done

# 3) Navegador em TELA CHEIA (kiosk). Cobre os dois nomes de binário do Chromium.
CHROME="$(command -v chromium-browser || command -v chromium || echo chromium-browser)"
while true; do
    # --password-store=basic: nao usa o GNOME Keyring -> evita o popup
    # "Choose password for new keyring" ao ligar (trava a tela do kiosk).
    "$CHROME" --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
        --disable-features=TranslateUI --check-for-update-interval=31536000 \
        --no-first-run --overscroll-history-navigation=0 --start-fullscreen \
        --password-store=basic \
        "http://localhost:8080" 2>/dev/null
    echo "[kiosk] navegador encerrou; reabrindo em 3s..."; sleep 3
done
