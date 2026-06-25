# Manual de Uso — Cubagem PI (Python)

Sistema de cubagem (medição automática de **altura, largura, comprimento e peso** de volumes)
para Raspberry Pi. Este manual cobre: a **lógica** do sistema, **instalação**, **aferição/
calibração**, **operação** e a **configuração pela web** (com foco na **balança**).

> Documentos relacionados: [`COMO-RODAR.md`](COMO-RODAR.md) (passo a passo rápido),
> [`../ANALISE-TECNICA.md`](../ANALISE-TECNICA.md) (protocolos/hardware), [`TODO.md`](TODO.md).

---

## 1. Como funciona (a lógica)

### 1.1 Visão geral
O equipamento mede um volume e devolve **A × L × C (cm)**, **peso (kg)**, **volume (m³)** e
envia ao ERP. Existem 4 modelos de máquina (definidos em `modelo_maquina`):

| Modelo | Como mede dimensões | Peso |
|---|---|---|
| **ESTATICA_2** (este equipamento) | 8 sensores ultrassônicos (estação fixa) | balança serial via ponte ATmega/I²C |
| CAMERA | câmera (L×C) + ultrassônico (altura) | balança Modbus |
| DINAMICA_CLP | esteira + câmera + ultrassônico, controlada por CLP | balança Modbus |
| ATM | cabine fechada com sensores de porta | balança Modbus |

### 1.2 O ciclo de uma medição (modelo estático)
1. O operador **escaneia/digita a etiqueta** do volume (ou um comando).
2. O sistema lê a **balança** (em paralelo) e faz uma **varredura dos sensores** (N leituras,
   descartando o maior e o menor e tirando a média).
3. Converte distância → dimensão pelas **fórmulas de ajuste**:
   ```
   altura      = aux_altura      − distância_altura            / fator_altura
   largura     = aux_largura     − distância_fundo             / fator_largura
   comprimento = aux_comprimento − (dist_esquerda + dist_direita) / fator_comprimento
   ```
4. **Valida** se está dentro das faixas (mín/máx por sensor). Fora da faixa → recusa e pede
   reposicionar a caixa.
5. **Grava** no banco local (SQLite), atualiza contadores e **envia ao ERP** (com fila/retry).

### 1.3 Aferição (a "trava de segurança")
Ao ligar, a máquina começa **NÃO aferida** e não aceita cubagens reais. O operador coloca o
**objeto-padrão** (de tamanho/peso conhecidos, definidos em `calibracao`) e faz uma medição:
- Se A, L, C e peso baterem com o padrão (dentro da tolerância) → a máquina fica **aferida** e
  passa a aceitar cubagens reais.
- Enquanto não aferir, toda medição é tratada como tentativa de aferição.

Isso garante que o equipamento só opera quando está medindo corretamente.

### 1.4 Arquitetura (resumo)
- **HAL**: camada de hardware (RS-485, I²C, GPIO) com versão real (Pi) e simulada (PC).
- **Drivers**: ultrassônico (protocolo 5 bytes), Modbus RTU, balança (ATmega/Trentin), CLP,
  câmera, leitor de código de barras, LCD.
- **Máquinas**: estática, câmera, dinâmica, ATM.
- **App**: junta tudo + aferição + login + contadores + comandos + integração.
- **Interfaces**: painel **web** (porta 8080) e **GUI** local (tela touch).

---

## 2. Instalação

### 2.1 No PC (modo simulado — para testes/treinamento)
Não precisa de hardware nem instalar nada (Python 3.10+).
```bash
cd python
python scripts/run.py            # abre GUI + painel web (http://localhost:8080)
python scripts/run.py --no-gui   # só o painel web
```
Para salvar configurações pela web, instale o PyYAML: `pip install pyyaml`.

### 2.2 No Raspberry Pi — instalação automática (um comando)
1. Copie a pasta `python/` para `/home/pi/cubagem-pi/python`.
2. Rode o instalador (uma vez):
   ```bash
   cd /home/pi/cubagem-pi/python
   bash deploy/install.sh
   sudo reboot
   ```

O `install.sh` é **inteligente quanto à versão**: antes de configurar, ele **detecta**:
- o **modelo do Pi** (3 / 4 / 5),
- a **versão do Raspberry Pi OS** (Bullseye, Bookworm…),
- o tipo de **sessão gráfica** (X11 ou Wayland / Wayfire / labwc).

