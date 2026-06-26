"""Servidor de frota (stdlib http.server): heartbeats, dashboard e distribuição de versões."""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import urllib.error
import urllib.request
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


_PAGE = r"""<!doctype html><html lang=pt-BR><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Frota — Cubagem</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,Arial,sans-serif}
body{background:#eef2f7;color:#0f172a;padding:18px}
h1{font-size:22px;margin-bottom:4px}.sub{color:#64748b;margin-bottom:16px}
.bar{background:#fff;border:1px solid #dbe3ec;border-radius:12px;padding:14px;margin-bottom:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
input,select,button{padding:9px 12px;border-radius:8px;border:1px solid #cbd5e1;font-size:14px}
label{display:block;font-size:13px;font-weight:600;color:#334155;margin:10px 0 4px}
input{width:100%}
.cmd{background:#0f172a;color:#e2e8f0;border-radius:8px;padding:12px;font-family:Consolas,monospace;font-size:13px;word-break:break-all;margin:8px 0}
.hint{color:#64748b;font-size:13px;line-height:1.5}
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
#modal,#regmodal{position:fixed;inset:0;background:rgba(0,0,0,.5);display:none;align-items:center;justify-content:center;padding:20px}
#modal .box{background:#fff;border-radius:14px;max-width:760px;width:100%;max-height:85vh;overflow:auto;padding:20px}
#regmodal .box{background:#fff;border-radius:14px;max-width:560px;width:100%;max-height:85vh;overflow:auto;padding:20px}
.ev{border-bottom:1px solid #eef2f7;padding:7px 0;font-size:13px;font-family:Consolas,monospace}
.ev .err{color:#b91c1c}.ev .warn{color:#b45309}
</style></head><body>
<h1>Frota de equipamentos</h1><div class="sub" id="resumo">—</div>
<div class="bar">
 <b>Versões publicadas:</b> <span class="badge b-ok" id="nver">0</span>
 <span style="color:#64748b;font-size:13px">Publique com <code>deploy/publish.py</code>. Para atualizar/rollback, clique no equipamento.</span>
 <button onclick="abrirCadastro()" style="background:#16a34a;margin-left:auto">➕ Cadastrar equipamento</button>
</div>
<div class="grid" id="grid"></div>
<div id="modal" onclick="if(event.target.id==='modal')fecha()"><div class="box" id="box"></div></div>
<div id="regmodal" onclick="if(event.target.id==='regmodal')fechaReg()"><div class="box" id="regbox"></div></div>
<script>
async function getj(u){return await (await fetch(u)).json()}
async function post(u,b){return await (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)})).json()}
function idadeSeg(last){if(!last)return Infinity;return (Date.now()-new Date(last).getTime())/1000}
// Online de verdade: heartbeat e a cada ~10s; toleramos 3 perdidos (35s) antes de marcar offline.
function online(last){return idadeSeg(last)<35}
function hatempo(last){const s=idadeSeg(last);if(!isFinite(s))return 'nunca visto';if(s<60)return 'há '+Math.round(s)+'s';if(s<3600)return 'há '+Math.round(s/60)+'min';if(s<86400)return 'há '+Math.round(s/3600)+'h';return 'há '+Math.round(s/86400)+'d'}
function verBadge(v,alvo){if(!v)return '<span class="badge b-off">?</span>';return v===alvo?'<span class="badge b-ok">'+v+'</span>':'<span class="badge b-old">'+v+' ↑</span>'}
let VERSOES=[];
async function carregar(){
 const vs=await getj('/api/versions');VERSOES=vs.disponiveis||[];
 document.getElementById('nver').textContent=VERSOES.length;
 const ds=await getj('/api/devices');
 let on=0;ds.forEach(d=>{if(online(d.last_seen))on++});
 document.getElementById('resumo').textContent=ds.length+' equipamento(s) · '+on+' online · '+(ds.length-on)+' offline';
 document.getElementById('grid').innerHTML=ds.map(d=>{const p=d.producao||{};const onl=online(d.last_seen);const pend=!d.last_seen;
  return `<div class="dev" onclick="detalhe('${d.device_id}')">
   <div class="top"><span class="nome">${d.nome||d.device_id}</span>${pend?'<span class="badge b-old">aguardando</span>':verBadge(d.versao,d.versao_alvo)}</div>
   <div class="uni"><span class="dot" style="background:${pend?'#f59e0b':(onl?'#22c55e':'#cbd5e1')}"></span>${pend?'aguardando instalação':'<b style="color:'+(onl?'#15803d':'#64748b')+'">'+(onl?'online':'offline')+'</b> · visto '+hatempo(d.last_seen)} · ${d.unidade||'sem unidade'} · ${d.modelo||''}</div>
   ${pend?'<div class="kv" style="color:#b45309">Cadastrado — rode o link de instalação no Raspberry.</div>':`
   <div class="kv">IP ${d.ip||'-'} · ${d.status||''} ${d.aferido?'':'· <b style=color:#b45309>não aferido</b>'}</div>
   <div class="kv">Volumes ${p.volumes||0} · Vol/h ${p.vol_h||0} · Integr. erro ${p.integracao_erro||0}</div>`}
  </div>`}).join('')||'<p style="color:#64748b">Nenhum equipamento ainda. Clique em “Cadastrar equipamento” para gerar um link de instalação.</p>';
}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function nivelPt(n){return {WARNING:'Aviso',ERROR:'Erro',CRITICAL:'Crítico',INFO:'Info',DEBUG:'Debug'}[n]||n}
function limparMsg(m){let s=(m||'').split('\n')[0].trim();return s.replace(/^\d{2}:\d{2}:\d{2}\s+\w+\s+\[[^\]]+\]\s*/,'')}
function resumirEventos(ev){
 if(!ev||!ev.length) return '<p style="color:#15803d">✓ Tudo certo — sem avisos nem erros recentes.</p>';
 const g=[];ev.forEach(e=>{const msg=limparMsg(e.mensagem),nivel=e.nivel,u=g[g.length-1];if(u&&u.msg===msg&&u.nivel===nivel){u.n++;u.data=e.data}else g.push({msg,nivel,data:e.data,n:1})});
 return g.slice(0,40).map(x=>`<div class="ev"><span class="${x.nivel==='WARNING'?'warn':'err'}">${nivelPt(x.nivel)}</span> ${esc(x.msg)}${x.n>1?` <b>×${x.n}</b>`:''} <span style="color:#94a3b8">${(x.data||'').replace('T',' ').substr(11,8)}</span></div>`).join('');
}
function statusCmd(s){return {pendente:'⏳ na fila',enviado:'📨 enviado',executado:'✅ ok',erro:'❌ erro'}[s]||s}
function ksec(s){if(s<60)return s+'s';if(s<3600)return Math.round(s/60)+'min';return Math.round(s/3600)+'h'}
function snapshot(est){
 if(!est)return '<p class="hint">Aguardando primeiro snapshot do equipamento…</p>';
 const sis=est.sistema||{}, st=est.status||{}, di=est.diagnostico;
 const card=(t,v,extra)=>`<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;min-width:120px"><div style="color:#64748b;font-size:11px;text-transform:uppercase">${t}</div><div style="font-weight:700;font-size:18px">${v}</div>${extra?'<div style="font-size:11px;color:#64748b">'+extra+'</div>':''}</div>`;
 let html='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px">';
 if(sis.cpu_temp!=null)html+=card('CPU °C',sis.cpu_temp,sis.modelo_pi||'');
 if(sis.uptime)html+=card('Uptime',sis.uptime,'');
 if(sis.disco_livre_gb!=null)html+=card('Disco livre',sis.disco_livre_gb+' GB','de '+(sis.disco_total_gb||'?')+' GB');
 if(sis.ip)html+=card('IP',sis.ip,sis.tipo_conexao||'');
 if(st.status_texto)html+=card('Estado',st.status_texto,st.aferido?'aferido':'NAO aferido');
 if(st.integracao_nome)html+=card('Integração',st.integracao_nome,st.integracao_habilitada?'on':'off');
 const tot=st.totalizacao||{};if(tot.volume!=null)html+=card('Totalização',tot.volume+' m³',tot.quantidade+' vol');
 html+='</div>';
 if(di){
  const ok=di.apto_producao?'✅ apto':'⚠️ com problemas';
  const sensores=(di.sensores||[]).map(s=>(s.respondendo?'✓':'✗')+s.endereco).join(' ');
  html+=`<div class="hint">Último diagnóstico: <b>${ok}</b> · sensores: ${sensores||'-'} · balança: ${di.balanca?.ok?'✓ '+di.balanca.peso+'kg':'✗'}${di.ts?' · '+(di.ts||'').replace('T',' ').substr(11,8):''}</div>`;
 }
 return html;
}
async function cmd(id,tipo,parametros){
 if((tipo==='reboot'||tipo==='shutdown')&&!confirm('Confirmar '+tipo+' no equipamento?'))return;
 const r=await post('/api/command',{device_id:id,tipo,parametros:parametros||{}});
 if(r&&r.erro){alert('Erro: '+r.erro);return}
 setTimeout(()=>detalhe(id),1500);
}
async function cmdTexto(id){const t=document.getElementById('cmdtxt').value.trim();if(t)await cmd(id,'comando',{texto:t})}
async function cmdConfig(id){const sec=document.getElementById('cfgsec').value.trim();let dd={};try{dd=JSON.parse(document.getElementById('cfgdados').value||'{}')}catch(e){alert('JSON inválido em Dados');return}if(sec)await cmd(id,'config',{secao:sec,dados:dd})}
async function cmdConfigKiosk(id,on){await cmd(id,'config',{secao:'kiosk',dados:{modo_producao:on}})}
async function limparHist(id){if(!confirm('Apagar TODO o histórico de avisos/erros deste equipamento?'))return;
 const r=await post('/api/events/clear',{device_id:id}); alert((r.removidos||0)+' eventos removidos'); detalhe(id)}
async function detalhe(id){const d=await getj('/api/device/'+id);const dev=d.device,ev=d.eventos||[],cmds=d.comandos||[];const onl=online(dev.last_seen);
 const optsVer=['<option value="">(não atualizar)</option>'].concat(VERSOES.map(v=>'<option value="'+v+'"'+(v===(dev.versao_alvo||'')?' selected':'')+'>'+v+'</option>')).join('');
 document.getElementById('box').innerHTML=`<h2 style="margin-bottom:4px">${esc(dev.nome||id)}</h2>
  <div style="color:#64748b;margin-bottom:6px"><span class="dot" style="background:${onl?'#22c55e':'#cbd5e1'}"></span><b style="color:${onl?'#15803d':'#64748b'}">${onl?'online':'offline'}</b> · visto ${hatempo(dev.last_seen)} · ${esc(dev.unidade||'sem unidade')} · ${esc(dev.modelo||'')} · versão ${esc(dev.versao||'?')}</div>

  <h3 style="margin:12px 0 6px">Versão &amp; atualização</h3>
  <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
   <span>atual: <b>${esc(dev.versao||'?')}</b></span>
   <span style="color:#64748b">alvo: ${dev.versao_alvo?esc(dev.versao_alvo):'(nenhum)'}</span>
   <select id="selVerDev">${optsVer}</select>
   <button onclick="setVersao('${id}')" style="background:#2563eb">Aplicar (update/rollback)</button>
  </div>
  ${VERSOES.length?'':'<div class="hint" style="margin-top:4px">Nenhuma versão publicada ainda — publique com <code>deploy/publish.py</code>.</div>'}

  <h3 style="margin:12px 0 6px">Estado do equipamento</h3>
  ${snapshot(dev.estado)}

  <h3 style="margin:12px 0 6px">Controles</h3>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
   <button onclick="window.open('/device/${id}/','_blank')" style="background:#7c3aed" ${dev.tunnel_port?'':'disabled title="Tunel nao registrado — atualize/reinstale o equipamento p/ esta versao"'}>🖥️ Abrir tela do equipamento</button>
   <button onclick="cmd('${id}','restart_app')" style="background:#f59e0b">⚡ Reiniciar app</button>
   <button onclick="cmd('${id}','update',{versao:dev.versao_alvo||''})" style="background:#2563eb" ${dev.versao_alvo?'':'disabled title="Defina a versao-alvo acima primeiro"'}>⬆️ Atualizar agora</button>
   <button onclick="cmd('${id}','diagnostico')" style="background:#0891b2">🩺 Rodar diagnóstico</button>
   <button onclick="cmd('${id}','reboot')" style="background:#dc2626">🔄 Reiniciar equipamento</button>
   <button onclick="cmd('${id}','shutdown')" style="background:#475569">⏻ Desligar</button>
  </div>

  <h3 style="margin:12px 0 6px">Modo produção (lockdown da tela local)</h3>
  <div class="hint" style="margin-bottom:6px">Quando ligado, a tela do equipamento mostra <b>SÓ a operação</b>: as abas Calibrar/Configuração/Diagnóstico/Sistema somem (e ficam liberadas só pelo painel da VPS).</div>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
   <button onclick="cmdConfigKiosk('${id}',true)" style="background:#16a34a">🔒 Ligar modo produção</button>
   <button onclick="cmdConfigKiosk('${id}',false)" style="background:#e2e8f0;color:#0f172a">🔓 Desligar (acesso completo local)</button>
  </div>
  ${onl?'':'<div class="hint" style="color:#b45309;margin-top:6px">Offline — o comando fica na fila e roda quando reconectar.</div>'}

  <h3 style="margin:14px 0 6px">Comando manual</h3>
  <div style="display:flex;gap:8px"><input id="cmdtxt" placeholder="texto do dispatcher (ex.: *tara*, *r*, *config*)" style="flex:1"><button onclick="cmdTexto('${id}')">Enviar</button></div>

  <h3 style="margin:14px 0 6px">Configuração remota</h3>
  <div style="display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap">
   <div style="width:150px"><label>Seção</label><input id="cfgsec" placeholder="ex.: frota"></div>
   <div style="flex:1;min-width:200px"><label>Dados (JSON)</label><input id="cfgdados" placeholder='{"heartbeat_segundos":10}'></div>
   <button onclick="cmdConfig('${id}')">Aplicar</button>
  </div>

  ${cmds.length?`<h3 style="margin:14px 0 6px">Comandos recentes</h3>${cmds.map(c=>`<div class="ev">${statusCmd(c.status)} <b>${esc(c.tipo)}</b>${c.parametros&&c.parametros.texto?' '+esc(c.parametros.texto):''}${c.resultado?' — '+esc(c.resultado):''} <span style="color:#94a3b8">${(c.ack_em||c.criado_em||'').replace('T',' ').substr(11,8)}</span></div>`).join('')}`:''}

  <h3 style="margin:14px 0 6px">Atividade (avisos e erros) <button onclick="limparHist('${id}')" style="background:#e2e8f0;color:#0f172a;font-size:12px;padding:4px 8px;margin-left:8px">🧹 Limpar histórico</button></h3>
  ${resumirEventos(ev)}

  <div style="margin-top:16px"><button onclick="fecha()" style="background:#e2e8f0;color:#0f172a">Fechar</button></div>`;
 document.getElementById('modal').style.display='flex';
}
function fecha(){document.getElementById('modal').style.display='none'}
async function setVersao(id){const v=document.getElementById('selVerDev').value;
 const msg=v?('Aplicar a versão '+v+' neste equipamento? Ele atualiza no próximo heartbeat.'):'Desligar a atualização deste equipamento (não atualizar)?';
 if(!confirm(msg))return;
 await post('/api/target',{device_id:id,versao:v});setTimeout(()=>detalhe(id),1000)}
function abrirCadastro(){
 document.getElementById('regbox').innerHTML=`
  <h2 style="margin-bottom:4px">Cadastrar equipamento</h2>
  <p class="hint" style="margin-bottom:6px">Informe os dados — o painel gera um instalador customizado pra essa placa e tipo de equipamento.</p>
  <label>Nome do equipamento *</label>
  <input id="regNome" placeholder="ex.: Cubadora Expedição 01">
  <label>Unidade (opcional)</label>
  <input id="regUni" placeholder="ex.: CD São Paulo">
  <div style="display:flex;gap:10px">
   <div style="flex:1">
    <label>Placa Raspberry *</label>
    <select id="regPlaca" style="width:100%">
     <option value="pi4">Raspberry Pi 4</option>
     <option value="pi5">Raspberry Pi 5</option>
     <option value="pi3">Raspberry Pi 3 / 3+</option>
    </select>
   </div>
   <div style="flex:1">
    <label>Tipo de equipamento *</label>
    <select id="regModelo" style="width:100%">
     <option value="ESTATICA_2" selected>Estática 2 (padrão)</option>
     <option value="ESTATICA_1">Estática 1</option>
     <option value="ESTATICA_LCD">Estática LCD</option>
     <option value="DINAMICA_PI">Dinâmica (PI)</option>
     <option value="DINAMICA_CLP">Dinâmica (CLP)</option>
    </select>
   </div>
  </div>
  <div style="margin-top:16px;display:flex;gap:8px">
   <button onclick="cadastrar()">Gerar link de instalação</button>
   <button onclick="fechaReg()" style="background:#e2e8f0;color:#0f172a">Cancelar</button>
  </div>`;
 document.getElementById('regmodal').style.display='flex';
 setTimeout(()=>{const e=document.getElementById('regNome');if(e)e.focus()},50);
}
function fechaReg(){document.getElementById('regmodal').style.display='none';carregar()}
async function cadastrar(){
 const nome=document.getElementById('regNome').value.trim();
 const unidade=document.getElementById('regUni').value.trim();
 const placa=document.getElementById('regPlaca').value;
 const modelo_maquina=document.getElementById('regModelo').value;
 if(!nome){alert('Informe o nome do equipamento');return}
 const r=await post('/api/register',{nome,unidade,placa,modelo_maquina});
 if(r.erro){alert(r.erro);return}
 document.getElementById('regbox').innerHTML=`
  <h2 style="margin-bottom:4px">✅ "${r.nome}" cadastrado</h2>
  <p class="hint">No Raspberry (via SSH), rode <b>um comando</b> para instalar e conectar este equipamento:</p>
  <div class="cmd" id="cmdTxt">${r.install_cmd}</div>
  <button onclick="copiar()">📋 Copiar comando</button>
  <p class="hint" style="margin-top:14px">
   • Já aparece no painel como <b>aguardando instalação</b>.<br>
   • Instalador customizado para <b>${r.placa||'?'}</b> + <b>${r.modelo_maquina||'?'}</b> — usa o código publicado no painel (sem GitHub).<br>
   • Depois do comando, ele instala, configura e começa a reportar sozinho.<br>
   • ID: <code>${r.device_id}</code>
  </p>
  <div style="margin-top:14px"><button onclick="fechaReg()" style="background:#e2e8f0;color:#0f172a">Fechar</button></div>`;
}
function copiar(){const b=event.target;const t=document.getElementById('cmdTxt').textContent;
 const ok=()=>{const o=b.textContent;b.textContent='✅ Copiado';setTimeout(()=>b.textContent=o,1500)};
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,ok)}else{ok()}}
carregar();setInterval(carregar,5000);
</script></body></html>"""


