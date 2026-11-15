'use strict';
const $=id=>document.getElementById(id);
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const percent=x=>x===null||x===undefined?'—':(Number(x)*100).toFixed(1)+'%';
const usd=x=>x===null||x===undefined?'Not priced':'$'+Number(x).toFixed(4);
const ms=x=>x===null||x===undefined?'—':Number(x).toFixed(0)+'ms';
const number=x=>x===null||x===undefined?'—':Number(x).toLocaleString();
let csrfToken=null;
const state={project:null,runs:[],selected:null,view:'overview'};
async function api(path,payload){const response=await fetch('/api/v2/'+path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json',...(csrfToken?{'X-CSRF-Token':csrfToken}:{})},body:JSON.stringify(payload)});const json=await response.json();if(!response.ok){if(response.status===401){$('authentication').classList.remove('hidden');$('login-form').classList.remove('hidden');}throw Error(json.detail||'Request failed');}return json;}
function error(message){$('error').textContent=message;$('error').classList.remove('hidden');}
function clearError(){$('error').classList.add('hidden');}
function switchView(view){state.view=view;document.querySelectorAll('.view').forEach(el=>el.classList.toggle('hidden',el.id!==view));document.querySelectorAll('.nav-btn').forEach(el=>el.classList.toggle('active',el.dataset.view===view));$('crumb').textContent='Workspace / '+view[0].toUpperCase()+view.slice(1);if(view==='history')renderHistory();}
async function load(){try{clearError();const [project,runs]=await Promise.all([api('project'),api('runs')]);state.project=project;state.runs=runs;$('workspace-name').textContent=project.name;renderProject();renderHistory();if(state.selected)await selectRun(state.selected);else if(runs.some(r=>r.status==='completed'))await selectRun(runs.find(r=>r.status==='completed').id);pollBusy();}catch(e){error(e.message);}}
function renderProject(){let p=state.project;if(!p)return;
  $('onboarding').classList.toggle('hidden',p.document_count>0&&p.task_count>0&&p.credential_ready);
  $('stats').innerHTML=[['Documents',number(p.document_count),'Actual imported files'],['Benchmark tasks',number(p.task_count),'Registered expectations'],['Completed runs',number(state.runs.filter(r=>r.status==='completed').length),'Locally persisted'],['Live model',escape(p.model_name||'Agent endpoint'),p.credential_ready?'Credential available':'Credential missing']].map(a=>`<div class="stat"><small>${a[0]}</small><strong>${a[1]}</strong><span>${a[2]}</span></div>`).join('');
  $('sources').innerHTML=p.sources.map((s,i)=>`<div class="source-row"><div class="source-left"><span class="source-dot" style="background:${['#6ce1c3','#a1abff','#edb977','#de92b3'][i%4]}"></span><div><b>${escape(s.name)}</b><small>${escape(s.id)}</small></div></div><span class="count">${s.document_count} docs</span></div>`).join('')||'<div class="empty">No sources configured.</div>';
  $('exclude-list').innerHTML=p.sources.map(s=>`<label><input type="checkbox" class="source-check" value="${escape(s.id)}"> ${escape(s.name)} <small>${s.document_count} files</small></label>`).join('')||'<div class="empty">No source files.</div>';
  $('document-check-list').innerHTML=(p.documents||[]).map(d=>`<label><input type="checkbox" class="document-check" value="${escape(d.id)}"> ${escape(d.title)} <small>${escape(d.source_id)}</small></label>`).join('');
  $('task-limit').max=Math.min(200,Math.max(1,p.task_count));$('task-limit').value=Math.min(10,Math.max(1,p.task_count));
  $('run-btn').disabled=!(p.document_count&&p.task_count&&p.credential_ready);
  $('diagnostics').innerHTML=[['Deployment','Single-user localhost beta'],['Independent quality','Pending external review'],['Native accounting','Pending; owned live inference gated'],['Workspace',p.data_root],['Runner',p.runner],['Model',p.model_name],['Host',p.endpoint_host],['API credential',p.credential_ready?'Ready':'Missing'],['Documents',number(p.document_count)],['Benchmark tasks',number(p.task_count)],['Token price config',p.model_pricing_configured?'Configured':'Not configured: USD costs unavailable']].map(([k,v])=>`<div class="source-row"><span style="color:#94afc4;font-size:11px">${escape(k)}</span><b style="font-size:11px;word-break:break-word;text-align:right">${escape(v)}</b></div>`).join('');
  renderCallEstimate();}
function renderCallEstimate(){if(!state.project)return;let mode=document.querySelector('input[name="mode"]:checked')?.value||'baseline';let tasks=Math.min(Number($('task-limit').value)||0,state.project.task_count);let docs=Array.from(document.querySelectorAll('.document-check:checked')).length;let variants=mode==='ablation'?1+state.project.sources.length:(mode==='document_ablation'?1+docs:1);$('call-estimate').textContent=`Planned model calls: ${tasks*variants}. Check your project.json call limit before starting.`;document.querySelectorAll('.source-check').forEach(x=>x.disabled=mode!=='baseline');$('document-choice').classList.toggle('hidden',mode!=='document_ablation');}
function mini(label,value,note=''){return `<div><span>${escape(label)}</span><strong>${escape(value)}</strong>${note?`<small>${escape(note)}</small>`:''}</div>`;}
function renderRun(run){state.selected=run.id;let r=run.report;if(!r){$('run-output').innerHTML=`<div class="empty">${escape(run.status)}: ${escape(run.error||'Run is in progress.')}</div>`;return;}
  if(r.kind==='knowledge_decision'){renderDecision(r);$('run-output').textContent='Knowledge decision loaded in Knowledge Change Review above.';$('tasks-panel').classList.add('hidden');return;}
  if(r.kind==='reliability_study'){renderReliability(run);return;}
  if(r.kind==='knowledge_release'){renderKnowledge(run);return;}
  if(r.kind==='data_ci'){renderDataCI(run);return;}
  if(r.kind==='standalone_policy_study'){renderStudy(run);return;}
  if(!r.variants){$('run-output').innerHTML='<pre>'+escape(JSON.stringify(r,null,2))+'</pre>';$('tasks-panel').classList.add('hidden');return;}
  let main=r.variants[0],m=main.metrics;
  const metricHtml=`<div class="metric-mini">${mini('Task accuracy',percent(m.accuracy),`${m.passed}/${m.task_count} correct · Wilson 95% CI ${m.accuracy_ci95?percent(m.accuracy_ci95[0])+'–'+percent(m.accuracy_ci95[1]):'—'}`)}${mini('Mean response time',ms(m.mean_latency_ms),'Real wall-clock latency')}${mini('Token usage',number((m.provider_reported_prompt_tokens??0)+(m.provider_reported_completion_tokens??0)),m.provider_reported_prompt_tokens===null?'Not reported by provider':'Provider reported')}${mini('Total run cost',usd(m.total_cost_usd),m.cost_type==='unavailable'?'Rate or usage unavailable':m.cost_type)}</div>`;
  let impact=(r.impacts||[]).map(i=>`<div class="result-row"><span>Without <b>${escape([...i.excluded_sources,...(i.excluded_documents||[])].join(', '))}</b></span><span class="${i.delta_accuracy_points<0?'negative':'positive'}">${i.delta_accuracy_points>0?'+':''}${i.delta_accuracy_points} pp · ${i.lost_tasks.length} lost</span></div>`).join('');
  $('run-output').innerHTML=`<div class="run-head"><span>${escape(run.id)} · ${escape(r.mode)} · ${r.api_calls} calls</span><span>${escape(new Date(run.created_at).toLocaleString())}</span></div>${metricHtml}${impact||'<p class="detail">One configuration. Run a source ablation study to rank source impacts.</p>'}<p class="fine">${escape(r.disclaimer)}</p>`;
  $('latest').innerHTML=metricHtml; $('tasks-panel').classList.remove('hidden');
  $('task-rows').innerHTML=main.tasks.map(t=>`<tr><td><b>${escape(t.id)}</b><small>${escape(t.category)}</small></td><td>${escape(t.question)}<small>Answer: ${escape(t.actual).slice(0,500)}</small><small>Expected: ${escape(t.expected).slice(0,200)}</small><small>Retrieved: ${escape(t.retrieved_source_ids.join(', ')||'(none)')}</small></td><td><span class="result-tag ${t.correct?'pass':'fail'}">${t.correct?'PASS':'FAIL'}</span><small>${escape(t.citations.join(', ')||'No citations')}</small></td><td>${ms(t.end_to_end_latency_ms)}<small>${t.prompt_tokens===null?'Tokens unreported':t.prompt_tokens+' input tokens'}</small></td></tr>`).join('');
  if(state.project){let cells=$('stats').querySelectorAll('.stat');cells[2].innerHTML=`<small>Last run accuracy</small><strong>${percent(m.accuracy)}</strong><span>${m.passed}/${m.task_count} correct</span>`;cells[3].innerHTML=`<small>Mean task latency</small><strong>${ms(m.mean_latency_ms)}</strong><span>Measured end to end</span>`;}
}
function renderDecision(r){
  $('decision-status').textContent=`${r.verdict} · ${r.id} · ${r.overhead.generation_attempts} generations · release not authorized`;
  $('decision-summary').innerHTML=`<p>Evidence-qualified alternative: <b>${escape(r.recommended_experiment||'None')}</b>. Model accuracy, provider tokens and monetary savings: UNKNOWN.</p>`+
    r.recommendations.map(x=>`<p><b>${escape(x.recommendation)} ${escape(x.level)} ${escape(x.id)}</b> — ${escape(x.reason)}<br>Tasks: ${escape(x.affected_tasks.join(', ')||'Unknown')}<br>${escape(x.uncertainty)}</p>`).join('')+
    r.experiments.map(x=>`<p><b>${escape(x.name)}: ${escape(x.verdict)}</b> · reference losses: ${escape(x.conventional.reference_regressions.join(', ')||'None')} · estimated context-token difference: ${escape(x.delta_estimated_context_tokens)} (characters/4 estimate)</p>`).join('');
  $('decision-output').textContent=JSON.stringify(r,null,2);
}
$('decision-run').addEventListener('click',async()=>{try{
  $('decision-run').disabled=true;$('decision-status').textContent='Comparing evidence…';
  const r=await api('knowledge/decisions',{snapshot_id:$('decision-snapshot').value.trim(),alternatives:JSON.parse($('decision-alternatives').value),requirements:JSON.parse($('decision-requirements').value)});
  renderDecision(r);state.runs=await api('runs');renderHistory();
}catch(e){$('decision-status').textContent='Comparison failed: '+e.message;error(e.message);}finally{$('decision-run').disabled=false;}});
async function selectRun(id){try{let run=await api('runs/'+encodeURIComponent(id));renderRun(run);}catch(e){error(e.message);}}
function renderHistory(){let rows=state.runs;$('history-rows').innerHTML=rows.length?rows.map(r=>`<div class="run-item"><div><b>${escape(r.id)}</b> &nbsp; <span class="result-tag ${r.status==='completed'?'pass':'fail'}">${escape(r.status)}</span><small>${escape(r.mode)} · ${escape(new Date(r.created_at).toLocaleString())} ${r.metrics?'· '+percent(r.metrics.accuracy)+' accuracy':''}</small></div><button class="outline" data-run="${escape(r.id)}">View run</button></div>`).join(''):'<div class="empty">No evaluations recorded yet.</div>';
  let complete=rows.filter(r=>r.status==='completed' && ['baseline','ablation','document_ablation'].includes(r.mode));let options=complete.map(r=>`<option value="${escape(r.id)}">${escape(r.id)} · ${percent(r.metrics?.accuracy)}</option>`).join('');$('compare-before').innerHTML=options;$('compare-after').innerHTML=options;if(complete.length>=2){$('compare-before').value=complete[1].id;$('compare-after').value=complete[0].id;}
  document.querySelectorAll('[data-run]').forEach(b=>b.addEventListener('click',async()=>{await selectRun(b.dataset.run);switchView('experiments');}));}
async function start(){try{clearError();let mode=document.querySelector('input[name="mode"]:checked').value;let exclude=Array.from(document.querySelectorAll('.source-check:checked')).map(x=>x.value);let confirmed=$('confirm').checked;if(!confirmed){error('Check the model-charge acknowledgement before starting.');return;}
  let ids=Array.from(document.querySelectorAll('.document-check:checked')).map(x=>x.value);let params={mode,exclude_sources:mode==='baseline'?exclude:[],document_ids:mode==='document_ablation'?ids:[],max_tasks:Number($('task-limit').value),acknowledge_model_calls:confirmed};let result=await api('runs',params);
  $('status').textContent='Running '+result.planned_model_calls+' calls';$('status').className='pill busy';$('run-btn').disabled=true;$('run-output').innerHTML=`<div class="empty">Running experiment ${escape(result.id)}. Processing real tasks with the configured model/agent…</div>`;
  await pollRun(result.id);
}catch(e){error(e.message);$('run-btn').disabled=false;}}
async function pollRun(id){for(let i=0;i<900;i++){await new Promise(r=>setTimeout(r,1000));let r=await api('runs/'+encodeURIComponent(id));if(r.status==='completed'||r.status==='failed'){await load();renderRun(r);$('run-btn').disabled=false;$('status').textContent=r.status==='completed'?'Completed':'Failed';$('status').className='pill '+(r.status==='failed'?'bad':'');if(r.status==='failed')error(r.error);return;}}error('The run is still processing; check Run History.');}
function pollBusy(){let run=state.project?.running;if(run){$('status').textContent=run.message||'Running';$('status').className='pill busy';}else if(!$('status').classList.contains('bad')){$('status').textContent='Ready';$('status').className='pill';}}
async function compare(){try{clearError();let before=$('compare-before').value,after=$('compare-after').value;if(!before||!after||before===after)throw Error('Choose two different completed runs.');let x=await api(`compare?before=${encodeURIComponent(before)}&after=${encodeURIComponent(after)}`);let m=x.comparison;
$('comparison').innerHTML=`<div class="metric-mini">${mini('Accuracy change',(m.delta_accuracy_points>0?'+':'')+m.delta_accuracy_points+' pp')}${mini('Change in response time',ms(m.delta_mean_latency_ms))}${mini('Newly failed tasks',number(m.lost_tasks.length))}${mini('Cost difference',m.delta_cost_usd===null?'Unknown':usd(m.delta_cost_usd))}</div><p class="detail"><b>Changed files:</b> ${escape(x.changed_documents.join(', ')||'None')}<br><b>Added:</b> ${escape(x.new_documents.join(', ')||'None')}<br><b>Removed:</b> ${escape(x.removed_documents.join(', ')||'None')}<br><b>Regressions:</b> ${escape(m.lost_tasks.join(', ')||'None')}<br><b>Recovered tasks:</b> ${escape(m.gained_tasks.join(', ')||'None')}</p><p class="fine">${escape(x.warnings.join(' '))}</p>`;
}catch(e){error(e.message);}}
function renderStudy(run){
  const r=run.report;
  const entries=r.experiments.filter(e=>e.partition==='heldout');
  let table='<div class="table-scroll"><table><thead><tr><th>Configuration</th><th>Accuracy</th><th>Tokens</th><th>Cost</th><th>Grounding</th></tr></thead><tbody>';
  for(const e of entries)for(const v of e.runs){const m=v.metrics;table+=`<tr><td>${escape(e.name)} / ${escape(v.repeat)}</td><td>${percent(m.accuracy)}</td><td>${m.total_tokens===null?'Unreported':number(m.total_tokens)}</td><td>${usd(m.total_cost_usd)}</td><td>${m.groundedness===null?'Unreviewed':percent(m.groundedness)}</td></tr>`;}
  table+='</tbody></table></div>';
  $('run-output').innerHTML=`<p><b>${escape(r.observed_verdict||r.status)}</b> · ${escape(r.recommendation?.deployment_verdict||r.deployment)}</p><p>Evidence: ${escape(r.measurement_kind)} · Labels: ${escape(r.review_status)}</p>${table}<p>Frozen policies were selected on development tasks only. Observed differences do not establish superiority.</p>`;
  if(r.status==='completed')for(const format of ['json','csv','markdown','review']){const a=document.createElement('a');a.href='/api/v2/studies/'+encodeURIComponent(run.id)+'/export?format='+format;a.textContent='Download '+format+' ';a.className='outline';$('run-output').appendChild(a);}
  $('tasks-panel').classList.add('hidden');
}
async function startStudy(){
  try{clearError();if(!$('study-confirm').checked)throw Error('Confirm free localhost model execution first.');
    $('study-btn').disabled=true;
    $('run-output').textContent='Running grouped policy study…';
    const result=await api('studies',{acknowledge_model_calls:true,quality_floor:Number($('study-quality').value),objective:$('study-objective').value});
    await load();renderStudy({id:result.id,report:result.report});
  }catch(e){error(e.message);}finally{$('study-btn').disabled=false;}
}
function renderDataCI(run){
  const r=run.report;
  let html=`<p><b>Data CI: ${escape(r.verdict||r.status)}</b> · severity ${escape(r.severity||'unknown')}</p>`;
  html+=`<p>Changed: ${escape([...(r.changed_documents||[]),...(r.removed_documents||[]),...(r.added_documents||[])].join(', ')||'None')}</p>`;
  if(r.comparison)html+=`<p>New failures: ${escape(r.comparison.lost_tasks.join(', ')||'None')} · Accuracy change: ${escape(r.comparison.delta_accuracy_points)} pp · Latency change: ${escape(r.comparison.delta_mean_latency_ms)} ms</p>`;
  for(const task of r.task_changes||[])html+=`<p><b>${escape(task.task_id)}</b> · ${escape(task.severity)} · Reference coverage ${escape(task.baseline_evidence_coverage)} → ${escape(task.candidate_evidence_coverage)}<br>Plausibly related documents: ${escape(task.plausibly_related_documents.join(', ')||'Uncertain')}<br>${escape(task.diagnosis?.reason||'')}</p>`;
  for(const action of r.suggested_actions||[])html+=`<p>Suggested review: ${escape(action.title||action.document_id)} · frozen version ${escape(action.frozen_fingerprint||'none')} · temporary rollback tested: ${escape(action.joint_rollback_tested)}</p>`;
  html+='<p>Associations are not conclusive causality. No detected regression is not proof of safety. No production policy or source was changed.</p>';
  $('run-output').innerHTML=html;$('tasks-panel').classList.add('hidden');
  if(run.id){const a=document.createElement('a');a.href='/api/v2/runs/'+encodeURIComponent(run.id);a.download='data-ci-report.json';a.textContent='Export persisted Data CI JSON';$('run-output').appendChild(a);}
}
async function freezeDataCI(){
  try{clearError();$('ci-freeze').disabled=true;const response=await api('data-ci/freeze',{});$('ci-snapshot').value=response.snapshot_id;$('ci-status').textContent='Frozen '+response.document_count+' documents. Edit source data, then run the comparison.';}
  catch(e){error(e.message);}finally{$('ci-freeze').disabled=false;}
}
async function startDataCI(){
  try{clearError();if(!$('ci-confirm').checked)throw Error('Confirm local model execution first.');$('ci-run').disabled=true;
    const result=await api('data-ci',{snapshot_id:$('ci-snapshot').value.trim(),acknowledge_model_calls:true,max_tasks:12,max_seconds:300});
    await load();renderDataCI({id:result.id,report:result.report});}
  catch(e){error(e.message);}finally{$('ci-run').disabled=false;}
}
function renderReliability(run){
  const r=run.report;
  let html=`<p><b>${escape(r.verdict||r.status)}</b> · Grounding review: ${escape(r.groundedness_review||'pending')}</p>`;
  html+='<table><thead><tr><th>Policy</th><th>Correct</th><th>Tokens</th><th>Median</th><th>Fallback</th><th>New failures</th></tr></thead><tbody>';
  for(const e of r.experiments||[])if(e.partition==='heldout'&&e.variant){const m=e.variant.metrics;html+=`<tr><td>${escape(e.name)}</td><td>${m.passed}/${m.task_count}</td><td>${m.total_tokens===null?'Unreported':number(m.total_tokens)}</td><td>${ms(m.median_latency_ms)}</td><td>${percent(m.fallback_rate)}</td><td>${escape((r.comparisons?.[e.name]?.lost_tasks||[]).join(', ')||'None')}</td></tr>`;}
  html+='</tbody></table><p>Evidence sufficiency is heuristic. No production changes were applied. Missing groundedness and costs remain unknown.</p>';
  $('run-output').innerHTML=html;$('tasks-panel').classList.add('hidden');
  if(run.id){const a=document.createElement('a');a.href='/api/v2/runs/'+encodeURIComponent(run.id);a.download='reliability-study.json';a.textContent='Export persisted reliability JSON';$('run-output').appendChild(a);}
}
document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>switchView(el.dataset.view)));$('refresh').addEventListener('click',load);$('run-btn').addEventListener('click',start);$('ci-freeze').addEventListener('click',freezeDataCI);$('ci-run').addEventListener('click',startDataCI);$('study-btn').addEventListener('click',startStudy);$('compare-btn').addEventListener('click',compare);$('task-limit').addEventListener('input',renderCallEstimate);$('document-check-list').addEventListener('change',renderCallEstimate);document.querySelectorAll('input[name="mode"]').forEach(x=>x.addEventListener('change',renderCallEstimate));initializeAuthentication();});

