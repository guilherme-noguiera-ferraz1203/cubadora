# TODO — reescrita Python (escopo completo)

Legenda: `[ ]` pendente · `[~]` versão funcional (precisa ajuste fino) · `[x]` feito

> Status: **paridade de funcionalidades atingida em simulação** — todas as áreas do sistema Java
> implementadas (63 módulos, 9 suítes de teste verdes). Restam: validação no hardware real,
> e o ajuste fino de alguns subsistemas que dependem de hardware/nuvem reais (ver `[~]`).

## Núcleo (Fases 1–7)
- [x] Config (YAML) + logging + log em memória
- [x] RS-485 (DE/BCM12) · ultrassônico (5 bytes, duplo, filtro, temperatura)
- [x] Modbus RTU + CLP · balança ATmega/I²C (Trentin/Weightech) + watchdog
- [x] Dimensões + persistência SQLite
- [x] Máquinas: estática, câmera, dinâmica/CLP, **ATM (estados)**

## Operacional (Onda 1)
- [x] Aferição/calibração (gate) · login/autologout · contadores completos
- [x] Parsing de etiqueta (posicional, regex, **DANFE/NF-e**, **CEP**)
- [x] Múltiplos volumes por nota + totalização
- [x] Todos os comandos do config.xml (`*r* *d* *ip* *tara* *i* *integracao* *fila* *limpar*
      *config* *spec* *bordas* *debug* *e* *cep* *danfe* *logout* *rede* *atualizar* *download*
      *manual* *plp* *qtd* *total* *485...`)

## Periféricos (Onda 2)
- [x] Leitor de código de barras (USB/serial/I²C + simulador)
- [x] LCD 16x2 (I²C PCF8574 + null + mock) + LcdView
- [x] Workers: heartbeat (LED), temperatura, botão de reboot

## Classificação / cabine (Onda 3)
- [x] Sorter (envio por destino, histórico, contagem, comando bruto *485)
- [x] ATM (máquina de estados da cabine)

## Visão (Onda 4)
- [x] Analisador OpenCV (contorno + minAreaRect) com calibração px→cm por altura
- [~] Fidelidade total ao photobox (color handler, compare.jpg, calibração A4 automática)

## Remoto / sistema (Onda 5)
- [x] Log em memória (/api/log) · admin web (status/cubagens/contadores/totalização/sorter/config)
- [x] **Edição de config pela web** (GET/POST por seção, persiste no YAML)
- [x] Nuvem (enviar/baixar/registrar — best-effort, desabilitada por padrão)
- [x] OTA (verificar/baixar/aplicar/reiniciar) + backup
- [x] Rede/Pi: Mount CIFS · TeamViewer · helpers Linux

## Onda 6 — calibração de sensores, comissionamento e gestão do Pi (web)
- [x] **Calibração dos sensores pela web** — leitura ao vivo + assistente de 2 objetos que
      CALCULA os fatores (fator/aux) automaticamente e salva
- [x] Limites mín/máx por sensor (web)
- [x] **Diagnóstico / comissionamento** — testa cada sensor, balança, erros; banner "APTO/NÃO APTO"
- [x] Tara real (registro Modbus configurável) + parâmetro Modbus da balança pela web
- [x] **Gestão do Pi/rede pela web** — hostname, Wi-Fi, IP (DHCP/estático), reiniciar/desligar/serviço

## Onda 7 — fluxo real de aferição (cubo + *cal*)
- [x] Comando **`*cal*`** calibra pelo cubo de aferição (recalibra offsets + peso, libera a máquina)
- [x] Reconhecimento do **código de barras do cubo** (`calibracao.codigo_cubo`) dispara o *cal*
- [x] **Status da integração por volume** na tela (painel + histórico) e na API
      (`ultima_integracao`, coluna `integracao`)

## Onda 8 — kiosk, status na tela e cubo editável
- [x] **Modo kiosk** (`--kiosk`, tela cheia, sem cursor, ESC sai) + `deploy/setup-kiosk.sh`
      (login automático + autostart no boot + auto-reinício + sem protetor de tela)
- [x] **Barra de status**: IP, tipo de conexão (Wi-Fi/Cabo) e nome da integração ativa (GUI + web)
- [x] **Cubo de aferição editável pela interface** (tela Calibrar: A/L/C/peso/código + Salvar +
      Aferir agora) — funciona com qualquer anteparo de medidas conhecidas

## Onda 9 — instalação multi-versão (Bullseye/Bookworm, Pi 3/4/5)
- [x] `install.sh` **detecta** modelo do Pi, versão do SO e sessão (X11/Wayland) antes de configurar
- [x] Dependências: `--break-system-packages` no Bookworm com fallback no Bullseye
- [x] **Porta serial** resolvida automaticamente (`/dev/serial0`→ttyAMA0→ttyS0) no código e no install
- [x] Autostart no mecanismo certo por versão: XDG (X11/LXDE) · `wayfire.ini` · `labwc/autostart`
- [x] Detecção de dispositivo exposta no log de start e na tela Sistema (modelo/SO/sessão)

## Onda 10 — repaginação da interface + kiosk Chromium + frota
- [x] **Painel web repaginado** (design system próprio): tela do operador com produção
      (volumes, vol/h, integrações ok/erro, totalização), histórico, alarmes, barra de status
- [x] **Config completa com tooltips (!)** em todos os campos + **editor de integração via API**
      flexível (adiciona/remove campos; nada fixo no código)
- [x] **Upload de logo** (splash inicial + topo)
- [x] **Kiosk via Chromium em tela cheia** (backend headless + navegador fullscreen no painel web)
- [x] **Pronto para frota**: device_id estável + `/api/identidade` + `/api/adopt` (config remota = local)
- [x] **Tema claro/escuro alternável** na configuração
- [ ] Splash de boot do Pi com a logo (plymouth) — opcional

## Onda 11 — atualização automática (OTA) + painel de frota
- [x] **Versão como código** (`cubagempi.__version__`), reportada pela máquina
- [x] **Agente de frota** no equipamento (`app/fleet_agent.py`): heartbeat (versão, unidade,
      status, produção, eventos/erros) + **auto-update** da versão-alvo
- [x] **OTA robusto** (`app/atualizacao.py`): baixa pacote, backup, extrai preservando
      config/banco/dados, reinicia
- [x] **Servidor de frota** (`fleet/`): heartbeats, dashboard estilo UniFi (versão/unidade/status/
      produção por máquina + histórico de erros ao clicar), versão-alvo, distribuição de pacotes
- [x] **publish.py**: 1 comando empacota o código e publica → frota atualiza sozinha
- [x] Testado o ciclo completo (heartbeat → registro → alvo → auto-update → eventos) + boot real
- [ ] Restauração automática da versão anterior se a nova falhar N vezes (refinamento)
- [ ] Autenticação/HTTPS no servidor de frota (produção)

## Pendências reais (precisam de hardware/nuvem)
- [ ] Validar no Raspberry Pi (8 sensores, balança, CLP, câmera reais)
- [ ] Endpoints exatos da nuvem Compudeck e do servidor de atualização (ajustar URLs)
- [ ] Fidelidade 1:1 do photobox (visão); deploy: imagem do cartão, fake-hwclock, splash
