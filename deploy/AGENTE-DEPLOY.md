# Tutorial de deploy — para o agente da VPS

Você (agente) vai implantar o **painel de frota da cubadora** num container Docker e publicá-lo em
**https://cubadora.specialcore.com.br** usando o NGINX já existente na VPS. Siga os passos na ordem,
**verificando a saída esperada de cada um** antes de prosseguir. As ações são idempotentes onde possível.

> Premissas: a VPS é Linux (Debian/Ubuntu) com **Docker + Docker Compose v2** e **NGINX** já
> instalados, e o usuário tem permissão para `docker` e `sudo`. O domínio
> `cubadora.specialcore.com.br` já resolve para o IP desta VPS.

---

## 0. Pré-checagem (não altera nada)
```bash
docker --version
docker compose version
nginx -v
whoami
```
Esperado: versões do Docker/Compose/NGINX impressas. Se faltar Docker ou Compose, instale antes.

## 1. Obter o código
Repositório: **`guilherme-noguiera-ferraz1203/cubadora`** (GitHub, privado).
```bash
sudo mkdir -p /opt/cubagem-fleet
sudo chown "$USER":"$USER" /opt/cubagem-fleet
git clone git@github.com:guilherme-noguiera-ferraz1203/cubadora.git /opt/cubagem-fleet
cd /opt/cubagem-fleet
```
> O `Dockerfile`, `docker-compose.yml` e a pasta `fleet/` estão na raiz do repositório.
> Se já existir, atualize com `git -C /opt/cubagem-fleet pull` em vez de clonar.

**Acesso ao repositório (é privado):** o agente precisa de leitura. Use UMA destas opções:
- **Deploy key (recomendado):** na VPS, gere `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""`,
  e adicione o conteúdo de `~/.ssh/id_ed25519.pub` em
  *GitHub → repo cubadora → Settings → Deploy keys → Add* (somente leitura). Aí o `git clone` por
  SSH (acima) funciona.
- **HTTPS com token:** `git clone https://<TOKEN>@github.com/guilherme-noguiera-ferraz1203/cubadora.git /opt/cubagem-fleet`.
- **Tornar o repo público** (não há segredos no código; `config.yaml` é ignorado) — aí clona direto.

## 2. Subir o container
```bash
cd /opt/cubagem-fleet
docker compose up -d --build
```
Verifique:
```bash
docker ps --filter name=cubagem-fleet           # deve estar "Up"
curl -s http://127.0.0.1:9000/api/versions       # deve responder: {"alvo": "", "disponiveis": []}
```
Esperado: o `curl` retorna um JSON. Se não, veja `docker compose logs --tail=50`.

> O container expõe a porta **só em 127.0.0.1:9000** (não fica público). Dados persistem em
> `/opt/cubagem-fleet/fleet-data`.

## 3. Configurar o NGINX (site novo, sem tocar nos outros)
```bash
SITE=/etc/nginx/sites-available/cubadora.specialcore.com.br
sudo cp /opt/cubagem-fleet/deploy/nginx-cubadora.conf "$SITE"
sudo ln -sf "$SITE" /etc/nginx/sites-enabled/cubadora.specialcore.com.br
sudo nginx -t
```
**Só prossiga se `nginx -t` disser `syntax is ok` e `test is successful`.** Então:
```bash
sudo systemctl reload nginx
curl -s -H "Host: cubadora.specialcore.com.br" http://127.0.0.1/api/versions   # deve responder JSON
```
> Se o `nginx -t` reclamar de `/etc/nginx/proxy_params` inexistente, edite o
> `nginx-cubadora.conf` e troque os `include /etc/nginx/proxy_params;` pelas linhas `proxy_set_header`
> comentadas no fim do arquivo; rode `nginx -t` de novo.

## 4. HTTPS (Let's Encrypt)
```bash
sudo certbot --nginx -d cubadora.specialcore.com.br --non-interactive --agree-tos -m guilherme.ferraz1203@gmail.com
sudo nginx -t && sudo systemctl reload nginx
```
Esperado: certificado emitido; o certbot ajusta o site para 443/HTTPS. Se o certbot não estiver
instalado: `sudo apt-get install -y certbot python3-certbot-nginx`.

## 5. Proteger o painel (OBRIGATÓRIO — ele empurra atualizações para todas as máquinas)
```bash
sudo apt-get install -y apache2-utils
# defina a senha do admin (substitua SENHA_FORTE):
printf "admin:$(openssl passwd -apr1 'SENHA_FORTE')\n" | sudo tee /etc/nginx/.htpasswd-cubadora
# ativar no site: descomentar as 2 linhas auth_basic no bloco "location /"
sudo sed -i 's/# auth_basic /auth_basic /' /etc/nginx/sites-available/cubadora.specialcore.com.br
sudo nginx -t && sudo systemctl reload nginx
```
> Isso protege o **painel** e a **publicação de versões**, mas mantém abertos os endpoints que os
> equipamentos usam (`/api/heartbeat`, `/api/package`, `/api/versions`) — eles continuam funcionando.

## 6. Verificação final
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://cubadora.specialcore.com.br/api/versions   # 200
curl -s -o /dev/null -w "%{http_code}\n" https://cubadora.specialcore.com.br/                # 401 (protegido por senha)
```
Esperado: `/api/versions` = **200** (equipamentos acessam); a raiz `/` = **401** (painel pede senha). Pronto.

---

## Operação e manutenção
```bash
docker compose -f /opt/cubagem-fleet/docker-compose.yml logs -f      # logs do painel
docker compose -f /opt/cubagem-fleet/docker-compose.yml restart      # reiniciar

# atualizar o PRÓPRIO painel quando houver versão nova no git:
cd /opt/cubagem-fleet && git pull && docker compose up -d --build     # dados em fleet-data/ são preservados
```

## Resultado
- Painel: **https://cubadora.specialcore.com.br** (login admin).
- Em cada equipamento, configurar `frota.servidor: https://cubadora.specialcore.com.br` + `frota.unidade`.
- Publicar novas versões do dev: `python deploy/publish.py --servidor https://cubadora.specialcore.com.br --versao X --user admin --senha SENHA_FORTE`.
