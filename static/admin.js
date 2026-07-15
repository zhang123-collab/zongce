/* =============== 管理员端 =============== */
let adminView = {section:null, data:null};
async function renderAdmin(){
  const titles = ['个人资料', '班级与师生管理', '规则配置中心', '管理员账号', '成绩核算、扣分与终审', '公示与异议管理'];
  const bodies = ['<div id="a1">加载中...</div>','<div id="a2">加载中...</div>','<div id="a3">加载中...</div>','<div id="a4">加载中...</div>','<div id="a5">加载中...</div>','<div id="a6">加载中...</div>'];
  $('#app').innerHTML = workspaceWrap('管理控制台', `你好，${currentUser.realName||currentUser.username}。管理组织、规则与终审结果，关键操作均保留审计记录。`, 'adminOverview', titles, bodies);
  renderRoleNav('系统管理员', '管理端', [
    {icon:'⌂',label:'个人资料'},{icon:'♜',label:'班级与师生'},{icon:'⚙',label:'规则配置'},
    {icon:'♟',label:'管理员账号'},{icon:'▥',label:'核算与终审'},{icon:'公',label:'公示与异议'},
  ]);
  loadAdminOverview(); loadAdminM1(); loadAdminM2(); loadAdminM3(); loadAdminM4(); loadAdminAccounting(); loadAdminPublications();
}
async function loadAdminOverview(){
  const [overview,accounting]=await Promise.all([api('/api/admin/accounting/overview'),api('/api/accounting/list')]);
  if(!overview||!accounting){$('#adminOverview').innerHTML='<div class="overview-loading">管理看板加载失败</div>';return;}
  const list=accounting.list||[], finalized=Number(overview.finalizedCount||0), pending=Number(overview.pendingApplicationCount||0);
  const notice=pending?overviewNotice(`当前还有 ${pending} 条申请等待审核，建议完成审核后再批量终审。`,'warn'):overviewNotice('当前没有待审核申请，可继续进行核算复核与终审。','ok');
  const max=Math.max(1,...(overview.distribution||[]).map(x=>x.count));
  const chart=(overview.distribution||[]).map(x=>`<div style="display:grid;grid-template-columns:90px 1fr 35px;gap:8px;align-items:center;margin:6px 0"><span>${h(x.label)}</span><div style="height:10px;background:#e5e7eb;border-radius:8px"><div style="width:${x.count/max*100}%;height:100%;background:#3b82f6;border-radius:8px"></div></div><b>${x.count}</b></div>`).join('');
  $('#adminOverview').innerHTML=overviewCard('学生总数',overview.studentCount||list.length,'当前纳入核算','blue')+overviewCard('待审核申请',pending,'需教师或管理员处理','orange')+overviewCard('已终审',finalized,`${Math.max(0,(overview.studentCount||list.length)-finalized)} 人尚未终审`,'green')+overviewCard('当前平均分',overview.averageScore||0,'按最新核算结果','purple')+`<div class="overview-notices">${notice}</div><div class="panel"><h4>总分分布</h4>${chart||'<div class="empty">暂无数据</div>'}</div>`;
}
async function loadAdminAccounting(kw=''){
  const [overview,data]=await Promise.all([api('/api/admin/accounting/overview'),api('/api/accounting/list'+(kw?'?keyword='+encodeURIComponent(kw):''))]);
  if(!overview||!data){ $('#a5').innerHTML='<div class="empty">核算数据加载失败</div>'; return; }
  const rows=(data.list||[]).map(x=>`<tr><td>${h(x.studentId)}</td><td>${h(x.studentName)}</td><td>${h(x.className)}</td><td>${x.moralScore}</td><td>${x.academicScore}</td><td>${x.innovationScore}</td><td>${x.workScore}</td><td>-${x.deductionScore}</td><td><b>${x.totalScore}</b></td><td>${x.classRank||'-'}</td><td>${x.gradeRank||'-'}</td><td>${x.isFinalized?'<span class="badge s2">已终审</span>':'<span class="badge s1">核算中</span>'}</td><td>
    <button class="btn btn-sm" onclick="showAccounting(${j(x.studentId)})">明细</button>
    <button class="btn btn-sm" onclick="editBaseScore(${j(x.studentId)},${x.moralScore},${x.academicScore})" ${x.isFinalized?'disabled':''}>基础分</button>
    <button class="btn btn-sm" onclick="addDeduction(${j(x.studentId)})" ${x.isFinalized?'disabled':''}>扣分</button>
    <button class="btn btn-sm" onclick="downloadAdminStudentReport(${j(x.studentId)})">PDF</button>
    ${x.isFinalized?`<button class="btn btn-sm btn-danger" onclick="reopenAccounting(${j(x.studentId)})">撤销终审</button>`:`<button class="btn btn-sm btn-primary" onclick="finalizeAccounting(${j(x.studentId)})">终审</button>`}
  </td></tr>`).join('') || '<tr><td colspan="13" class="empty">暂无学生</td></tr>';
  $('#a5').innerHTML=`
    <div class="grid"><div class="card"><small>学生数</small><div class="number">${overview.studentCount}</div></div><div class="card"><small>已终审</small><div class="number">${overview.finalizedCount}</div></div><div class="card"><small>待审核申请</small><div class="number">${overview.pendingApplicationCount}</div></div><div class="card"><small>当前平均分</small><div class="number">${overview.averageScore}</div></div></div>
    <div class="search-row" style="margin-top:12px"><input id="a5kw" placeholder="按姓名或学号搜索" value="${h(kw)}"><button class="btn" onclick="loadAdminAccounting($('#a5kw').value)">搜索</button><button class="btn" onclick="recalculateAdminRanks()">重算排名</button><button class="btn" onclick="showDuplicateEvidence()">重复材料</button><button class="btn btn-primary" onclick="downloadAccountingExport()">导出核算Excel</button></div>
    <table class="tbl"><thead><tr><th>学号</th><th>姓名</th><th>班级</th><th>思品</th><th>学业</th><th>创新</th><th>工作</th><th>扣分</th><th>总分</th><th>班级名次</th><th>年级名次</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`;
}
async function showAccounting(sid){
  const d=await api('/api/accounting/student/'+encodeURIComponent(sid)); if(!d)return;
  const bonus=(d.bonusDetails||[]).map(x=>`<tr><td>${h(x.category)}</td><td>${h(x.subCategory)}</td><td>${x.countedScore}</td></tr>`).join('')||'<tr><td colspan="3">暂无</td></tr>';
  const deductions=(d.deductions||[]).map(x=>`<tr><td>${h(x.ruleSnapshot)}</td><td>-${x.score}</td><td>${h(x.reason)}</td><td>${currentUser.role===2&&!d.isFinalized?`<button class="btn btn-sm btn-danger" onclick="removeDeduction(${x.id},'${sid}')">撤销</button>`:''}</td></tr>`).join('')||'<tr><td colspan="4">暂无</td></tr>';
  const logs=(d.operationLogs||[]).map(x=>`<tr><td>${h(x.createdAt)}</td><td>${h(x.action)}</td><td>${h(x.detail)}</td></tr>`).join('')||'<tr><td colspan="3">暂无</td></tr>';
  openModal(`${d.studentName}（${d.studentId}）核算明细`,`<div class="grid"><div class="card"><small>基础小计</small><div class="number">${d.moralScore+d.academicScore}</div></div><div class="card"><small>加分</small><div class="number">${d.innovationScore+d.workScore}</div></div><div class="card"><small>扣分</small><div class="number">-${d.deductionScore}</div></div><div class="card"><small>总分</small><div class="number">${d.totalScore}</div></div></div><h4>加分明细</h4><table class="tbl"><thead><tr><th>类别</th><th>子类</th><th>计入分</th></tr></thead><tbody>${bonus}</tbody></table><h4>扣分明细</h4><table class="tbl"><thead><tr><th>依据</th><th>扣分</th><th>原因</th><th>操作</th></tr></thead><tbody>${deductions}</tbody></table><h4>操作记录</h4><table class="tbl"><thead><tr><th>时间</th><th>操作</th><th>说明</th></tr></thead><tbody>${logs}</tbody></table>`,[{text:'关闭',cls:'btn',fn:closeModal}]);
}
async function editBaseScore(sid,moral,academic){
  const m=prompt('输入思品分（0-100）：',moral); if(m===null)return;
  const a=prompt('输入学业成绩（0-100）：',academic); if(a===null)return;
  const r=await api('/api/admin/accounting/base-score',{method:'POST',body:JSON.stringify({student_id:sid,moral_score:Number(m),academic_score:Number(a)})}); if(r){toast('基础分已保存并重新核算','ok');loadAdminAccounting();loadAdminOverview();}
}
async function addDeduction(sid){
  const score=prompt('输入扣分值（大于0）：'); if(score===null)return;
  const reason=prompt('输入扣分认定原因：'); if(!reason)return;
  const evidence=prompt('证据位置或说明（可留空）：','')??'';
  const r=await api('/api/admin/accounting/deduction',{method:'POST',body:JSON.stringify({student_id:sid,deduction_score:Number(score),reason,evidence_ref:evidence,scope:'综合测评总分'})}); if(r){toast('扣分已记录','ok');loadAdminAccounting();loadAdminOverview();}
}
async function removeDeduction(id,sid){if(!confirm('确认撤销这条扣分记录？记录仍会保留在审计日志中'))return;const r=await api('/api/admin/accounting/deduction/'+id,{method:'DELETE'});if(r){toast('扣分已撤销','ok');closeModal();loadAdminAccounting();loadAdminOverview();showAccounting(sid);}}
async function finalizeAccounting(sid){if(!confirm('确认终审？终审后基础分、申请、材料和扣分将锁定'))return;const r=await api('/api/admin/accounting/finalize/'+encodeURIComponent(sid),{method:'POST'});if(r){toast('终审完成','ok');loadAdminAccounting();loadAdminOverview();}}
async function reopenAccounting(sid){const reason=prompt('请输入撤销终审的原因：');if(!reason)return;const r=await api('/api/admin/accounting/reopen',{method:'POST',body:JSON.stringify({student_id:sid,reason})});if(r){toast('已撤销终审','ok');loadAdminAccounting();loadAdminOverview();}}
async function downloadAccountingExport(){
  try{
    const res=await fetch('/api/admin/accounting/export',{headers:auth()});
    if(!res.ok){const d=await res.json().catch(()=>({}));toast(d.message||'导出失败','err');return;}
    const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download='zongce_accounting.xlsx';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){toast('导出失败，请稍后重试','err');}
}
async function recalculateAdminRanks(){const r=await api('/api/admin/accounting/recalculate-ranks',{method:'POST'});if(r){toast(`已更新 ${r.count} 名学生排名`,'ok');loadAdminAccounting();loadAdminOverview();}}
async function downloadAdminStudentReport(studentId){
  try{const res=await fetch('/api/report/student/'+encodeURIComponent(studentId)+'.pdf',{headers:auth()});if(!res.ok){toast('PDF生成失败','err');return;}const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='zongce_'+studentId+'.pdf';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast('PDF生成失败','err');}
}
async function showDuplicateEvidence(){
  const d=await api('/api/evidence/duplicates');if(!d)return;
  const groups=(d.groups||[]).map(g=>`<div class="panel"><b>材料指纹 ${h(g.fingerprint)}</b> · 重复 ${g.count} 次<table class="tbl" style="margin-top:8px"><thead><tr><th>学生</th><th>班级</th><th>申请</th><th>文件</th></tr></thead><tbody>${g.files.map(x=>`<tr><td>${h(x.studentName)} ${h(x.studentId)}</td><td>${h(x.className)}</td><td>#${x.applicationId} ${h(x.projectName)}</td><td><button class="btn btn-sm" onclick="openEvidence(${x.fileId})">${h(x.fileName)}</button></td></tr>`).join('')}</tbody></table></div>`).join('')||'<div class="empty">暂未发现内容完全相同的重复材料</div>';
  openModal('重复证明材料检测',groups,[{text:'关闭',cls:'btn',fn:closeModal}]);
}

async function loadAdminPublications(){
  const [announcements,objections]=await Promise.all([api('/api/announcement/list'),api('/api/objection/list')]);
  if(!announcements||!objections){$('#a6').innerHTML='<div class="empty">公示数据加载失败</div>';return;}
  const announcementRows=(announcements.list||[]).map(x=>`<tr><td>${h(x.title)}</td><td>${h(x.scopeType==='all'?'全部':x.scopeValue)}</td><td>${h(x.startsAt)} 至 ${h(x.endsAt)}</td><td><span class="badge ${x.status==='active'?'s2':x.status==='upcoming'?'s1':'s3'}">${h({active:'公示中',upcoming:'未开始',ended:'已结束',closed:'已关闭'}[x.status]||x.status)}</span></td><td>${x.isActive?`<button class="btn btn-sm btn-danger" onclick="closeAnnouncement(${x.id})">结束公示</button>`:'-'}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">暂无公示</td></tr>';
  const objectionRows=(objections.list||[]).map(x=>`<tr><td>${h(x.studentName)} ${h(x.studentId)}</td><td>${h(x.className)}</td><td>${h(x.announcementTitle)}</td><td>${h(x.type)}</td><td>${h(x.description)}</td><td><span class="badge ${x.status==='pending'?'s1':x.status==='accepted'?'s2':'s3'}">${h({pending:'待处理',accepted:'异议成立',rejected:'异议不成立',need_more:'需补材料'}[x.status]||x.status)}</span></td><td>${x.status==='pending'?`<button class="btn btn-sm btn-primary" onclick="handleObjection(${x.id})">处理</button>`:h(x.resolution)}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">暂无异议</td></tr>';
  $('#a6').innerHTML=`<div style="text-align:right;margin-bottom:10px"><button class="btn btn-primary" onclick="newAnnouncement()">＋ 发布成绩公示</button></div><h4>公示记录</h4><table class="tbl"><thead><tr><th>标题</th><th>范围</th><th>公示期</th><th>状态</th><th>操作</th></tr></thead><tbody>${announcementRows}</tbody></table><h4 style="margin-top:18px">学生异议</h4><table class="tbl"><thead><tr><th>学生</th><th>班级</th><th>公示</th><th>类型</th><th>说明</th><th>状态</th><th>处理</th></tr></thead><tbody>${objectionRows}</tbody></table>`;
}
function newAnnouncement(){
  const now=new Date(),later=new Date(now.getTime()+7*86400000),local=d=>new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
  openModal('发布成绩公示',`<div class="info-grid"><div class="info-item"><label>公示标题</label><input id="ann_title" value="本科生综合测评成绩公示"></div><div class="info-item"><label>范围类型</label><select id="ann_scope"><option value="all">全部学生</option><option value="class">指定班级</option><option value="major">指定专业</option><option value="grade">指定年级</option></select></div><div class="info-item"><label>具体范围（全部时留空）</label><input id="ann_value" placeholder="例如：2023级1班"></div><div class="info-item"><label>开始时间</label><input id="ann_start" type="datetime-local" value="${local(now)}"></div><div class="info-item"><label>结束时间</label><input id="ann_end" type="datetime-local" value="${local(later)}"></div></div><div class="info-item"><label>公示说明</label><textarea id="ann_desc" rows="4"></textarea></div>`,[{text:'发布',cls:'btn btn-primary',fn:async()=>{const r=await api('/api/admin/announcement',{method:'POST',body:JSON.stringify({title:$('#ann_title').value,scope_type:$('#ann_scope').value,scope_value:$('#ann_value').value,description:$('#ann_desc').value,starts_at:$('#ann_start').value,ends_at:$('#ann_end').value})});if(r){toast('公示已发布','ok');closeModal();loadAdminPublications();}}},{text:'取消',cls:'btn',fn:closeModal}]);
}
async function closeAnnouncement(id){if(!confirm('确认结束该公示？结束后学生不能再提交异议'))return;const r=await api('/api/admin/announcement/'+id,{method:'DELETE'});if(r!==null){toast('公示已结束','ok');loadAdminPublications();}}
function handleObjection(id){
  openModal('处理成绩异议',`<div class="info-item"><label>处理结论</label><select id="obj_result"><option value="accepted">异议成立并已修正</option><option value="rejected">异议不成立</option><option value="need_more">需要补充材料</option></select></div><div class="info-item"><label>回复学生的处理意见</label><textarea id="obj_resolution" rows="5"></textarea></div><div class="tip">若异议成立且成绩已终审，请先到“核算与终审”撤销终审、修正数据并重新终审；系统不会根据异议自动改分。</div>`,[{text:'确认处理',cls:'btn btn-primary',fn:async()=>{const r=await api('/api/admin/objection/'+id+'/handle',{method:'POST',body:JSON.stringify({resolution_status:$('#obj_result').value,resolution:$('#obj_resolution').value})});if(r){toast('异议已处理','ok');closeModal();loadAdminPublications();}}},{text:'取消',cls:'btn',fn:closeModal}]);
}
async function loadAdminM1(){
  const d = await api('/api/user/profile'); if(!d){ $('#a1').innerHTML='<div class="empty">加载失败</div>'; return; }
  $('#a1').innerHTML = `
    <div class="info-grid">
      <div class="info-item"><label>账号（只读）</label><input readonly value="${h(d.username)}" /></div>
      <div class="info-item"><label>角色（只读）</label><input readonly value="${h(d.roleName)}" /></div>
      <div class="info-item"><label>姓名</label><input id="af_name" value="${h(d.realName)}" /></div>
      <div class="info-item"><label>年龄</label><input id="af_age" type="number" value="${d.age||''}" /></div>
      <div class="info-item"><label>邮箱</label><input id="af_email" value="${h(d.email)}" /></div>
      <div class="info-item"><label>电话</label><input id="af_phone" value="${h(d.phone)}" /></div>
    </div>
    <div class="panel"><h4>修改密码（如修改则必填旧密码）</h4>
      <div class="pwd">
        <div class="info-item"><label>旧密码</label><input id="af_opwd" type="password" /></div>
        <div class="info-item"><label>新密码（≥6位）</label><input id="af_npwd" type="password" /></div>
      </div>
    </div>
    <div style="text-align:right;margin-top:10px"><button class="btn btn-primary" onclick="saveAdminM1()">保存修改</button></div>`;
}
async function saveAdminM1(){
  const r = await api('/api/user/profile', {method:'PUT', body:JSON.stringify({
    real_name:$('#af_name').value, age:$('#af_age').value?Number($('#af_age').value):null,
    email:$('#af_email').value, phone:$('#af_phone').value,
    password:$('#af_opwd').value||undefined, new_password:$('#af_npwd').value||undefined
  })}); if(r!==null){ toast('已更新','ok'); currentUser.realName=$('#af_name').value; saveUser(currentUser); }
}
async function loadAdminM2(kw=''){
  adminView.section = 'class-list';
  const d = await api('/api/admin/class/list'+(kw?'?keyword='+encodeURIComponent(kw):'')); if(!d){ $('#a2').innerHTML='<div class="empty">加载失败</div>'; return; }
  const list = d.list||[];
  if(!list.length){
    $('#a2').innerHTML = `
      <div class="search-row"><input id="a2kw" placeholder="搜索班级名" /><button class="btn" onclick="loadAdminM2($('#a2kw').value)">搜索</button>
      <button class="btn btn-primary" onclick="newClass()">＋ 新增班级</button>
      <button class="btn btn-primary" onclick="newStudentDlg()">＋ 新增学生</button>
      <button class="btn" onclick="importStudentsExcel()">导入学生Excel</button></div>
      <div class="empty">暂无班级，点「新增班级」创建</div>`; return;
  }
  const cards = list.map(c=>{
    const tch = (c.teachers||[]).map(t=>`<div class="tch-item"><span>👨‍🏫 ${h(t.realName)}</span> <small style="color:#6b7280">（${h(t.username)}，${h(t.phone||t.email)}）</small>
      <button class="btn btn-sm btn-danger" style="margin-left:auto" onclick="assignTeacher(${t.id},'',${j(c.className)})">撤出该班</button></div>`).join('') || '<div class="tch-item" style="background:#fef3c7;color:#92400e">暂无负责老师（到「给该班分配老师」里添加）</div>';
    const stus = (c.students||[]).map(s=>`
      <tr><td>${h(s.studentId)}</td><td>${h(s.realName)}</td><td>${s.academicScore}</td><td>${s.moralScore}</td><td>${h(s.phone)}</td>
        <td>
          <button class="btn btn-sm" onclick="adminEditUser(${s.userId})">编辑</button>
          <button class="btn btn-sm" onclick="moveStudent(${j(s.studentId)},'',${j(c.className)})">移出班级</button>
        </td></tr>`).join('') || `<tr><td colspan="6" class="empty">暂无学生（点「移入学生到该班」按学号加）</td></tr>`;
    const k = 'cls_'+btoa(unescape(encodeURIComponent(c.className))).replace(/[^A-Za-z0-9]/g,'_');
    return `<div class="class-card" data-c="${h(c.className)}" id="${k}">
      <div class="cls-hd" onclick="toggleClass('${k}')">
        <span class="cls-arrow" id="${k}_arr">▶</span>
        <h4 style="display:inline;margin:0">📘 ${h(c.className)} （${c.studentCount||0} 名学生，${(c.teachers||[]).length} 位老师）</h4>
      </div>
      <div class="cls-body" id="${k}_body" style="display:none;margin-top:10px">
        <div class="cls-actions">
          <button class="btn btn-sm" onclick="event.stopPropagation();renameClass(${j(c.className)})">重命名班级</button>
          <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();assignTeacherDlg(${j(c.className)})">分配老师</button>
          <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();newStudentDlg(${j(c.className)})">新增学生</button>
          <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();moveStudentDlg(${j(c.className)})">移入学生</button>
          <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();delClass(${j(c.className)})">删除班级（空才能删）</button>
        </div>
        <div style="margin:10px 0 8px"><b>负责老师：</b></div>${tch}
        <table class="tbl" style="margin-top:10px"><thead><tr><th>学号</th><th>姓名</th><th>学业</th><th>思品</th><th>电话</th><th>操作</th></tr></thead><tbody>${stus}</tbody></table>
      </div>
    </div>`;
  }).join('');
  $('#a2').innerHTML = `
    <div class="search-row">
      <input id="a2kw" placeholder="搜索班级名" value="${h(kw)}" />
      <button class="btn" onclick="loadAdminM2($('#a2kw').value)">搜索</button>
      <button class="btn btn-primary" onclick="newClass()">＋ 新增班级</button>
      <button class="btn btn-primary" onclick="newStudentDlg()">＋ 新增学生</button>
      <button class="btn" onclick="importStudentsExcel()">导入学生Excel</button>
      <button class="btn" onclick="openTeacherMgr()">管理老师账号（新增/删除）</button>
    </div>
    ${cards}`;
}
async function newStudentDlg(defaultClass=''){
  const classes = await api('/api/admin/class/list');
  if(!classes) return;
  const names = (classes.list||[]).map(c=>c.className);
  const options = names.map(name=>`<option value="${h(name)}"${name===defaultClass?' selected':''}>${h(name)}</option>`).join('');
  const inferredGrade = (/^\d{4}/.exec(defaultClass)||[])[0] || String(new Date().getFullYear());
  openModal('新增学生账号',`
    <div class="info-grid">
      <div class="info-item"><label>学号 *</label><input id="ns_sid" maxlength="20" placeholder="6-20位数字" oninput="if(!$('#ns_username').dataset.edited) $('#ns_username').value=this.value"></div>
      <div class="info-item"><label>姓名 *</label><input id="ns_name" maxlength="50" placeholder="学生姓名"></div>
      <div class="info-item"><label>班级 *</label><select id="ns_class" onchange="const m=/^\\d{4}/.exec(this.value);if(m) $('#ns_grade').value=m[0]"><option value="">请选择班级</option>${options}</select></div>
      <div class="info-item"><label>专业 *</label><input id="ns_major" maxlength="100" placeholder="例如：计算机科学与技术"></div>
      <div class="info-item"><label>年级 *</label><input id="ns_grade" maxlength="4" value="${inferredGrade}" placeholder="例如：2023"></div>
      <div class="info-item"><label>登录账号 *</label><input id="ns_username" maxlength="50" placeholder="默认与学号相同" oninput="this.dataset.edited='1'"></div>
      <div class="info-item"><label>初始密码 *</label><input id="ns_password" type="password" value="123456" minlength="6"></div>
      <div class="info-item"><label>思品分</label><input id="ns_moral" type="number" min="0" max="100" step="0.01" value="0"></div>
      <div class="info-item"><label>学业成绩</label><input id="ns_academic" type="number" min="0" max="100" step="0.01" value="0"></div>
      <div class="info-item"><label>邮箱</label><input id="ns_email" type="email" maxlength="100" placeholder="可选"></div>
      <div class="info-item"><label>电话</label><input id="ns_phone" maxlength="20" placeholder="可选"></div>
    </div>
    <div class="tip">学生创建后即可使用登录账号和初始密码登录；建议首次登录后修改默认密码。</div>`,
    [{text:'确认新增',cls:'btn btn-primary',fn:async()=>{
      const sid=$('#ns_sid').value.trim(), username=$('#ns_username').value.trim()||sid;
      const required=[['学号',sid],['姓名',$('#ns_name').value.trim()],['班级',$('#ns_class').value],['专业',$('#ns_major').value.trim()],['年级',$('#ns_grade').value.trim()],['登录账号',username],['初始密码',$('#ns_password').value]];
      const missing=required.find(item=>!item[1]); if(missing){toast(`请填写${missing[0]}`,'err');return;}
      const r=await api('/api/admin/student/create',{method:'POST',body:JSON.stringify({
        student_id:sid, real_name:$('#ns_name').value.trim(), class_name:$('#ns_class').value,
        major:$('#ns_major').value.trim(), grade:$('#ns_grade').value.trim(), username,
        password:$('#ns_password').value, moral_score:Number($('#ns_moral').value||0),
        academic_score:Number($('#ns_academic').value||0), email:$('#ns_email').value.trim(), phone:$('#ns_phone').value.trim()
      })});
      if(r){toast('学生创建成功，可使用新账号登录','ok');closeModal();loadAdminM2();}
    }},{text:'取消',cls:'btn',fn:closeModal}]);
}
function importStudentsExcel(){
  openModal('批量导入学生',
    `<div class="info-item"><label>选择 .xlsx 文件（不超过5MB）</label><input id="student_excel" type="file" accept=".xlsx" /></div>
     <div style="font-size:12px;color:#6b7280;line-height:1.8;margin-top:10px">必需列：学号、姓名、班级、专业、年级、思品分、学业成绩。可选列：登录账号、初始密码、邮箱、电话。单次最多1000人。</div>`,
    [{text:'开始导入',cls:'btn btn-primary',fn:async()=>{
      const file=$('#student_excel').files[0]; if(!file){toast('请选择Excel文件','err');return;}
      const fd=new FormData(); fd.append('file',file);
      const result=await uploadFile('/api/admin/student/import',fd);
      if(!result) return;
      toast(`导入完成：成功 ${result.success}，失败 ${result.failed}`,result.failed?'':'ok');
      closeModal(); loadAdminM2();
    }},{text:'取消',cls:'btn',fn:closeModal}]);
}
function newClass(){
  const n = prompt('输入新班级名称，如 2023级5班');
  if(!n) return; api('/api/admin/class/create', {method:'POST', body:JSON.stringify({class_name:n})}).then(r=>{ if(r){ toast('班级已创建，可在下方列表最末看到','ok'); loadAdminM2(); } });
}
function toggleClass(k){
  const b = document.getElementById(k+'_body'), arr = document.getElementById(k+'_arr');
  const card = document.getElementById(k); if(!b || !card) return;
  if(b.style.display==='none'){ b.style.display='block'; card.classList.add('cls-open'); if(arr) arr.textContent='▼'; }
  else{ b.style.display='none'; card.classList.remove('cls-open'); if(arr) arr.textContent='▶'; }
}
function renameClass(old){
  const n = prompt('新班级名称：', old); if(!n || n===old) return;
  api('/api/admin/class/rename', {method:'POST', body:JSON.stringify({old_name:old, new_name:n})}).then(r=>{ if(r){ toast('已重命名（学生和老师自动同步）','ok'); loadAdminM2(); } });
}
function delClass(n){ if(!confirm('删除班级 '+n+' ？班级必须为空')) return;
  api('/api/admin/class/delete/'+encodeURIComponent(n), {method:'DELETE'}).then(r=>{ if(r){ toast('已删除','ok'); loadAdminM2(); } }); }
async function assignTeacherDlg(cls){
  const all = (await api('/api/admin/teacher/list'))?.list || [];
  const html = `<div>选择老师分配到班级 <b>${h(cls)}</b>：<br><br>
    <select id="dlg_t" style="padding:8px;width:100%;border:1px solid #d1d5db;border-radius:6px">
      ${all.map(t=>`<option value="${t.id}">${h(t.realName)}（${h(t.username)}，当前：${h(t.managedClass||'未分配')}）</option>`).join('')}
    </select><br><br>
    说明：同一个老师可以重新分配；目标为「取消分配」的话下面单独按钮</div>`;
  openModal('分配老师', html, [
    {text:'分配', cls:'btn btn-primary', fn:async()=>{
      const id = Number($('#dlg_t').value); const r = await api('/api/admin/class/assign_teacher', {method:'POST', body:JSON.stringify({user_id:id, target_class:cls})});
      if(r){ toast('已分配','ok'); closeModal(); loadAdminM2(); }
    }},
    {text:'取消',cls:'btn',fn:closeModal}
  ]);
}
async function assignTeacher(id, target, old){ if(target){ if(!confirm('把老师 '+id+' 分配到 '+target+' ？')) return; }
  const r = await api('/api/admin/class/assign_teacher', {method:'POST', body:JSON.stringify({user_id:id, target_class:target})});
  if(r){ toast('已更新','ok'); loadAdminM2(); }
}
async function moveStudentDlg(cls){
  const sid = prompt('输入学生学号，如 202311081002：'); if(!sid) return;
  const r = await api('/api/admin/class/move_student', {method:'POST', body:JSON.stringify({student_id:sid, target_class:cls})});
  if(r){ toast('已移入该班','ok'); loadAdminM2(); }
}
async function moveStudent(sid, target, from){ if(target){ if(!confirm(`把 ${sid} 移出 ${from}？`)) return; }
  const r = await api('/api/admin/class/move_student', {method:'POST', body:JSON.stringify({student_id:sid, target_class:target})});
  if(r){ toast('已移出','ok'); loadAdminM2(); }
}
async function openTeacherMgr(){
  const all = (await api('/api/admin/teacher/list'))?.list || [];
  const rows = all.map(t=>`<tr><td>${h(t.username)}</td><td>${h(t.realName)}</td><td>${h(t.managedClass||'-')}</td><td>${h(t.email)}</td><td>${h(t.phone)}</td><td>${t.age||''}</td>
    <td><button class="btn btn-sm btn-primary" onclick="adminEditUser(${t.id});closeModal();">编辑</button>
        <button class="btn btn-sm btn-primary" onclick="resetPwd(${t.id});">重置密码</button>
        <button class="btn btn-sm btn-danger" onclick="delTeacher(${t.id})">删除</button></td></tr>`).join('') || '<tr><td colspan="7" class="empty">暂无教师</td></tr>';
  openModal('教师账号管理',
    `<div style="margin-bottom:10px;text-align:right"><button class="btn btn-primary" onclick="newTeacherDlg()">＋ 新增教师（密码默认123456）</button></div>
    <table class="tbl"><thead><tr><th>账号</th><th>姓名</th><th>负责班级</th><th>邮箱</th><th>电话</th><th>年龄</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`,
    [{text:'关闭',cls:'btn',fn:closeModal}]);
}
function newTeacherDlg(){ openModal('新增教师账号',
  `<div class="info-grid">
    <div class="info-item"><label>账号 *</label><input id="nt_user" /></div>
    <div class="info-item"><label>姓名 *</label><input id="nt_name" /></div>
    <div class="info-item"><label>负责班级</label><input id="nt_cls" placeholder="如 2023级1班" /></div>
    <div class="info-item"><label>邮箱</label><input id="nt_email" /></div>
    <div class="info-item"><label>电话</label><input id="nt_phone" /></div>
    <div class="info-item"><label>年龄</label><input id="nt_age" type="number" /></div>
  </div>
  <div style="color:#6b7280;font-size:12px">密码默认 123456</div>`,
  [ {text:'创建',cls:'btn btn-primary', fn:async()=>{
      const r = await api('/api/admin/teacher/create', {method:'POST', body:JSON.stringify({
        username:$('#nt_user').value, real_name:$('#nt_name').value, managed_class:$('#nt_cls').value,
        email:$('#nt_email').value, phone:$('#nt_phone').value, age:$('#nt_age').value?Number($('#nt_age').value):null
      })});
      if(r){ toast('已创建，密码123456','ok'); closeModal(); openTeacherMgr(); loadAdminM2(); }
    }}, {text:'取消',cls:'btn', fn:closeModal} ]
  );
}
async function delTeacher(id){ if(!confirm('删除该教师账号？')) return;
  const r = await api('/api/admin/teacher/delete/'+id, {method:'DELETE'}); if(r){ toast('已删除','ok'); openTeacherMgr(); loadAdminM2(); } }
async function resetPwd(id){ if(!confirm('重置该用户密码为 123456 ？')) return;
  const r = await api('/api/admin/user/edit', {method:'POST', body:JSON.stringify({user_id:id, reset_password:true})});
  if(r){ toast('密码已重置为 123456','ok'); } }
async function adminEditUser(uid){
  const tl = (await api('/api/admin/teacher/list'))?.list || []; let user = tl.find(t=>t.id===uid);
  if(!user){
    const al = (await api('/api/admin/admin/list'))?.list || [];
    user = al.find(a=>a.id===uid);
  }
  if(!user){
    const sl = (await api('/api/admin/student/list?page_size=500'))?.list || [];
    const s = sl.find(x=>x.userId===uid);
    if(s) user = Object.assign({user_id:s.userId, role:0, studentId:s.studentId, className:s.className, major:s.major, grade:s.grade, moralScore:s.moralScore, academicScore:s.academicScore}, s);
  }
  if(!user){ toast('找不到该用户信息','err'); return; }
  const isT = (user.managedClass!==undefined && user.managedClass !== null) || user.role===1;
  const isS = user.role===0 || (user.studentId!==undefined);
  openModal(`编辑用户 #${uid}（${isS?'学生':isT?'教师':'管理员'}：${user.realName||user.username}）`,
    `<div class="info-grid">
      <div class="info-item"><label>登录账号</label><input id="eu_user" value="${h(user.username)}" /></div>
      <div class="info-item"><label>姓名</label><input id="eu_name" value="${h(user.realName)}" /></div>
      <div class="info-item"><label>邮箱</label><input id="eu_email" value="${h(user.email)}" /></div>
      <div class="info-item"><label>电话</label><input id="eu_phone" value="${h(user.phone)}" /></div>
      <div class="info-item"><label>年龄</label><input id="eu_age" type="number" value="${user.age||''}" /></div>
      <div class="info-item"><label>密码（留空则不改，填写即更新为该值，建议≥6位）</label><input id="eu_pwd" placeholder="如：123456" value="" /></div>
      <div class="info-item"><label>账号状态</label><select id="eu_active"><option value="1" ${user.isActive===false?'':'selected'}>启用</option><option value="0" ${user.isActive===false?'selected':''}>停用</option></select></div>
      <div class="info-item"><label>登录锁定</label><label style="display:flex;gap:8px;align-items:center"><input id="eu_unlock" type="checkbox" style="width:auto" />${user.isLocked?'账号当前已锁定，勾选后解锁':'勾选可清除失败次数和锁定状态'}</label></div>
      ${isT?`<div class="info-item"><label>负责班级</label><input id="eu_cls" value="${h(user.managedClass)}" /></div>`:''}
      ${isS?`
        <div class="info-item"><label>学号</label><input id="eu_sid" value="${h(user.studentId||user.student_id)}" /></div>
        <div class="info-item"><label>班级</label><input id="eu_scls" value="${h(user.className||user.class_name)}" /></div>
        <div class="info-item"><label>专业</label><input id="eu_mj" value="${h(user.major)}" /></div>
        <div class="info-item"><label>年级</label><input id="eu_gd" value="${h(user.grade)}" /></div>
        <div class="info-item"><label>思品分</label><input id="eu_ms" type="number" step="0.1" value="${user.moralScore??''}" /></div>
        <div class="info-item"><label>学业分</label><input id="eu_as" type="number" step="0.1" value="${user.academicScore??''}" /></div>
      `:''}
    </div>`,
    [
      {text:'保存修改', cls:'btn btn-primary', fn:async()=>{
        const body = {
          user_id: uid,
          username: $('#eu_user').value, real_name: $('#eu_name').value,
          email: $('#eu_email').value, phone: $('#eu_phone').value,
          age: $('#eu_age').value?Number($('#eu_age').value):null,
          new_password: $('#eu_pwd').value.trim() || undefined,
          is_active: $('#eu_active').value === '1',
          unlock_account: $('#eu_unlock').checked
        };
        if($('#eu_cls')) body.managed_class = $('#eu_cls').value;
        if($('#eu_sid')){ Object.assign(body, {
          student_id: $('#eu_sid').value, class_name: $('#eu_scls').value,
          major: $('#eu_mj').value, grade: $('#eu_gd').value,
          moral_score: $('#eu_ms').value!==''?Number($('#eu_ms').value):null,
          academic_score: $('#eu_as').value!==''?Number($('#eu_as').value):null,
        }); }
        const r = await api('/api/admin/user/edit', {method:'POST', body:JSON.stringify(body)});
        if(r){ toast('已更新','ok'); closeModal(); loadAdminM2(); }
      }},
      {text:'取消',cls:'btn',fn:closeModal}
    ]
  );
}
async function loadAdminM3(kw=''){
  const d = await api('/api/admin/rule/list'); const list = (Array.isArray(d)?d:(d.list||[]));
  list.sort((a,b)=>{
    const ai = a.isActive===false?1:0, bi = b.isActive===false?1:0;
    if(ai!==bi) return ai-bi;
    return (a.category||'').localeCompare(b.category||'') || (a.subCategory||a.sub_category||'').localeCompare(b.subCategory||b.sub_category||'');
  });
  const rows = list.map(r=>{
    const id = r.id || r.ruleId;
    const dis = r.isActive===false;
    return `<tr style="${dis?'opacity:0.55;background:#fafafa':''}">
      <td>${h(r.category)}</td><td>${h(r.subCategory||r.sub_category)}</td><td>${h(r.itemName||r.item_name)}</td>
      <td>${r.baseScore??r.base_score}</td><td>${r.maxScore??(r.max_score||'-')}</td>
      <td>${['','取最高','累加','上限值'][r.policy??1]}</td>
      <td>${dis?'<span class="badge s3">已停用</span>':'<span class="badge s2">启用</span>'}</td>
      <td><button class="btn btn-sm" onclick="editRule(${id})">编辑</button>
          <button class="btn btn-sm ${dis?'btn-success':'btn-danger'}" onclick="toggleRule(${id})">${dis?'启用':'停用'}</button></td>
    </tr>`;
  }).join('');
  $('#a3').innerHTML = `
    <div class="search-row">
      <input id="a3kw" placeholder="搜索项目名/子类" value="${h(kw)}" />
      <button class="btn" onclick="$$('#a3 tbody tr').forEach(r=>{const t=r.innerText.toLowerCase(); r.style.display=t.includes($('#a3kw').value.toLowerCase())?'':'none';})">搜索</button>
      <button class="btn btn-primary" onclick="newRuleDlg()">＋ 新增加分规则</button>
    </div>
    <table class="tbl"><thead><tr><th>大类</th><th>子类</th><th>项目</th><th>基础分</th><th>最高分</th><th>计分</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}
async function editRule(id){
  const d = (await api('/api/admin/rule/list'))?.find?.(r=>r.id===id) || (await api('/api/admin/rule/list'))?.list?.find(r=>r.id===id);
  if(!d) return;
  openModal(`编辑规则 #${id}`, `
    <div class="info-grid">
      <div class="info-item"><label>大类</label><input id="rl_cat" value="${h(d.category)}" /></div>
      <div class="info-item"><label>子类</label><input id="rl_sub" value="${h(d.subCategory||d.sub_category)}" /></div>
      <div class="info-item"><label>项目名</label><input id="rl_item" value="${h(d.itemName||d.item_name)}" /></div>
      <div class="info-item"><label>基础分</label><input id="rl_bs" type="number" step="0.1" value="${d.baseScore??d.base_score}" /></div>
      <div class="info-item"><label>最高分</label><input id="rl_mx" type="number" step="0.1" value="${d.maxScore??(d.max_score??'')}" /></div>
      <div class="info-item"><label>计分规则</label><select id="rl_pol">
        <option value="1" ${(d.policy??1)===1?'selected':''}>取最高</option>
        <option value="2" ${(d.policy??2)===2?'selected':''}>累加</option>
        <option value="3" ${(d.policy??3)===3?'selected':''}>上限值</option>
      </select></div>
    </div>`,
    [{text:'保存',cls:'btn btn-primary', fn:async()=>{
      const r = await api('/api/admin/rule/edit', {method:'POST', body:JSON.stringify({
        rule_id:id, category:$('#rl_cat').value, sub_category:$('#rl_sub').value,
        item_name:$('#rl_item').value, base_score:Number($('#rl_bs').value),
        max_score:$('#rl_mx').value?Number($('#rl_mx').value):null, policy:Number($('#rl_pol').value)
      })});
      if(r){ toast('已保存','ok'); closeModal(); loadAdminM3(); }
    }}, {text:'取消',cls:'btn',fn:closeModal}]
  );
}
async function toggleRule(id){
  const list = (await api('/api/admin/rule/list'))?.list || (await api('/api/admin/rule/list')) || [];
  const r = list.find(x=>x.id===id); if(!r){ return; }
  const next = r.isActive===false;
  const res = await api('/api/admin/rule/edit', {method:'POST', body:JSON.stringify({rule_id:id, is_active:next})});
  if(res){ toast(next?'已启用':'已停用','ok'); loadAdminM3(); }
}
function newRuleDlg(){ openModal('新增加分规则',
  `<div class="info-grid">
    <div class="info-item"><label>大类</label><input id="nr_cat" value="学术创新成果" /></div>
    <div class="info-item"><label>子类</label><input id="nr_sub" /></div>
    <div class="info-item"><label>项目名</label><input id="nr_item" /></div>
    <div class="info-item"><label>基础分</label><input id="nr_bs" type="number" step="0.1" value="1" /></div>
    <div class="info-item"><label>最高分</label><input id="nr_mx" type="number" step="0.1" value="10" /></div>
    <div class="info-item"><label>计分规则</label><select id="nr_pol">
      <option value="1">取最高</option><option value="2" selected>累加</option><option value="3">上限值</option></select></div>
  </div>`,
  [{text:'创建', cls:'btn btn-primary', fn:async()=>{
      const r = await api('/api/admin/rule/create', {method:'POST', body:JSON.stringify({
        category:$('#nr_cat').value, sub_category:$('#nr_sub').value, item_name:$('#nr_item').value,
        base_score:Number($('#nr_bs').value), max_score:$('#nr_mx').value?Number($('#nr_mx').value):null, policy:Number($('#nr_pol').value)
      })});
      if(r){ toast('已创建','ok'); closeModal(); loadAdminM3(); }
  }}, {text:'取消',cls:'btn',fn:closeModal}]);
}
async function loadAdminM4(){
  const d = await api('/api/admin/admin/list'); if(!d){ $('#a4').innerHTML='<div class="empty">加载失败</div>'; return; }
  const list = d.list||[];
  const rows = list.map(a=>`<tr><td>${a.id}</td><td>${h(a.username)}</td><td>${h(a.realName)}</td><td>${h(a.email)}</td><td>${h(a.phone)}</td><td>${a.age||''}</td>
    <td>
      <button class="btn btn-sm" onclick="adminEditUser(${a.id})">编辑</button>
      <button class="btn btn-sm" onclick="resetPwd(${a.id})">重置密码</button>
      ${a.canDelete?`<button class="btn btn-sm btn-danger" onclick="delAdmin(${a.id})">删除</button>`:'<span style="color:#9ca3af;font-size:12px">admin 不可删</span>'}
    </td></tr>`).join('');
  $('#a4').innerHTML = `
    <div style="margin-bottom:10px;text-align:right"><button class="btn btn-primary" onclick="newAdminDlg()">＋ 新增管理员账号</button></div>
    <table class="tbl"><thead><tr><th>ID</th><th>账号</th><th>姓名</th><th>邮箱</th><th>电话</th><th>年龄</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`;
}
function newAdminDlg(){ openModal('新增管理员',
  `<div class="info-grid">
    <div class="info-item"><label>账号 *</label><input id="na_user" /></div>
    <div class="info-item"><label>密码 *（≥6位）</label><input id="na_pwd" type="password" value="123456" /></div>
    <div class="info-item"><label>姓名</label><input id="na_name" /></div>
    <div class="info-item"><label>邮箱</label><input id="na_email" /></div>
    <div class="info-item"><label>电话</label><input id="na_phone" /></div>
    <div class="info-item"><label>年龄</label><input id="na_age" type="number" /></div>
  </div>`,
  [{text:'创建', cls:'btn btn-primary', fn:async()=>{
    const r = await api('/api/admin/admin/create', {method:'POST', body:JSON.stringify({
      username:$('#na_user').value, password:$('#na_pwd').value,
      real_name:$('#na_name').value, email:$('#na_email').value, phone:$('#na_phone').value,
      age:$('#na_age').value?Number($('#na_age').value):null
    })}); if(r){ toast('已创建','ok'); closeModal(); loadAdminM4(); }
  }}, {text:'取消',cls:'btn',fn:closeModal}]
);}
async function delAdmin(id){ if(!confirm('删除该管理员账号？')) return;
  const r = await api('/api/admin/admin/delete/'+id, {method:'DELETE'}); if(r){ toast('已删除','ok'); loadAdminM4(); } }
