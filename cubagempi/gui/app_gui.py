"""GUI local do operador em Tkinter (substitui a tela Swing do Java).

Mostra status colorido, as medidas, peso e volume, e um campo para etiqueta/comando.
Roda na thread principal (requisito do Tkinter); a medição roda em thread separada.
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import font as tkfont

log = logging.getLogger(__name__)

_CORES = {"verde": "#166534", "amarelo": "#854d0e", "vermelho": "#991b1b"}


class GuiApp:
    def __init__(self, app, kiosk: bool = False):
        self.app = app
        self.kiosk = kiosk
        self.root = tk.Tk()
        self.root.title("Cubagem")
        self.root.configure(bg="#0f172a")
        self.root.geometry("820x560")

        if kiosk:
            # tela cheia, sem bordas, sem cursor — operação só com leitor/touch
            self.root.attributes("-fullscreen", True)
            self.root.config(cursor="none")
            # Esc sai do modo kiosk (manutenção)
            self.root.bind("<Escape>", lambda _e: self.root.attributes("-fullscreen", False))

        big = tkfont.Font(size=40, weight="bold")
        med = tkfont.Font(size=16)

        # barra de status: IP · conexão · integração ativa
        topo = tk.Frame(self.root, bg="#1e293b")
        topo.pack(fill="x")
        self.lbl_topo = tk.Label(topo, text="IP: — · — · Integração: —", font=tkfont.Font(size=13),
                                 bg="#1e293b", fg="#cbd5e1", anchor="w", padx=12, pady=6)
        self.lbl_topo.pack(fill="x")

        self.lbl_status = tk.Label(self.root, text="Aferição", font=tkfont.Font(size=22, weight="bold"),
                                   bg="#854d0e", fg="white", pady=14)
        self.lbl_status.pack(fill="x", padx=12, pady=12)

        grid = tk.Frame(self.root, bg="#0f172a")
        grid.pack(fill="x", padx=12)
        self.vals: dict[str, tk.Label] = {}
        for i, (chave, titulo) in enumerate([("altura", "Altura cm"), ("largura", "Largura cm"),
                                             ("comprimento", "Compr. cm"), ("peso", "Peso kg"),
                                             ("volume_m3", "Vol m³")]):
            card = tk.Frame(grid, bg="#1e293b")
            card.grid(row=0, column=i, padx=6, sticky="nsew")
            grid.columnconfigure(i, weight=1)
            v = tk.Label(card, text="-", font=big, bg="#1e293b", fg="white")
            v.pack(pady=(10, 0))
            tk.Label(card, text=titulo, font=med, bg="#1e293b", fg="#94a3b8").pack(pady=(0, 10))
            self.vals[chave] = v

        entry_frame = tk.Frame(self.root, bg="#0f172a")
        entry_frame.pack(fill="x", padx=12, pady=18)
        self.entry = tk.Entry(entry_frame, font=med, bg="#0b1220", fg="white", insertbackground="white")
        self.entry.pack(side="left", fill="x", expand=True, ipady=6)
        self.entry.bind("<Return>", lambda _e: self._enviar())
        tk.Button(entry_frame, text="Medir", font=med, bg="#2563eb", fg="white",
                  command=self._enviar).pack(side="left", padx=8)

        self.lbl_msg = tk.Label(self.root, text="", font=med, bg="#0f172a", fg="#fbbf24")
        self.lbl_msg.pack(fill="x", padx=12)
        self.lbl_info = tk.Label(self.root, text="", font=tkfont.Font(size=11), bg="#0f172a", fg="#64748b")
        self.lbl_info.pack(side="bottom", fill="x", padx=12, pady=6)

        self.entry.focus_set()
        self._atualizar()

    def _enviar(self) -> None:
        texto = self.entry.get().strip()
        self.entry.delete(0, tk.END)
        self.lbl_msg.config(text="Processando...")

        def tarefa() -> None:
            try:
                r = self.app.tratar_etiqueta(texto)
                msg = r.get("mensagem") or ("Medido" if r.get("tipo") == "cubagem" else "")
            except Exception as exc:  # noqa: BLE001
                msg = f"Erro: {exc}"
            self.root.after(0, lambda: self.lbl_msg.config(text=msg))

        threading.Thread(target=tarefa, daemon=True).start()

    def _atualizar(self) -> None:
        s = self.app.status_dict()
        cor = _CORES.get(s["status_cor"], "#854d0e")
        self.lbl_status.config(text=s["status_texto"], bg=cor)
        rede = s.get("rede", {})
        self.lbl_topo.config(text=f"IP: {rede.get('ip', '—')}  ·  {rede.get('tipo', '—')}  ·  "
                                  f"Integração: {s.get('integracao_nome', '—')}")
        cub = s.get("ultima_cubagem")
        if cub:
            for chave, lbl in self.vals.items():
                lbl.config(text=cub.get(chave, "-"))
        cont = s.get("contadores", {})
        self.lbl_info.config(text=f"Modelo: {s['modelo']}{' (simulado)' if s['simulado'] else ''}  |  "
                                  f"Cubagens: {cont.get('cubagem', 0)}  |  Versão: {s['versao']}")
        self.root.after(500, self._atualizar)

    def run(self) -> None:
        self.root.mainloop()
