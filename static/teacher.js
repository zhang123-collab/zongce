/* =============== 教师端 =============== */
let teacherView = {mode:'list'}; // 'list' | 'detail'
async function renderTeacher(){
  const titles = ['个人资料', '负责班级学生', '加分规则参考', '申请审核中心', '班级核算结果'];
  const bodies = ['<div id="t1">加载中...</div>','<div id="t2">加载中...</div>','<div id="t2b">加载中...</div>','<div id="t3">加载中...</div>','<div id="t4">加载中...</div>'];
  $('#app').innerHTML = workspaceWrap('审核工作台', `你好，${currentUser.realName||currentUser.username}。集中处理负责班级的材料核验、分数复核与成绩汇总。`, 'teacherOverview', titles, bodies);
  renderRoleNav('审核教师', '审核端', [
    {icon:'⌂',label:'个人资料'},{icon:'♙',label:'班级学生'},{icon:'⌘',label:'规则参考'},
    {icon:'✓',label:'申请审核'},{icon:'▥',label:'班级核算'},
  ]);
  loadTeacherOverview(); loadTeacherM1(); loadTeacherM2StudentList(); loadTeacherRules(); loadTeacherAudit('pending'); loadTeacherAccounting();
}
async function loadTeacherOverview(){
  const [applications,accounting]=await Promise.all([api('/api/application/list?page_size=999'),api('/api/accounting/list')]);
  if(!applications||!accounting){$('#teacherOverview').innerHTML='<div class="overview-loading">审核工作台加载失败</div>';return;}
  const list=applications.list||[], students=accounting.list||[], pending=list.filter(x=>x.status===1).length, passed=list.filter(x=>x.status===2).length, rejected=list.filter(x=>x.status===3).length;
  const average=students.length?(students.reduce((sum,item)=>sum+Number(item.totalScore||0),0)/students.length).toFixed(2):'0.00';
  const notices=[];
  if(!accounting.managedClass)notices.push(overviewNotice('当前账号尚未分配负责班级，请联系管理员。','warn'));
  else if(pending)notices.push(overviewNotice(`${accounting.managedClass} 当前有 ${pending} 条申请等待人工审核。AI建议仅供材料核验参考。`,'info'));
  else notices.push(overviewNotice(`${accounting.managedClass} 当前没有待审核申请。`,'ok'));
  $('#teacherOverview').innerHTML=overviewCard('待审核',pending,'需要人工处理','orange')+overviewCard('已通过',passed,'本班累计通过','green')+overviewCard('未通过',rejected,'可等待学生修改','red')+overviewCard('班级平均分',average,`${students.length} 名学生`,'purple')+`<div class="overview-notices">${notices.join('')}</div>`;
}
async function loadTeacherAccounting(){
  const d=await api('/api/accounting/list');
  if(!d){ $('#t4').innerHTML='<div class="empty">加载失败</div>'; return; }
  const rows=(d.list||[]).map(x=>`<tr><td>${h(x.studentId)}</td><td>${h(x.studentName)}</td><td>${x.moralScore}</td><td>${x.academicScore}</td><td>${x.innovationScore}</td><td>${x.workScore}</td><td>-${x.deductionScore}</td><td><b>${x.totalScore}</b></td><td>${x.classRank||'-'}</td><td>${x.gradeRank||'-'}</td><td>${x.isFinalized?'<span class="badge s2">已终审</span>':'<span class="badge s1">核算中</span>'}</td><td><button class="btn btn-sm" onclick="showAccounting(${j(x.studentId)})">明细</button></td></tr>`).join('') || '<tr><td colspan="12" class="empty">负责班级暂无学生</td></tr>';
  $('#t4').innerHTML=`<div>负责班级：<b>${h(d.managedClass||'未分配')}</b><button class="btn btn-sm" style="float:right" onclick="showTeacherDuplicateEvidence()">查看重复材料</button></div><table class="tbl" style="margin-top:10px"><thead><tr><th>学号</th><th>姓名</th><th>思品</th><th>学业</th><th>创新</th><th>工作</th><th>扣分</th><th>总分</th><th>班级名次</th><th>年级名次</th><th>状态</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`;
}
async function loadTeacherM1(){
  const d = await api('/api/user/profile');
  if(!d){ $('#t1').innerHTML = '<div class="empty">加载失败</div>'; return; }
  $('#t1').innerHTML = `
    <div class="info-grid">
      <div class="info-item"><label>账号（只读）</label><input readonly value="${h(d.username)}" /></div>
      <div class="info-item"><label>角色（只读）</label><input readonly value="${h(d.roleName)}" /></div>
      <div class="info-item"><label>姓名</label><input id="tf_name" value="${h(d.realName)}" /></div>
      <div class="info-item"><label>负责班级（管理员分配）</label><input id="tf_cls" readonly value="${h(d.managedClass)}" /></div>
      <div class="info-item"><label>年龄</label><input id="tf_age" type="number" value="${d.age||''}" /></div>
      <div class="info-item"><label>邮箱</label><input id="tf_email" value="${h(d.email)}" /></div>
      <div class="info-item"><label>电话</label><input id="tf_phone" value="${h(d.phone)}" /></div>
    </div>
    <div class="panel">
      <h4>修改密码（如修改则必填旧密码）</h4>
      <div class="pwd">
        <div class="info-item"><label>旧密码</label><input id="tf_opwd" type="password" /></div>
        <div class="info-item"><label>新密码（≥6位）</label><input id="tf_npwd" type="password" /></div>
      </div>
    </div>
    <div style="text-align:right;margin-top:10px"><button class="btn btn-primary" onclick="saveTeacherM1()">保存修改</button></div>`;
}
async function saveTeacherM1(){
  const r = await api('/api/user/profile', {method:'PUT', body:JSON.stringify({
    real_name: $('#tf_name').value,
    age: $('#tf_age').value?Number($('#tf_age').value):null,
    email: $('#tf_email').value, phone: $('#tf_phone').value,
    password: $('#tf_opwd').value || undefined, new_password: $('#tf_npwd').value || undefined,
  })}); if(r!==null){ toast('已更新', 'ok'); currentUser.realName = $('#tf_name').value; saveUser(currentUser); }
}
async function loadTeacherM2StudentList(kw=''){
  teacherView.mode = 'list';
  const url = '/api/teacher/class/students' + (kw?('?keyword='+encodeURIComponent(kw)):'');
  const d = await api(url); if(!d){ $('#t2').innerHTML = '<div class="empty">加载失败</div>'; return; }
  const list = d.list || [];
  if(!list.length){ $('#t2').innerHTML = `<div class="search-row"><input id="t2kw" placeholder="搜索姓名或学号" value="${h(kw)}" /><button class="btn" onclick="loadTeacherM2StudentList($('#t2kw').value)">搜索</button></div><div class="empty">${d.managedClass?('负责班级 '+h(d.managedClass)+' 暂无学生'):'您还未分配负责班级，请联系管理员'}</div>`; return; }
  const rows = list.map(s=>`
    <tr><td>${h(s.studentId)}</td><td>${h(s.realName)}</td><td>${h(s.className)}</td><td>${h(s.major)}</td>
      <td><input type="number" min="0" max="100" step="0.1" class="ac_score" data-sid="${s.studentId}" value="${s.academicScore}" /></td>
      <td>${s.moralScore}</td><td>${h(s.email)}</td><td>${h(s.phone)}</td>
      <td><button class="btn btn-sm btn-primary" onclick="saveAcademic(${j(s.studentId)}, this)">保存成绩</button>
          <button class="btn btn-sm" onclick="showStudentT(${j(s.studentId)})">详情</button></td></tr>`).join('');
  $('#t2').innerHTML = `
    <div>负责班级：<b style="color:#1e3a8a">${h(d.managedClass||'（未分配）')}</b></div>
    <div class="search-row" style="margin-top:10px">
      <input id="t2kw" placeholder="搜索姓名或学号" value="${h(kw)}" />
      <button class="btn" onclick="loadTeacherM2StudentList($('#t2kw').value)">搜索</button>
    </div>
    <table class="tbl"><thead><tr><th>学号</th><th>姓名</th><th>班级</th><th>专业</th><th>学业成绩（可改）</th><th>思品</th><th>邮箱</th><th>电话</th><th>操作</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}
async function saveAcademic(sid, btn){
  const val = document.querySelector(`.ac_score[data-sid="${sid}"]`).value;
  if(val === ''){ toast('请输入成绩', 'err'); return; }
  const score = Number(val);
  if(!Number.isFinite(score) || score < 0 || score > 100){ toast('学业成绩必须在0到100之间', 'err'); return; }
  const actionKey = 'academic:'+sid;
  if(!beginAction(actionKey)) return;
  btn.disabled = true;
  const old = btn.textContent;
  try{
    const r = await api('/api/teacher/student/update_academic', {method:'POST', body:JSON.stringify({student_id:sid, academic_score:score})});
    if(r!==null){ btn.textContent='✓ 已保存'; loadTeacherOverview(); setTimeout(()=>{ if(btn.isConnected) btn.textContent=old; }, 1200); }
  }finally{
    btn.disabled = false;
    endAction(actionKey);
  }
}
async function showStudentT(sid){
  const list = (await api('/api/teacher/class/students?keyword='+encodeURIComponent(sid))).list || [];
  const s = list[0]; if(!s) return;
  teacherView.mode='detail';
  $('#t2').innerHTML = `<span class="back" onclick="loadTeacherM2StudentList()">← 返回学生列表</span>
    <div class="info-grid">
      <div class="info-item"><label>学号</label><input readonly value="${h(s.studentId)}" /></div>
      <div class="info-item"><label>姓名</label><input readonly value="${h(s.realName)}" /></div>
      <div class="info-item"><label>班级</label><input readonly value="${h(s.className)}" /></div>
      <div class="info-item"><label>专业</label><input readonly value="${h(s.major)}" /></div>
      <div class="info-item"><label>年级</label><input readonly value="${h(s.grade)}" /></div>
      <div class="info-item"><label>思品</label><input readonly value="${s.moralScore}" /></div>
      <div class="info-item"><label>学业成绩</label><input readonly value="${s.academicScore}" /></div>
      <div class="info-item"><label>年龄</label><input readonly value="${s.age||''}" /></div>
      <div class="info-item"><label>邮箱</label><input readonly value="${h(s.email)}" /></div>
      <div class="info-item"><label>电话</label><input readonly value="${h(s.phone)}" /></div>
    </div>`;
}
async function loadTeacherRules(){
  const d = await api('/api/rule/list');
  const list = Array.isArray(d)?d:(d.list||[]);
  const rows = list.map(r=>`<tr><td>${h(r.category)}</td><td>${h(r.subCategory||r.sub_category)}</td><td>${h(r.itemName||r.item_name)}</td><td>${r.baseScore??r.base_score}</td><td>${r.maxScore??(r.max_score||'-')}</td></tr>`).join('');
  $('#t2b').innerHTML = `<table class="tbl"><thead><tr><th>大类</th><th>子类</th><th>项目</th><th>基础分</th><th>最高分</th></tr></thead><tbody>${rows}</tbody></table>`;
}
let tAuditTab = 'pending';
async function loadTeacherAudit(tab='pending', kw=''){
  tAuditTab = tab;
  const url = `/api/application/list?page_size=999&status_group=${tab}&keyword=${encodeURIComponent(kw)}`;
  const d = await api(url); if(!d){ $('#t3').innerHTML='<div class="empty">加载失败</div>'; return; }
  const list = d.list||[];
  const rows = list.map(it=>`
    <tr>
      <td>${it.id}</td><td>${h(it.projectName)}</td><td>${h(it.studentName)}</td><td>${h(it.studentId)}</td>
      <td>${h(it.className)}</td><td>${h(it.itemName)}</td><td>${it.finalScore}</td>
      <td><span class="badge ${SC[it.status]}">${ST[it.status]||it.statusName}</span></td>
      <td>${T(it.submittedAt)}</td>
      <td>${it.isWithdrawn?'—':`<button class="btn btn-sm btn-primary" onclick="showAuditDetail(${it.id})">${tAuditTab==='pending'?'审核':'查看'}</button>`}</td>
    </tr>`).join('');
  $('#t3').innerHTML = `
    <div class="tabs">
      <div class="tab ${tAuditTab==='pending'?'active':''}" onclick="loadTeacherAudit('pending', $('#t3kw').value)">待处理申请</div>
      <div class="tab ${tAuditTab==='handled'?'active':''}" onclick="loadTeacherAudit('handled', $('#t3kw').value)">已处理申请</div>
    </div>
    <div class="search-row">
      <input id="t3kw" placeholder="搜索学生姓名或学号" value="${h(kw)}" />
      <button class="btn" onclick="loadTeacherAudit(tAuditTab, $('#t3kw').value)">搜索</button>
    </div>
    <table class="tbl"><thead><tr><th>ID</th><th>题目</th><th>学生姓名</th><th>学号</th><th>班级</th><th>项目</th><th>分数</th><th>状态</th><th>提交时间</th><th>操作</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="10" class="empty">${tAuditTab==='pending'?'目前没有待处理申请':'目前没有已处理申请'}</td></tr>`}</tbody></table>`;
}
async function showAuditDetail(id){
  const d = await api('/api/application/detail/'+id);
  if(!d) return;
  if(d.withdrawnForbidden){
    openModal('撤回的申请', `<div class="empty">学生已撤回该申请，教师仅可查看概要：<br><br><b>#${d.id} ${h(d.projectName)}</b><br>学生：${h(d.studentName)} ${h(d.studentId)}<br>状态：<span class="badge s4">已撤回</span></div>`,
      [{text:'关闭',cls:'btn',fn:closeModal}]);
    return;
  }
  let evHtml = '';
  if(d.evidenceFiles && d.evidenceFiles.length){
    evHtml = '<h4 style="margin:10px 0 6px">证明材料（点击后通过权限校验打开）</h4><div class="evidences">'+
      d.evidenceFiles.map(f=>`<div class="ev-pdf" onclick="openEvidence(${f.id})">📎 ${h(f.fileName||'证明材料')}</div>`).join('') + '</div>';
  }
  const canAudit = tAuditTab==='pending' && d.status === 1;
  const audits = (d.auditRecords||[]).map(a=>`<li>${h(a.auditorName||'系统')}：${h(a.opinion)} <span style="color:#6b7280">(${T(a.createdAt)})</span></li>`).join('')||'<li style="color:#9ca3af">暂无审核记录</li>';
  openModal(`申请 #${d.id} - ${d.projectName}`, `
    <div class="info-grid">
      <div class="info-item"><label>学生</label><input readonly value="${h(d.studentName)} ${h(d.studentId)} ${h(d.className)}" /></div>
      <div class="info-item"><label>题目</label><input readonly value="${h(d.projectName)}" /></div>
      <div class="info-item"><label>领域 / 子类</label><input readonly value="${h(d.category)} / ${h(d.subCategory)}" /></div>
      <div class="info-item"><label>项目名</label><input readonly value="${h(d.itemName)}" /></div>
      <div class="info-item"><label>系统分</label><input readonly value="${d.systemCalculatedScore||0}" /></div>
      <div class="info-item"><label>状态</label><input readonly value="${ST[d.status]||d.statusName}" /></div>
    </div>
    <div class="info-item" style="margin-bottom:8px"><label>描述</label><textarea rows="2" readonly>${h(d.description)}</textarea></div>
    ${evHtml}
    <h4 style="margin:14px 0 6px">审核记录</h4><ol style="padding-left:20px;font-size:13px;line-height:1.8">${audits}</ol>
    ${canAudit? `
    <div class="panel" style="margin-top:14px">
      <h4>进行审核</h4>
      <div class="two-cols">
        <div class="info-item"><label>修改后分数（留空则使用系统分 ${d.systemCalculatedScore||0}）</label><input type="number" min="0" max="100" step="0.1" id="ad_score" placeholder="${d.systemCalculatedScore||0}" /></div>
        <div class="info-item"><label>审核意见（驳回时必填，最多500字）</label><textarea rows="2" maxlength="500" id="ad_op"></textarea></div>
      </div>
    </div>`:''}
  `,
  canAudit ? [
    {text:'AI辅助核验', cls:'btn', fn:()=>teacherApplicationAi(d.id)},
    {text:'通过（按系统分）', cls:'btn btn-success', fn:()=>doAuditPass(d.id, null, '')},
    {text:'按修改后分数通过', cls:'btn btn-primary', fn:()=>{ const s=$('#ad_score').value; if(s==='' || Number(s)<0 || Number(s)>100){toast('修改后分数应在0-100之间','err');return;} doAuditPass(d.id, Number(s), $('#ad_op').value||`按修改后分数 ${s} 通过`); }},
    {text:'驳回', cls:'btn btn-danger', fn:()=>{ const o=$('#ad_op').value; if(!o){toast('驳回必填原因','err');return;} doAuditReject(d.id, o); }},
    {text:'取消', cls:'btn', fn:closeModal}
  ] : [ {text:'查看AI建议', cls:'btn', fn:()=>teacherShowApplicationAi(d.id)}, {text:'关闭', cls:'btn', fn:closeModal} ]
  );
}
async function doAuditPass(id, modified_score=null, opinion=''){
  const body = modified_score !== null
    ? { application_id:id, modified_score, opinion: opinion || '按修改后分数审核通过' }
    : { application_id:id, opinion: opinion || '审核通过' };
  const url = modified_score !== null ? '/api/audit/modify' : '/api/audit/pass';
  const r = await api(url, {method:'POST', body: JSON.stringify(body)});
  if(r!==null){ toast('审核完成','ok'); closeModal(); loadTeacherAudit(tAuditTab, $('#t3kw')?.value || ''); loadTeacherOverview(); }
}
async function doAuditReject(id, op){
  const r = await api('/api/audit/reject', {method:'POST', body:JSON.stringify({application_id:id, reject_reason:op, opinion:op})});
  if(r!==null){ toast('已驳回','ok'); closeModal(); loadTeacherAudit(tAuditTab, $('#t3kw')?.value || ''); loadTeacherOverview(); }
}

