"""Painel web (stdlib http.server) — tela do operador (kiosk) + configuração completa.

Páginas: / (operador), /config, /calibrar, /diagnostico, /sistema.
A interface é servida em HTML/CSS/JS sem dependências externas. No equipamento, o Chromium
abre esta página em tela cheia (kiosk).
"""

from __future__ import annotations

import base64
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .ui_help import HELP, INTEGRACAO_CAMPOS_PADRAO, INTEGRACAO_HELP

log = logging.getLogger(__name__)

# ───────────────────────────── Design system (CSS comum, tema claro/escuro) ─────────────────────────────
_CSS = """<script>document.documentElement.dataset.tema='__TEMA__'</script><style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0b1220;--panel:#111a2e;--panel2:#16213c;--line:#243049;--txt:#e8edf7;--mut:#94a3b8;--inp:#0a1426;
 --ok:#16a34a;--ok2:#22c55e;--warn:#d97706;--err:#dc2626;--acc:#2563eb;--acc2:#3b82f6;
 --vok:#4ade80;--vinfo:#60a5fa;--verr:#f87171}
html[data-tema="claro"]{--bg:#eef2f7;--panel:#ffffff;--panel2:#f4f7fb;--line:#dbe3ec;--txt:#0f172a;--mut:#5b6b7f;--inp:#ffffff;
 --acc:#2563eb;--acc2:#1d4ed8;--vok:#15803d;--vinfo:#1d4ed8;--verr:#dc2626}
body{font-family:'Segoe UI',system-ui,Arial,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh}
a{color:var(--acc2);text-decoration:none}
.nav{display:flex;align-items:center;gap:18px;background:var(--panel);padding:10px 18px;border-bottom:1px solid var(--line)}
.nav .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:18px}
.nav .brand img{height:30px;border-radius:6px}
.nav .links{display:flex;gap:6px;margin-left:auto;flex-wrap:wrap}
.nav .links a{padding:7px 14px;border-radius:8px;color:var(--mut);font-weight:600}
.nav .links a.on,.nav .links a:hover{background:var(--panel2);color:var(--txt)}
.nav .clock{color:var(--mut);font-variant-numeric:tabular-nums;margin-left:8px}
.wrap{max-width:1100px;margin:0 auto;padding:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:16px}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin-bottom:12px}
.row{display:flex;align-items:center;gap:10px;margin:7px 0}
.row label{flex:0 0 230px;color:var(--mut);font-size:13px;display:flex;align-items:center;gap:6px}
input,select{background:var(--inp);color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:9px 10px;flex:1;font-size:14px;width:100%}
input:focus,select:focus{outline:none;border-color:var(--acc)}
button{background:var(--acc);color:#fff;border:none;border-radius:9px;padding:10px 16px;cursor:pointer;font-size:14px;font-weight:600}
button:hover{background:var(--acc2)} button.ok{background:var(--ok)} button.ok:hover{background:var(--ok2)}
button.ghost{background:var(--panel2);color:var(--txt);border:1px solid var(--line)}
button.danger{background:var(--err)}
.tip{display:inline-flex;width:16px;height:16px;align-items:center;justify-content:center;border-radius:50%;
 background:#475569;color:#fff;font-size:11px;font-weight:700;cursor:help;position:relative;flex:0 0 auto}
.tip:hover::after{content:attr(data-tip);position:absolute;left:22px;top:-6px;width:280px;background:#0f172a;
 color:#e5e7eb;border:1px solid var(--line);padding:9px 11px;border-radius:8px;font-size:12px;font-weight:400;
 line-height:1.4;z-index:50;box-shadow:0 8px 24px rgba(0,0,0,.5);white-space:normal}
#msg{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#0f172a;border:1px solid var(--line);
 color:#fbbf24;padding:10px 18px;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.5);opacity:0;transition:.3s;z-index:60}
#msg.show{opacity:1}
table{width:100%;border-collapse:collapse;font-size:14px}
td,th{border-bottom:1px solid var(--line);padding:8px;text-align:left}
th{color:var(--mut);font-size:12px;text-transform:uppercase}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:12px;font-weight:700}
.b-ok{background:rgba(34,197,94,.15);color:#4ade80} .b-err{background:rgba(220,38,38,.15);color:#f87171}
.b-wait{background:rgba(217,119,6,.15);color:#fbbf24}
html[data-tema="claro"] .b-ok{color:#15803d} html[data-tema="claro"] .b-err{color:#b91c1c} html[data-tema="claro"] .b-wait{color:#b45309}
html[data-tema="claro"] .etq{background:var(--inp)}
</style>"""


def _nav(active: str) -> str:
    def lk(href, txt, key):
        return f'<a href="{href}" class="{"on" if key==active else ""}">{txt}</a>'
    return ('<div class="nav"><div class="brand"><img src="/logo" onerror="this.style.display=\'none\'">'
            '<span id="nomeEq">Cubagem</span></div><div class="links">'
            + lk("/", "📊 Painel", "dash") + lk("/calibrar", "🎯 Calibrar", "cal")
            + lk("/config", "⚙️ Configuração", "cfg") + lk("/diagnostico", "🩺 Diagnóstico", "diag")
            + lk("/sistema", "🖥️ Sistema", "sis")
            + '</div><span class="clock" id="clk"></span></div><div id="msg"></div>')