let knowledgeSpec=null, knowledgeApproval=null;
function renderKnowledge(run){
 const r=run.report;
 $('run-output').innerHTML=`<h3>Knowledge release: ${escape(r.verdict)}</h3><p>${escape(r.reason)}</p><p>Calls: ${escape(r.execution.calls)} · Unexecuted tasks: ${escape(r.execution.tasks_not_executed)}</p><p>Spec ${escape(r.spec_id)}</p>`+(r.tasks||[]).map(t=>`<p><b>${escape(t.task_id)}</b> · Approved change: ${escape(t.expected_change)} · Correct: ${escape(t.baseline_correct)} → ${escape(t.candidate_correct)} · Evidence loss: ${escape(t.evidence_loss)}<br>Candidate causes: ${escape(t.candidate_causes.join(', '))} (hypotheses)</p>`).join('');
 $('run-output').innerHTML+=`<p>Policy: ${escape(r.release_policy?.name||'historical legacy checks')}</p><pre>${escape(JSON.stringify(r.check_statuses||{},null,2))}</pre><p>Missing checks: ${escape((r.missing_checks||[]).join(', ')||'None')}</p><p>Blocking reasons: ${escape((r.blocking_reasons||[]).join(', ')||'None')}</p><p>Next actions: ${escape((r.next_actions||[]).join('; ')||'None')}</p><pre>${escape(JSON.stringify(r.versions||{},null,2))}</pre>`;
 $('tasks-panel').classList.add('hidden');
}
$('knowledge-plan').addEventListener('click',async()=>{try{
 knowledgeSpec=await api('knowledge/plan',{snapshot_id:$('ci-snapshot').value.trim(),intent:$('knowledge-intent').value.trim()?JSON.parse($('knowledge-intent').value):null});knowledgeApproval=null;
 $('knowledge-proposal').textContent=JSON.stringify(knowledgeSpec,null,2);$('knowledge-status').textContent='Proposal only. No labels changed.';
}catch(e){error(e.message);}});
$('knowledge-review').addEventListener('click',async()=>{try{
 if(!knowledgeSpec)throw Error('Propose changes first.');
 knowledgeApproval=await api('knowledge/review',{specification:knowledgeSpec,decisions:JSON.parse($('knowledge-decisions').value)});
 $('knowledge-status').textContent='Review recorded for specification '+knowledgeSpec.id;
}catch(e){error(e.message);}});
$('knowledge-release').addEventListener('click',async()=>{try{
 if(!knowledgeSpec||!$('ci-confirm').checked)throw Error('Propose changes and confirm local model execution.');
 $('knowledge-release').disabled=true;
 const report=await api('knowledge/release',{snapshot_id:$('ci-snapshot').value.trim(),specification:knowledgeSpec,approval:knowledgeApproval,policy:$('knowledge-policy').value,acknowledge_model_calls:true,max_calls:40,max_seconds:120});
 await load();renderKnowledge({report});$('knowledge-status').textContent=report.verdict+': '+report.reason;
}catch(e){error(e.message);}finally{$('knowledge-release').disabled=false;}});