async function teacherApplicationAi(id){
  const job=await api('/api/ai/application/'+id+'/analyze',{method:'POST'});if(!job)return;
  toast('AI辅助核验已启动，材料会先在本机脱敏','ok');teacherPollApplicationAi(id,0);
}
async function teacherPollApplicationAi(id,attempt){
  const job=await api('/api/ai/application/'+id+'/latest');if(!job)return;
  if(['completed','failed'].includes(job.status)){toast(job.status==='completed'?'AI建议已生成':(job.errorMessage||'AI分析失败'),job.status==='completed'?'ok':'err');teacherShowApplicationAi(id);return;}
  if(attempt<45)setTimeout(()=>teacherPollApplicationAi(id,attempt+1),2000);else toast('AI仍在后台分析，可稍后查看','ok');
}
async function teacherShowApplicationAi(id){
  const job=await api('/api/ai/application/'+id+'/latest');if(!job){toast('该申请还没有AI核验记录','err');return;}
  openModal('申请 #'+id+' AI辅助核验',`<div class="grid"><div class="card"><small>状态</small><div class="number" style="font-size:18px">${h(job.status)}</div></div><div class="card"><small>材料匹配</small><div class="number" style="font-size:18px">${h(job.verificationStatus||'-')}</div></div><div class="card"><small>建议分</small><div class="number">${job.suggestedScore??'-'}</div></div></div><div class="panel"><b>建议理由：</b>${h(job.reason||job.errorMessage||'等待生成')}<br><br><b>脱敏材料摘要：</b><div class="tip">${h(job.evidenceSummary||'暂无')}</div></div><div class="tip">AI建议不会自动修改分数或审核状态。</div>`,[{text:'关闭',cls:'btn',fn:closeModal}]);
}
async function showTeacherDuplicateEvidence(){
  const d=await api('/api/evidence/duplicates');if(!d)return;
  const groups=(d.groups||[]).map(g=>`<div class="panel"><b>材料指纹 ${h(g.fingerprint)}</b> · 重复 ${g.count} 次<table class="tbl" style="margin-top:8px"><tbody>${g.files.map(x=>`<tr><td>${h(x.studentName)} ${h(x.studentId)}</td><td>#${x.applicationId} ${h(x.projectName)}</td><td><button class="btn btn-sm" onclick="openEvidence(${x.fileId})">${h(x.fileName)}</button></td></tr>`).join('')}</tbody></table></div>`).join('')||'<div class="empty">本班暂未发现内容完全相同的重复材料</div>';
  openModal('重复证明材料检测',groups,[{text:'关闭',cls:'btn',fn:closeModal}]);
}
