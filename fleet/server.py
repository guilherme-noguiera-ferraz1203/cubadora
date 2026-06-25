"""Servidor de frota (stdlib http.server): heartbeats, dashboard e distribuição de versões."""

from __future__ import annotations

import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .db import FleetDB

log = logging.getLogger(__name__)

# Pasta dos pacotes de versão. Configurável por env (FLEET_PACKAGES) para persistir em volume Docker.
_PKG_DIR = os.environ.get("FLEET_PACKAGES") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "packages")


def versoes_disponiveis() -> list[str]:
    if not os.path.isdir(_PKG_DIR):
        return []
    return sorted(f[:-4] for f in os.listdir(_PKG_DIR) if f.endswith(".zip"))


_PAGE = """<!doctype html><html lang=pt-BR><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Frota — Cubagem</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,Arial,sans-serif}
body{background:#eef2f7;color:#0f172a;padding:18px}
h1{font-size:22px;margin-bottom:4px}.sub{color:#64748b;margin-bottom:16px}
.bar{background:#fff;border:1px solid #dbe3ec;border-radius:12px;padding:14px;margin-bottom:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
select,button{padding:9px 12px;border-radius:8px;border:1px solid #cbd5e1;font-size:14px}
button{background:#2563eb;color:#fff;border:none;cursor:pointer;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.dev{background:#fff;border:1px solid #dbe3ec;border-radius:12px;padding:14px;cursor:pointer}
.dev:hover{border-color:#2563eb}
.dev .top{display:flex;justify-content:space-between;align-items:center}
.dev .nome{font-weight:700;font-size:16px}.dev .uni{color:#64748b;font-size:13px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;font-weight:700}
.b-ok{background:#dcfce7;color:#15803d}.b-old{background:#fee2e2;color:#b91c1c}.b-off{background:#f1f5f9;color:#64748b}
.kv{color:#475569;font-size:13px;margin-top:8px}
#modal{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;padding:20px}
#modal .box{background:#fff;border-radius:14px;max-width:760px;width:100%;max-height:85vh;overflow:auto;padding:20px}
.ev{border-bottom:1px solid #eef2f7;padding:7px 0;font-size:13px;font-family:Consolas,monospace}
.ev .err{color:#b91c1c}.ev .warn{color:#b45309}
</style></head><body>
<h1>Frota de equipamentos</h1><div class="sub" id="resumo">—</div>
<div class="bar">
 <b>Versão alvo:</b> <span class="badge b-ok" id="alvo">—</span>
 <select id="selVer"></select>
 <button onclick="definirAlvo()">Definir versão alvo (atualiza todos)</button>
 <span style="color:#64748b;font-size:13px">Publique novas versões com <code>deploy/publish.py</code>.</span>
</div>
<div class="grid" id="grid"></div>
<div id="modal" onclick="if(event.target.id==='modal')fecha()"><div class="box" id="box"></div></div>
<script>
async function getj(u){return await (await fetch(u)).json()}
async function post(u,b){return await (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json()}
function online(last){if(!last)return false;return (Date.now()-new Date(last).getTime())<15*60*1000}
function verBadge(v,alvo){if(!v)return '<span class="badge b-off">?</span>';return v===alvo?'<span class="badge b-ok">'+v+'</span>':'<span class="badge b-old">'+v+' ↑</span>'}
let ALVO='';
async function carregar(){
 const vs=await getj('/api/versions');ALVO=vs.alvo||'';
 document.getElementById('alvo').textContent=ALVO||'(nenhuma)';
 document.getElementById('selVer').innerHTML=vs.disponiveis.map(v=>'<option '+(v===ALVO?'selected':'')+'>'+v+'</option>').join('')||'<option>(sem pacotes)</option>';
 const ds=await getj('/api/devices');
 let on=0;ds.forEach(d=>{if(online(d.last_seen))on++});
 document.getElementById('resumo').textContent=ds.length+' equipamento(s) · '+on+' online · '+(ds.length-on)+' offline';
 document.getElementById('grid').innerHTML=ds.map(d=>{const p=d.producao||{};const onl=online(d.last_seen);
  return `<div class="dev" onclick="detalhe('${d.device_id}')">
   <div class="top"><span class="nome">${d.nome||d.device_id}</span>${verBadge(d.versao,ALVO)}</div>
   <div class="uni"><span class="dot" style="background:${onl?'#22c55e':'#cbd5e1'}"></span>${onl?'online':'offline'} · ${d.unidade||'sem unidade'} · ${d.modelo||''}</div>
   <div class="kv">IP ${d.ip||'-'} · ${d.status||''} ${d.aferido?'':'· <b style=color:#b45309>não aferido</b>'}</div>
   <div class="kv">Volumes ${p.volumes||0} · Vol/h ${p.vol_h||0} · Integr. erro ${p.integracao_erro||0}</div>
  </div>`}).join('')||'<p style="color:#64748b">Nenhum equipamento ainda. Configure o servidor no equipamento (frota.servidor) e aguarde o heartbeat.</p>';
}
async function detalhe(id){const d=await getj('/api/device/'+id);const dev=d.device,ev=d.eventos;
 document.getElementById('box').innerHTML=`<h2 style="margin-bottom:8px">${dev.nome||id}</h2>
  <div style="color:#64748b;margin-bottom:12px">${dev.unidade||'sem unidade'} · ${dev.modelo||''} · versão ${dev.versao||'?'} · visto ${(dev.last_seen||'').replace('T',' ').substr(0,19)}</div>
  <h3 style="margin:10px 0 6px">Últimos avisos e erros</h3>
  ${ev.length?ev.map(e=>`<div class="ev"><span class="${e.nivel==='WARNING'?'warn':'err'}">[${e.nivel}]</span> ${e.mensagem} <span style="color:#94a3b8">(${(e.data||'').replace('T',' ').substr(0,19)})</span></div>`).join(''):'<p style="color:#64748b">Sem eventos registrados.</p>'}
  <div style="margin-top:14px"><button onclick="fecha()">Fechar</button></div>`;
 document.getElementById('modal').style.display='flex';
}
function fecha(){document.getElementById('modal').style.display='none'}
async function definirAlvo(){const v=document.getElementById('selVer').value;await post('/api/target',{versao:v});carregar()}
carregar();setInterval(carregar,5000);
</script></body></html>"""


