"""Textos de ajuda (tooltips) dos campos de configuração — exibidos no ícone (!) do painel."""

# Ajuda por "secao.campo"
HELP = {
    # Equipamento
    "nome_equipamento": "Nome que aparece na tela e no painel de frota. Ex.: 'Cubadora Expedição 1'.",
    "modelo_maquina": "Tipo da máquina: ESTATICA_2 (estação fixa por ultrassônico), CAMERA, DINAMICA_CLP (esteira), ATM.",
    "casa_decimal_medidas": "Divisor das medidas para exibir/integrar. 1 = em cm.",
    # RS-485
    "rs485.serial_port": "Porta serial do barramento RS-485. No Pi normalmente /dev/serial0 ou /dev/ttyAMA0.",
    "rs485.baudrate": "Velocidade da comunicação serial (bits/s). Deve ser igual à dos sensores (ex.: 115200).",
    "rs485.timeout_ms": "Tempo máximo (ms) de espera pela resposta de um dispositivo no barramento.",
    "rs485.millis_min_write_interval": "Intervalo mínimo (ms) entre envios, para não colidir no barramento.",
    "rs485.de_pin_bcm": "Pino GPIO (numeração BCM) que controla o DE/RE do transceptor RS-485. Padrão 12.",
    # Sensores
    "sensor.enderecos": "Endereços do 1º sensor de cada lado (direita, fundo, esquerda, altura).",
    "sensor.enderecos2": "Endereços do 2º sensor (sensor duplo). 0 = sem segundo sensor.",
    "sensor.leituras": "Quantas varreduras por medição (mais = mais preciso, porém mais lento).",
    "sensor.delay_sensores_ms": "Pausa (ms) entre leituras dos sensores.",
    "sensor.minimo_sensor": "Distância mínima aceita por sensor (cm). Abaixo disso a medida é recusada.",
    "sensor.maximo_sensor": "Distância máxima aceita por sensor (cm). Acima disso a medida é recusada.",
    "sensor.endereco_temperatura": "Endereço do sensor de temperatura (corrige a velocidade do som). 0 = não usa.",
    # Ajustes (calibração de escala)
    "ajustes.altura": "Fator de escala da altura (perto de 1,0). Calibrado pelo assistente de 2 objetos.",
    "ajustes.aux_altura": "Offset da altura (cm) = altura de referência da estrutura vazia.",
    "ajustes.largura": "Fator de escala da largura.",
    "ajustes.aux_largura": "Offset da largura (cm).",
    "ajustes.comprimento": "Fator de escala do comprimento.",
    "ajustes.aux_comprimento": "Offset do comprimento (cm).",
    # Balança
    "balanca.casa_decimal_peso": "Divisor do valor lido para obter kg. Ex.: 100 = peso vem em centésimos.",
    "balanca.ajuste_peso": "Soma/desconto fixo no peso (kg). Tara de software (recalibrada pelo *cal*).",
    "balanca.peso_minimo": "Peso mínimo aceito (kg). Evita registrar leitura de plataforma vazia.",
    "balanca.endereco": "Endereço Modbus da balança (modelos dinâmicos).",
    "balanca.registro_peso": "Registro Modbus onde o peso é lido.",
    "balanca.i2c_address": "Endereço I²C do ATmega que faz a ponte com a balança serial (estática). Padrão 4.",
    "balanca.i2c_serial_device": "'Device' do ATmega que entrega a serial da balança. Padrão 20.",
    "balanca.registro_tara": "Registro Modbus do comando de tara (0 = não usa tara via Modbus).",
    # Calibração / cubo
    "calibracao.altura": "Altura real (cm) do cubo de aferição.",
    "calibracao.largura": "Largura real (cm) do cubo de aferição.",
    "calibracao.comprimento": "Comprimento real (cm) do cubo de aferição.",
    "calibracao.peso": "Peso real (kg) do cubo de aferição.",
    "calibracao.range_sensor": "Tolerância (cm) aceita na aferição das dimensões.",
    "calibracao.range_peso": "Tolerância (kg) aceita na aferição do peso.",
    "calibracao.codigo_cubo": "Opcional: código de barras alternativo do cubo. Normalmente o cubo já contém '*cal*'.",
    # Etiqueta
    "etiqueta.nota_mais_volumes": "Ativa o modo 'nota + volumes' (ex.: NF123+3).",
    "etiqueta.danfe": "Interpreta a chave de NF-e (44 dígitos) lida.",
    "etiqueta.modo_cep": "Trata a etiqueta como CEP.",
    "etiqueta.regex": "Expressão regular para extrair campos da etiqueta (grupos: nota, cnpj, cep...).",
    # Esteira / CLP
    "dinamica.clp_enabled": "Liga a comunicação com o CLP (esteira).",
    "dinamica.velocidade_esteira": "Velocidade configurada da esteira.",
    "dinamica.peso_min": "Peso mínimo válido (kg) na esteira.",
    "dinamica.peso_max": "Peso máximo válido (kg) na esteira.",
    # Web
    "web.porta": "Porta do painel web (padrão 8080).",
    # Leitor
    "leitor.modelo": "Tipo do leitor de código de barras: NENHUM, USB, SERIAL, I2C, VMS.",
    "leitor.com_port": "Porta serial do leitor (modelos SERIAL/USB).",
    # LCD
    "lcd.modelo": "Display: NENHUM ou I2C_16X2.",
}

# Ajuda dos campos da INTEGRAÇÃO via API (lista de chave/valor, igual ao sistema original)
INTEGRACAO_HELP = {
    "name": "Nome amigável da integração (aparece na tela do operador).",
    "enabled": "true para ativar esta integração; false para desligar.",
    "classe": "(interno) tipo de integração. Mantenha 'com.compudeck.cubagem.model.integracao.RestClient'.",
    "$target": "URL do endpoint do seu sistema (recebe POST). Pode conter $etiqueta, etc.",
    "header-Authorization": "Cabeçalho de autenticação. Ex.: 'Bearer SEU_TOKEN'.",
    "json": "Corpo JSON enviado. Use as variáveis $etiqueta, $peso, $altura, $largura, $comprimento, $data.",
    "medida-fator": "Multiplica as medidas (cm) antes de enviar. Ex.: 0.01 = enviar em metros.",
    "medida-format": "Formato dos números das medidas. Ex.: %.2f (2 casas decimais).",
    "peso-fator": "Multiplica o peso antes de enviar. Ex.: 1 = enviar em kg.",
    "peso-format": "Formato do número do peso. Ex.: %.2f",
    "locale": "Formato regional dos números. en_US usa ponto decimal (1.50); pt_BR usa vírgula.",
    "success-tag": "Texto que deve aparecer na resposta para considerar sucesso. '*' = qualquer resposta serve.",
    "accept-media-type": "Cabeçalho Accept enviado. Ex.: */* ou application/json.",
    "enable-command": "Comando digitado/escaneado que liga/desliga esta integração. Ex.: *i*",
    "timer": "true para reprocessar a fila de pendentes periodicamente.",
    "timeout": "Tempo limite (ms) da requisição. Ex.: 5000",
}

# Campos sugeridos ao criar uma nova integração (ordem amigável)
INTEGRACAO_CAMPOS_PADRAO = [
    "name", "enabled", "$target", "header-Authorization", "json",
    "medida-fator", "medida-format", "peso-fator", "peso-format",
    "locale", "success-tag", "accept-media-type", "enable-command", "timeout", "classe",
]


def help_para(secao: str, campo: str) -> str:
    return HELP.get(f"{secao}.{campo}") or HELP.get(campo, "")