# URL do repositório de código do equipamento (clone público no Pi durante a instalação).
_REPO = os.environ.get("FLEET_REPO", "https://github.com/guilherme-noguiera-ferraz1203/cubadora.git")

# Caminhos / config do tunel reverso (autossh dos Pis -> container cubadora-sshd)
_TUNNEL_KEYS = os.environ.get("TUNNEL_KEYS_PATH", "/tunnel-keys/authorized_keys")
_TUNNEL_SSH_HOST_PUBLIC = os.environ.get("TUNNEL_HOST_PUBLIC", "cubadora.specialcore.com.br")
_TUNNEL_SSH_PORT_PUBLIC = int(os.environ.get("TUNNEL_PORT_PUBLIC", "2222"))
_TUNNEL_SSH_USER = os.environ.get("TUNNEL_USER", "tunnel")
# Hostname/porta do container sshd visto pelo fleet (proxy reverso interno)
_TUNNEL_BACKEND_HOST = os.environ.get("TUNNEL_BACKEND_HOST", "cubadora-sshd")


def _rewrite_authorized_keys(db) -> int:
    """Regenera /tunnel-keys/authorized_keys com TODOS os devices registrados.
    Cada chave fica restrita a fazer port-forward APENAS na porta do seu device, sem shell/X11/agent.
    Chamado quando devices registram chave nova."""
    linhas = []
    for d in db.list_tunnels():
        port = d["tunnel_port"]
        pk = (d["tunnel_pubkey"] or "").strip()
        if not pk or not port:
            continue
        # restricoes: so port-forward em 0.0.0.0:<port>, nada mais
        restr = (
            f'no-pty,no-user-rc,no-X11-forwarding,no-agent-forwarding,'
            f'permitlisten="0.0.0.0:{port}",permitlisten="127.0.0.1:{port}",command="/sbin/nologin"'
        )
        linhas.append(f"{restr} {pk}\n")
    os.makedirs(os.path.dirname(_TUNNEL_KEYS) or "/", exist_ok=True)
    with open(_TUNNEL_KEYS, "w") as f:
        f.writelines(linhas)
    try:
        # sshd no container roda como user 'tunnel' (uid 1000) e precisa ler o arquivo;
        # o arquivo é gravado pelo fleet (root). 0644 = sshd consegue ler; chave nao tem
        # segredo (so identifica o Pi), entao publico ler nao e problema.
        os.chmod(_TUNNEL_KEYS, 0o644)
        d = os.path.dirname(_TUNNEL_KEYS)
        if d: os.chmod(d, 0o755)
    except OSError:
        pass
    return len(linhas)