E então configura tudo **do jeito certo para aquela versão**:
- instala dependências (com `--break-system-packages` no Bookworm, sem ele no Bullseye);
- habilita **UART** e **I²C**, detecta a **porta serial** correta (`/dev/serial0`, `ttyAMA0`…) e já
  grava no `config.yaml`;
- ativa **login automático** e configura o **auto-início em tela cheia** no mecanismo certo
  (XDG autostart no X11; `wayfire.ini` no Wayfire; `labwc/autostart` no labwc);
- desliga o protetor de tela e deixa a aplicação **reiniciando sozinha** se cair.

> **Resultado:** depois do `reboot`, o operador só **liga a energia** → o Pi dá boot → a tela do
> sistema **abre sozinha em tela cheia**, em qualquer das versões suportadas.
> Para sair do kiosk em manutenção: tecla **ESC**. Painel web sempre em `http://<IP>:8080`.

### 2.3 Conferências no Pi
```bash
ls -l /dev/serial0 /dev/ttyAMA0   # qual porta serial existe?
i2cdetect -y 1                    # ATmega aparece no endereço 0x04? LCD no 0x27?
```
O modelo do Pi e a versão do SO detectados aparecem na tela **Sistema** (`/sistema`) e no log de
inicialização.

### 2.4 Reconfigurar o kiosk isoladamente
Se precisar refazer só a parte do auto-início (sem reinstalar tudo):
```bash
bash deploy/setup-kiosk.sh && sudo reboot
```
> Kiosk (com tela) e o serviço headless (`systemctl`) são **excludentes** — o instalador
> desabilita o serviço para não haver conflito na porta 8080. Para uma instalação **sem monitor**
> (headless, só web), use o `deploy/cubagempi.service` e rode com `--no-gui`.

---

## 3. Aferição e calibração (deixar tudo OK)

Há **dois níveis**, com finalidades diferentes:

| | Quando | O que faz | Onde |
|---|---|---|---|
| **Setup dos fatores** | 1 vez, na instalação | acerta a **escala** dos sensores (fator) | tela **Calibrar** (§3.4) |
| **Aferição pelo cubo (`*cal*`)** | **toda vez que liga** (dia a dia) | reajusta os **offsets** e o **peso** pelo cubo conhecido e **libera** a máquina | leitor de código de barras |

> Resumindo: o **fator** se acerta uma vez; depois, a cada ligada, o **cubo de aferição + `*cal*`**
> deixa o equipamento pronto em segundos (com a pequena margem de erro esperada).

### 3.1 Configurar o cubo de aferição (pela própria tela)
Cubo (ou **qualquer anteparo de medidas conhecidas**) com dimensões e peso conhecidos. A forma
mais fácil é pela tela **Calibrar** (`http://<IP>:8080/calibrar`), no quadro **"Cubo de aferição"**:
preencha **Altura, Largura, Comprimento, Peso** e clique **"Salvar cubo"**. (Há também o botão
**"Aferir agora"** para calibrar na hora.)

> **Como a calibração dispara:** o **código de barras do cubo contém o texto `*cal*`**. Quando o
> leitor lê o cubo, ele emite `*cal*` e a calibração acontece automaticamente — não precisa
> configurar nada para isso. (O campo `codigo_cubo` é **opcional**: só preencha se quiser um
> código de barras **alternativo** além do `*cal*`; normalmente fica vazio.)

| Campo | Significado |
|---|---|
| `altura` / `largura` / `comprimento` | dimensões reais do cubo/anteparo (cm) |
| `peso` | peso real (kg) |
| `range_sensor` / `range_peso` | margens de tolerância |
| `codigo_cubo` | (opcional) código alternativo além do `*cal*` |

> Como as dimensões são editáveis na interface, você **não depende de um cubo específico**:
> pode aferir com qualquer objeto de medidas conhecidas — informe os valores, salve, e use um
> cubo cujo código de barras seja `*cal*`.

### 3.2 Aferir ao ligar (o processo do dia a dia)
1. Ligue o equipamento (status fica **amarelo "Aferição"**).
2. Coloque o **cubo de aferição** na máquina.
3. **Leia o código de barras do cubo** (ou digite **`*cal*`** no campo de etiqueta).
4. O equipamento mede o cubo, **recalibra os offsets e o peso** para casar com o cubo conhecido,
   e mostra **"Aferição OK"** (status verde). A máquina passa a aceitar volumes reais.
5. Se o cubo não for detectado (sem leitura) → mensagem de erro; verifique a posição e repita.

> Atalho para bancada/testes: `modo_teste: true` no config **pula a aferição** (nunca em produção).