async function initializeAuthentication(){
 try{const mode=await api('auth/mode');
 if(mode.authenticated){$('authentication').classList.remove('hidden');return;}
 await load();}catch(e){error(e.message);}
}
$('login-form').addEventListener('submit',async event=>{
 event.preventDefault();try{
 const session=await api('auth/login',{username:$('login-user').value,password:$('login-password').value});
 csrfToken=session.csrf;$('login-password').value='';$('login-form').classList.add('hidden');$('logout').classList.remove('hidden');
 $('auth-status').textContent=`Signed in as ${session.user.name} (${session.user.role}). Execution disabled pending production gates.`;
 await load();}catch(e){$('login-password').value='';error(e.message);}
});
$('logout').addEventListener('click',async()=>{
 try{await api('auth/logout',{});location.reload();}catch(e){error(e.message);}
});

let jobPollTimer=null;
async function inspectDurableJob(){
 try{const id=$('durable-job-id').value.trim();if(!id)throw Error('Enter a job ID.');
 const result=await api('jobs/'+encodeURIComponent(id));$('durable-output').textContent=JSON.stringify(result,null,2);
 if(!['COMPLETED','FAILED','CANCELLED','INCONCLUSIVE'].includes(result.job.state)){clearTimeout(jobPollTimer);jobPollTimer=setTimeout(inspectDurableJob,2000);}
 }catch(e){clearTimeout(jobPollTimer);error(e.message);}
}
$('durable-inspect').addEventListener('click',inspectDurableJob);
$('durable-cancel').addEventListener('click',async()=>{try{await api('jobs/'+encodeURIComponent($('durable-job-id').value.trim())+'/cancel',{});await inspectDurableJob();}catch(e){error(e.message);}});
$('fixture-submit').addEventListener('click',async()=>{try{
 if(!knowledgeSpec||!knowledgeApproval)throw Error('Create and review a change plan first.');
 const responses=JSON.parse($('fixture-answers').value);
 const auth=await api('fixture-authorizations',{specification:knowledgeSpec,max_attempts:20,max_seconds:60});
 const response=await fetch('/api/v2/jobs',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrfToken||'','Idempotency-Key':crypto.randomUUID()},body:JSON.stringify({operation:'fixture_release',specification:knowledgeSpec,approval:knowledgeApproval,fixture_authorization:auth.id,fixture_responses:responses,max_seconds:60})});
 const result=await response.json();if(!response.ok)throw Error(result.detail||'Fixture submission rejected');
 $('durable-job-id').value=result.job.id;await inspectDurableJob();
 }catch(e){error(e.message);}});

