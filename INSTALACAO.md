# Guia de Instalação e Estado Atual — Cubagem PI (Python)

Este documento ensina **como instalar** o software (no seu PC para testes e no Raspberry Pi para
produção) e descreve **como o programa está funcionando hoje**.

> Para **operar** o equipamento (calibrar, medir, configurar a balança pela web) veja o
> [`MANUAL.md`](MANUAL.md). Para a engenharia do sistema original, veja
> [`../ANALISE-TECNICA.md`](../ANALISE-TECNICA.md).

---

## 1. Estado atual do programa

Reescrita completa em **Python** do sistema de cubagem (originalmente Java). Roda **em simulação no
PC** (sem hardware) e **no Raspberry Pi** com o hardware real, trocando só uma flag (`--real`).

- **64 módulos Python**, **13 suítes de teste** (todas passando).
- Sem dependências obrigatórias no modo simulado (PyYAML é opcional, para salvar config).

### Funcionalidades implementadas
| Área | Situação |
|---|---|
| Comunicação RS-485 (ultrassônico 5 bytes, Modbus, I²C/ATmega) | ✅ |
| 4 modelos de máquina: **estática, câmera, dinâmica/CLP, ATM** | ✅ |
| Cálculo de dimensões + persistência (SQLite) | ✅ |
| **Aferição pelo cubo** (`*cal*` lido do código de barras) | ✅ |
| Calibração de sensores pela web (leitura ao vivo + assistente de 2 objetos) | ✅ |
| **Cubo de aferição editável pela interface** (qualquer anteparo conhecido) | ✅ |
| Balança: peso ao vivo, tara, parâmetros Modbus, config pela web | ✅ |
| Leitor de código de barras (USB/serial/I²C) · LCD 16x2 | ✅ |
| **Integração via API totalmente editável** (não fixa) + status por volume + fila/retry | ✅ |
| Painel **web repaginado**: tela do operador (produção, histórico, alarmes), config com **tooltips**, calibrar, diagnóstico, sistema | ✅ |
| **Kiosk em tela cheia via Chromium** (o painel web É a tela do equipamento) + barra de status (IP, Wi-Fi/Cabo, integração) | ✅ |
| **Upload de logo** (splash + topo) · estatísticas de produção (volumes, vol/h, integrações ok/erro) | ✅ |
| **Pronto para frota** (device_id + adoção estilo UniFi; painel central = próxima fase) | ✅ |
| **Diagnóstico/comissionamento** (banner "APTO / NÃO APTO") | ✅ |
| Gestão do Pi/rede pela web (hostname, Wi-Fi, IP, reiniciar/desligar) | ✅ |
| **Instalação multi-versão** (Bullseye/Bookworm, Pi 3/4/5) | ✅ |
| Atualização OTA + nuvem | 🟡 esqueleto (precisa das URLs reais) |
| Visão (câmera) | 🟡 OpenCV funcional, não é cópia 1:1 do photobox |

### O que ainda depende do hardware/credenciais reais
- Validar leitura dos 8 sensores, balança, CLP e câmera **no equipamento físico**.
- URLs/credenciais reais da **nuvem** e do **servidor de atualização**.
- Ajuste fino do autostart em imagens Bookworm/Wayland (estrutura já cobre os 3 mecanismos).

---

## 2. Pré-requisitos

| | PC (testes) | Raspberry Pi (produção) |
|---|---|---|
| SO | Windows/Linux/Mac | Raspberry Pi OS (Bullseye ou Bookworm) |
| Python | 3.10+ | 3.10+ (já vem no Raspberry Pi OS) |
| Dependências | nenhuma (PyYAML opcional) | pyserial, smbus2, gpiozero, lgpio |
| Hardware | nenhum (simulado) | sensores, balança, transceptor RS-485, I²C |

---

## 3. Instalação no PC (modo simulado)

Serve para você **testar, treinar e configurar** sem o equipamento. Tudo é simulado.

### Passo 1 — Ter o Python
Confirme a versão (precisa ser 3.10 ou superior):
```bash
python --version
```

### Passo 2 — (Opcional) instalar o PyYAML
Só é necessário se você quiser **salvar configurações** pela web no PC:
```bash
pip install pyyaml
```