_JS_COMMON = """
function g(id){return document.getElementById(id)}
async function getj(u){return await (await fetch(u)).json()}
async function post(u,b){return await (await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})).json()}
function toast(t){const m=g('msg');m.textContent=t;m.classList.add('show');clearTimeout(window._tt);window._tt=setTimeout(()=>m.classList.remove('show'),3500)}
function relogio(){const c=g('clk');if(c)c.textContent=new Date().toLocaleString('pt-BR')}
setInterval(relogio,1000);relogio();
async function carregarNome(){try{const s=await getj('/api/status');if(g('nomeEq'))g('nomeEq').textContent=s.nome_equipamento||'Cubagem';aplicarLockdown(s)}catch(e){}}
function aplicarLockdown(s){
 // Em modo producao, esconde dinamicamente as abas Calibrar/Config/Diagnostico/Sistema mesmo
 // sem F5 — atualiza em ate ~5s (proximo poll). NAO afeta o acesso admin via ?admin=<chave>.
 const oculto = !!(s && s.kiosk_modo_producao) && !(location.search.indexOf('admin=')>=0);
 const map={ '/calibrar':oculto, '/config':oculto, '/diagnostico':oculto, '/sistema':oculto };
 document.querySelectorAll('.nav .links a').forEach(a=>{
   const href=a.getAttribute('href'); if(map[href]!==undefined) a.style.display = map[href]?'none':'';
 });
}
setInterval(carregarNome, 5000);
carregarNome();
"""

