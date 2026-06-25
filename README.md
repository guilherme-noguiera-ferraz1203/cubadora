# cubagem-pi (Python)

Reescrita em **Python para Raspberry Pi** do sistema de cubagem Compudeck (originalmente Java).
Mede **altura, largura, comprimento e peso** de volumes e integra com ERP/nuvem.

> Especificação técnica completa (engenharia reversa do sistema Java): ver
> [`../ANALISE-TECNICA.md`](../ANALISE-TECNICA.md). Lista de tarefas: [`TODO.md`](TODO.md).

## Escopo (definido com o cliente)
- **Modelos:** estática (ultrassônico), câmera, e dinâmica/CLP (esteira) — escopo completo.
- **Hardware:** o mesmo do sistema atual (sensores com protocolo proprietário de 5 bytes,
  balança via ponte ATmega/I²C, Modbus RTU para CLP/balança dinâmica).
- **Interface:** GUI local (operador) + painel web (admin/suporte).
- **Integrações:** ERP (Vestra/ESL via REST) + nuvem Compudeck.

## Arquitetura (camadas)
```
cubagempi/
  config/      Carregamento de configuração (YAML) e modelos
  core/        Logging e utilidades transversais
  hal/         Hardware Abstraction Layer (RS-485, GPIO, I²C) — real (Pi) + mock (PC)
  drivers/     Protocolos: ultrassônico (5 bytes), Modbus RTU, balança, ATmega I²C
  cubagem/     Regras de negócio: cálculo de dimensões, calibração, fluxo de medição
  sim/         Simuladores de hardware para desenvolver/testar sem o Pi
scripts/       Utilitários de linha de comando / demos
tests/         Testes (rodam sem hardware via simuladores)
```

A HAL permite **desenvolver e testar no PC (Windows)** usando simuladores e depois rodar no
Raspberry Pi apenas trocando a implementação (mesma interface).

## Rodando a demo sem hardware (PC)
```bash
cd python
python scripts/read_sensors.py          # usa simulador de sensores
```
Opcional (para ler config de arquivo): `pip install pyyaml` e
`python scripts/read_sensors.py --config config.example.yaml`.

## No Raspberry Pi
```bash
pip install -r requirements.txt -r requirements-pi.txt
python scripts/read_sensors.py --config /home/pi/cubagem-pi/config.yaml --real
```

## Status
Em construção. Núcleo implementado até agora: camada RS-485, driver ultrassônico,
cálculo de dimensões e simulador. Próximas fases em `TODO.md`.