### Passo 3 — Rodar
Abra o terminal na pasta `python`:
```bash
cd C:\Users\User\Desktop\cubagem-pi\python

python scripts/run.py            # abre a janela (GUI) + o painel web
# ou
python scripts/run.py --no-gui   # só o painel web (sem janela)
```
- Painel web: abra **http://localhost:8080** no navegador.
- Para "medir": digite uma etiqueta (ex.: `CAIXA1`) e tecle Enter, ou use o botão **Medir**.
- Para "aferir" no simulado: digite `*cal*` (simula a leitura do cubo).

### Passo 4 — (Opcional) rodar os testes
```bash
python tests/test_fluxo_cubo.py
python tests/test_calibracao_diag.py
# ... ou todos, se tiver o pytest:
pip install pytest && pytest tests/
```

---

## 4. Instalação no Raspberry Pi (produção)

### Passo 1 — Preparar o cartão
Grave o **Raspberry Pi OS (com desktop)** no cartão (Raspberry Pi Imager). Bullseye ou Bookworm.
No primeiro boot, conclua o assistente e conecte à rede (Wi-Fi ou cabo).

### Passo 2 — Copiar o software
Copie a pasta `python/` para `/home/pi/cubagem-pi/python` (via `scp`, pendrive ou `git`). Ex.:
```bash
# de outro PC, via scp:
scp -r python pi@<IP-do-pi>:/home/pi/cubagem-pi/
```

### Passo 3 — Rodar o instalador (um comando)
```bash
cd /home/pi/cubagem-pi/python
bash deploy/install.sh
sudo reboot
```

O `install.sh` **detecta a versão do dispositivo** (modelo do Pi, versão do SO, X11/Wayland) e
configura tudo automaticamente:
- instala as dependências (lida com Bullseye **e** Bookworm);
- habilita **UART** e **I²C** e detecta a **porta serial** correta, gravando no `config.yaml`;
- instala o **Chromium** e configura o **auto-início em tela cheia** (kiosk): o equipamento abre
  o **painel web** em tela cheia no boot — essa é a tela do operador;
- ativa **login automático**, desliga o protetor de tela e deixa tudo **reiniciando sozinho** se cair.

### Passo 4 — Ajustar o config
Edite `/home/pi/cubagem-pi/python/config.yaml` (ou pela web, depois): `modelo_maquina`, endereços
dos sensores, faixas e os fatores de `ajustes`/`calibracao` (cubo). Veja o `MANUAL.md` (seções 3 e 4).

### Resultado
Depois do `reboot`, **basta ligar a energia**: o Pi dá boot, faz login sozinho e abre a tela do
sistema em **tela cheia**. O painel web continua acessível em `http://<IP-do-pi>:8080`.

### Instalação manual (se preferir não usar o script)
```bash
cd /home/pi/cubagem-pi/python
pip3 install --break-system-packages -r requirements.txt -r requirements-pi.txt   # Bookworm
# (no Bullseye, sem a flag: pip3 install -r requirements.txt -r requirements-pi.txt)
sudo raspi-config        # Interface Options: Serial (sem console) = ON; I2C = ON
bash deploy/setup-kiosk.sh   # configura o auto-início
sudo reboot
```

### Modo headless (sem monitor, só web)
Se o equipamento não tiver tela, use o serviço systemd em vez do kiosk:
```bash
sudo cp deploy/cubagempi.service /etc/systemd/system/
sudo systemctl enable --now cubagempi
journalctl -u cubagempi -f
```

---

## 5. Estrutura dos arquivos

