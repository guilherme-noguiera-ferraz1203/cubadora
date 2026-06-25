FROM alpine:3.20
RUN apk add --no-cache openssh-server tini && \
    ssh-keygen -A && \
    addgroup tunnel && \
    adduser -D -s /sbin/nologin -G tunnel tunnel && \
    # Conta sem senha (NAO bloqueada): sshd com PubkeyAuth nao precisa de senha, mas se a conta
    # esta "locked" (!) no /etc/shadow, ele rejeita "account is locked". passwd -u destrava.
    sed -i 's/^tunnel:!:/tunnel:*:/' /etc/shadow && \
    mkdir -p /home/tunnel/.ssh && \
    chown -R tunnel:tunnel /home/tunnel/.ssh && chmod 700 /home/tunnel/.ssh
COPY sshd_config /etc/ssh/sshd_config
EXPOSE 22
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