let semanticPacket=null;
$('semantic-load').addEventListener('click',async()=>{try{
 semanticPacket=await api('jobs/'+encodeURIComponent($('durable-job-id').value.trim())+'/review-packet?task_id='+encodeURIComponent($('semantic-task').value.trim()));
 $('semantic-packet').textContent=JSON.stringify(semanticPacket,null,2);
 $('semantic-status').textContent='Exact frozen evidence loaded. Enter your judgment; independence remains externally unverified.';
}catch(e){semanticPacket=null;$('semantic-packet').textContent='';error(e.message);}});
$('semantic-submit').addEventListener('click',async()=>{try{
 if(!semanticPacket)throw Error('Load the exact review packet first.');
 if($('durable-job-id').value.trim()!==semanticPacket.job||$('semantic-task').value.trim()!==semanticPacket.task)throw Error('Job/task changed: reload the review packet.');
 const tri=id=>$(id).value==='unknown'?null:$(id).value==='true';
 const record=await api('jobs/'+encodeURIComponent(semanticPacket.job)+'/semantic-reviews',{task_id:semanticPacket.task,binding:semanticPacket.binding,decision:$('semantic-decision').value,claims:JSON.parse($('semantic-claims').value||'[]'),dimensions:{semantic_correctness:tri('semantic-correct'),citation_correctness:tri('semantic-citations'),scope_appropriate:tri('semantic-scope'),uses_outdated_fact:tri('semantic-outdated')},rationale:$('semantic-rationale').value,authorization_basis:$('semantic-basis').value});
 const assessment=await api('jobs/'+encodeURIComponent(semanticPacket.job)+'/assessment');
 $('semantic-status').textContent='Judgment '+record.id+' recorded by authenticated '+record.reviewer.name+'. Release assessment: '+assessment.verdict+'. External independence: '+String(record.independence_verified_externally)+'.';
}catch(e){error(e.message);}});
