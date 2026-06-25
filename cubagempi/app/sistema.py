"""Integração com o sistema operacional (rede, mount CIFS, TeamViewer).

Ações específicas de Linux/Raspberry Pi; no Windows retornam mensagem informativa.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import subprocess
import sys

log = logging.getLogger(__name__)


def detectar_dispositivo() -> dict:
    """Detecta modelo do Pi, versão do SO e tipo de sessão (X11/Wayland)."""
    info = {"modelo": "desconhecido", "os": "desconhecido",
            "sessao": os.environ.get("XDG_SESSION_TYPE", ""), "plataforma": sys.platform}
    try:
        with open("/proc/device-tree/model") as f:
            info["modelo"] = f.read().replace("\x00", "").strip()
    except Exception:  # noqa: BLE001
        pass
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("VERSION_CODENAME="):
                    info["os"] = line.split("=", 1)[1].strip().strip('"')
    except Exception:  # noqa: BLE001
        pass
    return info


def _linux() -> bool:
    return sys.platform.startswith("linux")


def get_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return socket.gethostbyname(socket.gethostname())


def tipo_conexao() -> str:
    """Retorna 'Wi-Fi', 'Cabo' ou o nome da interface da rota padrão."""
    if not _linux():
        return "Rede"
    try:
        out = subprocess.check_output(["ip", "route", "get", "8.8.8.8"], text=True)
        m = re.search(r"dev (\w+)", out)
        dev = m.group(1) if m else ""
        if dev.startswith("wlan"):
            return "Wi-Fi"
        if dev.startswith("eth"):
            return "Cabo"
        return dev or "—"
    except Exception:  # noqa: BLE001
        return "—"


def info_rede() -> dict:
    info = {"hostname": socket.gethostname(), "ip": get_ip()}
    if _linux():
        try:
            out = subprocess.check_output(["hostname", "-I"], text=True).strip()
            info["ips"] = out.split()
        except Exception:  # noqa: BLE001
            pass
    return info


def configurar_dhcp(interface: str = "eth0") -> str:
    if not _linux():
        return "Configuração de rede disponível apenas no Raspberry Pi"
    try:
        subprocess.run(["sudo", "dhclient", "-r", interface], check=False)
        subprocess.run(["sudo", "dhclient", interface], check=False)
        return f"DHCP renovado em {interface}"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao configurar rede: {exc}"


def montar_cifs(share: str, ponto: str, usuario: str = "", senha: str = "") -> str:
    if not _linux():
        return "Mount CIFS disponível apenas no Raspberry Pi"
    try:
        subprocess.run(["sudo", "mkdir", "-p", ponto], check=False)
        opts = f"username={usuario},password={senha}" if usuario else "guest"
        subprocess.run(["sudo", "mount", "-t", "cifs", share, ponto, "-o", opts], check=True)
        return f"Montado {share} em {ponto}"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao montar CIFS: {exc}"


def teamviewer_info() -> str:
    if not _linux():
        return "TeamViewer: disponível apenas no Raspberry Pi"
    try:
        out = subprocess.check_output(["teamviewer", "--info"], text=True)
        return out.strip()
    except Exception as exc:  # noqa: BLE001
        return f"TeamViewer indisponível: {exc}"


# ------------------------------------------------------------- Raspberry Pi
def _cpu_temp() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:  # noqa: BLE001
        return 0.0


def _uptime() -> str:
    try:
        with open("/proc/uptime") as f:
            seg = int(float(f.read().split()[0]))
        h, m = seg // 3600, (seg % 3600) // 60
        return f"{h}h{m:02d}m"
    except Exception:  # noqa: BLE001
        return "-"


def get_pi_info() -> dict:
    import shutil

    total, usado, livre = shutil.disk_usage("/" if _linux() else ".")
    dev = detectar_dispositivo()
    return {
        "hostname": socket.gethostname(),
        "ip": get_ip(),
        "tipo_conexao": tipo_conexao(),
        "cpu_temp": _cpu_temp(),
        "uptime": _uptime(),
        "disco_total_gb": round(total / 1e9, 1),
        "disco_livre_gb": round(livre / 1e9, 1),
        "plataforma": sys.platform,
        "modelo_pi": dev["modelo"],
        "os": dev["os"],
        "sessao": dev["sessao"],
    }


def set_hostname(nome: str) -> str:
    if not _linux():
        return "Definir hostname disponível apenas no Raspberry Pi"
    try:
        subprocess.run(["sudo", "hostnamectl", "set-hostname", nome], check=True)
        return f"Hostname alterado para {nome} (reinicie para aplicar)"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao alterar hostname: {exc}"


def configurar_wifi(ssid: str, senha: str, pais: str = "BR") -> str:
    if not _linux():
        return "Configuração de Wi-Fi disponível apenas no Raspberry Pi"
    conf = (f"country={pais}\nctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
            f"update_config=1\n\nnetwork={{\n  ssid=\"{ssid}\"\n  psk=\"{senha}\"\n}}\n")
    try:
        with open("/tmp/wpa_supplicant.conf", "w") as f:
            f.write(conf)
        subprocess.run(["sudo", "cp", "/tmp/wpa_supplicant.conf",
                        "/etc/wpa_supplicant/wpa_supplicant.conf"], check=True)
        subprocess.run(["sudo", "wpa_cli", "-i", "wlan0", "reconfigure"], check=False)
        return f"Wi-Fi configurado para a rede '{ssid}'"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao configurar Wi-Fi: {exc}"


def configurar_ip(modo: str = "dhcp", ip: str = "", gateway: str = "", dns: str = "",
                  interface: str = "eth0") -> str:
    """modo = 'dhcp' ou 'estatico'. Escreve no dhcpcd.conf (Raspberry Pi OS)."""
    if not _linux():
        return "Configuração de IP disponível apenas no Raspberry Pi"
    try:
        if modo == "estatico":
            bloco = (f"\ninterface {interface}\nstatic ip_address={ip}\n"
                     f"static routers={gateway}\nstatic domain_name_servers={dns}\n")
            with open("/tmp/dhcpcd_extra.conf", "w") as f:
                f.write(bloco)
            subprocess.run("sudo bash -c 'cat /tmp/dhcpcd_extra.conf >> /etc/dhcpcd.conf'",
                           shell=True, check=False)
            return f"IP estático {ip} configurado em {interface} (reinicie a rede)"
        configurar_dhcp(interface)
        return f"DHCP configurado em {interface}"
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao configurar IP: {exc}"


def reiniciar_servico(servico: str = "cubagempi") -> str:
    if not _linux():
        return "Reiniciar serviço disponível apenas no Raspberry Pi"
    subprocess.Popen(["sudo", "systemctl", "restart", servico])
    return f"Reiniciando o serviço {servico}..."
