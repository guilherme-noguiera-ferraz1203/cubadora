# Preview da UI do device cubagempi rodando em modo SIMULADO (sem hardware real).
# Serve a tela exata que aparece no kiosk do Raspberry Pi, para visualizacao no navegador.
# Risco: NENHUM - container isolado, nao toca em nada do host nem do SO dos equipamentos reais.
FROM python:3.12-slim

WORKDIR /app

# Deps minimas para o cubagempi subir em modo simulado.
RUN pip install --no-cache-dir pyserial PyYAML

# Copia o pacote cubagempi (+ scripts e config de exemplo).
COPY cubagempi ./cubagempi
COPY scripts ./scripts
COPY config.example.yaml ./config.example.yaml

# Config: usa o exemplo (modelo ESTATICA_2) com pequenas customizacoes para o preview.
RUN cp config.example.yaml config.yaml && \
    sed -i 's/^nome_equipamento:.*/nome_equipamento: "Cubadora · Preview"/' config.yaml

# Diretorio para banco persistente (opcional) e dados.
RUN mkdir -p /app/data

EXPOSE 8080

# Sobe sem --real (= simulado) e sem --gui.
CMD ["python", "scripts/run.py", "--no-gui", "--config", "config.yaml"]