# ───────────────────────────── Página: PAINEL (operador / kiosk) ─────────────────────────────
_DASH = _CSS + """
<style>
.kpi{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.kpi .b{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:14px;text-align:center}
.kpi .b .v{font-size:40px;font-weight:800;line-height:1.1}
.kpi .b .l{color:var(--mut);font-size:12px;text-transform:uppercase;margin-top:4px}
.banner{border-radius:16px;padding:22px;text-align:center;font-size:30px;font-weight:800;margin-bottom:16px;transition:.3s}
.g3{display:grid;grid-template-columns:1.1fr 1.3fr 1fr;gap:16px}
.etq{font-size:30px;font-weight:800;text-align:center;background:#0a1426;border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:12px;letter-spacing:1px}
.hist{max-height:60vh;overflow:auto} .hist .it{padding:9px 4px;border-bottom:1px solid var(--line)}
.hist .it b{font-size:15px} .hist .it small{color:var(--mut)}
.prod{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.prod .b{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center}
.prod .b .v{font-size:28px;font-weight:800} .prod .b .l{color:var(--mut);font-size:11px;text-transform:uppercase}
.foot{display:flex;gap:18px;flex-wrap:wrap;color:var(--mut);font-size:13px;padding:10px 18px;border-top:1px solid var(--line);background:var(--panel)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
#splash{position:fixed;inset:0;background:var(--bg);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:18px;z-index:99;transition:opacity .6s}
#splash img{max-width:40vw;max-height:40vh} #splash .t{font-size:22px;color:var(--mut)}
</style>
""" + _nav("dash") + """
<div id="splash"><img src="/logo" onerror="this.style.display='none'"><div class="t" id="splashNome">Iniciando…</div></div>
<div class="wrap">
 <div id="banner" class="banner" style="background:#1f2937">—</div>
 <div class="g3">
  <div class="card"><h2>Último volume</h2>
   <div class="etq" id="etq">—</div>
   <div class="kpi">
    <div class="b"><div class="v" id="ka" style="color:var(--vok)">-</div><div class="l">Altura (cm)</div></div>
    <div class="b"><div class="v" id="kl" style="color:var(--vok)">-</div><div class="l">Largura (cm)</div></div>
    <div class="b"><div class="v" id="kc" style="color:var(--vok)">-</div><div class="l">Comprimento (cm)</div></div>
    <div class="b"><div class="v" id="kp" style="color:var(--vinfo)">-</div><div class="l">Peso (kg)</div></div>
   </div>
   <div class="b" style="margin-top:12px;text-align:center;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:10px">
    Volume: <b id="kv" style="font-size:20px">-</b> m³ · Integração: <span id="kintw"></span></div>
  </div>
  <div class="card"><h2>Histórico</h2><div class="hist" id="hist"></div></div>
  <div class="card"><h2>Produção</h2>
   <div class="prod">
    <div class="b"><div class="v" id="pv" style="color:var(--txt)">0</div><div class="l">Volumes cubados</div></div>
    <div class="b"><div class="v" id="ph" style="color:var(--vinfo)">0</div><div class="l">Vol/hora</div></div>
    <div class="b"><div class="v" id="pio" style="color:var(--vok)">0</div><div class="l">Integrações OK</div></div>
    <div class="b"><div class="v" id="pie" style="color:var(--verr)">0</div><div class="l">Integrações erro</div></div>
   </div>
   <div class="b" style="margin-top:10px;text-align:center;background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px">
    Totalização: <b id="ptot" style="font-size:20px">0</b> m³</div>
   <h2 style="margin-top:16px">Alarmes</h2><div id="alarmes" style="color:var(--mut)">Sem alarmes</div>
  </div>
 </div>
</div>
<div class="foot">
 <span><span class="dot" id="dnet"></span><b id="fip">-</b> · <span id="fconx">-</span></span>
 <span>Integração: <b id="fint">-</b></span>
 <span>Aferido: <b id="fafer">-</b></span>
 <span style="margin-left:auto">Versão <span id="fver">-</span> · <span id="fmodelo">-</span></span>
</div>
""" + "<script>" + _JS_COMMON + """
const CORES={verde:'#166534',amarelo:'#854d0e',vermelho:'#7f1d1d'};
const TXTC={verde:'#bbf7d0',amarelo:'#fde68a',vermelho:'#fecaca'};
function badgeInteg(s){const m={enviado:['b-ok','enviado'],fila:['b-err','na fila'],erro:['b-err','erro'],
 sem_integracao:['b-wait','sem integração'],desligada:['b-wait','desligada']};const x=m[s]||['b-wait',s||'—'];return '<span class="badge '+x[0]+'">'+x[1]+'</span>'}
async function tick(){
 let s;try{s=await getj('/api/status')}catch(e){return}
 const b=g('banner');b.textContent=s.status_texto;b.style.background=CORES[s.status_cor]||'#1f2937';b.style.color=TXTC[s.status_cor]||'#e8edf7';
 const c=s.ultima_cubagem;
 if(c){g('etq').textContent=c.etiqueta||'—';g('ka').textContent=c.altura;g('kl').textContent=c.largura;g('kc').textContent=c.comprimento;g('kp').textContent=c.peso;g('kv').textContent=c.volume_m3}
 g('kintw').innerHTML=badgeInteg(s.ultima_integracao);
 const p=s.producao||{};g('pv').textContent=p.volumes||0;g('ph').textContent=p.vol_h||0;g('pio').textContent=p.integracao_ok||0;g('pie').textContent=p.integracao_erro||0;g('ptot').textContent=(p.totalizacao_volume||0).toFixed(4);
 const al=[];if((p.integracao_erro||0)>0)al.push('⚠️ '+p.integracao_erro+' integração(ões) com erro');if((p.erro_cubagem||0)>0)al.push('⚠️ '+p.erro_cubagem+' cubagem(ns) com erro');if(!s.aferido)al.push('🟡 Equipamento não aferido (leia o cubo *cal*)');
 g('alarmes').innerHTML=al.length?al.map(x=>'<div>'+x+'</div>').join(''):'Sem alarmes';
 const r=s.rede||{};g('fip').textContent=r.ip;g('fconx').textContent=r.tipo;g('fint').textContent=s.integracao_nome;g('fver').textContent=s.versao;g('fmodelo').textContent=s.modelo;g('fafer').textContent=s.aferido?'sim':'não';
 g('dnet').style.background=r.ip&&r.ip!=='127.0.0.1'?'#22c55e':'#dc2626';
 try{const h=await getj('/api/cubagens');g('hist').innerHTML=h.map(r=>`<div class="it"><b>${r.etiqueta||'—'}</b> ${badgeInteg(r.integracao)}<br><small>${(r.data||'').substr(11,8)} · ${r.altura.toFixed(1)} × ${r.largura.toFixed(1)} × ${r.comprimento.toFixed(1)} cm · ${r.peso.toFixed(3)} kg</small></div>`).join('')}catch(e){}
}
async function init(){const s=await getj('/api/status');g('splashNome').textContent=s.nome_equipamento||'Cubagem';
 setTimeout(()=>{const sp=g('splash');sp.style.opacity=0;setTimeout(()=>sp.style.display='none',600)},1600);}
init();tick();setInterval(tick,1000);
</script>"""


