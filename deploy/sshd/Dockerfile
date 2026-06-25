FROM alpine:3.20
RUN apk add --no-cache openssh-server tini && \
    ssh-keygen -A && \
    addgroup -S tunnel && \
    adduser -D -S -s /sbin/nologin -G tunnel tunnel && \
    mkdir -p /home/tunnel/.ssh && \
    chown -R tunnel:tunnel /home/tunnel/.ssh && chmod 700 /home/tunnel/.ssh && \
    touch /home/tunnel/.ssh/authorized_keys && \
    chown tunnel:tunnel /home/tunnel/.ssh/authorized_keys && chmod 600 /home/tunnel/.ssh/authorized_keys
COPY sshd_config /etc/ssh/sshd_config
EXPOSE 22
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