def _make_handler(db: FleetDB):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode("utf-8"))

        def _read(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            return self.rfile.read(n) if n else b""

        def do_GET(self):
            u = urlparse(self.path)
            p = u.path
            if p == "/" or p.startswith("/index"):
                self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif p.startswith("/api/devices"):
                self._json(db.list_devices())
            elif p.startswith("/api/device/"):
                did = p.rsplit("/", 1)[-1]
                dev = db.get_device(did)
                self._json({"device": dev, "eventos": db.get_events(did, 100)} if dev else {"erro": "não encontrado"},
                           200 if dev else 404)
            elif p.startswith("/api/versions"):
                self._json({"alvo": db.get_config("versao_alvo"), "disponiveis": versoes_disponiveis()})
            elif p.startswith("/api/package/"):
                versao = p.rsplit("/", 1)[-1]
                caminho = os.path.join(_PKG_DIR, versao + ".zip")
                if os.path.exists(caminho):
                    with open(caminho, "rb") as f:
                        self._send(200, f.read(), "application/zip")
                else:
                    self._json({"erro": "pacote não encontrado"}, 404)
            else:
                self._json({"erro": "not found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            p = u.path
            if p.startswith("/api/heartbeat"):
                try:
                    payload = json.loads(self._read().decode("utf-8") or "{}")
                    db.upsert_device(payload)
                    db.add_events(payload.get("device_id", ""), payload.get("eventos", []))
                    self._json({"versao_alvo": db.get_config("versao_alvo")})
                except Exception as exc:  # noqa: BLE001
                    self._json({"erro": str(exc)}, 500)
            elif p.startswith("/api/target"):
                versao = json.loads(self._read().decode("utf-8") or "{}").get("versao", "")
                db.set_config("versao_alvo", versao)
                self._json({"versao_alvo": versao})
            elif p.startswith("/api/publish"):
                versao = (parse_qs(u.query).get("versao", [""])[0]).strip()
                if not versao:
                    self._json({"erro": "informe ?versao="}, 400)
                    return
                os.makedirs(_PKG_DIR, exist_ok=True)
                with open(os.path.join(_PKG_DIR, versao + ".zip"), "wb") as f:
                    f.write(self._read())
                db.set_config("versao_alvo", versao)
                log.info("Publicada versão %s (alvo da frota)", versao)
                self._json({"mensagem": f"Versão {versao} publicada e definida como alvo"})
            else:
                self._json({"erro": "not found"}, 404)

    return H


class FleetServer:
    def __init__(self, porta: int = 9000, db_path: str = "fleet.db"):
        self.porta = porta
        self.db = FleetDB(db_path)
        self._server: ThreadingHTTPServer | None = None

    @property
    def port(self) -> int:
        return self._server.server_address[1] if self._server else self.porta

    def start(self, background: bool = True) -> None:
        self._server = ThreadingHTTPServer(("0.0.0.0", self.porta), _make_handler(self.db))
        if background:
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        log.info("Servidor de frota em http://0.0.0.0:%d", self.porta)
        if not background:
            self._server.serve_forever()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