# Script de bootstrap servido em GET /install/<device_id>. Roda no Raspberry como:
#   curl -fsSL https://.../install/<id> | sudo bash
# Placeholders __X__ são substituídos por _bootstrap_script(); o bash usa $VAR normalmente.
_BOOTSTRAP = r"""#!/usr/bin/env bash
# Instalacao automatica da Cubadora — equipamento "__NOME__" (__UNIDADE__).
# Gerado pelo painel de frota. NAO edite: regenere cadastrando o equipamento de novo.
# Codigo distribuido pelo PROPRIO PAINEL (sem dependencia do GitHub):
#   curl -fsSL $SERVIDOR/api/package/latest -> /tmp/cubagem.zip -> unzip em APP_DIR.
set -euo pipefail

SERVIDOR="__SERVIDOR__"
DEVICE_ID="__DEVICE_ID__"
NOME="__NOME__"
UNIDADE="__UNIDADE__"
PLACA="__PLACA__"             # pi3 | pi4 | pi5 (escolhido no cadastro)
MODELO_MAQUINA="__MODELO__"   # ESTATICA_1 | ESTATICA_2 | ESTATICA_LCD | DINAMICA_PI | DINAMICA_CLP

echo "==================================================================="
echo " Cubadora — instalacao de '$NOME'"
echo " Unidade: ${UNIDADE:-(nao informada)} | Placa: $PLACA | Modelo: $MODELO_MAQUINA"
echo " Servidor: $SERVIDOR | ID: $DEVICE_ID"
echo "==================================================================="

if [ "$(id -u)" -ne 0 ]; then
  echo "!! Precisa de root. Rode:  curl -fsSL $SERVIDOR/install/$DEVICE_ID | sudo bash" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-pi}"
id "$TARGET_USER" >/dev/null 2>&1 || TARGET_USER="$(id -un)"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
[ -n "$TARGET_HOME" ] || TARGET_HOME="/home/$TARGET_USER"
APP_BASE="$TARGET_HOME/cubagem-pi"
APP_DIR="$APP_BASE/python"

# Detecta SO p/ escolher entre 'chromium-browser' (Bullseye) e 'chromium' (Bookworm/Trixie).
. /etc/os-release 2>/dev/null || true
CODENAME="${VERSION_CODENAME:-desconhecido}"
echo ">> SO detectado: $CODENAME"

echo ">> Dependencias do sistema (curl, unzip, python3, autossh)..."
apt-get update -y || true
apt-get install -y curl unzip python3 python3-pip python3-yaml autossh openssh-client i2c-tools unclutter || true
# Navegador do kiosk: pacote varia conforme SO/placa.
if ! command -v chromium-browser >/dev/null 2>&1 && ! command -v chromium >/dev/null 2>&1; then
    apt-get install -y chromium-browser 2>/dev/null || apt-get install -y chromium 2>/dev/null || \
        echo "   AVISO: nao instalou navegador (kiosk nao vai abrir ate isso ser resolvido)."
fi

# Backup automatico de instalacao anterior, NUNCA apaga.
if [ -e "$APP_DIR" ]; then
  BKP="$APP_DIR.bak.$(date +%Y%m%d%H%M%S)"
  echo ">> Instalacao anterior encontrada -> backup em $BKP"
  mv "$APP_DIR" "$BKP"
fi

echo ">> Baixando o codigo do painel ($SERVIDOR/api/package/latest)..."
mkdir -p "$APP_BASE" "$APP_DIR"
TMP_ZIP="$(mktemp --suffix=.zip)"
curl -fsSL --max-time 60 "$SERVIDOR/api/package/latest" -o "$TMP_ZIP"
unzip -oq "$TMP_ZIP" -d "$APP_DIR"
rm -f "$TMP_ZIP"
chown -R "$TARGET_USER":"$TARGET_USER" "$APP_BASE"

# Dependencias Python. Em Pi 3 (Bullseye) o lgpio costuma quebrar na compilacao
# (kernel/libgpiod antigos); RPi.GPIO + pyserial cobrem o que precisa nessa placa.
echo ">> Dependencias Python (placa=$PLACA, SO=$CODENAME)..."
PIP="pip3"
if [ "$CODENAME" = "bookworm" ] || [ "$CODENAME" = "trixie" ]; then
    PIP="pip3 --break-system-packages"
fi
$PIP install pyserial smbus2 gpiozero PyYAML || true
if [ "$PLACA" = "pi4" ] || [ "$PLACA" = "pi5" ]; then
    $PIP install lgpio || echo "   AVISO: lgpio nao instalou — gpiozero cai para outro backend."
else
    # Pi 3: lgpio raramente compila; usa RPi.GPIO como backend (gpiozero detecta).
    $PIP install RPi.GPIO || true
fi

# UART/I2C
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_serial_hw 0    2>/dev/null || true
    raspi-config nonint do_serial_cons 1  2>/dev/null || true
    raspi-config nonint do_i2c 0          2>/dev/null || true
fi
[ -e /dev/serial0 ] && PORTA="/dev/serial0" || PORTA="/dev/ttyAMA0"

# Sudoers: necessario p/ comandos remotos (reboot/poweroff/systemctl) sem TTY.
SUDOERS_TMP="$(mktemp)"
echo "$TARGET_USER ALL=(ALL) NOPASSWD: /sbin/reboot, /sbin/poweroff, /sbin/halt, /sbin/shutdown, /bin/systemctl, /usr/bin/systemctl" > "$SUDOERS_TMP"
visudo -cf "$SUDOERS_TMP" >/dev/null 2>&1 && install -m 440 "$SUDOERS_TMP" /etc/sudoers.d/cubagempi-nopasswd || true
rm -f "$SUDOERS_TMP"

# Configura systemd + kiosk usando o setup do proprio pacote.
echo ">> Configurando backend (systemd) e tela local (navegador)..."
APP_DIR="$APP_DIR" USER_ALVO="$TARGET_USER" bash "$APP_DIR/deploy/setup-kiosk.sh" || true

echo ">> Gravando identidade, frota e MODELO no config.yaml..."
[ -f "$APP_DIR/config.yaml" ] || cp "$APP_DIR/config.example.yaml" "$APP_DIR/config.yaml"
python3 - "$APP_DIR/config.yaml" "$NOME" "$UNIDADE" "$SERVIDOR" "$DEVICE_ID" "$MODELO_MAQUINA" "$PORTA" <<'PY'
import sys, yaml
cfg_path, nome, unidade, servidor, device_id, modelo, porta = sys.argv[1:8]
try:
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f) or {}
except FileNotFoundError:
    cfg = {}
cfg["nome_equipamento"] = nome
cfg["modelo_maquina"]   = modelo
rs485 = cfg.get("rs485") or {}
if porta: rs485["serial_port"] = porta
cfg["rs485"] = rs485
frota = cfg.get("frota") or {}
frota.update({"servidor": servidor, "unidade": unidade,
              "device_id": device_id, "auto_update": True})
frota["heartbeat_segundos"] = 10
cfg["frota"] = frota
with open(cfg_path, "w") as f:
    yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
print("   config gravado:", cfg_path, "modelo=", modelo)
PY
chown "$TARGET_USER":"$TARGET_USER" "$APP_DIR/config.yaml"

# Reinicia o backend para carregar a config de frota recem-gravada e comecar a reportar ja.
systemctl restart cubagempi 2>/dev/null || true

# ----- Tunel reverso (Fase 2): permite operar a tela do equipamento pelo painel -----
echo ">> Configurando tunel reverso (autossh)..."
SSH_DIR="$TARGET_HOME/.ssh"
KEY="$SSH_DIR/cubadora-tunnel"
sudo -u "$TARGET_USER" mkdir -p "$SSH_DIR" && chmod 700 "$SSH_DIR"
[ -f "$KEY" ] || sudo -u "$TARGET_USER" ssh-keygen -t ed25519 -N "" -f "$KEY" -C "cubadora-$DEVICE_ID" -q
# host key do servidor (evita prompt)
SSH_HOST_PORT_LINE="[$(echo "$SERVIDOR" | sed -E 's#https?://##; s#/.*##')]:2222"
sudo -u "$TARGET_USER" sh -c "ssh-keyscan -p 2222 -t ed25519 $(echo '$SERVIDOR' | sed -E 's#https?://##; s#/.*##') 2>/dev/null >> $SSH_DIR/known_hosts" || true
PUBKEY="$(cat "$KEY.pub")"
# registra a pubkey no painel; recebe porta+host+user
TUNNEL_JSON="$(curl -fsS --max-time 15 -X POST -H 'Content-Type: application/json' \
  -d "{\"pubkey\":\"$PUBKEY\"}" "$SERVIDOR/api/device/$DEVICE_ID/tunnel" || echo '{}')"
TUNNEL_PORT="$(echo "$TUNNEL_JSON" | python3 -c 'import sys,json;d=json.load(sys.stdin) if sys.stdin.isatty() is False else {};print(d.get("tunnel_port",""))' 2>/dev/null || true)"
TUNNEL_HOST="$(echo "$TUNNEL_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("ssh_host",""))' 2>/dev/null || true)"
TUNNEL_USER="$(echo "$TUNNEL_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("ssh_user","tunnel"))' 2>/dev/null || true)"
TUNNEL_SSH_PORT="$(echo "$TUNNEL_JSON" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("ssh_port",2222))' 2>/dev/null || true)"
if [ -n "$TUNNEL_PORT" ]; then
  TSVC=/etc/systemd/system/cubagempi-tunnel.service
  cat <<EOF | sudo tee "$TSVC" >/dev/null
[Unit]
Description=Cubadora tunel reverso (autossh) p/ painel da frota
After=network-online.target
Wants=network-online.target

[Service]
User=$TARGET_USER
Environment="AUTOSSH_GATETIME=0"
ExecStart=/usr/bin/autossh -M 0 -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$SSH_DIR/known_hosts -i $KEY -p $TUNNEL_SSH_PORT -R 0.0.0.0:$TUNNEL_PORT:127.0.0.1:8080 $TUNNEL_USER@$TUNNEL_HOST
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now cubagempi-tunnel
  echo "   tunel ativo na porta $TUNNEL_PORT (servidor $TUNNEL_HOST:$TUNNEL_SSH_PORT)"
else
  echo "   AVISO: registro do tunel falhou — tente novamente com: curl -fsSL $SERVIDOR/install/$DEVICE_ID | sudo bash"
fi

# O install.sh ja configurou o backend como servico systemd (cubagempi) — sobe sozinho no boot,
# independente do desktop — e a tela local pelo navegador. Nada a desabilitar aqui.
echo ">> Modo: backend por systemd + tela local pelo navegador (configurado pelo install.sh)."

echo ""
echo "==================================================================="
echo " Pronto! '$NOME' instalado. O backend ja roda e reporta ao painel:"
echo "   $SERVIDOR"
echo " Reinicie para a tela local abrir:  sudo reboot"
echo " Status do backend:  systemctl status cubagempi"
echo "==================================================================="
"""