def build_config_page() -> str:
    return _CSS + _nav("cfg") + """
<div class="wrap">
 <div class="card"><h2>Equipamento</h2>
  <div class="row"><label>Nome do equipamento <span class="tip" data-tip="Nome exibido na tela e no painel de frota.">!</span></label><input id="nomeEqInput"></div>
  <div class="row"><label>Tema da tela <span class="tip" data-tip="Claro (alto contraste, como a referência) ou escuro (moderno).">!</span></label>
   <select id="temaSel"><option value="claro">Claro</option><option value="escuro">Escuro</option></select></div>
  <div class="row"><label>Logotipo da empresa <span class="tip" data-tip="Aparece na tela inicial (splash) e no topo. PNG/JPG.">!</span></label><input type="file" id="logoFile" accept="image/*"></div>
  <button class="ok" onclick="salvarEquip()">Salvar equipamento</button>
  <button class="ghost" onclick="enviarLogo()">Enviar logo</button>
 </div>

 <div class="card"><h2>Integração via API (envio para o seu sistema)</h2>
  <p style="color:var(--mut);font-size:13px;margin-bottom:10px">Configure para onde os volumes são enviados. Use as variáveis
   <code>$etiqueta $peso $altura $largura $comprimento $data</code> no corpo JSON. Adicione/remova campos livremente.</p>
  <div id="integs"></div>
  <button class="ghost" onclick="novaInteg()">+ Nova integração</button>
  <button class="ok" onclick="salvarIntegs()">Salvar integrações</button>
 </div>

 <div id="secoes"></div>
</div>
""" + "<script>" + _JS_COMMON + """
let CFG={},HELP={},IHELP={},ICAMPOS=[];
const SECOES=[['rs485','Comunicação RS-485'],['sensor','Sensores ultrassônicos'],['ajustes','Fatores de medida (escala)'],
 ['balanca','Balança'],['calibracao','Cubo de aferição'],['etiqueta','Etiqueta'],['dinamica','Esteira / CLP'],
 ['camera','Câmera'],['leitor','Leitor de código de barras'],['lcd','Display LCD'],['web','Painel web']];
function tip(t){return t?'<span class="tip" data-tip="'+t.replace(/"/g,'&quot;')+'">!</span>':''}
function inputFor(sec,k,v){
 const id='f_'+sec+'_'+k;
 if(typeof v==='boolean')return '<select id="'+id+'"><option value="true"'+(v?' selected':'')+'>Sim</option><option value="false"'+(!v?' selected':'')+'>Não</option></select>';
 if(Array.isArray(v))return '<input id="'+id+'" value="'+v.join(', ')+'">';
 return '<input id="'+id+'" value="'+(v==null?'':v)+'">';
}
function render(){
 const div=g('secoes');div.innerHTML='';
 for(const [sec,titulo] of SECOES){const obj=CFG[sec];if(!obj)continue;
  let h='<div class="card"><h2>'+titulo+'</h2>';
  for(const [k,v] of Object.entries(obj)){if(v&&typeof v==='object'&&!Array.isArray(v))continue;
   h+='<div class="row"><label>'+k+' '+tip(HELP[sec+'.'+k]||HELP[k]||'')+'</label>'+inputFor(sec,k,v)+'</div>';}
  h+='<button class="ok" onclick="salvarSecao(\\''+sec+'\\')">Salvar '+titulo+'</button></div>';
  div.innerHTML+=h;}
}
function valOf(sec,k,orig){const e=g('f_'+sec+'_'+k);if(!e)return orig;
 if(Array.isArray(orig))return e.value.split(',').map(x=>{const n=Number(x.trim());return isNaN(n)?x.trim():n});
 return e.value;}
async function salvarSecao(sec){const dados={};for(const k of Object.keys(CFG[sec]))if(typeof CFG[sec][k]!=='object'||Array.isArray(CFG[sec][k]))dados[k]=valOf(sec,k,CFG[sec][k]);
 toast((await post('/api/config',{secao:sec,dados})).mensagem);CFG=await getj('/api/config');}
async function salvarEquip(){await post('/api/config',{secao:'__top__',dados:{nome_equipamento:g('nomeEqInput').value,tema:g('temaSel').value}});toast('Salvo. Aplicando tema…');setTimeout(()=>location.reload(),600)}
function enviarLogo(){const f=g('logoFile').files[0];if(!f){toast('Escolha um arquivo');return}
 const r=new FileReader();r.onload=async()=>{const b64=r.result.split(',')[1];toast((await post('/api/logo',{data:b64})).mensagem);setTimeout(()=>location.reload(),700)};r.readAsDataURL(f)}
// ---- integrações ----
function integCard(idx,item){
 let rows='';for(const [k,v] of Object.entries(item)){rows+=integRow(idx,k,v)}
 return '<div class="card" style="background:var(--panel2)" data-idx="'+idx+'"><h2>Integração #'+(idx+1)+
  ' <button class="danger" style="float:right;padding:4px 10px" onclick="rmInteg('+idx+')">remover</button></h2>'+
  '<div id="introws_'+idx+'">'+rows+'</div>'+
  '<div class="row"><input placeholder="novo campo (ex: header-X-Token)" id="nk_'+idx+'" style="flex:0 0 280px">'+
  '<button class="ghost" onclick="addCampo('+idx+')">+ campo</button></div></div>';
}
function integRow(idx,k,v){return '<div class="row" data-k="'+k+'"><label>'+k+' '+tip(IHELP[k]||'')+
 '</label><input value="'+(v==null?'':String(v).replace(/"/g,'&quot;'))+'" data-ik="'+k+'">'+
 '<button class="ghost" style="flex:0 0 auto" onclick="this.parentElement.remove()">×</button></div>'}
let INTEGS=[];
function renderIntegs(){g('integs').innerHTML=INTEGS.map((it,i)=>integCard(i,it)).join('')}
function coletarIntegs(){const out=[];document.querySelectorAll('#integs .card').forEach(card=>{const o={};
 card.querySelectorAll('.row[data-k] input[data-ik]').forEach(inp=>{o[inp.dataset.ik]=inp.value});out.push(o)});return out}
function addCampo(idx){const k=g('nk_'+idx).value.trim();if(!k)return;const c=document.querySelectorAll('#integs .card')[idx];
 INTEGS=coletarIntegs();INTEGS[idx][k]='';renderIntegs()}
function rmInteg(idx){INTEGS=coletarIntegs();INTEGS.splice(idx,1);renderIntegs()}
function novaInteg(){INTEGS=coletarIntegs();const o={};for(const k of ICAMPOS)o[k]=k==='enabled'?'true':(k==='success-tag'?'*':(k==='classe'?'com.compudeck.cubagem.model.integracao.RestClient':''));INTEGS.push(o);renderIntegs()}
async function salvarIntegs(){INTEGS=coletarIntegs();toast((await post('/api/integracao',{integracao:INTEGS})).mensagem)}
async function carregar(){
 CFG=await getj('/api/config');const hp=await getj('/api/config/help');HELP=hp.help;IHELP=hp.integracao_help;ICAMPOS=hp.integracao_campos;
 g('nomeEqInput').value=CFG.nome_equipamento||'';
 g('temaSel').value=CFG.tema||'escuro';
 INTEGS=await getj('/api/integracao');if(!INTEGS.length)novaInteg();else renderIntegs();
 render();
}
carregar();
</script>"""


