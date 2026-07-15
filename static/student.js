/* =============== 学生端 =============== */
async function renderStudent(){
  const titles = ['我的基本信息', '加分规则库', '申请记录与撤回', '新建与管理草稿', '我的综测分数', '批量申报与AI核验', '成绩公示与异议'];
  const bodies = ['<div id="m1">加载中...</div>', '<div id="m2">加载中...</div>', '<div id="m3">加载中...</div>', '<div id="m4">加载中...</div>', '<div id="m5">加载中...</div>', '<div id="m6">加载中...</div>', '<div id="m7">加载中...</div>'];
  $('#app').innerHTML = workspaceWrap('学生工作台', `你好，${currentUser.realName||currentUser.username}。在这里完成材料申报、查看审核进度与核算结果。`, 'studentOverview', titles, bodies);
  renderRoleNav('学生', '学生端', [
    {icon:'⌂',label:'我的基本信息'},{icon:'⌘',label:'加分规则库'},{icon:'◷',label:'申请记录'},
    {icon:'＋',label:'新增加分申请'},{icon:'▥',label:'我的综测分数'},{icon:'AI',label:'批量申报与核验'},{icon:'公',label:'公示与异议'},
  ]);
  loadStudentOverview(); loadStudentM1(); loadStudentM2(); loadStudentM3(); loadStudentM4(); loadStudentAccounting(); loadStudentBatches(); loadStudentPublications();
}
async function loadStudentOverview(){
  const [applications,accounting]=await Promise.all([api('/api/application/list?page_size=999'),api('/api/accounting/me')]);
  if(!applications||!accounting){$('#studentOverview').innerHTML='<div class="overview-loading">工作台数据加载失败</div>';return;}
  const list=applications.list||[], pending=list.filter(x=>x.status===1).length, passed=list.filter(x=>x.status===2).length, rejected=list.filter(x=>x.status===3).length, drafts=list.filter(x=>x.status===0).length;
  const notices=[];
  list.filter(x=>x.status===3).slice(0,2).forEach(x=>notices.push(overviewNotice(`“${x.projectName}”未通过：${x.rejectReason||'请补充材料后重新提交'}`,'danger')));
  if(drafts) notices.push(overviewNotice(`你还有 ${drafts} 条草稿未提交，可在“新建与管理草稿”中继续完善。`,'warn'));
  if(pending) notices.push(overviewNotice(`${pending} 条申请正在审核中，审核结果不会由AI自动决定。`,'info'));
  if(!notices.length) notices.push(overviewNotice('当前没有需要立即处理的申请。','ok'));
  $('#studentOverview').innerHTML=overviewCard('审核中',pending,'等待负责老师审核','blue')+overviewCard('已通过',passed,'已计入规则核算','green')+overviewCard('需修改',rejected,'可修改后重新提交','red')+overviewCard('当前总分',accounting.totalScore,accounting.isFinalized?'结果已终审':'动态核算中','purple')+`<div class="overview-notices">${notices.join('')}</div>`;
}
async function loadStudentAccounting(){
  const d = await api('/api/accounting/me');
  if(!d){ $('#m5').innerHTML='<div class="empty">核算结果加载失败</div>'; return; }
  const details=(d.bonusDetails||[]).map(x=>`<tr><td>${h(x.category)}</td><td>${h(x.subCategory)}</td><td>${h(x.policy===1?'取最高':'累加')}</td><td>${x.countedScore}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">暂无审核通过的可计分申请</td></tr>';
  const deductions=(d.deductions||[]).map(x=>`<tr><td>${h(x.ruleSnapshot)}</td><td>${h(x.scope)}</td><td>-${x.score}</td><td>${h(x.reason)}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">暂无扣分</td></tr>';
  $('#m5').innerHTML=`
    <div class="grid">
      <div class="card"><small>思品</small><div class="number">${d.moralScore}</div></div>
      <div class="card"><small>学业</small><div class="number">${d.academicScore}</div></div>
      <div class="card"><small>学术创新</small><div class="number">${d.innovationScore}</div></div>
      <div class="card"><small>学生工作</small><div class="number">${d.workScore}</div></div>
      <div class="card"><small>扣分</small><div class="number">-${d.deductionScore}</div></div>
      <div class="card"><small>综合总分</small><div class="number">${d.totalScore}</div></div>
      <div class="card"><small>班级排名</small><div class="number">${d.classRank||'-'}</div></div>
      <div class="card"><small>年级排名</small><div class="number">${d.gradeRank||'-'}</div></div>
    </div>
    <div class="panel"><b>状态：</b>${d.isFinalized?`<span class="badge s2">已终审</span> ${h(d.finalizedAt)}`:'<span class="badge s1">动态核算中</span>'}<button class="btn btn-sm" style="float:right" onclick="downloadStudentReport(${j(d.studentId)})">导出个人PDF报告</button></div>
    <h4>加分核算明细</h4><table class="tbl"><thead><tr><th>类别</th><th>子类</th><th>聚合规则</th><th>计入分</th></tr></thead><tbody>${details}</tbody></table>
    <h4 style="margin-top:16px">扣分明细</h4><table class="tbl"><thead><tr><th>依据</th><th>范围</th><th>扣分</th><th>原因</th></tr></thead><tbody>${deductions}</tbody></table>`;
}
async function loadStudentBatches(){
  const d=await api('/api/batch/my');
  if(!d){$('#m6').innerHTML='<div class="empty">批次记录加载失败</div>';return;}
  const statusName={parsed:'待确认',needs_correction:'需修正',confirmed:'已生成草稿'};
  const cards=(d.list||[]).map(batch=>{
    const ai=batch.latestAiJob||null, suggestions=new Map(((ai&&ai.suggestions)||[]).map(x=>[x.itemId,x]));
    const items=(batch.items||[]).map(item=>{const s=suggestions.get(item.id);return `<tr><td>${item.rowNumber}</td><td>${h(item.projectName)}</td><td>${h(item.projectLevel)}</td><td>${item.declaredScore}</td><td>${item.status==='valid'?'<span class="badge s2">有效</span>':`<span class="badge s3">错误</span> ${h(item.errorMessage)}`}</td><td>${s?`<span class="badge ${s.verificationStatus==='匹配'?'s2':s.verificationStatus==='不匹配'?'s3':'s1'}">${h(s.verificationStatus)}</span> ${s.suggestedScore===null?'':`建议 ${s.suggestedScore} 分`}<div class="tip">${h(s.reason)}</div>`:'-'}</td><td>${item.applicationId?`申请 #${item.applicationId}`:'-'}</td></tr>`}).join('');
    const materials=(batch.materials||[]).map(file=>`<button class="btn btn-sm" onclick="openProtectedFile('/api/batch/material/${file.id}')">${h(file.filename)}</button>`).join(' ');
    const aiState=ai?({pending:'等待分析',running:'分析中',completed:'分析完成',failed:'分析失败'}[ai.status]||ai.status):'尚未分析';
    const canAnalyze=['parsed','confirmed'].includes(batch.status)&&!batch.errorCount;
    return `<div class="panel"><div style="display:flex;justify-content:space-between;gap:10px"><div><b>批次 #${batch.id}</b> · ${h(batch.excelName)} · ${h(batch.createdAt)}</div><div><span class="badge ${batch.status==='confirmed'?'s2':batch.status==='parsed'?'s1':'s3'}">${h(statusName[batch.status]||batch.status)}</span></div></div><div style="margin:8px 0">共 ${batch.itemCount} 条，有效 ${batch.validCount}，错误 ${batch.errorCount}；材料：${materials||'无'}</div><div class="tip">AI辅助核验：${h(aiState)}${ai&&ai.errorMessage?' · '+h(ai.errorMessage):''}。AI结果仅供人工审核参考，不计入最终成绩。</div><table class="tbl"><thead><tr><th>Excel行</th><th>项目</th><th>等级</th><th>申报分</th><th>解析结果</th><th>AI建议</th><th>生成申请</th></tr></thead><tbody>${items}</tbody></table><div style="text-align:right;margin-top:10px">${canAnalyze?`<button class="btn" onclick="analyzeStudentBatch(${batch.id})">${ai&&['pending','running'].includes(ai.status)?'查看分析进度':'材料脱敏并由AI辅助核验'}</button>`:''} ${batch.status==='parsed'?`<button class="btn btn-primary" onclick="confirmStudentBatch(${batch.id})">确认并生成草稿申请</button>`:''}</div></div>`;
  }).join('')||'<div class="empty">还没有批量申报记录</div>';
  $('#m6').innerHTML=`<div class="panel"><h4>一份Excel + 最多5份证明材料</h4><div class="tip">系统读取“申报明细”工作表。学生申报分仅用于对照，实际系统分由已启用规则计算；AI链路先在本机提取/OCR并脱敏，只把相关片段交给DeepSeek，结果仅作建议。</div><div class="info-grid"><div class="info-item"><label>申报Excel（.xlsx，不超过5MB）</label><input id="batch_excel" type="file" accept=".xlsx"></div><div class="info-item"><label>证明材料（PDF/JPG/PNG，最多5份）</label><input id="batch_materials" type="file" accept=".pdf,.jpg,.jpeg,.png" multiple></div></div><div class="actions"><button class="btn" onclick="downloadBatchTemplate()">下载标准模板</button><button class="btn btn-primary" onclick="uploadStudentBatch()">上传并解析</button></div></div>${cards}`;
}
async function analyzeStudentBatch(id){
  if(!beginAction('ai-batch:'+id))return;
  try{const job=await api('/api/ai/batch/'+id+'/analyze',{method:'POST'});if(job){toast(job.status==='completed'?'已加载AI建议':'AI辅助核验已启动','ok');pollStudentAiJob(job.id,0);}}
  finally{endAction('ai-batch:'+id);}
}
async function pollStudentAiJob(jobId,attempt){
  const job=await api('/api/ai/job/'+jobId);
  if(!job)return;
  if(['completed','failed'].includes(job.status)){toast(job.status==='completed'?'AI建议已生成':(job.errorMessage||'AI分析失败'),job.status==='completed'?'ok':'err');loadStudentBatches();return;}
  if(attempt<45)setTimeout(()=>pollStudentAiJob(jobId,attempt+1),2000);else{toast('AI仍在后台分析，可稍后刷新查看','ok');loadStudentBatches();}
}
async function uploadStudentBatch(){
  const excel=$('#batch_excel').files[0],materials=[...$('#batch_materials').files];
  if(!excel){toast('请选择申报Excel','err');return;}if(!materials.length){toast('请至少选择一份证明材料','err');return;}if(materials.length>5){toast('证明材料最多5份','err');return;}
  if(!beginAction('batch-upload'))return;
  try{const form=new FormData();form.append('excel',excel);materials.forEach(file=>form.append('materials',file));const result=await uploadFile('/api/batch/upload',form);if(result){toast(result.errorCount?'解析完成，请修正错误后重新上传':'解析成功，请核对后确认',result.errorCount?'err':'ok');loadStudentBatches();}}
  finally{endAction('batch-upload');}
}
async function confirmStudentBatch(id){
  if(!confirm('确认解析结果并生成草稿申请？生成后仍需逐条提交审核')||!beginAction('batch-confirm:'+id))return;
  try{const r=await api('/api/batch/'+id+'/confirm',{method:'POST'});if(r){toast(`已生成 ${r.applicationIds.length} 条草稿申请`,'ok');loadStudentBatches();loadStudentM4();loadStudentOverview();}}
  finally{endAction('batch-confirm:'+id);}
}
async function downloadBatchTemplate(){
  try{const res=await fetch('/api/batch/template',{headers:auth()});if(!res.ok){toast('模板下载失败','err');return;}const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='zongce_submission_template.xlsx';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){toast('模板下载失败','err');}
}
async function loadStudentM1(){
  const d = await api('/api/student/profile');
  if(!d){ $('#m1').innerHTML = '<div class="empty">加载失败</div>'; return; }
  $('#m1').innerHTML = `
    <div class="info-grid">
      <div class="info-item"><label>学号（只读）</label><input readonly value="${h(d.studentId)}" /></div>
      <div class="info-item"><label>登录账号（只读）</label><input readonly value="${h(d.username)}" /></div>
      <div class="info-item"><label>姓名（只读）</label><input readonly value="${h(d.realName)}" /></div>
      <div class="info-item"><label>班级（只读）</label><input readonly value="${h(d.className)}" /></div>
      <div class="info-item"><label>专业（只读）</label><input readonly value="${h(d.major)}" /></div>
      <div class="info-item"><label>年级（只读）</label><input readonly value="${h(d.grade)}" /></div>
      <div class="info-item"><label>思品分（只读）</label><input readonly value="${d.moralScore}" /></div>
      <div class="info-item"><label>学业成绩（只读）</label><input readonly value="${d.academicScore}" /></div>
      <div class="info-item"><label>年龄</label><input id="f_age" type="number" min="15" max="50" value="${d.age||''}" /></div>
      <div class="info-item"><label>邮箱</label><input id="f_email" value="${h(d.email)}" /></div>
      <div class="info-item"><label>电话</label><input id="f_phone" value="${h(d.phone)}" /></div>
    </div>
    <div class="panel">
      <h4>修改密码（如修改则必填旧密码）</h4>
      <div class="pwd">
        <div class="info-item"><label>旧密码</label><input id="f_opwd" type="password" /></div>
        <div class="info-item"><label>新密码（≥6位）</label><input id="f_npwd" type="password" /></div>
      </div>
    </div>
    <div style="margin-top:10px;text-align:right"><button class="btn btn-primary" onclick="saveStudentM1()">保存修改</button></div>`;
}
async function saveStudentM1(){
  const payload = {
    age: $('#f_age').value ? Number($('#f_age').value) : null,
    email: $('#f_email').value, phone: $('#f_phone').value,
    password: $('#f_opwd').value || undefined,
    new_password: $('#f_npwd').value || undefined,
  };
  const r = await api('/api/student/profile', {method:'PUT', body:JSON.stringify(payload)});
  if(r !== null){ toast('已同步到数据库', 'ok'); currentUser.email = payload.email; saveUser(currentUser); }
}
async function loadStudentM2(){
  const d = await api('/api/rule/list');
  if(!d){ $('#m2').innerHTML='<div class="empty">加载失败</div>'; return; }
  const list = Array.isArray(d)?d:(d.list||[]);
  const cats = [...new Set(list.map(r=>r.category))];
  const chips = cats.map((c,i)=>`<span class="chip ${i===0?'active':''}" data-c="${c}" onclick="$$('#m2 .chip').forEach(x=>x.classList.remove('active')); this.classList.add('active'); filterM2(this.dataset.c)">${c}</span>`).join('');
  const rows = list.map(r => `
    <tr data-c="${r.category}">
      <td>${h(r.category)}</td><td>${h(r.subCategory||r.sub_category)}</td><td>${h(r.itemName||r.item_name)}</td>
      <td>${r.baseScore ?? r.base_score}</td><td>${r.maxScore ?? (r.max_score||'-')}</td>
      <td>${['','取最高','累加','上限值'][r.policy ?? 1]}</td>
    </tr>`).join('');
  $('#m2').innerHTML = `
    <div class="tag-row">${chips}</div>
    <table class="tbl"><thead><tr><th>大类</th><th>子类</th><th>项目</th><th>基础分</th><th>最高分</th><th>计分规则</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}
function filterM2(c){ $$('#m2 tbody tr').forEach(tr => { tr.style.display = (tr.dataset.c===c)?'':'none'; }); }
async function loadStudentM3(){
  const d = await api('/api/application/list?page_size=999');
  if(!d){ $('#m3').innerHTML='<div class="empty">加载失败</div>'; return; }
  const list = d.list || [];
  if(!list.length){ $('#m3').innerHTML = '<div class="empty">当前没有申请</div>'; return; }
  const rows = list.map(it => `
    <tr>
      <td>${it.id}</td><td>${h(it.projectName)}</td><td>${h(it.itemName)}</td><td>${it.finalScore}</td>
      <td><span class="badge ${SC[it.status]}">${ST[it.status]||it.statusName}</span></td>
      <td>${h(it.status===3 && it.rejectReason ? ('未通过，原因：'+it.rejectReason) : it.rejectReason)}</td>
      <td>${T(it.submittedAt)}</td>
      <td>
        ${it.status===1?`<button class="btn btn-sm btn-danger" onclick="withdrawApp(${it.id})">撤回</button>`:''}
        <button class="btn btn-sm" onclick="${[0,3,4].includes(it.status)?`editDraftApp(${it.id})`:`showAppDetail(${it.id})`}">${[0,3,4].includes(it.status)?'修改并重提':'详情'}</button>
      </td>
    </tr>`).join('');
  $('#m3').innerHTML = `<table class="tbl"><thead><tr><th>ID</th><th>题目</th><th>项目</th><th>分数</th><th>状态</th><th>说明</th><th>提交时间</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`;
}
async function withdrawApp(id){
  const actionKey = 'withdraw:'+id;
  if(!confirm('确认撤回该申请？撤回后状态将变更为「已撤回」') || !beginAction(actionKey)) return;
  try{
    const r = await api(`/api/application/withdraw/${id}`, {method:'PUT'});
    if(r !== null){ toast('已撤回', 'ok'); loadStudentM3(); loadStudentM4(); loadStudentOverview(); }
  }finally{ endAction(actionKey); }
}
async function showAppDetail(id){
  const d = await api('/api/application/detail/'+id); if(!d) return;
  let evHtml = '';
  if(d.evidenceFiles && d.evidenceFiles.length){
    evHtml = '<h4 style="margin:10px 0 6px">证明材料</h4><div class="evidences">'+
      d.evidenceFiles.map(f=>`<div class="ev-pdf" onclick="openEvidence(${f.id})">📎 ${h(f.fileName||'证明材料')}</div>`).join('') + '</div>';
  }
  const audits = (d.auditRecords||[]).map(a=>`<li>${h(a.auditorName||'系统')}：${h(a.opinion)} <span style="color:#6b7280">(${T(a.createdAt)})</span></li>`).join('')||'<li style="color:#9ca3af">暂无审核记录</li>';
  openModal(`申请 #${id} - ${d.projectName||''}`,
    `<div class="info-grid">
      <div class="info-item"><label>题目</label><input readonly value="${h(d.projectName)}" /></div>
      <div class="info-item"><label>分类/子类</label><input readonly value="${h(d.category)} / ${h(d.subCategory)}" /></div>
      <div class="info-item"><label>项目名</label><input readonly value="${h(d.itemName)}" /></div>
      <div class="info-item"><label>状态</label><input readonly value="${ST[d.status]||d.statusName}" /></div>
      <div class="info-item"><label>系统分</label><input readonly value="${d.systemCalculatedScore||0}" /></div>
      <div class="info-item"><label>最终分</label><input readonly value="${d.finalScore||0}" /></div>
      <div class="info-item"><label>提交时间</label><input readonly value="${T(d.submittedAt)}" /></div>
      <div class="info-item"><label>学生</label><input readonly value="${h(d.studentName)} ${h(d.studentId)} ${h(d.className)}" /></div>
    </div>
    <div class="info-item" style="margin-bottom:8px"><label>描述</label><textarea rows="2" readonly>${h(d.description)}</textarea></div>
    ${d.rejectReason?`<div class="info-item"><label>驳回原因</label><textarea rows="2" readonly>${h(d.rejectReason)}</textarea></div>`:''}
    ${evHtml}
    <h4 style="margin:14px 0 6px">审核记录</h4><ol style="padding-left:20px;font-size:13px;line-height:1.8">${audits}</ol>`,
    [
      {text:'AI辅助核验', cls:'btn btn-primary', fn:()=>startApplicationAi(id)},
      {text:'查看AI建议', cls:'btn', fn:()=>showApplicationAi(id)},
      {text:'关闭', cls:'btn', fn:closeModal}
    ]);
}

async function startApplicationAi(id){
  if(!beginAction('ai-app:'+id)) return;
  try{
    const job=await api('/api/ai/application/'+id+'/analyze',{method:'POST'});
    if(job){toast('AI辅助核验已启动，材料会先在本机脱敏','ok');pollApplicationAi(id,0);}
  }finally{endAction('ai-app:'+id);}
}
async function pollApplicationAi(id,attempt){
  const job=await api('/api/ai/application/'+id+'/latest');
  if(!job)return;
  if(['completed','failed'].includes(job.status)){toast(job.status==='completed'?'AI建议已生成':(job.errorMessage||'AI分析失败'),job.status==='completed'?'ok':'err');showApplicationAi(id);return;}
  if(attempt<45)setTimeout(()=>pollApplicationAi(id,attempt+1),2000);else toast('AI仍在后台分析，可稍后查看','ok');
}
async function showApplicationAi(id){
  const job=await api('/api/ai/application/'+id+'/latest');
  if(!job){toast('该申请还没有AI核验记录','err');return;}
  openModal('申请 #'+id+' AI辅助核验',`<div class="grid"><div class="card"><small>任务状态</small><div class="number" style="font-size:18px">${h(job.status)}</div></div><div class="card"><small>材料匹配</small><div class="number" style="font-size:18px">${h(job.verificationStatus||'-')}</div></div><div class="card"><small>建议分</small><div class="number">${job.suggestedScore??'-'}</div></div></div><div class="panel"><b>建议理由：</b>${h(job.reason||job.errorMessage||'等待生成')}<br><br><b>脱敏材料摘要：</b><div class="tip">${h(job.evidenceSummary||'暂无')}</div></div><div class="tip">AI结果仅供审核人员参考，不会修改申请分数、审核状态或最终成绩。</div>`,[{text:'关闭',cls:'btn',fn:closeModal}]);
}

async function downloadStudentReport(studentId){
  try{
    const res=await fetch('/api/report/student/'+encodeURIComponent(studentId)+'.pdf',{headers:auth()});
    if(!res.ok){const data=await res.json().catch(()=>({}));toast(data.message||'PDF生成失败','err');return;}
    const blob=await res.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download='zongce_'+studentId+'.pdf';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){toast('PDF生成失败','err');}
}

async function loadStudentPublications(){
  const [announcements,objections]=await Promise.all([api('/api/announcement/list'),api('/api/objection/list')]);
  if(!announcements||!objections){$('#m7').innerHTML='<div class="empty">公示信息加载失败</div>';return;}
  const objectionRows=(objections.list||[]).map(x=>`<tr><td>${h(x.announcementTitle)}</td><td>${h(x.scoreItem)}</td><td>${h(x.type)}</td><td><span class="badge ${x.status==='pending'?'s1':x.status==='accepted'?'s2':'s3'}">${h({pending:'处理中',accepted:'异议成立',rejected:'异议不成立',need_more:'需补充材料'}[x.status]||x.status)}</span></td><td>${h(x.resolution||'-')}</td><td>${h(x.createdAt)}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">暂无异议记录</td></tr>';
  const cards=(announcements.list||[]).map(x=>`<div class="panel"><div style="display:flex;justify-content:space-between;gap:10px"><div><b>${h(x.title)}</b><div class="tip">${h(x.scopeType==='all'?'全部学生':x.scopeValue)} · ${h(x.startsAt)} 至 ${h(x.endsAt)}</div></div><span class="badge ${x.status==='active'?'s2':x.status==='upcoming'?'s1':'s3'}">${h({active:'公示中',upcoming:'未开始',ended:'已结束',closed:'已关闭'}[x.status]||x.status)}</span></div><p>${h(x.description||'')}</p><button class="btn btn-sm" onclick="viewStudentPublication(${x.id})">查看本人公示成绩</button> ${x.status==='active'?`<button class="btn btn-sm btn-primary" onclick="newObjection(${x.id})">提交异议</button>`:''}</div>`).join('')||'<div class="empty">暂无与你相关的成绩公示</div>';
  $('#m7').innerHTML=cards+'<h4 style="margin-top:18px">我的异议</h4><table class="tbl"><thead><tr><th>公示</th><th>分数项</th><th>类型</th><th>状态</th><th>处理意见</th><th>提交时间</th></tr></thead><tbody>'+objectionRows+'</tbody></table>';
}
async function viewStudentPublication(id){
  const d=await api('/api/announcement/'+id);if(!d)return;
  const x=(d.results||[])[0];if(!x){toast('当前公示没有你的成绩数据','err');return;}
  openModal(h(d.announcement.title),`<div class="grid"><div class="card"><small>综合总分</small><div class="number">${x.totalScore}</div></div><div class="card"><small>班级排名</small><div class="number">${x.classRank||'-'}</div></div><div class="card"><small>年级排名</small><div class="number">${x.gradeRank||'-'}</div></div><div class="card"><small>终审状态</small><div class="number" style="font-size:18px">${x.isFinalized?'已终审':'核算中'}</div></div></div>`,[{text:'关闭',cls:'btn',fn:closeModal}]);
}
function newObjection(announcementId){
  openModal('提交成绩异议',`<div class="info-grid"><div class="info-item"><label>关联分数项</label><input id="obj_item" value="综合测评总分"></div><div class="info-item"><label>异议类型</label><select id="obj_type"><option>分数计算错误</option><option>类别归类错误</option><option>材料未被认可</option><option>其他</option></select></div></div><div class="info-item"><label>异议说明（最多500字）</label><textarea id="obj_desc" maxlength="500" rows="5"></textarea></div>`,[{text:'提交',cls:'btn btn-primary',fn:async()=>{const r=await api('/api/objection',{method:'POST',body:JSON.stringify({announcement_id:announcementId,score_item:$('#obj_item').value,objection_type:$('#obj_type').value,description:$('#obj_desc').value})});if(r){toast('异议已提交','ok');closeModal();loadStudentPublications();}}},{text:'取消',cls:'btn',fn:closeModal}]);
}
async function loadStudentM4(){
  const d = await api('/api/application/list?page_size=999&status=0');
  const list = (d && d.list) ? d.list : [];
  let rowsHtml;
  if(!list.length) rowsHtml = '<div class="empty">目前没有草稿加分申请</div>';
  else rowsHtml = `<table class="tbl"><thead><tr><th>ID</th><th>题目</th><th>项目</th><th>状态</th><th>分数</th><th>创建时间</th><th>操作</th></tr></thead>
    <tbody>${list.map(it=>`
      <tr><td>${it.id}</td><td>${h(it.projectName)}</td><td>${h(it.itemName)}</td>
      <td><span class="badge ${SC[it.status]}">${ST[it.status]||it.statusName}</span></td>
      <td>${it.systemCalculatedScore||0}</td><td>${T(it.createdAt)}</td>
      <td><button class="btn btn-sm btn-primary" onclick="submitApp(${it.id})">提交</button>
        <button class="btn btn-sm" onclick="${it.status===0?`editDraftApp(${it.id})`:`showAppDetail(${it.id})`}">${it.status===0?'修改':'详情'}</button>
        <button class="btn btn-sm btn-danger" onclick="delApp(${it.id})">删除</button></td>
      </tr>`).join('')}</tbody></table>`;
  $('#m4').innerHTML = `
    <div style="margin-bottom:12px;text-align:right"><button class="btn btn-primary" onclick="openCreateApp()">＋ 创建加分申请</button></div>
    ${rowsHtml}
  `;
}
async function submitApp(id){ if(!confirm('确认提交该申请？提交后进入审核中状态') || !beginAction('submit:'+id)) return;
  try{ const r = await api(`/api/application/submit/${id}`, {method:'PUT'}); if(r!==null){ toast('已提交，等待审核', 'ok'); loadStudentM3(); loadStudentM4(); loadStudentOverview(); } }
  finally{ endAction('submit:'+id); } }
async function delApp(id){ const actionKey='delete:'+id; if(!confirm('确认删除该草稿？不可恢复') || !beginAction(actionKey)) return;
  try{ const r = await api(`/api/application/delete/${id}`, {method:'DELETE'}); if(r!==null){ toast('已删除', 'ok'); loadStudentM4(); loadStudentOverview(); } }
  finally{ endAction(actionKey); } }
async function editDraftApp(id){
  const d = await api('/api/application/detail/'+id);
  if(!d) return;
  if(![0,3,4].includes(d.status)){ toast('该申请当前状态不能修改','err'); return; }
  const groups = (await api('/api/rule/grouped')) || {};
  const cats = Object.keys(groups);
  const opts = (arr,val)=>arr.map(x=>`<option value="${h(x)}" ${x===val?'selected':''}>${h(x)}</option>`).join('');
  openModal(`修改草稿申请 #${id}`,
    `<div class="info-grid">
      <div class="info-item"><label>题目 *</label><input id="app_title" value="${d.projectName||''}" /></div>
      <div class="info-item"><label>大类（申请加分领域）</label><select id="app_cat" onchange="renderSubCat()">${opts(cats, d.category||'')}</select></div>
      <div class="info-item"><label>子类 *</label><select id="app_sub" onchange="updateRuleEstimate()"></select></div>
      <div class="info-item"><label>项目级别</label><select id="app_level">${opts(['国家级','省级','市级','校级','院级','班级级'],d.projectLevel||'校级')}</select></div>
      <div class="info-item"><label>获奖/参与日期</label><input id="app_date" type="date" value="${d.projectDate||''}" /></div>
      <div class="info-item"><label>团队总人数</label><input id="app_total" type="number" min="1" value="${d.teamTotal||1}" oninput="updateRuleEstimate()" /></div>
      <div class="info-item"><label>个人排名</label><input id="app_rank" type="number" min="1" value="${d.teamRank||1}" oninput="updateRuleEstimate()" /></div>
      <div class="info-item"><label>项目描述</label><textarea rows="3" id="app_desc">${d.description||''}</textarea></div>
      <div class="info-item"><label>备注</label><textarea rows="2" id="app_remark">${d.remark||''}</textarea></div>
      <div class="info-item"><label>证明材料（jpg/png/pdf，≤10MB，可空=保留原文件）</label><input id="app_file" type="file" accept=".jpg,.jpeg,.png,.pdf" /></div>
      <div id="app_estimate" class="rule-estimate"></div>
    </div>`,
    [ {text:'保存',cls:'btn btn-primary', fn:()=>saveCreateApp(false, id)}, {text:'取消',cls:'btn', fn:closeModal} ]
  );
  window.catGroups = groups; setTimeout(()=>renderSubCat(d.subCategory||''), 10);
}
async function openCreateApp(){
  const d = await api('/api/rule/grouped');
  const groups = d || {};
  const cats = Object.keys(groups);
  const opts = (arr,val)=>arr.map(x=>`<option value="${h(x)}" ${x===val?'selected':''}>${h(x)}</option>`).join('');
  openModal('创建加分申请',
    `<div class="info-grid">
      <div class="info-item"><label>题目 *</label><input id="app_title" placeholder="如 第八届大学生创新创业训练" /></div>
      <div class="info-item"><label>大类（申请加分领域）</label><select id="app_cat" onchange="renderSubCat()">${opts(cats)}</select></div>
      <div class="info-item"><label>子类 *</label><select id="app_sub" onchange="updateRuleEstimate()"></select></div>
      <div class="info-item"><label>项目级别</label><select id="app_level">${opts(['国家级','省级','市级','校级','院级','班级级'],'校级')}</select></div>
      <div class="info-item"><label>获奖/参与日期</label><input id="app_date" type="date" /></div>
      <div class="info-item"><label>团队总人数</label><input id="app_total" type="number" min="1" value="1" oninput="updateRuleEstimate()" /></div>
      <div class="info-item"><label>个人排名</label><input id="app_rank" type="number" min="1" value="1" oninput="updateRuleEstimate()" /></div>
      <div class="info-item"><label>项目描述</label><textarea rows="3" id="app_desc"></textarea></div>
      <div class="info-item"><label>备注</label><textarea rows="2" id="app_remark"></textarea></div>
      <div class="info-item"><label>证明材料（jpg/png/pdf，≤10MB，可空先保存草稿）</label><input id="app_file" type="file" accept=".jpg,.jpeg,.png,.pdf" /></div>
      <div id="app_estimate" class="rule-estimate"></div>
    </div>
    <div style="font-size:12px;color:#6b7280;margin-top:8px">提交后会显示在模块③「我的申请详情」里；即使不传材料也可先保存为草稿，再点提交</div>`,
    [ {text:'保存为草稿',cls:'btn', fn:()=>saveCreateApp(false)}, {text:'创建并提交',cls:'btn btn-primary', fn:()=>saveCreateApp(true)}, {text:'取消',cls:'btn', fn:closeModal} ]
  );
  window.catGroups = groups; renderSubCat();
}
function renderSubCat(preSel){
  const g = window.catGroups || {};
  const sub_obj = g[$('#app_cat').value] || {};
  const subs = Array.isArray(sub_obj) ? sub_obj : Object.keys(sub_obj);
  $('#app_sub').innerHTML = subs.map(s=>`<option value="${h(s)}" ${s===preSel?'selected':''}>${h(s)}</option>`).join('');
  updateRuleEstimate();
}
function updateRuleEstimate(){
  const target=$('#app_estimate'); if(!target||!$('#app_cat')||!$('#app_sub'))return;
  const category=$('#app_cat').value, sub=$('#app_sub').value, group=(window.catGroups||{})[category]||{};
  const rules=Array.isArray(group)?group:(group[sub]||[]), rule=rules[0];
  if(!rule){target.innerHTML='<span>请选择有效规则以查看预计分数</span>';return;}
  const rank=Number($('#app_rank')?.value||1), mapping=rule.rankCoefficient||{}, coefficient=Number(mapping[String(rank)]??mapping.default??1);
  const base=Number(rule.baseScore??rule.base_score??0), max=rule.maxScore??rule.max_score;
  let score=base*coefficient; if(max!==null&&max!==undefined)score=Math.min(score,Number(max));
  target.innerHTML=`<span><small>规则预估（最终以教师审核和聚合封顶为准）</small><br><b>${score.toFixed(2)} 分</b></span><span class="tip">基础分 ${base} × 排名系数 ${coefficient}${max!==null&&max!==undefined?`，单项上限 ${max}`:''}</span>`;
}
async function saveCreateApp(submit_now, editing_id){
  const title = $('#app_title').value.trim();
  if(!title){ toast('请填写题目', 'err'); return; }
  const cat = $('#app_cat').value, sub = $('#app_sub').value;
  const rules = await api('/api/rule/list'); const list = Array.isArray(rules)?rules:(rules.list||[]);
  const rule = list.find(r=>(r.category===cat) && (r.subCategory===sub||r.sub_category===sub));
  if(!rule){ toast('找不到对应的加分规则', 'err'); return; }
  const teamTotal = Number($('#app_total').value||1), teamRank = Number($('#app_rank').value||1);
  if(teamRank<1 || teamTotal<1 || teamRank>teamTotal){ toast('个人排名必须在1和团队总人数之间','err'); return; }
  const body = {
    rule_id: rule.id, project_name: title,
    project_level: $('#app_level').value, project_date: $('#app_date').value,
    team_total: teamTotal, team_rank: teamRank,
    description: $('#app_desc').value, remark: $('#app_remark').value,
    apply_score: rule.baseScore||rule.base_score, submit_now:false
  };
  const file = $('#app_file').files[0];
  let appId, modeMsg;
  if(editing_id){
    // 编辑模式：强制只走 PUT 更新原草稿，绝不新建
    const r = await api(`/api/application/update/${editing_id}`, {method:'PUT', body:JSON.stringify(body)});
    if(!r) return;
    appId = editing_id;
    modeMsg = `申请 #${appId} 已保存修改（未新建申请）`;
  }else{
    // 新建模式：走 POST 创建新草稿
    const r = await api('/api/application/create', {method:'POST', body:JSON.stringify(body)});
    if(!r) return;
    appId = r.id || r.applicationId;
    modeMsg = '已保存为新草稿';
  }
  if(file && appId){
    const fd = new FormData(); fd.append('file', file);
    const uploaded = await uploadFile('/api/file/upload', fd, `application_id=${appId}`);
    if(!uploaded){ toast('申请已保存为草稿，但材料上传失败','err'); return; }
  }
  if(submit_now){
    const submitted = await api(`/api/application/submit/${appId}`, {method:'PUT'});
    if(submitted===null){ toast('申请已保存为草稿，请补充材料后再提交','err'); return; }
    modeMsg = `申请 #${appId} 已提交审核`;
  }
  toast(modeMsg, 'ok');
  closeModal(); loadStudentM3(); loadStudentM4(); loadStudentOverview();
}
