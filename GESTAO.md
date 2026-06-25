# Atualização automática e Painel de Frota

Este sistema permite **desenvolver, publicar uma versão e os equipamentos se atualizam sozinhos** —
sem precisar mexer em cada Pi. E um **painel central** mostra qual versão está em cada máquina, em
qual unidade, o status e o histórico de erros.

```
   VOCÊ (dev)              SERVIDOR DE FROTA            EQUIPAMENTOS (cada Pi)
  publish.py  ──zip──►   guarda pacote + "versão alvo"  ◄─heartbeat─  reporta versão, unidade,
  (1 comando)            dashboard da frota             (periódico)   status, produção, erros
                         define alvo = 1.1.0  ──────►   baixa, aplica e reinicia sozinho
```

- **Pull-based:** cada equipamento consulta o servidor periodicamente. Só o **servidor** precisa de
  endereço fixo; os Pis podem estar em unidades/redes diferentes, atrás de NAT.

---

## 1. Subir o servidor de frota (uma vez)

Num servidor central (um PC, VPS ou um Pi dedicado — não precisa ser um dos equipamentos):
```bash
cd cubagem-pi/python
python3 fleet/run.py --porta 9000
```
Abra **http://<ip-do-servidor>:9000** no navegador → é o **painel da frota**.

> Em produção, deixe rodando como serviço (systemd) e, se for acesso pela internet, atrás de
> HTTPS (proxy reverso). O banco fica em `fleet.db`; os pacotes em `fleet/packages/`.

## 2. Apontar cada equipamento para o servidor

No `config.yaml` de cada equipamento (ou pela tela **Sistema/Configuração**), seção `frota`:
```yaml
frota:
  servidor: http://<ip-do-servidor>:9000   # endereço do painel de frota
  unidade: "CD São Paulo"                    # onde a máquina está (aparece no painel)
  heartbeat_segundos: 300                    # de quanto em quanto reporta (padrão 5 min)
  auto_update: true                          # baixa e aplica a versão alvo sozinho
```
Pronto. No próximo heartbeat, o equipamento **aparece no painel** com nome, unidade, versão e status.

## 3. Publicar uma nova versão (o dia a dia do desenvolvimento)

Você desenvolve normalmente. Para liberar para a frota, **um comando**:
```bash
cd cubagem-pi/python
python deploy/publish.py --servidor http://<ip-do-servidor>:9000 --versao 1.1.0
```
Isso: (1) marca o código como versão `1.1.0`, (2) **empacota** só o código (sem config/dados),
(3) **envia** ao servidor e define como **versão alvo**.

A partir daí, **cada equipamento**, no próximo heartbeat, vê que há versão nova, **baixa, aplica
(preservando config/calibração/banco) e reinicia sozinho**. Em minutos toda a frota está atualizada.

> Você também pode definir a versão alvo manualmente no painel (dropdown + "Definir versão alvo"),
> útil para reverter para uma versão anterior já publicada.

## 4. O que o painel mostra (gerenciar a frota)

- **Lista de equipamentos** (estilo UniFi): cada card mostra **nome, unidade, versão, status,
  online/offline, IP e produção** (volumes, vol/h, integrações com erro).
- Versão **destacada em vermelho** quando está atrás da versão alvo (ainda vai atualizar).
- **Clique num equipamento** → histórico: **últimos avisos e erros** (erros de leitura, timeouts,
  falhas de integração, etc.), com data/hora.
- **Resumo no topo**: total de equipamentos, quantos online/offline, versão alvo atual.

## 5. Segurança das atualizações
- O equipamento faz **backup** do código atual em `bkp/<versao>` antes de aplicar.
- Config (`config.yaml`), banco (`cubagem.db`), dados e logo **nunca** são sobrescritos.
- Se a aplicação cair após atualizar, o **kiosk reinicia sozinho** (loop). (Restauração automática
  da versão anterior em caso de falha repetida é um próximo refinamento.)

---

## 6. Atualização manual (alternativa, sem servidor)
Se não usar o painel de frota, dá para atualizar na mão: copiar a pasta `python/` nova por cima
(preservando `config.yaml`/`cubagem.db`/`data/`) e reiniciar. Mas o objetivo do painel é
justamente **eliminar esse processo manual**.

## 7. Backup e migração
- **Configuração**: `config.yaml` · **Dados**: `cubagem.db` · **Logo**: `data/logo.png`.
- Migrar p/ outro Pi = copiar `python/` + esses arquivos + rodar `install.sh`.
- **Servidor de frota**: backup do `fleet.db` e da pasta `fleet/packages/`.

---

## Resumo do fluxo
| Ação | Comando / lugar |
|---|---|
| Subir o painel de frota | `python3 fleet/run.py --porta 9000` |
| Ver a frota | navegador em `http://<servidor>:9000` |
| Conectar um equipamento | `frota.servidor` + `frota.unidade` no config |
| Publicar nova versão | `python deploy/publish.py --servidor ... --versao X` |
| Equipamento atualiza | sozinho, no próximo heartbeat |
| Ver versão/unidade/erros de cada um | painel de frota (card + clique no equipamento) |