# ───────────────────────────── Página: CALIBRAR ─────────────────────────────
_CALIBRAR = _CSS + _nav("cal") + """
<div class="wrap">
 <div class="card"><h2>Cubo de aferição (pode ser qualquer anteparo de medidas conhecidas)</h2>
  <div class="row"><label>Altura (cm)<span class="tip" data-tip="Altura real do cubo.">!</span></label><input id="ca" type="number"></div>
  <div class="row"><label>Largura (cm)<span class="tip" data-tip="Largura real do cubo.">!</span></label><input id="cl" type="number"></div>
  <div class="row"><label>Comprimento (cm)<span class="tip" data-tip="Comprimento real do cubo.">!</span></label><input id="cc" type="number"></div>
  <div class="row"><label>Peso (kg)<span class="tip" data-tip="Peso real do cubo.">!</span></label><input id="cp" type="number" step="0.001"></div>
  <button class="ok" onclick="salvarCubo()">Salvar cubo</button>
  <button onclick="aferir()">Aferir agora (cubo na máquina)</button>
  <span style="color:var(--mut);font-size:13px;margin-left:8px">Dica: o cubo costuma ter o código de barras <b>*cal*</b>.</span>
 </div>
 <div class="card"><h2>Leitura ao vivo</h2>
  <div class="prod" style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px">
   <div class="b" style="background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center"><div class="v" id="ma" style="font-size:26px;font-weight:800">-</div><div class="l" style="color:var(--mut);font-size:11px">ALTURA</div></div>
   <div class="b" style="background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center"><div class="v" id="ml" style="font-size:26px;font-weight:800">-</div><div class="l" style="color:var(--mut);font-size:11px">LARGURA</div></div>
   <div class="b" style="background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center"><div class="v" id="mc" style="font-size:26px;font-weight:800">-</div><div class="l" style="color:var(--mut);font-size:11px">COMPRIMENTO</div></div>
   <div class="b" style="background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px;text-align:center"><div class="v" id="mp" style="font-size:26px;font-weight:800">-</div><div class="l" style="color:var(--mut);font-size:11px">PESO</div></div>
  </div>
  <div style="color:var(--mut);font-size:13px;margin-top:10px">Distâncias: ALT <b id="da">-</b> · FUNDO <b id="df">-</b> · ESQ <b id="de">-</b> · DIR <b id="dd">-</b> cm</div>
 </div>
 <div class="card"><h2>Assistente — calibrar a escala com 2 objetos diferentes</h2>
  <div class="row"><label>Altura real (cm)</label><input id="ra" type="number"></div>
  <div class="row"><label>Largura real (cm)</label><input id="rl" type="number"></div>
  <div class="row"><label>Comprimento real (cm)</label><input id="rc" type="number"></div>
  <button onclick="capturar()">Capturar ponto</button> <span id="pts">0 pontos</span>
  <button onclick="calcular()">Calcular fatores</button> <button class="ghost" onclick="limpar()">Limpar</button>
  <pre id="prop" style="color:#4ade80;margin-top:8px"></pre>
  <button class="ok" id="btap" style="display:none" onclick="aplicar()">Aplicar e salvar</button>
 </div>
 <div class="card"><h2>Limites por sensor (cm)</h2>
  <table><tr><th>Sensor</th><th>Mín</th><th>Máx</th><th></th></tr>
  <tr><td>1 Direita</td><td><input id="min0" type="number"></td><td><input id="max0" type="number"></td><td><button onclick="salvarLim(0)">Salvar</button></td></tr>
  <tr><td>2 Fundo</td><td><input id="min1" type="number"></td><td><input id="max1" type="number"></td><td><button onclick="salvarLim(1)">Salvar</button></td></tr>
  <tr><td>3 Esquerda</td><td><input id="min2" type="number"></td><td><input id="max2" type="number"></td><td><button onclick="salvarLim(2)">Salvar</button></td></tr>
  <tr><td>4 Altura</td><td><input id="min3" type="number"></td><td><input id="max3" type="number"></td><td><button onclick="salvarLim(3)">Salvar</button></td></tr>
  </table>
 </div>
</div>
""" + "<script>" + _JS_COMMON + """
let PROP={};
async function vivo(){const s=await getj('/api/debug/sensores');
 g('da').textContent=s.distancias.altura;g('df').textContent=s.distancias.fundo;g('de').textContent=s.distancias.esquerda;g('dd').textContent=s.distancias.direita;
 g('ma').textContent=s.dimensoes.altura;g('ml').textContent=s.dimensoes.largura;g('mc').textContent=s.dimensoes.comprimento;g('mp').textContent=s.peso}
async function salvarCubo(){toast((await post('/api/config',{secao:'calibracao',dados:{altura:g('ca').value,largura:g('cl').value,comprimento:g('cc').value,peso:g('cp').value}})).mensagem)}
async function aferir(){toast((await post('/api/calibrar/cubo',{})).mensagem)}
async function capturar(){const r=await post('/api/calibrar/capturar',{altura:+g('ra').value,largura:+g('rl').value,comprimento:+g('rc').value});g('pts').textContent=r.pontos+' pontos';toast('Ponto capturado')}
async function calcular(){const r=await getj('/api/calibrar/calcular');if(r.erro){toast(r.erro);return}PROP=r.ajustes;g('prop').textContent=JSON.stringify(r.ajustes,null,1);g('btap').style.display='inline-block'}
async function aplicar(){toast((await post('/api/calibrar/aplicar',{ajustes:PROP})).mensagem);g('btap').style.display='none'}
async function limpar(){await post('/api/calibrar/limpar',{});g('pts').textContent='0 pontos';g('prop').textContent='';g('btap').style.display='none'}
async function salvarLim(i){toast((await post('/api/sensor/limites',{index:i,minimo:+g('min'+i).value,maximo:+g('max'+i).value})).mensagem)}
async function carregar(){const c=await getj('/api/config');g('ca').value=c.calibracao.altura;g('cl').value=c.calibracao.largura;g('cc').value=c.calibracao.comprimento;g('cp').value=c.calibracao.peso;
 for(let i=0;i<4;i++){g('min'+i).value=c.sensor.minimo_sensor[i];g('max'+i).value=c.sensor.maximo_sensor[i]}}
carregar();setInterval(vivo,1200);vivo();
</script>"""