### 3.3 Operação após a aferição
Coloque uma caixa por vez e **leia o código de barras dela**. O sistema:
1. pega **largura, altura e comprimento** (ultrassônicos) e o **peso** (célula de carga);
2. **grava** o volume e **dispara a integração** configurada;
3. mostra na tela as **medidas** e o **status da integração** daquele volume (ver §5.4).

### 3.4 Setup inicial dos fatores — assistente de 2 objetos (uma vez)
Use a tela **Calibrar** (`http://<IP>:8080/calibrar`) na instalação, para acertar a **escala**:

**a) Leitura ao vivo** — distância de cada sensor + dimensões calculadas + peso, atualizando sozinho.

**b) Assistente de 2 objetos (calcula os fatores sozinho):**
1. Coloque o **objeto 1** (tamanho conhecido), informe A/L/C reais e **"Capturar ponto"**.
2. Troque pelo **objeto 2** (tamanho **diferente**), informe as medidas e **"Capturar ponto"**.
3. **"Calcular fatores"** → confira a proposta → **"Aplicar e salvar"**.
   > Use 2 objetos bem diferentes (um baixo e um alto) para a conta ficar precisa.

**c) Limites por sensor** — defina mín/máx (cm) de cada sensor (recusa leituras fora da faixa).

> Depois desse setup, no dia a dia basta a aferição pelo cubo (§3.2).

### 3.4 Calibrar os sensores pela web (assistente automático) — RECOMENDADO
Em vez de calcular os fatores na mão, use a tela **Calibrar** (`http://<IP>:8080/calibrar`):

**a) Leitura ao vivo** — mostra, atualizando sozinho, a **distância de cada sensor** (cm) e as
**dimensões calculadas** (A/L/C) + peso. Útil para ver na hora o efeito de qualquer ajuste.

**b) Assistente de 2 objetos (calcula os fatores sozinho):**
1. Coloque o **objeto 1** (de tamanho conhecido) na estação.
2. Preencha Altura/Largura/Comprimento reais dele e clique **"Capturar ponto"**.
3. Troque pelo **objeto 2** (tamanho **diferente**), preencha as medidas reais e **"Capturar ponto"**.
4. Clique **"Calcular fatores"** → o sistema resolve `fator` e `aux` de cada dimensão.
5. Confira a proposta e clique **"Aplicar e salvar"**. Pronto — fatores calibrados e gravados.

   > Use 2 objetos bem diferentes (ex.: um baixo e um alto) para a conta ficar precisa.

**c) Limites por sensor** — defina mín/máx (cm) de cada um dos 4 sensores e salve (recusa
medidas fora da faixa, evitando leituras erradas).

---

## 4. Configuração pela web

### 4.1 Como acessar
Com o programa rodando, abra no navegador (de qualquer PC/celular na mesma rede):
```
http://<IP-do-equipamento>:8080
```
- Não sabe o IP? Digite o comando **`*ip*`** no campo de etiqueta (mostra o IP), ou veja no
  rodapé da tela.
- A porta (8080) e as senhas ficam na seção `web` do config.

No painel você vê: **status colorido**, as medidas da última cubagem, histórico, e um campo
para **medir/enviar comandos**. No rodapé há o link **⚙️ Configuração**, que leva a:
```
http://<IP-do-equipamento>:8080/config
```

### 4.2 A tela de Configuração
A página `/config` carrega **todas as seções** editáveis (balança, ajustes, calibração,
sensores, RS-485, etiqueta, esteira). Cada seção tem um botão **"Salvar"** próprio — ao salvar,
a mudança é aplicada e **gravada no `config.yaml`**.

> Observação: mudanças de **ajustes/calibração** valem na hora. Mudanças de **hardware**
> (porta serial, baudrate, endereço I²C, casas decimais da balança I²C) podem exigir
> **reiniciar** o programa para valer 100%.

### 4.3 Configurando TUDO sobre a balança
A seção **balança** na tela `/config` tem todos os parâmetros. O que cada um faz:

| Campo | Para que serve | Quando mexer |
|---|---|---|
| `casa_decimal_peso` | divisor do valor lido → kg (ex.: 100 = peso em centésimos) | se o peso vier 100× errado |
| `ajuste_peso` | soma/desconto fixo no peso (kg) — tara fixa de software | calibrar o zero |
| `peso_minimo` | peso mínimo aceito (kg) | evitar leitura de "vazio" |
| `endereco` | endereço Modbus da balança (modelos dinâmicos) | conforme a balança |
| `registro_peso` | registro Modbus de onde ler o peso | conforme a balança |
| `i2c_address` | endereço I²C do ATmega (modelos estáticos) | padrão 4 |
| `i2c_serial_device` | "device" do ATmega que entrega a serial da balança | padrão 20 |
| `registro_tara` | registro Modbus para o comando de tara (0 = não usa) | se a balança tem tara via Modbus |

