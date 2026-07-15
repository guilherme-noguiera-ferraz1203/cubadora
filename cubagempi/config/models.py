"""Modelos de configuração (espelham as seções relevantes do etc/config.xml do Java)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ModeloMaquina(str, Enum):
    DINAMICA_PI = "DINAMICA_PI"
    DINAMICA_CLP = "DINAMICA_CLP"
    ESTATICA_1 = "ESTATICA_1"
    ESTATICA_2 = "ESTATICA_2"
    ESTATICA_LCD = "ESTATICA_LCD"
    CAMERA = "CAMERA"
    ATM = "ATM"


# Mapeia o enum de baudrate do Java (BaudrateRs485) para o valor numérico.
BAUDRATE_MAP = {
    "BPS_300": 300, "BPS_600": 600, "BPS_1200": 1200, "BPS_2400": 2400,
    "BPS_4800": 4800, "BPS_9600": 9600, "BPS_14400": 14400, "BPS_19200": 19200,
    "BPS_28800": 28800, "BPS_38400": 38400, "BPS_57600": 57600, "BPS_115200": 115200,
}


@dataclass
class ConfigRs485:
    serial_port: str = "/dev/ttyAMA0"
    baudrate: int = 115200
    timeout_ms: int = 50
    millis_min_write_interval: int = 5
    de_pin_bcm: int = 12          # linha DE/RE do transceptor (Pi4j GPIO_26 = BCM 12)
    use_lib_pi485: bool = True
    # Auto-direção: adaptadores USB-RS485 (FT232RL etc.) chaveiam TX/RX em HARDWARE — não há
    # pino GPIO para controlar. Com auto_dir=True (ou de_pin_bcm <= 0) o software não toca o
    # GPIO e não depende do gpiozero. Use junto com serial_port=/dev/ttyUSB0.
    auto_dir: bool = False


@dataclass
class ConfigSensorDistancia:
    enderecos: list[int] = field(default_factory=lambda: [11, 13, 15, 17])
    enderecos2: list[int] = field(default_factory=lambda: [12, 14, 16, 18])
    endereco_temperatura: int = 1
    leituras: int = 10
    leituras_ultrasonico: int = 1
    delay_ultrasonico: int = 1
    range_ultrasonico: int = 1
    tentativas: int = 1
    delay_inicio: int = 200            # ms de espera antes de iniciar (afastar-se)
    delay_sensores_ms: int = 10
    intervalo_minimo_endereco_ms: int = 0
    minimo_sensor: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    maximo_sensor: list[float] = field(default_factory=lambda: [124.0, 41.0, 41.0, 66.0])
    temperatura: float = 19.9
    ajuste_temperatura: float = 0.0
    intervalo_temperatura_s: int = 100


@dataclass
class ConfigAjustes:
    """Fatores de conversão distância(cm) -> dimensão(cm). Ver Config.java do Java."""
    altura: float = 0.988
    aux_altura: float = 124.0
    largura: float = 0.995
    aux_largura: float = 66.0
    comprimento: float = 0.9829
    aux_comprimento: float = 82.0


@dataclass
class ConfigBalanca:
    endereco: int = 2               # Modbus (modelos dinâmicos)
    registro_peso: int = 400
    peso_minimo: float = 0.2
    ajuste_peso: float = 0.0
    casa_decimal_peso: float = 100.0
    i2c_bus: int = 1                # ponte ATmega (modelos estáticos)
    i2c_address: int = 4
    i2c_serial_device: int = 20     # device 20 = serial 0 com checksum
    registro_tara: int = 0          # registro Modbus de tara (0 = não usa)
    peso_simulado: float = 2.17     # usado no simulador (PC)


@dataclass
class ConfigCamera:
    habilitada: bool = False
    comando: str = "picamera -n -awb fluorescent -co -20 -br 50 -ss 5500 -t 50 -w 1600 -h 900 -o /tmp/$etiqueta.jpg"
    arquivo: str = "/tmp/$etiqueta.jpg"
    delay_ms: int = 550
    largura_simulada: float = 37.0   # cm (usado no simulador/mock)
    comprimento_simulado: float = 31.0
    # Região de análise (recorte) na imagem, em pixels (0 = imagem inteira)
    crop_left: int = 0
    crop_top: int = 0
    crop_right: int = 0
    crop_bottom: int = 0
    # Calibração px->cm dependente da altura: escala = altura_a * altura_cm + altura_b
    altura_a: float = -0.00105763
    altura_b: float = 0.178915663
    rgb_threshold: int = 60          # limiar p/ separar a caixa do fundo


@dataclass
class ConfigDinamica:
    clp_enabled: bool = True
    endereco_clp: int = 1
    velocidade_esteira: int = 825
    millis_aguardar_cubagem: int = 2000
    altura_min: float = 5.0
    altura_max: float = 95.0
    largura_min: float = 5.0
    largura_max: float = 90.0
    comprimento_min: float = 5.0
    comprimento_max: float = 110.0
    peso_min: float = 0.4
    peso_max: float = 60.0


@dataclass
class ConfigCloud:
    target: str = "http://cloud.compudeck.com.br/cubagem/webresources"
    target_secure: str = "https://cloud.compudeck.com.br/cubagem/webresources"


@dataclass
class ConfigWeb:
    porta: int = 8080
    senha_admin: str = ""
    senha_cliente: str = ""
    senha_suporte: str = ""


@dataclass
class ConfigEtiqueta:
    tamanho_total: int = 0
    posicao_nota: int = 0
    tamanho_nota: int = 0
    posicao_quantidade_volumes: int = 0
    tamanho_quantidade_volumes: int = 0
    posicao_numero_volume: int = 0
    tamanho_numero_volume: int = 0
    posicao_cnpj: int = 0
    tamanho_cnpj: int = 0
    tamanho_cep: int = 0
    regex: str = ""
    nome_cep: str = "CEP"
    nota_mais_volumes: bool = False
    danfe: bool = False
    peso_nota_fiscal: bool = False
    modo_cep: bool = False


@dataclass
class ConfigCalibracao:
    """Cubo de aferição (dimensões/peso conhecidos) usado na calibração (*cal*)."""
    altura: float = 15.0
    largura: float = 20.0
    comprimento: float = 25.0
    peso: float = 2.17
    range_peso: float = 0.2
    range_sensor: float = 1.0
    codigo_cubo: str = ""           # código de barras do cubo (lido dispara a calibração)


@dataclass
class ConfigLogin:
    enabled: bool = False
    minutes_autologout: int = 10
    # usuários válidos (mapa usuário->senha em texto/MD5); vazio = qualquer um
    usuarios: dict = field(default_factory=dict)


@dataclass
class ConfigLeitor:
    """Leitor de código de barras / etiqueta."""
    modelo: str = "NENHUM"      # NENHUM | USB | SERIAL | I2C | VMS
    com_port: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    i2c_serial_device: int = 21  # device do ATmega p/ leitor (modelo I2C)


@dataclass
class ConfigLcd:
    modelo: str = "NENHUM"      # NENHUM | I2C_16X2
    i2c_bus: int = 1
    i2c_address: int = 0x27


@dataclass
class ConfigSorter:
    enabled: bool = False
    endereco_clp: int = 1
    registro_destino: int = 260
    envio_imediato: bool = False


@dataclass
class ConfigAtm:
    endereco_clp: int = 1
    registro_porta_fechada: int = 1020
    registro_objeto_presente: int = 1021


@dataclass
class ConfigFrota:
    """Identidade do equipamento + integração com o painel central de frota."""
    device_id: str = ""          # gerado a partir do serial/MAC se vazio
    unidade: str = ""            # unidade/local onde a máquina está (ex.: "CD São Paulo")
    servidor: str = ""           # URL do painel central de frota (ex.: https://frota.empresa.com)
    adotado: bool = False
    chave: str = ""              # chave de pareamento com o painel
    heartbeat_segundos: int = 300  # de quanto em quanto tempo reporta ao servidor
    auto_update: bool = True     # baixa e aplica a versão-alvo automaticamente


@dataclass
class ConfigKiosk:
    """Lockdown da tela local (modo produção): esconde abas de parametrização e bloqueia rotas."""
    modo_producao: bool = False  # True = só mostra Painel; Calibrar/Config/Diag/Sistema só via ?admin=<chave>
    chave_admin: str = ""        # se vazia, em modo produção, NINGUEM acessa as abas localmente


@dataclass
class AppConfig:
    modelo_maquina: ModeloMaquina = ModeloMaquina.ESTATICA_2
    casa_decimal_medidas: int = 1
    serial_maquina: str = ""
    versao: str = "0.1.0-py"
    nome_equipamento: str = "Cubadora"
    logo_path: str = "data/logo.png"
    tema: str = "claro"          # "claro" (referência, alto contraste) ou "escuro"
    rs485: ConfigRs485 = field(default_factory=ConfigRs485)
    sensor: ConfigSensorDistancia = field(default_factory=ConfigSensorDistancia)
    ajustes: ConfigAjustes = field(default_factory=ConfigAjustes)
    balanca: ConfigBalanca = field(default_factory=ConfigBalanca)
    camera: ConfigCamera = field(default_factory=ConfigCamera)
    dinamica: ConfigDinamica = field(default_factory=ConfigDinamica)
    cloud: ConfigCloud = field(default_factory=ConfigCloud)
    web: ConfigWeb = field(default_factory=ConfigWeb)
    etiqueta: ConfigEtiqueta = field(default_factory=ConfigEtiqueta)
    calibracao: ConfigCalibracao = field(default_factory=ConfigCalibracao)
    login: ConfigLogin = field(default_factory=ConfigLogin)
    leitor: ConfigLeitor = field(default_factory=ConfigLeitor)
    lcd: ConfigLcd = field(default_factory=ConfigLcd)
    sorter: ConfigSorter = field(default_factory=ConfigSorter)
    atm: ConfigAtm = field(default_factory=ConfigAtm)
    frota: ConfigFrota = field(default_factory=ConfigFrota)
    kiosk: ConfigKiosk = field(default_factory=ConfigKiosk)
    modo_teste: bool = False
    totalizacao_peso: bool = False
    # Lista de integrações (cada item = dict de parâmetros, igual ao listIntegracao do Java).
    integracao: list[dict] = field(default_factory=list)
