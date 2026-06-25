# Cubadora — sistema de cubagem + painel de frota

Reescrita em **Python** do sistema de cubagem Compudeck. Dois componentes:

1. **Equipamento** (roda em cada Raspberry Pi): mede altura/largura/comprimento/peso, tela do
   operador (kiosk), calibração, integração com ERP. Pacote `cubagempi/`.
2. **Painel de frota** (roda numa VPS central): gerencia **todas** as máquinas — versão, unidade,
   status, histórico de erros — e distribui atualizações. Pacote `fleet/`.

---

## 🚀 Deploy do PAINEL DE FROTA na VPS (Docker + NGINX)

> **Para um agente/operador na VPS:** o objetivo é publicar o painel de frota em
> **https://cubadora.specialcore.com.br** usando o NGINX já existente. Siga o tutorial completo,
> passo a passo e com saídas esperadas, em **[`deploy/AGENTE-DEPLOY.md`](deploy/AGENTE-DEPLOY.md)**.

Resumo (detalhes e segurança no tutorial):
```bash
# 1) clonar e subir o container (porta exposta só em 127.0.0.1:9000)
git clone <ESTE_REPO> /opt/cubagem-fleet && cd /opt/cubagem-fleet
docker compose up -d --build
curl -s http://127.0.0.1:9000/api/versions          # deve responder JSON

# 2) NGINX: site novo para o domínio (não toca nos outros sites)
sudo cp deploy/nginx-cubadora.conf /etc/nginx/sites-available/cubadora.specialcore.com.br
sudo ln -sf /etc/nginx/sites-available/cubadora.specialcore.com.br /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 3) HTTPS + senha do painel (recomendado)
sudo certbot --nginx -d cubadora.specialcore.com.br
# ver passo 5 do tutorial para o htpasswd
```
Arquivos do deploy: `Dockerfile`, `docker-compose.yml`, `deploy/nginx-cubadora.conf`,
`deploy/DEPLOY-VPS.md` (humano) e `deploy/AGENTE-DEPLOY.md` (passo a passo para agente).

---

## Rodar o EQUIPAMENTO (Raspberry Pi)
Instalação automática (detecta a versão do Pi/SO e configura o kiosk):
```bash
cd cubagem-pi/python && bash deploy/install.sh && sudo reboot
```
Para apontar o equipamento ao painel de frota, no `config.yaml`:
```yaml
frota:
  servidor: https://cubadora.specialcore.com.br
  unidade: "Nome da unidade"
  auto_update: true
```
Guias: **[`INSTALACAO.md`](INSTALACAO.md)** (instalar) · **[`MANUAL.md`](MANUAL.md)** (operar/calibrar)
· **[`GESTAO.md`](GESTAO.md)** (atualização automática + frota) · **[`COMO-RODAR.md`](COMO-RODAR.md)**.

## Rodar no PC sem hardware (simulado)
```bash
cd python
python scripts/run.py --no-gui     # painel em http://localhost:8080 (usa simuladores)
```

## Publicar uma nova versão para a frota (do dev)
```bash
python deploy/publish.py --servidor https://cubadora.specialcore.com.br --versao 1.1.0 --user admin --senha SENHA
```
→ os equipamentos baixam e atualizam sozinhos no próximo heartbeat.

## Estrutura
```
cubagempi/   aplicação do equipamento (config, hal, drivers, maquina, web, gui, integracao, app)
fleet/       servidor do painel de frota (db + http server + dashboard)
deploy/      Docker/NGINX/kiosk/instalador + publish.py + tutoriais de deploy
scripts/     run.py (inicia a aplicação), read_sensors.py (demo)
tests/       15 suítes de teste (rodam sem hardware via simuladores)
```

Versão atual: **v1.0.0**. Roadmap/itens em [`TODO.md`](TODO.md).