# ───────────────────────────── Página: DIAGNÓSTICO ─────────────────────────────
_DIAG = _CSS + _nav("diag") + """
<div class="wrap">
 <div id="banner" class="banner" style="border-radius:16px;padding:20px;text-align:center;font-size:24px;font-weight:800;margin-bottom:16px;background:#1f2937">Verificando…</div>
 <div class="card"><h2>Sensores</h2><table id="tsens"><tr><th>Endereço</th><th>Resp.</th><th>Dist (cm)</th><th>Versão</th></tr></table></div>
 <div class="card"><h2>Balança</h2><div class="row">Peso: <b id="peso">-</b> kg · <span id="bok"></span></div></div>
 <div class="card"><h2>Status</h2><div class="row">Aferido: <span id="afer"></span> · Erros checksum/timeout: <span id="err"></span></div>
  <button onclick="atualizar()">Atualizar</button></div>
</div>
""" + "<script>" + _JS_COMMON + """
async function atualizar(){const d=await getj('/api/diagnostico');const b=g('banner');
 if(d.apto_producao){b.textContent='✅ APTO PARA PRODUÇÃO';b.style.background='#166534';b.style.color='#bbf7d0'}
 else{b.textContent='⛔ NÃO APTO — verifique os itens';b.style.background='#7f1d1d';b.style.color='#fecaca'}
 let h='<tr><th>Endereço</th><th>Resp.</th><th>Dist (cm)</th><th>Versão</th></tr>';
 for(const s of d.sensores)h+='<tr><td>'+s.endereco+'</td><td>'+(s.respondendo?'<span class="badge b-ok">✓</span>':'<span class="badge b-err">✗</span>')+'</td><td>'+s.distancia_cm+'</td><td>'+(s.versao||'-')+'</td></tr>';
 g('tsens').innerHTML=h;g('peso').textContent=d.balanca.peso;g('bok').innerHTML=d.balanca.ok?'<span class="badge b-ok">OK</span>':'<span class="badge b-err">FALHA</span>';
 g('afer').innerHTML=d.aferido?'<span class="badge b-ok">sim</span>':'<span class="badge b-err">não</span>';g('err').textContent=d.erros.checksum+' / '+d.erros.timeout}
atualizar();setInterval(atualizar,3000);
</script>"""


