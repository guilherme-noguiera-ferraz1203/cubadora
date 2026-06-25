# Subir o painel de frota na VPS (Docker + NGINX)

Objetivo: acessar **https://cubadora.specialcore.com.br** e cair no painel de frota, rodando num
container Docker, com o NGINX que já existe na VPS fazendo o proxy.

> O container expõe a porta **só no localhost** da VPS (`127.0.0.1:9000`). Quem fala com a internet
> é o **NGINX**, que já está instalado — só adicionamos um site novo. Nada dos outros sites é tocado.

---

## Passo 1 — Enviar o código para a VPS
Do seu PC (na pasta `python/`):
```bash
scp -r . usuario@SEU_VPS:/opt/cubagem-fleet
```
(ou via git). Só a pasta `fleet/` é usada na imagem, mas pode mandar tudo.

## Passo 2 — Subir o container
Na VPS:
```bash
cd /opt/cubagem-fleet
docker compose up -d --build
```
Confira:
```bash
docker ps                       # deve listar 'cubagem-fleet'
curl -s http://127.0.0.1:9000/api/versions   # deve responder JSON
```
Os dados (banco + pacotes) ficam em `/opt/cubagem-fleet/fleet-data` (persistem entre reinícios).

## Passo 3 — Apontar o NGINX para o container
```bash
sudo cp deploy/nginx-cubadora.conf /etc/nginx/sites-available/cubadora.specialcore.com.br
sudo ln -s /etc/nginx/sites-available/cubadora.specialcore.com.br /etc/nginx/sites-enabled/
sudo nginx -t            # valida a configuração
sudo systemctl reload nginx
```
Garanta que o DNS de `cubadora.specialcore.com.br` aponta para o IP da VPS.

## Passo 4 — HTTPS (recomendado)
```bash
sudo certbot --nginx -d cubadora.specialcore.com.br
```
O certbot ajusta o NGINX para HTTPS sozinho.

## Passo 5 — Proteger o painel (recomendado, é acesso público)
```bash
sudo apt-get install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd-cubadora admin
# descomente as 2 linhas auth_basic no nginx-cubadora.conf e recarregue:
sudo systemctl reload nginx
```

---

## Pronto. Agora:
- Acesse **https://cubadora.specialcore.com.br** → painel de frota.
- Em cada equipamento, configure:
  ```yaml
  frota:
    servidor: https://cubadora.specialcore.com.br
    unidade: "Nome da unidade"
    auto_update: true
  ```
- Para publicar uma nova versão (do seu PC):
  ```bash
  python deploy/publish.py --servidor https://cubadora.specialcore.com.br --versao 1.1.0
  ```
  > Se ativou o htpasswd, o `publish.py` precisará da credencial — me avise que eu adiciono o
  > suporte a usuário/senha no publish (hoje ele faz POST sem auth).

## Operação do container
```bash
docker compose logs -f          # ver logs do painel
docker compose restart          # reiniciar
docker compose pull && docker compose up -d --build   # atualizar a imagem do painel
```

## Atualizar o PRÓPRIO painel de frota no futuro
É só reenviar o código e `docker compose up -d --build`. Os dados em `fleet-data/` são preservados.
