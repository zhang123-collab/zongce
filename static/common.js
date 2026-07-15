const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const T = (d, f = 'YYYY-MM-DD HH:mm') => { if(!d) return ''; const dt = new Date(d); const p = n => String(n).padStart(2,'0'); return `${dt.getFullYear()}-${p(dt.getMonth()+1)}-${p(dt.getDate())} ${p(dt.getHours())}:${p(dt.getMinutes())}` };
const ST = {0:'草稿',1:'审核中',2:'已通过',3:'未通过',4:'已撤回'};
const SC = {0:'s0',1:'s1',2:'s2',3:'s3',4:'s4'};
const LS_KEY = 'zongce_token';
const LS_USER = 'zongce_user';
const actionLocks = new Set();
function escapeHtml(value){
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
const h = escapeHtml;
function jsString(value){
  return `'${String(value ?? '')
    .replaceAll('\\', '\\\\')
    .replaceAll("'", "\\'")
    .replaceAll('"', '&quot;')
    .replaceAll('\r', '\\r')
    .replaceAll('\n', '\\n')
    .replaceAll('<', '\\x3c')}'`;
}
const j = jsString;
function beginAction(key){
  if(actionLocks.has(key)){ toast('操作正在处理中，请勿重复提交', 'err'); return false; }
  actionLocks.add(key); return true;
}
function endAction(key){ actionLocks.delete(key); }
function toast(msg, type=''){ const t=document.createElement('div'); t.className='msg '+type; t.textContent=msg; $('#toast').appendChild(t); setTimeout(()=>t.remove(),2000); }
function auth(){ return { Authorization: 'Bearer ' + (localStorage.getItem(LS_KEY) || '') }; }
async function api(url, opt = {}){
  opt.headers = Object.assign({'Content-Type':'application/json'}, auth(), opt.headers || {});
  try{
    const res = await fetch(url, opt);
    const data = await res.json().catch(()=>({code:res.status || 500, message:'服务器返回了无法解析的数据'}));
    if (data.code !== 200){
      toast(data.message || '操作失败', 'err');
      if(data.code===401){ localStorage.removeItem(LS_KEY); localStorage.removeItem(LS_USER); currentUser=null; render(); }
      return null;
    }
    return (data.data === null || data.data === undefined) ? true : data.data;
  }catch(e){ toast('网络错误', 'err'); return null; }
}
async function uploadFile(url, formData, query=''){
  try{
    const res = await fetch(url + (query?('?'+query):''), {
      method:'POST', headers: { Authorization: 'Bearer ' + (localStorage.getItem(LS_KEY)||'') }, body: formData
    });
    const data = await res.json().catch(()=>({code:res.status || 500, message:'上传响应无法解析'}));
    if(data.code !== 200){ toast(data.message||'上传失败','err'); return null; }
    return data.data;
  }catch(e){ toast('上传失败，请检查网络后重试','err'); return null; }
}
async function openProtectedFile(path){
  try{
    const res = await fetch(path, {headers:auth()});
    if(!res.ok){ toast('材料打开失败或无访问权限','err'); return; }
    const contentType = res.headers.get('content-type') || '';
    if(contentType.includes('application/json')){
      const data = await res.json();
      toast(data.message || '材料打开失败或无访问权限','err'); return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank', 'noopener');
    setTimeout(()=>URL.revokeObjectURL(url), 60000);
  }catch(e){ toast('材料打开失败','err'); }
}
async function openEvidence(fileId){ return openProtectedFile('/api/file/'+fileId); }
let currentUser = JSON.parse(localStorage.getItem(LS_USER) || 'null');
function saveUser(u){ currentUser = u; localStorage.setItem(LS_USER, JSON.stringify(u)); }
function logout(){ localStorage.removeItem(LS_KEY); localStorage.removeItem(LS_USER); currentUser = null; render(); }
function workspaceWrap(title, description, overviewId, titles, bodies){
  return `<section class="workspace-head"><div><div class="eyebrow">COMPREHENSIVE ASSESSMENT</div><h2>${h(title)}</h2><p>${h(description)}</p></div><div class="workspace-mark">综</div></section>
    <div id="${overviewId}" class="overview-grid"><div class="overview-loading">正在汇总最新数据...</div></div>
    <div class="accordion">${accWrap(titles, bodies)}</div>`;
}
function renderRoleNav(roleTitle, roleSubtitle, items){
  const sidebar = $('#sidebar');
  if(!sidebar) return;
  sidebar.innerHTML = `<div class="side-brand"><span class="side-logo">综</span><div><b>综合测评系统</b><small>${h(roleSubtitle)}</small></div></div>
    <nav class="side-nav">${items.map((item,index)=>`<button class="side-nav-item ${index===0?'active':''}" onclick="focusModule(${index},this)"><span class="nav-icon">${item.icon}</span><span>${h(item.label)}</span></button>`).join('')}</nav>
    <div class="side-user"><span class="side-avatar">${h((currentUser.realName||currentUser.username||'用').slice(0,1))}</span><div><b>${h(currentUser.realName||currentUser.username)}</b><small>${h(roleTitle)}</small></div></div>`;
}
function focusModule(index, button){
  const modules=[...document.querySelectorAll('.acc')];
  const target=modules[index];
  if(!target) return;
  target.classList.add('open');
  const arrow=target.querySelector('.arrow'); if(arrow) arrow.textContent='▼';
  $$('.side-nav-item').forEach(item=>item.classList.remove('active'));
  if(button) button.classList.add('active');
  target.scrollIntoView({behavior:'smooth',block:'start'});
}
function overviewCard(label, value, hint, tone='blue'){
  return `<div class="overview-card tone-${tone}"><div class="overview-label">${h(label)}</div><div class="overview-value">${h(value)}</div><div class="overview-hint">${h(hint||'')}</div></div>`;
}
function overviewNotice(text, tone='info'){
  return `<div class="overview-notice notice-${tone}">${h(text)}</div>`;
}
/* =============== 登录 =============== */
function renderLogin(){
  $('#app').innerHTML = `
  <div class="login-wrap"><div class="login-card">
    <h2>用户登录</h2>
    <div class="tip">登录后可查看对应角色的业务内容</div>
    <div class="err" id="loginErr"></div>
    <div class="field"><label>账号（用户名）</label><input id="lu" placeholder="学号 / teacher01 / admin" /></div>
    <div class="field"><label>密码</label><input id="lp" type="password" placeholder="默认 123456" /></div>
    <button onclick="doLogin()">登 录</button>
    <div class="demo">
      💡 演示账号（密码均为 <b>123456</b>）：<br>
      管理员：<code>admin</code><br>
      教师：<code>teacher01</code>（负责 2023级1班）<br>
      学生：<code>202311081002</code>（张奕驰）<br>
      更多学生账号=学号，可在管理员→班级管理中查看
    </div>
  </div></div>`;
  $('#hdr').innerHTML = `<span>未登录</span>`;
  $('#lp').addEventListener('keydown', e => { if(e.key==='Enter') doLogin(); });
  $('#lu').addEventListener('keydown', e => { if(e.key==='Enter') doLogin(); });
}
async function doLogin(){
  const u = $('#lu').value.trim(), p = $('#lp').value;
  if(!u || !p){ $('#loginErr').textContent='请输入账号密码'; return; }
  if(!beginAction('login')) return;
  const button = document.querySelector('.login-card button');
  if(button) button.disabled = true;
  $('#loginErr').textContent = '';
  try{
    const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u,password:p})});
    const d = await r.json().catch(()=>({code:r.status || 500, message:'服务器返回了无法解析的数据'}));
    if(d.code !== 200){ $('#loginErr').textContent = d.message || '登录失败'; return; }
    localStorage.setItem(LS_KEY, d.data.token);
    saveUser({id:d.data.userId, username:d.data.username, role:d.data.role, roleName:d.data.roleName, realName:d.data.realName, email:d.data.email, phone:d.data.phone, studentId:d.data.studentId, className:d.data.className});
    toast('登录成功', 'ok'); render();
  }catch(e){
    $('#loginErr').textContent = '网络错误，请稍后重试';
  }finally{
    if(button) button.disabled = false;
    endAction('login');
  }
}
/* =============== 顶栏 =============== */
function renderHeader(){
  document.body.classList.toggle('login-mode', !currentUser);
  if(!currentUser){ $('#hdr').innerHTML = ``; if($('#sidebar')) $('#sidebar').innerHTML=''; return; }
  const rl = ['学生','教师','管理员'][currentUser.role];
  $('#hdr').innerHTML = `<span class="header-avatar">${h((currentUser.realName||currentUser.username||'用').slice(0,1))}</span><span class="header-user"><b>${h(currentUser.realName || currentUser.username)}</b><small>${h(rl)}</small></span><button onclick="logout()">退出登录</button>`;
}
/* =============== 折叠卡片 =============== */
function accWrap(titles, bodies, openFirst = true){
  return titles.map((t, i) => `
    <div class="acc ${i===0 && openFirst ? 'open' : ''}" data-i="${i}">
      <div class="acc-hd" onclick="this.parentNode.classList.toggle('open'); this.querySelector('.arrow').textContent = this.parentNode.classList.contains('open') ? '▼' : '▶';">
        <h3>${t}</h3><span class="arrow">${i===0 && openFirst ? '▼' : '▶'}</span>
      </div>
      <div class="acc-bd" id="accbd-${i}">${bodies[i]}</div>
    </div>`).join('');
}

/* =============== 通用弹窗 =============== */
function openModal(title, bodyHtml, actions=[]){
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = bodyHtml;
  const ft = $('#modalFt'); ft.innerHTML = '';
  actions.forEach(a=>{
    const b = document.createElement('button');
    b.className = 'a-btn ' + (a.cls || '');
    b.textContent = a.text;
    b.addEventListener('click', async e=>{
      if(b.disabled) return;
      const buttons = [...ft.querySelectorAll('button')];
      buttons.forEach(button=>button.disabled=true);
      try{ await a.fn(e); }
      catch(err){ toast('操作失败：'+(err.message||err), 'err'); console.error(err); }
      finally{ buttons.forEach(button=>button.disabled=false); }
    });
    ft.appendChild(b);
  });
  $('#modalMask').classList.add('show');
}
function closeModal(){ $('#modalMask').classList.remove('show'); }
$('#modalMask').addEventListener?.('click', e=>{ if(e.target.id==='modalMask') closeModal(); });
