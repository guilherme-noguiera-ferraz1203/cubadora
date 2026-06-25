# Como rodar o cubagem-pi (Python)

Há dois cenários: **(A) no seu PC** (modo simulado, para desenvolver/testar) e **(B) no
Raspberry Pi** (hardware real, produção). O mesmo código serve para os dois — muda só o `--real`.

---

## A) No PC (simulado, sem hardware)

Nada de hardware é necessário: simuladores fazem o papel dos sensores, da balança e do CLP.

### 1. Requisitos
- Python 3.10+ (você já tem o 3.13). Nenhuma dependência obrigatória para o modo simulado.
- Opcional (para ler `config.yaml`): `pip install pyyaml`.

### 2. Rodar o programa completo (GUI local + painel web)
```bash
cd python
python scripts/run.py
```
- Abre a **janela do operador** (Tkinter).
- Sobe o **painel web** em http://localhost:8080
- Digite uma etiqueta (ex.: `CAIXA1`) e Enter → faz a medição simulada.
- Digite um comando (ex.: `*ip*`, `*i*`, `*config*`) → executa o comando.

### 3. Só o painel web (sem janela)
```bash
python scripts/run.py --no-gui
```
Acesse http://localhost:8080 no navegador.

### 4. Demo rápida de sensores (sem subir o programa todo)
```bash
python scripts/read_sensors.py
```

### 5. Rodar os testes
```bash
python tests/test_checksum.py
python tests/test_ultrasonic.py
python tests/test_balanca_modbus.py
python tests/test_maquina_app.py
# (ou todos de uma vez, se tiver pytest:  pip install pytest && pytest tests/)
```

### Trocar o modelo de máquina (estática / câmera / dinâmica)
Crie um `config.yaml` (baseado em `config.example.yaml`) e rode:
```bash
python scripts/run.py --config config.yaml --no-gui
```
Mude `modelo_maquina:` para `ESTATICA_2`, `CAMERA` ou `DINAMICA_CLP`.

---

## B) No Raspberry Pi (hardware real)

### 1. Copiar os arquivos
Copie a pasta `python/` para `/home/pi/cubagem-pi/python` (scp, git, pendrive...).

### 2. Instalar (uma vez)
```bash
cd /home/pi/cubagem-pi/python
bash deploy/install.sh
```
O instalador:
- instala Python, pip, i2c-tools e as dependências (`requirements*.txt`);
- habilita a **UART** (`/dev/ttyAMA0`) e o **I²C**, e desabilita o console serial;
- instala e habilita o serviço `cubagempi` no systemd.

> Se preferir manual: `pip3 install -r requirements.txt -r requirements-pi.txt` e habilite
> UART/I²C via `sudo raspi-config` (Interface Options → Serial = sem console; I2C = on). Reinicie.

### 3. Configurar
Crie `/home/pi/cubagem-pi/python/config.yaml` a partir de `config.example.yaml` e ajuste:
- `modelo_maquina` (ex.: `ESTATICA_2`)
- endereços dos sensores, faixas (`minimo_sensor`/`maximo_sensor`) e **fatores de ajuste**
  (`ajustes:`) — copie os valores do `etc/config.xml` da máquina atual para manter a calibração.

### 4. Rodar
```bash
# manualmente (para testar):
python3 scripts/run.py --config config.yaml --real --no-gui

# como serviço (produção):
sudo systemctl start cubagempi
sudo systemctl status cubagempi
journalctl -u cubagempi -f          # acompanhar os logs
```
Painel web: http://<ip-do-pi>:8080

### 5. Com tela touch local (GUI)
Edite `deploy/cubagempi.service`, remova `--no-gui`, descomente `Environment=DISPLAY=:0`,
depois `sudo systemctl daemon-reload && sudo systemctl restart cubagempi`.

---

## Verificações úteis no Pi
```bash
ls -l /dev/ttyAMA0          # a porta serial existe?
i2cdetect -y 1             # o ATmega aparece no endereço 0x04?
groups | grep -E 'dialout|i2c'   # o usuário tem permissão de serial/i2c?
```

## Diferenças PC × Pi
| | PC (simulado) | Raspberry Pi (real) |
|---|---|---|
| Flag | (nenhuma) | `--real` |
| RS-485 | `MockRs485` + simulador | `/dev/ttyAMA0` + DE em BCM12 (pyserial) |
| Balança | `AtmegaSimulator` / `ModbusSimulator` | ATmega I²C real / Modbus real |
| Câmera | `MockCamera` | `picamera2` (+ OpenCV) |
| GPIO | `MockOutputPin` | `gpiozero` |