def _bootstrap_script(servidor: str, device_id: str, nome: str, unidade: str,
                      placa: str = "pi4", modelo_maquina: str = "ESTATICA_2") -> str:
    return (_BOOTSTRAP
            .replace("__SERVIDOR__", servidor)
            .replace("__DEVICE_ID__", device_id)
            .replace("__NOME__", nome)
            .replace("__UNIDADE__", unidade)
            .replace("__PLACA__", placa or "pi4")
            .replace("__MODELO__", modelo_maquina or "ESTATICA_2"))


# Script de limpeza servido em GET /uninstall. Roda no Raspberry como:
#   curl -fsSL https://.../uninstall | sudo bash
# Remove services, sudoers, autostarts (em /root e /home/*) e move o repo pra backup.
_UNINSTALL = r"""#!/usr/bin/env bash
# Cubadora - desinstalar este equipamento (limpeza completa antes de reinstalar).
echo "==================================================================="
echo " Cubadora - DESINSTALAR este equipamento"
echo "==================================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "!! Precisa de root. Rode: curl -fsSL <servidor>/uninstall | sudo bash" >&2
    exit 1
fi

for svc in cubagempi cubagempi-tunnel; do
    if systemctl list-unit-files 2>/dev/null | grep -q "^$svc.service"; then
        echo ">> Parando e desabilitando $svc.service..."
        systemctl disable --now "$svc" 2>/dev/null || true
        rm -f "/etc/systemd/system/$svc.service"
    fi
done
systemctl daemon-reload 2>/dev/null || true

if [ -f /etc/sudoers.d/cubagempi-nopasswd ]; then
    echo ">> Removendo /etc/sudoers.d/cubagempi-nopasswd"
    rm -f /etc/sudoers.d/cubagempi-nopasswd
fi

for HOME_DIR in /root /home/*; do
    [ -d "$HOME_DIR" ] || continue
    for f in \
        "$HOME_DIR/.config/autostart/cubagem-kiosk.desktop" \
        "$HOME_DIR/.config/labwc/autostart" \
        "$HOME_DIR/.config/wayfire.ini"; do
        if [ -e "$f" ]; then
            echo ">> Limpando $f"
            case "$f" in
                *.desktop)
                    rm -f "$f"
                    ;;
                */labwc/autostart|*/wayfire.ini)
                    sed -i '/cubagem/d' "$f" 2>/dev/null || true
                    [ -s "$f" ] || rm -f "$f"
                    ;;
            esac
        fi
    done
done

for HOME_DIR in /root /home/*; do
    [ -d "$HOME_DIR" ] || continue
    if [ -d "$HOME_DIR/cubagem-pi" ]; then
        FINAL_BAK="$HOME_DIR/cubagem-pi.bak.$(date +%Y%m%d%H%M%S)"
        echo ">> Movendo $HOME_DIR/cubagem-pi -> $FINAL_BAK (preserva config.yaml e dados)"
        mv "$HOME_DIR/cubagem-pi" "$FINAL_BAK"
    fi
    for k in "$HOME_DIR/.ssh/cubadora-tunnel" "$HOME_DIR/.ssh/cubadora-tunnel.pub"; do
        [ -e "$k" ] && { echo ">> Removendo chave do tunel $k"; rm -f "$k"; }
    done
done

rm -f /tmp/cubagem-kiosk*.lock /run/user/*/cubagem-kiosk*.lock 2>/dev/null || true

echo ""
echo "==================================================================="
echo " Desinstalacao concluida. Para reinstalar, peca o link novo no painel"
echo " (cadastrar equipamento) ou rode novamente o curl do device existente."
echo "==================================================================="
"""


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

        def _base_url(self):
            # Atrás do nginx: respeita o domínio e o esquema (https) reais do request.
            proto = self.headers.get("X-Forwarded-Proto", "http")
            host = self.headers.get("Host") or self.headers.get("X-Forwarded-Host") or "localhost"
            return f"{proto}://{host}"

        def _tunnel_proxy(self, db):
            """Reverse proxy /device/<id>/<path>  ->  http://cubadora-sshd:<tunnel_port>/<path>.
            A request ja chega autenticada pelo nginx central (auth_basic do painel).
            O Pi precisa estar com autossh ativo para a porta tunelada estar de pe.

            Reescreve URLs absolutas no HTML/JS/CSS para incluir o prefixo /device/<id>/ —
            necessario porque o frontend do equipamento usa fetch('/api/...') (absoluto)."""
            parts = self.path.split("/", 3)   # ['', 'device', '<id>', '<resto>?qs']
            if len(parts) < 3:
                self._json({"erro": "rota invalida"}, 400); return
            did = parts[2]
            resto = "/" + (parts[3] if len(parts) > 3 else "")
            dev = db.get_device(did)
            if not dev or not dev.get("tunnel_port"):
                self._send(404, b"<h3>Tunel deste equipamento nao configurado.</h3>", "text/html; charset=utf-8"); return
            url = f"http://{_TUNNEL_BACKEND_HOST}:{dev['tunnel_port']}{resto}"
            data = self._read() if self.command in ("POST", "PUT", "PATCH") else None
            headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ("host", "content-length", "authorization", "connection")}
            prefix = f"/device/{did}"
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=self.command)
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read()
                    ctype = resp.headers.get("Content-Type", "") or ""
                    # Reescreve paths absolutos so em HTML/JS/CSS (nao em binarios/JSON)
                    if any(t in ctype for t in ("text/html", "javascript", "text/css")):
                        try:
                            txt = body.decode("utf-8")
                            # Reescreve paths absolutos -> /device/<id>/...
                            # Ordem importa: PRIMEIRO atributos HTML (href=/src=/action=), DEPOIS literals
                            # JS soltos. Senao um href="/calibrar" reescrito vira /device/.../device/.../...
                            for atr in ("href", "src", "action"):
                                for q in ('"', "'"):
                                    txt = txt.replace(f'{atr}={q}/', f'{atr}={q}{prefix}/')
                            # Literals JS (chamadas fetch, chaves de map, etc.). Apos os atributos,
                            # esses '/calibrar' que ja estao em href= viraram '/device/<id>/calibrar'
                            # entao o pattern nao acha mais a versao antiga -> sem duplicacao.
                            rotas = ("api/", "logo", "calibrar", "config", "diagnostico", "sistema")
                            for r in rotas:
                                for q in ('"', "'"):
                                    txt = txt.replace(f'{q}/{r}', f'{q}{prefix}/{r}')
                            # nao prefixar URLs absolutas (http*) — desfaz qualquer encavalamento
                            for bad in (prefix + '/http', prefix + '/https'):
                                txt = txt.replace(bad, '/' + bad[len(prefix)+1:])
                            body = txt.encode("utf-8")
                        except UnicodeDecodeError:
                            pass
                    self.send_response(resp.status)
                    for h, v in resp.headers.items():
                        if h.lower() in ("transfer-encoding", "connection", "content-length"): continue
                        self.send_header(h, v)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except urllib.error.HTTPError as e:
                body = e.read() or f"<h3>Erro {e.code} do equipamento</h3>".encode()
                self._send(e.code, body, e.headers.get("Content-Type", "text/plain"))
            except Exception as exc:  # noqa: BLE001
                self._send(502, f"<h3>Equipamento inacessivel via tunel: {exc}</h3>".encode(),
                           "text/html; charset=utf-8")

        def do_GET(self):
            u = urlparse(self.path)
            p = u.path
            if p == "/" or p.startswith("/index"):
                self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif p.startswith("/api/devices"):
                self._json(db.list_devices())
            elif p.startswith("/api/device/") and p.endswith("/tunnel"):
                # Pi consulta a config do tunel reverso (sem auth — vinculado por device_id). DEVE
                # vir antes do /api/device/<id> generico.
                did = p.split("/")[3]
                if not db.get_device(did):
                    self._json({"erro": "device nao cadastrado"}, 404); return
                port = db.alloc_tunnel_port(did)
                self._json({
                    "device_id": did, "tunnel_port": port,
                    "ssh_host": _TUNNEL_SSH_HOST_PUBLIC, "ssh_port": _TUNNEL_SSH_PORT_PUBLIC,
                    "ssh_user": _TUNNEL_SSH_USER,
                })
            elif p.startswith("/api/device/"):
                did = p.rsplit("/", 1)[-1]
                dev = db.get_device(did)
                self._json({"device": dev, "eventos": db.get_events(did, 100),
                            "comandos": db.list_commands(did, 15)} if dev else {"erro": "não encontrado"},
                           200 if dev else 404)
            elif p.startswith("/api/versions"):
                # Lista de versões publicadas (gravadas na plataforma p/ update/rollback por equipamento).
                self._json({"disponiveis": versoes_disponiveis()})
            elif p.startswith("/api/package/"):
                versao = p.rsplit("/", 1)[-1]
                # 'latest' resolve para a versao publicada mais recente (auto-elimina dependencia do github)
                if versao == "latest":
                    disp = versoes_disponiveis()
                    if not disp:
                        self._json({"erro": "nenhuma versao publicada"}, 404); return
                    versao = disp[-1]
                caminho = os.path.join(_PKG_DIR, versao + ".zip")
                if os.path.exists(caminho):
                    with open(caminho, "rb") as f:
                        self._send(200, f.read(), "application/zip")
                else:
                    self._json({"erro": "pacote não encontrado"}, 404)
            elif p.startswith("/device/"):
                # Proxy reverso HTTP para a UI do equipamento (atras de auth_basic do nginx).
                # /device/<id>/<resto>  ->  http://cubadora-sshd:<tunnel_port>/<resto>
                self._tunnel_proxy(db)
            elif p.startswith("/install/"):
                # Público (sem senha): o Pi baixa este script no momento da instalação.
                device_id = p.rsplit("/", 1)[-1]
                dev = db.get_device(device_id)
                if not dev:
                    self._send(404, b"# Equipamento nao encontrado. Cadastre-o no painel.\n",
                               "text/plain; charset=utf-8")
                    return
                script = _bootstrap_script(self._base_url(), device_id,
                                           dev.get("nome") or "", dev.get("unidade") or "",
                                           dev.get("placa") or "pi4",
                                           dev.get("modelo_maquina") or "ESTATICA_2")
                self._send(200, script.encode("utf-8"), "text/x-shellscript; charset=utf-8")
            elif p in ("/uninstall", "/uninstall/"):
                # Público: o Pi baixa para limpar tudo antes de reinstalar.
                self._send(200, _UNINSTALL.encode("utf-8"),
                           "text/x-shellscript; charset=utf-8")
            else:
                self._json({"erro": "not found"}, 404)

        def do_POST(self):
            u = urlparse(self.path)
            p = u.path
            if p.startswith("/device/"):
                self._tunnel_proxy(db); return
            if p.startswith("/api/heartbeat"):
                try:
                    payload = json.loads(self._read().decode("utf-8") or "{}")
                    did = payload.get("device_id", "")
                    db.upsert_device(payload)
                    db.add_events(did, payload.get("eventos", []))
                    # ACK: resultados dos comandos executados pelo equipamento
                    for r in payload.get("comandos_resultado", []) or []:
                        if r.get("id") is not None:
                            db.ack_command(r["id"], r.get("status", "executado"), str(r.get("resultado", "")))
                    # Entrega os comandos pendentes deste equipamento (entrega única)
                    comandos = db.pull_commands(did) if did else []
                    # Versão-alvo POR equipamento; só entrega se houver pacote (nunca lixo/placeholder).
                    dev = db.get_device(did)
                    alvo = (dev or {}).get("versao_alvo") or ""
                    if alvo and alvo not in versoes_disponiveis():
                        alvo = ""
                    self._json({"versao_alvo": alvo, "comandos": comandos})
                except Exception as exc:  # noqa: BLE001
                    self._json({"erro": str(exc)}, 500)
            elif p.startswith("/api/device/") and p.endswith("/tunnel"):
                # Pi registra sua chave publica SSH (POST sem auth — vinculado pelo device_id).
                # O fleet regenera authorized_keys do container sshd, aplicando restricoes
                # de port-forwarding so para a porta deste device.
                did = p.split("/")[3]
                body = json.loads(self._read().decode("utf-8") or "{}")
                pubkey = (body.get("pubkey") or "").strip()
                if not db.get_device(did):
                    self._json({"erro": "device nao cadastrado"}, 404); return
                if not pubkey or "ssh-" not in pubkey:
                    self._json({"erro": "pubkey ausente/invalida"}, 400); return
                port = db.alloc_tunnel_port(did)
                db.set_tunnel_pubkey(did, pubkey)
                n = _rewrite_authorized_keys(db)
                log.info("Tunel: device %s registrado na porta %s (total %s chaves)", did, port, n)
                self._json({
                    "device_id": did, "tunnel_port": port,
                    "ssh_host": _TUNNEL_SSH_HOST_PUBLIC, "ssh_port": _TUNNEL_SSH_PORT_PUBLIC,
                    "ssh_user": _TUNNEL_SSH_USER,
                })
            elif p.startswith("/api/events/clear"):
                # Limpa todo o historico de eventos de UM equipamento (botao no painel).
                body = json.loads(self._read().decode("utf-8") or "{}")
                did = (body.get("device_id") or "").strip()
                if not did:
                    self._json({"erro": "informe device_id"}, 400); return
                n = db.clear_events(did)
                self._json({"removidos": n})
            elif p.startswith("/api/command"):
                # Protegido pela senha do painel (nginx). Enfileira um comando para o equipamento.
                body = json.loads(self._read().decode("utf-8") or "{}")
                did = (body.get("device_id") or "").strip()
                tipo = (body.get("tipo") or "").strip()
                if not did or not tipo:
                    self._json({"erro": "informe device_id e tipo"}, 400)
                    return
                cid = db.add_command(did, tipo, body.get("parametros") or {})
                log.info("Comando enfileirado: %s para %s (id=%s)", tipo, did, cid)
                self._json({"command_id": cid, "status": "pendente"})
            elif p.startswith("/api/register"):
                # Protegido pela senha do painel (nginx). Cadastra um equipamento e devolve o link.
                body = json.loads(self._read().decode("utf-8") or "{}")
                nome = (body.get("nome") or "").strip()
                unidade = (body.get("unidade") or "").strip()
                placa = (body.get("placa") or "pi4").strip().lower()
                modelo_maquina = (body.get("modelo_maquina") or "ESTATICA_2").strip().upper()
                if not nome:
                    self._json({"erro": "informe o nome do equipamento"}, 400); return
                if placa not in ("pi3", "pi4", "pi5"):
                    self._json({"erro": "placa invalida (pi3|pi4|pi5)"}, 400); return
                if modelo_maquina not in ("ESTATICA_1", "ESTATICA_2", "ESTATICA_LCD",
                                          "DINAMICA_PI", "DINAMICA_CLP"):
                    self._json({"erro": "modelo_maquina invalido"}, 400); return
                device_id = "pi-" + secrets.token_hex(5)
                db.create_pending_device(device_id, nome, unidade, placa, modelo_maquina)
                base = self._base_url()
                install_url = f"{base}/install/{device_id}"
                log.info("Equipamento cadastrado: %s (%s) placa=%s modelo=%s id=%s",
                         nome, unidade, placa, modelo_maquina, device_id)
                self._json({"device_id": device_id, "nome": nome, "unidade": unidade,
                            "placa": placa, "modelo_maquina": modelo_maquina,
                            "install_url": install_url,
                            "install_cmd": f"curl -fsSL {install_url} | sudo bash"})
            elif p.startswith("/api/target"):
                # Versão-alvo POR equipamento (update/rollback de UM equipamento).
                body = json.loads(self._read().decode("utf-8") or "{}")
                did = (body.get("device_id") or "").strip()
                versao = (body.get("versao") or "").strip()
                if versao == "(sem pacotes)":
                    versao = ""   # placeholder do dropdown: nunca vira alvo
                if not did:
                    self._json({"erro": "informe device_id"}, 400)
                    return
                db.set_device_target(did, versao)
                log.info("Versão-alvo de %s definida: %s", did, versao or "(nenhuma)")
                self._json({"device_id": did, "versao_alvo": versao})
            elif p.startswith("/api/publish"):
                versao = (parse_qs(u.query).get("versao", [""])[0]).strip()
                if not versao:
                    self._json({"erro": "informe ?versao="}, 400)
                    return
                os.makedirs(_PKG_DIR, exist_ok=True)
                with open(os.path.join(_PKG_DIR, versao + ".zip"), "wb") as f:
                    f.write(self._read())
                log.info("Publicada versão %s (disponível para selecionar nos equipamentos)", versao)
                self._json({"mensagem": f"Versão {versao} publicada", "versao": versao})
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

    def _retention_loop(self) -> None:
        """Roda prune_events a cada 1h para o banco nao crescer indefinidamente."""
        import time as _t
        while True:
            try:
                n = self.db.prune_events(max_por_device=500, max_dias=30)
                if n: log.info("Retencao: %d eventos antigos descartados", n)
            except Exception as exc:  # noqa: BLE001
                log.warning("Retencao: erro (%s)", exc)
            _t.sleep(3600)

    def start(self, background: bool = True) -> None:
        self._server = ThreadingHTTPServer(("0.0.0.0", self.porta), _make_handler(self.db))
        threading.Thread(target=self._retention_loop, name="retention", daemon=True).start()
        if background:
            threading.Thread(target=self._server.serve_forever, daemon=True).start()
        log.info("Servidor de frota em http://0.0.0.0:%d", self.porta)
        if not background:
            self._server.serve_forever()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
