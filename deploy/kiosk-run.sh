#!/usr/bin/env bash
# Tela local da cubadora: SO o navegador em tela cheia apontando para o backend.
# O backend (porta 8080) roda como servico systemd (cubagempi.service) — NAO e iniciado aqui.
# Isso elimina o conflito de dois backends (GPIO busy / porta 8080) que causava tela piscando.

export DISPLAY="${DISPLAY:-:0}"

# Instancia unica do navegador (o autostart pode disparar em mais de um lugar: XDG + labwc/wayfire).
# Lock por usuario num local sempre gravavel -> nunca impede a tela de abrir por erro de permissao.
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/cubagem-kiosk-$(id -u).lock"
flock -n 9 || { echo "[kiosk] navegador ja aberto; saindo."; exit 0; }

# Em X11, desliga o protetor de tela (no Wayland e via raspi-config do-blanking)
if [ "${XDG_SESSION_TYPE:-x11}" = "x11" ]; then
    xset s off -dpms s noblank 2>/dev/null || true
fi

# Espera o backend (systemd) responder antes de abrir o navegador
for i in $(seq 1 120); do
    curl -s http://localhost:8080/api/status >/dev/null 2>&1 && break
    sleep 0.5
done

# Navegador em TELA CHEIA. Cobre os dois nomes de binario do Chromium.
CHROME="$(command -v chromium-browser || command -v chromium || echo chromium-browser)"
while true; do
    # --password-store=basic: nao usa o GNOME Keyring -> evita o popup do keyring ao ligar.
    "$CHROME" --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
        --disable-features=TranslateUI --check-for-update-interval=31536000 \
        --no-first-run --overscroll-history-navigation=0 --start-fullscreen \
        --password-store=basic \
        "http://localhost:8080" 2>/dev/null
    echo "[kiosk] navegador encerrou; reabrindo em 3s..."; sleep 3
done