No topo da tela há duas ferramentas práticas para a balança:

**a) Peso ao vivo + Tara**
- **"Ler peso"** mostra o peso atual em kg (útil para conferir a balança).
- **"Tara (zerar)"** zera a balança. Em balança Modbus, escreve no `registro_tara` configurado.

**b) Parâmetro Modbus da balança**
Para balanças industriais que têm registros internos (ex.: Peso de Calibração, Estabilização,
SetPoint, Filtro). Informe **Registro** e **Valor** e clique **"Gravar parâmetro na balança"**.
Exemplos (do equipamento original):

| Parâmetro | Registro | Exemplo de valor |
|---|---|---|
| Peso de Calibração | 5001 | 8000 |
| Filtro (ms) | 5000 | 200 |
| SetPoint de Peso | 5400 | 1000 |
| Estabilização | 5404 | 430 |
| Medição | 5405 | 100 |

> Esses registros são gravados direto na balança via Modbus. Consulte o manual da sua balança
> para a lista de registros e valores corretos.

### 4.4 Pela API (automação)
Tudo o que a tela faz está disponível por HTTP (útil para scripts):
```bash
# ler toda a config
curl http://<IP>:8080/api/config

# alterar a balança (ajuste de peso e mínimo)
curl -X POST http://<IP>:8080/api/config -H "Content-Type: application/json" \
  -d '{"secao":"balanca","dados":{"ajuste_peso":"0.0","peso_minimo":"0.2"}}'

# ler o peso atual / tara
curl http://<IP>:8080/api/balanca/peso
curl -X POST http://<IP>:8080/api/balanca/tara -d '{}'

# gravar um parâmetro Modbus na balança
curl -X POST http://<IP>:8080/api/balanca/parametro -H "Content-Type: application/json" \
  -d '{"registro":5001,"valor":8000}'
```

### 4.5 Diagnóstico e comissionamento (deixar apto para produção)
Tela **Diagnóstico** (`http://<IP>:8080/diagnostico`) — use ao instalar e sempre que algo parecer
errado. Ela testa e mostra, atualizando sozinha:
- **cada sensor**: se está **respondendo** (✓/✗), a distância atual e a versão do firmware;
- **balança**: peso atual e se está OK;
- **aferição** e contadores de **erros** (checksum/timeout) do barramento;
- um **banner**: ✅ **APTO PARA PRODUÇÃO** ou ⛔ **NÃO APTO** (com o que falta).

Roteiro de comissionamento (do zero até produção):
1. **Diagnóstico** → confirme que os 8 sensores respondem (✓) e a balança lê peso.
2. **Calibrar** (§3.4) → rode o assistente de 2 objetos e aplique.
3. **Limites** dos sensores (§3.4c) e parâmetros da **balança** (§4.3).
4. **Aferição** (§3.3) com o objeto-padrão → status verde.
5. Volte ao **Diagnóstico** → banner deve ficar ✅ **APTO PARA PRODUÇÃO**.

### 4.6 Gestão do sistema e da rede (Raspberry Pi)
Tela **Sistema** (`http://<IP>:8080/sistema`):
- **Info do Pi**: hostname, IP, temperatura da CPU, uptime, disco livre.
- **Rede**: alterar **hostname**, configurar **Wi-Fi** (SSID/senha), e o **IP** (DHCP ou estático
  com IP/gateway/DNS). Salva direto no Raspberry Pi.
- **Energia/serviço**: **reiniciar o serviço** (aplica mudanças sem religar), **reiniciar** ou
  **desligar** o Pi.

> Essas ações de rede/energia só funcionam no Raspberry Pi (no PC aparecem como informativas).

---

## 5. Operação no dia a dia

> **Barra de status (sempre visível):** tanto na tela do equipamento (kiosk) quanto no painel web,
> o topo mostra o **IP** que o equipamento pegou, se está em **Wi-Fi** ou **Cabo**, e o **nome da
> integração ativa**. Assim o operador vê de relance se está em rede e conectado ao ERP.

### 5.1 Medir um volume
- **Com leitor de código de barras**: escaneie a etiqueta — a medição dispara sozinha.
- **Manual**: digite a etiqueta no campo (web ou GUI) e tecle Enter / **Medir**.

O status fica verde com as medidas, grava no banco e envia ao ERP automaticamente.