```
python/
├─ scripts/run.py            ← INICIA o programa (--real, --kiosk, --no-gui, --config)
├─ config.example.yaml       ← modelo de configuração (copie para config.yaml)
├─ requirements*.txt         ← dependências (base / Raspberry Pi)
├─ deploy/
│  ├─ install.sh             ← instalador multi-versão (detecta + configura + kiosk)
│  ├─ setup-kiosk.sh         ← configura o auto-início (X11/Wayfire/labwc)
│  ├─ kiosk-run.sh           ← script que abre a app em tela cheia (com auto-reinício)
│  └─ cubagempi.service      ← serviço systemd (modo headless)
├─ cubagempi/                ← o programa
│  ├─ app/                   ← orquestração (app.py, main.py, login, contador, sistema, atualização)
│  ├─ config/                ← configuração (YAML) e modelos
│  ├─ hal/                   ← hardware: rs485, i2c, gpio (real + simulado)
│  ├─ drivers/               ← protocolos: ultrasonic, modbus, balança, clp, atmega, câmera, leitor, lcd
│  ├─ maquina/               ← lógica: estática, câmera, dinâmica, atm, sorter, hardware, workers
│  ├─ cubagem/               ← dimensões, calibração, etiqueta, nota+volumes
│  ├─ integracao/            ← ERP (REST), nuvem
│  ├─ persistence/           ← banco SQLite
│  ├─ vision/                ← análise de imagem da câmera
│  ├─ web/                   ← painel web (porta 8080)
│  ├─ gui/                   ← interface local (Tkinter / kiosk)
│  ├─ comandos/              ← comandos (*cal*, *ip*, *tara*, ...)
│  ├─ core/                  ← logging
│  └─ sim/                   ← simuladores de hardware (PC)
├─ tests/                    ← 13 suítes de teste
├─ INSTALACAO.md             ← este documento
├─ MANUAL.md                 ← manual de uso/operação
├─ COMO-RODAR.md             ← guia rápido
└─ TODO.md                   ← lista de tarefas / progresso
```

---

## 6. Conferindo se está tudo certo

| Verificação | Comando | Esperado |
|---|---|---|
| Programa importa | `python -c "import cubagempi"` | sem erro |
| Painel web no ar | abrir `http://<IP>:8080` | painel carrega |
| Testes | `python tests/test_fluxo_cubo.py` | `OK test_fluxo_cubo` |
| Porta serial (Pi) | `ls -l /dev/serial0 /dev/ttyAMA0` | existe ao menos uma |
| ATmega no I²C (Pi) | `i2cdetect -y 1` | aparece `04` |
| Modelo/SO detectados | tela **Sistema** (`/sistema`) | mostra modelo e SO |
| Diagnóstico dos sensores | tela **Diagnóstico** (`/diagnostico`) | sensores respondendo |

---

## 7. Primeiros passos depois de instalado (resumo)
1. **Configurar** (tela `/config` ou `config.yaml`): modelo da máquina, balança, sensores.
2. **Calibrar os fatores** uma vez (tela `/calibrar`, assistente de 2 objetos).
3. **Definir o cubo** de aferição (tela `/calibrar`, quadro "Cubo de aferição").
4. **Aferir** ao ligar: leia o cubo (código `*cal*`) → status verde.
5. **Operar**: leia o código de cada caixa → mede + integra + mostra status na tela.
> Detalhes completos no [`MANUAL.md`](MANUAL.md).

---

## 8. Atualizar o software
- **Manual**: substitua a pasta `python/` pela nova versão e reinicie (`sudo systemctl restart
  cubagempi` no headless, ou `sudo reboot` no kiosk).
- **OTA (pela rede)**: comando `*atualizar*` (precisa configurar as URLs do servidor de atualização).

---

## 9. Problemas comuns na instalação

| Sintoma | Causa provável / solução |
|---|---|
| `pip install` falha com "externally-managed-environment" | Bookworm: use `--break-system-packages` (o `install.sh` já faz) |
| Não abre em tela cheia no boot | confirme o login automático e rode de novo `bash deploy/setup-kiosk.sh`; veja a versão na tela Sistema |
| `/dev/ttyAMA0` não existe | o código tenta `/dev/serial0` e `ttyS0` sozinho; confira UART habilitada no `raspi-config` |
| Não acha o ATmega (`i2cdetect`) | habilite o I²C no `raspi-config`; confira a fiação SDA/SCL |
| Sensores sem resposta | baudrate (`rs485.baudrate`), fiação RS-485, pino DE (BCM12), porta serial liberada |
| Web não abre | confira o IP (comando `*ip*`), e se a porta 8080 não está em uso por outro processo |
| Permissão negada na serial/I²C | usuário precisa estar nos grupos `dialout` e `i2c` (`groups`) |