# ───────────────────────────── Página: SISTEMA ─────────────────────────────
_SISTEMA = _CSS + _nav("sis") + """
<div class="wrap">
 <div class="card"><h2>Raspberry Pi</h2>
  <div class="row">Modelo: <b id="modelo">-</b> · SO: <b id="os">-</b> · Sessão: <b id="sessao">-</b></div>
  <div class="row">Host: <b id="host">-</b> · IP: <b id="ip">-</b> (<span id="conx">-</span>) · CPU: <b id="temp">-</b>°C · Uptime: <b id="up">-</b> · Disco livre: <b id="disco">-</b> GB</div>
 </div>
 <div class="card"><h2>Identidade / Frota</h2>
  <div class="row">Device ID: <b id="did">-</b> · Adotado: <b id="adot">-</b> · Servidor: <b id="serv">-</b></div>
 </div>
 <div class="card"><h2>Rede</h2>
  <div class="row"><label>Hostname</label><input id="hostname"></div>
  <div class="row"><label>Wi-Fi SSID</label><input id="ssid"></div>
  <div class="row"><label>Wi-Fi senha</label><input id="senha" type="password"></div>
  <div class="row"><label>IP (dhcp/estatico)</label><input id="ipmodo" placeholder="dhcp"></div>
  <div class="row"><label>IP estático</label><input id="ipaddr" placeholder="192.168.0.50/24"></div>
  <div class="row"><label>Gateway</label><input id="gw"></div>
  <div class="row"><label>DNS</label><input id="dns"></div>
  <button class="ok" onclick="salvarRede()">Salvar rede</button>
 </div>
 <div class="card"><h2>Energia / serviço</h2>
  <button onclick="acao('restart_servico')">Reiniciar serviço</button>
  <button onclick="acao('reboot')">Reiniciar Pi</button>
  <button class="danger" onclick="acao('shutdown')">Desligar Pi</button>
 </div>
</div>
""" + "<script>" + _JS_COMMON + """
async function info(){const s=await getj('/api/sistema');g('host').textContent=s.hostname;g('ip').textContent=s.ip;g('conx').textContent=s.tipo_conexao;
 g('temp').textContent=s.cpu_temp;g('up').textContent=s.uptime;g('disco').textContent=s.disco_livre_gb;g('modelo').textContent=s.modelo_pi;g('os').textContent=s.os;g('sessao').textContent=s.sessao||'-';
 const id=await getj('/api/identidade');g('did').textContent=id.device_id;g('adot').textContent=id.adotado?'sim':'não';g('serv').textContent=id.servidor||'—'}
async function salvarRede(){toast((await post('/api/sistema/rede',{hostname:g('hostname').value,wifi_ssid:g('ssid').value,wifi_senha:g('senha').value,ip_modo:g('ipmodo').value,ip:g('ipaddr').value,gateway:g('gw').value,dns:g('dns').value})).mensagem)}
async function acao(a){if(a!=='restart_servico'&&!confirm('Confirmar '+a+'?'))return;toast((await post('/api/sistema/acao',{acao:a})).mensagem)}
info();setInterval(info,5000);
</script>"""


