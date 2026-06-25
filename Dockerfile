# Servidor de frota da cubagem (painel central). Imagem mínima, sem dependências externas.
FROM python:3.12-slim

WORKDIR /app

# Só o pacote do servidor de frota é necessário (stdlib apenas).
COPY fleet ./fleet

# /data guarda o banco (fleet.db) e os pacotes de versão — monte como volume.
RUN mkdir -p /data/packages
ENV FLEET_PACKAGES=/data/packages
VOLUME ["/data"]

EXPOSE 9000

CMD ["python", "fleet/run.py", "--porta", "9000", "--db", "/data/fleet.db"]