### 5.2 Comandos (digite no campo de etiqueta)
| Comando | Ação |
|---|---|
| `*cal*` | **calibra pelo cubo de aferição** que está na máquina (libera a operação) |
| `*ip*` | mostra o IP do equipamento |
| `*tara*` | tara a balança |
| `*e*` | liga/desliga o **modo envelope** (mede só o peso, dimensões = 1) |
| `*i*` | liga/desliga o envio ao ERP (integração) |
| `*integracao*` | reenvia a última cubagem ao ERP |
| `*fila*` | limpa a fila de integração |
| `*total*` | zera a totalização |
| `*config*` | mostra um resumo da configuração |
| `*spec*` | mostra versão/modelo/sensores |
| `*cep*` / `*danfe*` | liga/desliga os modos de etiqueta CEP / DANFE |
| `*logout*` | encerra a sessão (se login estiver ativo) |
| `*rede*` | mostra dados de rede |
| `*r*` / `*d*` | reinicia / desliga o equipamento |
| `*485 <end> <reg> <val>` | envia comando bruto ao sorter/CLP |

### 5.3 Etiquetas especiais
- **Nota + volumes**: escaneie `NOTA+3` para registrar uma nota com 3 volumes; depois escaneie
  cada volume (ative `etiqueta.nota_mais_volumes`).
- **DANFE/NF-e**: com `etiqueta.danfe` ligado, a chave de 44 dígitos é interpretada (CNPJ + nº da nota).
- **CEP**: com `etiqueta.modo_cep`, a etiqueta é tratada como CEP.

### 5.4 Status da integração na tela
A cada volume medido, o painel mostra:
- as **medidas** (A/L/C, peso, volume) da última cubagem;
- **"Integração do último volume"** com o status:
  - **enviado** — aceito pelo ERP;
  - **fila** — falhou no momento e ficou na fila (reenvia sozinho a cada 10 s);
  - **sem_integracao** / **desligada** — não há integração ativa ou o envio foi desligado (`*i*`);
- o **histórico** dos últimos volumes, com a coluna **Integr.** (status de cada um).

Tudo isso também está na API: `GET /api/status` (campo `ultima_integracao`) e
`GET /api/cubagens` (campo `integracao` por volume).

---

## 6. Solução de problemas

| Sintoma | O que verificar |
|---|---|
| Peso sempre 0 ou errado em 100× | `casa_decimal_peso`; conexão da balança; `i2cdetect -y 1` (deve ver 0x04) |
| "Sensor fora da faixa" | `minimo_sensor`/`maximo_sensor`; posição da caixa; calibração dos `ajustes` |
| Sensor sem resposta | fiação RS-485, baudrate (`rs485.baudrate`), pino DE (BCM12), `/dev/ttyAMA0` liberado |
| Não aceita cubagem (fica em "Aferição") | faça a aferição com o objeto-padrão (seção 3) |
| Não envia ao ERP | comando `*i*` (pode estar desligado); rede; token; ver `/api/log` |
| Não acho o IP | comando `*ip*`; `hostname -I` no Pi |
| Não salva config pela web | instale o PyYAML (`pip install pyyaml`) e rode com `--config <arquivo>` |

Logs:
- Painel web → `http://<IP>:8080/api/log`
- Serviço no Pi → `journalctl -u cubagempi -f`

---

## 7. Referência rápida de configuração (config.yaml)

```yaml
modelo_maquina: ESTATICA_2
modo_teste: false            # true pula a aferição (só em bancada)

rs485:
  serial_port: /dev/ttyAMA0
  baudrate: 115200
  de_pin_bcm: 12

balanca:
  casa_decimal_peso: 100.0
  ajuste_peso: 0.0
  peso_minimo: 0.2
  endereco: 2                # Modbus
  registro_peso: 400
  i2c_address: 4             # ATmega (estático)
  i2c_serial_device: 20
  registro_tara: 0

ajustes:                      # conversão distância -> dimensão (CALIBRAÇÃO)
  altura: 0.988
  aux_altura: 124.0
  largura: 0.995
  aux_largura: 66.0
  comprimento: 0.9829
  aux_comprimento: 82.0

calibracao:                   # cubo de aferição (usado pelo *cal*)
  altura: 15.0
  largura: 20.0
  comprimento: 25.0
  peso: 2.17
  range_sensor: 1.0
  range_peso: 0.2
  codigo_cubo: "CUBO-AFERICAO"   # código de barras do cubo (ler dispara o *cal*)

web:
  porta: 8080
```