# ───────────────────────────── Handler ─────────────────────────────
def _make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, page):
            tema = getattr(app.config, "tema", "escuro")
            self._send(200, page.replace("__TEMA__", tema).encode("utf-8"), "text/html; charset=utf-8")

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode("utf-8"))

        def _body(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            if not n:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except Exception:  # noqa: BLE001
                return {}

        def _lockdown_ativo(self) -> bool:
            """Modo producao: esconde abas de parametrizacao e bloqueia as paginas /config etc.
            Libera via ?admin=<chave_admin> (se chave nao vazia)."""
            k = getattr(app.config, "kiosk", None)
            if not k or not getattr(k, "modo_producao", False):
                return False
            try:
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                admin = (qs.get("admin", [""])[0] or "").strip()
            except Exception:  # noqa: BLE001
                admin = ""
            chave = (k.chave_admin or "").strip()
            return not (chave and admin == chave)

        def _html_locked(self, html: str) -> str:
            # Em modo producao, remove os links das abas que nao devem aparecer no kiosk.
            if not self._lockdown_ativo():
                return html
            for href in ('/calibrar', '/config', '/diagnostico', '/sistema'):
                # remove a tag <a href="<href>" ...>...</a> inteira
                import re
                html = re.sub(r'<a href="' + re.escape(href) + r'"[^>]*>.*?</a>', '', html)
            return html

        def do_GET(self):
            p = self.path
            if p == "/" or p.startswith("/index"):
                self._html(self._html_locked(_DASH))
            elif p.startswith("/config"):
                if self._lockdown_ativo(): return self._send(403, b"bloqueado: modo producao", "text/plain")
                self._html(build_config_page())
            elif p.startswith("/calibrar"):
                if self._lockdown_ativo(): return self._send(403, b"bloqueado: modo producao", "text/plain")
                self._html(_CALIBRAR)
            elif p.startswith("/diagnostico"):
                if self._lockdown_ativo(): return self._send(403, b"bloqueado: modo producao", "text/plain")
                self._html(_DIAG)
            elif p.startswith("/sistema"):
                if self._lockdown_ativo(): return self._send(403, b"bloqueado: modo producao", "text/plain")
                self._html(_SISTEMA)
            elif p.startswith("/logo"):
                data = app.ler_logo()
                if data:
                    self._send(200, data, "image/png")
                else:
                    self._json({"erro": "sem logo"}, 404)
            elif p.startswith("/api/status"):
                self._json(app.status_dict())
            elif p.startswith("/api/cubagens"):
                self._json(app.db.listar_cubagens(15))
            elif p.startswith("/api/config/help"):
                self._json({"help": HELP, "integracao_help": INTEGRACAO_HELP,
                            "integracao_campos": INTEGRACAO_CAMPOS_PADRAO})
            elif p.startswith("/api/config"):
                self._json(app.get_config_dict())
            elif p.startswith("/api/integracao"):
                self._json(app.get_integracao_config())
            elif p.startswith("/api/identidade"):
                self._json(app.identidade())
            elif p.startswith("/api/contadores"):
                self._json(app.contador.todos())
            elif p.startswith("/api/balanca/peso"):
                self._json({"peso": app.ler_peso_atual()})
            elif p.startswith("/api/debug/sensores"):
                self._json(app.ler_sensores_ao_vivo())
            elif p.startswith("/api/diagnostico"):
                self._json(app.diagnostico())
            elif p.startswith("/api/sistema"):
                self._json(app.get_sistema_info())
            elif p.startswith("/api/calibrar/calcular"):
                try:
                    self._json({"ajustes": app.calibrar_calcular()})
                except Exception as exc:  # noqa: BLE001
                    self._json({"erro": str(exc)}, 400)
            elif p.startswith("/api/log"):
                from ..core.log_buffer import get_log_buffer
                self._json({"linhas": get_log_buffer().linhas()})
            else:
                self._json({"erro": "not found"}, 404)

        def do_POST(self):
            p = self.path
            d = self._body()
            try:
                if p.startswith("/api/medir"):
                    self._json(app.tratar_etiqueta(d.get("etiqueta", "")))
                elif p.startswith("/api/comando"):
                    self._json({"mensagem": app.dispatcher.execute(d.get("texto", "")) or "não reconhecido"})
                elif p.startswith("/api/config"):
                    if d.get("secao") == "__top__":
                        for k, v in d.get("dados", {}).items():
                            setattr(app.config, k, v)
                        app._salvar_config("equipamento")
                        self._json({"mensagem": "Equipamento atualizado"})
                    else:
                        self._json({"mensagem": app.atualizar_config(d.get("secao", ""), d.get("dados", {}))})
                elif p.startswith("/api/integracao"):
                    self._json({"mensagem": app.salvar_integracao_config(d.get("integracao", []))})
                elif p.startswith("/api/logo"):
                    app.salvar_logo(base64.b64decode(d.get("data", "")))
                    self._json({"mensagem": "Logo enviada"})
                elif p.startswith("/api/balanca/parametro"):
                    self._json({"mensagem": app.escrever_parametro_balanca(int(d.get("registro", 0)), int(d.get("valor", 0)))})
                elif p.startswith("/api/balanca/tara"):
                    self._json({"mensagem": app.tarar()})
                elif p.startswith("/api/calibrar/capturar"):
                    self._json(app.calibrar_capturar(float(d.get("altura", 0)), float(d.get("largura", 0)), float(d.get("comprimento", 0))))
                elif p.startswith("/api/calibrar/cubo"):
                    self._json({"mensagem": app.calibrar_com_cubo()})
                elif p.startswith("/api/calibrar/aplicar"):
                    self._json({"mensagem": app.calibrar_aplicar(d.get("ajustes", {}))})
                elif p.startswith("/api/calibrar/limpar"):
                    self._json({"mensagem": app.calibrar_limpar()})
                elif p.startswith("/api/sensor/limites"):
                    self._json({"mensagem": app.set_limites_sensor(int(d.get("index", 0)), d.get("minimo", 0), d.get("maximo", 0))})
                elif p.startswith("/api/sistema/rede"):
                    self._json({"mensagem": app.configurar_sistema(d)})
                elif p.startswith("/api/sistema/acao"):
                    self._json({"mensagem": app.acao_sistema(d.get("acao", ""))})
                elif p.startswith("/api/adopt"):
                    self._json({"mensagem": app.adotar(d.get("servidor", ""), d.get("chave", ""))})
                else:
                    self._json({"erro": "not found"}, 404)
            except Exception as exc:  # noqa: BLE001
                log.exception("Erro no POST %s", p)
                self._json({"erro": str(exc)}, 500)

    return Handler


class WebServer:
    def __init__(self, app, porta: int = 8080):
        self.app = app
        self.porta = porta
        self._server: ThreadingHTTPServer | None = None

    def start(self) -> None:
        self._server = ThreadingHTTPServer(("0.0.0.0", self.porta), _make_handler(self.app))
        threading.Thread(target=self._server.serve_forever, name="webserver", daemon=True).start()
        log.info("Web server em http://0.0.0.0:%d", self.porta)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
