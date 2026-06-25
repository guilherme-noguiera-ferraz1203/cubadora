#!/usr/bin/env bash
# Remove TODA a instalacao da cubadora deste equipamento.
# Uso: curl -fsSL https://cubadora.specialcore.com.br/uninstall | sudo bash
#       ou: sudo bash /home/pi/cubagem-pi/python/deploy/uninstall.sh
#
# Limpa: services systemd, sudoers, autostarts (em /root e em /home/*), repo, backups e chaves do tunel.
# NAO apaga: config.yaml/cubagem.db/data salvos no ~/cubagem-pi/python (eles vao pra um .bak final).

echo "==================================================================="
echo " Cubadora — DESINSTALAR este equipamento"
echo "==================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "!! Precisa de root. Rode: sudo bash $0" >&2
    exit 1
fi

# 1) Parar e remover services systemd
for svc in cubagempi cubagempi-tunnel; do
    if systemctl list-unit-files | grep -q "^$svc.service"; then
        echo ">> Parando e desabilitando $svc.service..."
        systemctl disable --now "$svc" 2>/dev/null || true
        rm -f "/etc/systemd/system/$svc.service"
    fi
done
systemctl daemon-reload 2>/dev/null || true

# 2) Sudoers
if [ -f /etc/sudoers.d/cubagempi-nopasswd ]; then
    echo ">> Removendo /etc/sudoers.d/cubagempi-nopasswd"
    rm -f /etc/sudoers.d/cubagempi-nopasswd
fi

# 3) Autostarts (varre TODOS os homes + /root porque instalacoes antigas com 'sudo bash'
#    podem ter gravado em /root/.config/...).
for HOME_DIR in /root /home/*; do
    [ -d "$HOME_DIR" ] || continue
    for f in \
        "$HOME_DIR/.config/autostart/cubagem-kiosk.desktop" \
        "$HOME_DIR/.config/labwc/autostart" \
        "$HOME_DIR/.config/wayfire.ini"; do
        if [ -e "$f" ]; then
            echo ">> Limpando $f"
            case "$f" in
                *.desktop)
                    rm -f "$f"
                    ;;
                */labwc/autostart|*/wayfire.ini)
                    # remove apenas linhas com 'cubagem' do arquivo (preserva o resto)
                    sed -i '/cubagem/d' "$f" 2>/dev/null || true
                    # se o arquivo ficou vazio (so labwc), remove
                    [ -s "$f" ] || rm -f "$f"
                    ;;
            esac
        fi
    done
done

# 4) Repo + backups + chaves do tunel
for HOME_DIR in /root /home/*; do
    [ -d "$HOME_DIR" ] || continue
    if [ -d "$HOME_DIR/cubagem-pi" ]; then
        FINAL_BAK="$HOME_DIR/cubagem-pi.bak.$(date +%Y%m%d%H%M%S)"
        echo ">> Movendo $HOME_DIR/cubagem-pi -> $FINAL_BAK (preserva config.yaml e dados)"
        mv "$HOME_DIR/cubagem-pi" "$FINAL_BAK"
    fi
    for k in "$HOME_DIR/.ssh/cubadora-tunnel" "$HOME_DIR/.ssh/cubadora-tunnel.pub"; do
        if [ -e "$k" ]; then
            echo ">> Removendo chave do tunel $k"
            rm -f "$k"
        fi
    done
done

# 5) Lock do kiosk (instancia unica)
rm -f /tmp/cubagem-kiosk*.lock /run/user/*/cubagem-kiosk*.lock 2>/dev/null || true

echo ""
echo "==================================================================="
echo " Desinstalacao concluida. Para reinstalar:"
echo "   curl -fsSL https://cubadora.specialcore.com.br/install/<DEVICE_ID> | sudo bash"
echo "==================================================================="
