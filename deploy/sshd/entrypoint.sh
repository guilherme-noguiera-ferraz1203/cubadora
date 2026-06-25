#!/bin/sh
# Gera host keys em volume persistente (sobrevive a rebuilds, evita "host key changed" no Pi).
set -e
KEYDIR=/etc/ssh/host_keys
mkdir -p "$KEYDIR"
for t in ed25519 rsa ecdsa; do
    K="$KEYDIR/ssh_host_${t}_key"
    [ -f "$K" ] || ssh-keygen -q -N "" -t "$t" -f "$K"
done
chmod 600 "$KEYDIR"/ssh_host_*_key 2>/dev/null || true
chmod 644 "$KEYDIR"/ssh_host_*_key.pub 2>/dev/null || true
exec /usr/sbin/sshd -D -e
