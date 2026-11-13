
(() => {
'use strict';
const C=JSON.parse(document.getElementById('qa-config').textContent);
const KEY='qa-bench:'+C.slug+':v1';let state={executions:[],defects:[],evidence:[],customCases:[],auto:{}};
try{const p=JSON.parse(localStorage.getItem(KEY)||'{}');if(p&&typeof p==='object'){for(const k of Object.keys(state))if(p[k]&& (Array.isArray(state[k])?Array.isArray(p[k]):typeof p[k]==='object'))state[k]=p[k];}}catch{}
let tab='engineering',selected=(C.cases[0]||{}).id||'',showCase='',running=false;
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[ch]));
const fmt=x=>esc(JSON.stringify(x,null,2));const cases=()=>[...C.cases,...state.customCases];
const latest=id=>state.executions.find(x=>x.caseId===id);
const count=(k)=>state.executions.filter((x,i,a)=>a.findIndex(v=>v.caseId===x.caseId)===i&&x.status===k).length;
const total=()=>cases().length;const completed=()=>new Set(state.executions.map(x=>x.caseId)).size;
function save(){try{localStorage.setItem(KEY,JSON.stringify(state));return true}catch{note('Browser storage unavailable; export your report.');return false}}
function note(s){document.querySelector('#notice').textContent=s}
function tag(v){const t=String(v||'Not run');return '<span class="tag '+(t==='P0'?'p0':t.toLowerCase().replaceAll(' ','-'))+'">'+esc(t)+'</span>'}
function renderReq(){return '<h2>Requirements analysis and traceability</h2><p>Representative acceptance criteria and product-owner clarification questions derived from the application. They are not approved client requirements.</p><div class="grid">'+C.requirements.map(r=>'<article class="panel"><div class="row"><strong>'+esc(r.id)+'</strong>'+tag(r.risk)+'</div><h3>'+esc(r.title)+'</h3><p><b>Acceptance criteria:</b> '+esc(r.acceptance)+'</p><p><b>Clarify with Product Owner:</b> '+esc(r.clarify)+'</p><div class="fine">'+cases().filter(c=>c.req===r.id).length+' linked manual cases · '+esc(r.id)+'</div><div class="actions"><button class="btn alt" data-act="req" data-id="'+esc(r.id)+'">Inspect linked cases</button></div></article>').join('')+'</div>'}
function listCases(){const req=showCase||'', filtered=cases().filter(x=>!req||x.req===req);
return '<h2>Test design repository</h2><p>Application-specific functional, integration, boundary, negative, E2E, and reliability scenarios. Tests here are specifications until executed and evidenced.</p><div class="actions"><button class="btn" data-act="add-case">+ Write test case</button><button class="btn alt" data-act="all-cases">Show all cases</button></div><div id="new-case"></div><div class="grid">'+filtered.map(x=>'<article class="panel"><div class="row"><strong>'+esc(x.id)+'</strong>'+tag(x.priority)+'</div><h3>'+esc(x.title)+'</h3><p>'+esc(x.req)+' · '+esc(x.level)+'</p><p><b>Expected:</b> '+esc(x.expected)+'</p><div class="actions"><button class="btn alt" data-act="open-case" data-id="'+esc(x.id)+'">Steps / execute</button></div></article>').join('')+'</div>'}
function detail(c){return '<article class="panel"><div class="row"><h3>'+esc(c.id)+' — '+esc(c.title)+'</h3>'+tag(c.priority)+'</div><p>'+esc(c.req)+' · '+esc(c.level)+'</p><p><b>Preconditions</b><br>'+esc(c.pre)+'</p><p><b>Steps</b></p><div class="teststep">'+esc(c.steps)+'</div><p><b>Expected result</b><br>'+esc(c.expected)+'</p><div class="cardlinks"><a target="_blank" rel="noopener noreferrer" href="'+esc(C.url)+'">Open application under test ↗</a></div></article>'}
function manual(){const c=cases().find(x=>x.id===selected)||cases()[0];if(!c)return '<p>No test cases configured.</p>';
return '<h2>Manual QA execution</h2><p>Execute actual steps against the application, enter observations, and capture evidence. These are tester-entered verdicts, not independently verified test outcomes.</p><div class="two"><div><label>Choose case<select id="case-select">'+cases().map(x=>'<option value="'+esc(x.id)+'" '+(x.id===c.id?'selected':'')+'>'+esc(x.id+' · '+x.title)+'</option>').join('')+'</select></label>'+detail(c)+'</div><form class="panel" id="manual-form"><h3>Record an actual test run</h3><label>Execution result<select name="status" required><option value="">Select</option><option>Passed</option><option>Failed</option><option>Blocked</option></select></label><label>Actual result and comparison<textarea name="actual" rows="4" required placeholder="Observed response, state, calculations, and discrepancies"></textarea></label><label>Environment and notes<textarea name="notes" rows="3" placeholder="Browser/device/version, test data, defects"></textarea></label><button class="btn" type="submit">Save manual execution</button><p class="fine">Stored only in this browser. Every verdict is human-entered.</p><hr><label>Screenshot, video, trace or log<input id="evidence-upload" type="file" accept="image/*,video/*,.json,.txt,.log" multiple></label><p class="fine">Evidence saved in local browser IndexedDB, max 15 MB per attachment.</p><button class="btn alt" type="button" data-act="log-defect">Log defect</button></form></div><h3>Recent manual records</h3>'+execTable(state.executions.filter(x=>x.caseId===c.id).slice(0,8))}
function execTable(arr){if(!arr.length)return '<p class="note">Not run. No execution verdict has been claimed.</p>';return '<div class="panel tablewrap"><table><thead><tr><th>Test</th><th>Result</th><th>Timestamp</th><th>Actual observations</th></tr></thead><tbody>'+arr.map(x=>'<tr><td>'+esc(x.caseId)+'</td><td>'+tag(x.status)+'</td><td>'+esc(new Date(x.time).toLocaleString())+'</td><td>'+esc(x.actual)+'</td></tr>').join('')+'</tbody></table></div>'}
function auto(){return '<h2>Executable application-specific QA checks</h2><p>Run only safe, read-only checks of this application and inspect the actual HTTP response or imported deterministic engine output. Tests begin Not run; nothing is pre-marked passed.</p><div class="actions"><button class="btn" data-act="run-all" '+(running?'disabled':'')+'>Run all safe checks</button><button class="btn alt" data-act="reset-auto">Reset outcomes</button><a class="btn alt" target="_blank" rel="noopener noreferrer" href="'+esc(C.sourceTestsUrl)+'">Existing source tests ↗</a><a class="btn alt" target="_blank" rel="noopener noreferrer" href="'+esc(C.ciUrl)+'">CI evidence ↗</a></div><div class="panel"><p class="fine">Live HTTP and JavaScript results are generated by this visitor’s current run. These smoke/business-rule checks are not substitutes for full Selenium browser journeys, cross-device validation, load/security testing, or production sign-off.</p></div>'+C.automatic.map(t=>{const r=state.auto[t.id];return '<article class="panel"><div class="row"><div><strong>'+esc(t.id)+' — '+esc(t.title)+'</strong><p>'+esc(t.level)+' · '+esc(t.kind.toUpperCase())+'</p></div>'+(r?tag(r.status):tag('Not run'))+'</div><button class="btn alt" data-act="run-one" data-id="'+esc(t.id)+'" '+(running?'disabled':'')+'>▶ Run check</button>'+(r?'<details><summary>Technical proof — '+esc(r.elapsed)+' ms</summary><pre>'+fmt({request:r.request,actual:r.actual,assertion:r.assertion,time:r.time})+'</pre></details>':'<p class="fine">Not executed in this browser.</p>')+'</article>'}).join('')}
function defects(){return '<h2>Defect tracking and evidence</h2><p>Log defects with severity, exact reproduction steps, expected/actual behavior, and retest status. No unresolved defects are fabricated.</p><button class="btn" data-act="log-defect">+ Log defect</button><div id="new-defect"></div><h3>Recorded defect history</h3>'+(state.defects.length?state.defects.map(d=>'<div class="panel row"><div><strong>'+esc(d.id)+' — '+esc(d.title)+'</strong><p>'+esc(d.caseId)+' · '+esc(d.severity)+'</p><p>'+esc(d.description)+'</p><small>'+esc(new Date(d.time).toLocaleString())+'</small></div><label style="min-width:140px">Status<select data-defect="'+esc(d.id)+'">'+['Open','In progress','Fixed awaiting retest','Verified','Closed'].map(s=>'<option '+(d.status===s?'selected':'')+'>'+s+'</option>').join('')+'</select></label></div>').join(''):'<p class="note">No browser-local defects recorded.</p>')+'<h3>Saved screenshots, video and logs</h3>'+(state.evidence.length?state.evidence.map(e=>'<div class="panel row"><div><strong>'+esc(e.name)+'</strong><p>'+esc(e.caseId)+' · '+esc(e.size)+' bytes · '+esc(e.time)+'</p></div><button class="btn alt" data-act="view-evidence" data-id="'+esc(e.id)+'">Open evidence</button></div>').join(''):'<p class="note">No evidence attachments saved in this browser.</p>')}
function report(){const p=count('Passed'),f=count('Failed'),b=count('Blocked'),pending=total()-completed();const autoDone=Object.keys(state.auto).length,autoPass=Object.values(state.auto).filter(x=>x.status==='Passed').length;
return '<h2>QA execution & leadership summary</h2><p>Manual and automation results are reported separately. Portfolio specifications do not count as executed tests.</p><div class="metrics"><div class="metric"><strong>'+total()+'</strong><span>Manual cases</span></div><div class="metric"><strong>'+p+'</strong><span>Manual passed</span></div><div class="metric"><strong>'+f+'</strong><span>Manual failed</span></div><div class="metric"><strong>'+b+'</strong><span>Manual blocked</span></div><div class="metric"><strong>'+pending+'</strong><span>Not run</span></div></div><div class="grid"><div class="panel"><h3>Automation results</h3><p><strong>'+autoPass+' / '+autoDone+'</strong> executed checks passed; '+(C.automatic.length-autoDone)+' not yet run.</p><p><b>Open/retest defects:</b> '+state.defects.filter(x=>!['Closed','Verified'].includes(x.status)).length+'</p><p><b>Release recommendation:</b> Conditional / portfolio demonstration only. Review actual failures and external evidence before any production sign-off.</p></div><div class="panel"><h3>Publish QA evidence</h3><p>Export tester-entered manual outcomes, safe technical execution proof, defects, requirements and evidence metadata. Screenshot/video files remain browser-local and are not embedded in this export.</p><div class="actions"><button class="btn" data-act="export-json">Export QA report (JSON)</button><button class="btn alt" data-act="export-csv">Export CSV</button></div></div></div><h3>Recent test executions</h3>'+execTable(state.executions.slice(0,12))+'<p class="fine">'+esc(C.caveats)+'</p>'}

/* QA engineering evidence extension. Inlined inside the existing QA Bench IIFE.
 * Existing six lifecycle panels and their click/change/submit handlers are retained.
 * All source tests are linked to actual repository paths and source excerpts. */
let qaTechFilter='All';
let qaCiRuns=null, qaCiBusy=false, qaCiError='', qaCiAt='';
const qaCategories=[
  'Unit / business rules','Functional / regression','API / contract',
  'SIT / integration','E2E / workflow','UX / responsive',
  'Security / RBAC','UAT / smoke'
];
const qaEsc=s=>esc(s);
function qaSrcLink(x){
  const p=String(x.file||'').split('/').map(encodeURIComponent).join('/');
  return 'https://github.com/sachintechpro/'+encodeURIComponent(C.repository)+'/blob/main/'+p+(x.line?'#L'+x.line:'');
}
function qaBadge(st){
 const label=String(st||'Not checked');
 const cls=label==='success'||label==='Passed'?'passed':label==='failure'||label==='Failed'?'failed':label==='in_progress'||label==='queued'?'blocked':'';
 return '<span class="tag '+cls+'">'+qaEsc(label.replaceAll('_',' '))+'</span>';
}
function qaCatCounts(){
 return qaCategories.map(cat=>({name:cat,count:(C.technicalCases||[]).filter(t=>t.category===cat).length}))
}
function qaCiWorkflowLink(path){
 const file=String(path||'').split('/').pop();
 return 'https://github.com/sachintechpro/'+encodeURIComponent(C.repository)+'/actions/workflows/'+encodeURIComponent(file);
}
function qaCiResult(file){
 if(!Array.isArray(qaCiRuns))return null;
 return qaCiRuns.find(r=>String(r.path||'')===file)||null;
}
function qaCiLink(r){
 const u=String(r?.html_url||'');
 return u.startsWith('https://github.com/')?'<a target="_blank" rel="noopener noreferrer" href="'+qaEsc(u)+'">Inspect actual run ↗</a>':'';
}
function qaEngineering(){
 const tc=C.technicalCases||[];
 const manualRan=new Set(state.executions.map(x=>x.caseId)).size;
 const actual=Object.values(state.auto||{});
 const proofCount=actual.filter(x=>x.status==='Passed').length;
 const latestRun=Array.isArray(qaCiRuns)?qaCiRuns[0]:null;
 return '<section class="tech-workbench"><div class="tech-hero"><div><span class="tech-kicker">LIVE TEST ENGINEERING · '+qaEsc(C.domain)+'</span><h2>Actual tests. Source assertions. Verifiable evidence.</h2><p>Source-backed cases come from this application’s real repository. Browser-local manual verdicts, safe HTTP checks and GitHub CI results remain separate—no prefilled pass rates.</p></div><a class="btn" href="'+qaEsc(C.sourceUrl)+'" target="_blank" rel="noopener noreferrer">Inspect repository ↗</a></div>'+
 '<div class="tech-stats">'+
 '<div class="tech-stat"><strong>'+tc.length+'</strong><span>Source-backed test cases</span><small>Test functions and assertions</small></div>'+
 '<div class="tech-stat"><strong>'+(C.suites||[]).length+'</strong><span>Test suites/files</span><small>Clickable source paths</small></div>'+
 '<div class="tech-stat"><strong>'+C.automatic.length+'</strong><span>Runnable live checks</span><small>'+proofCount+' passed of '+actual.length+' attempted</small></div>'+
 '<div class="tech-stat"><strong>'+cases().length+'</strong><span>Manual cases</span><small>'+manualRan+' cases executed in this browser</small></div>'+
 '</div>'+
 '<div class="tech-layout"><section class="panel"><h3>Source coverage by test level</h3><p class="fine">Counts reflect tests found in source files; they are not pass counts.</p><div class="tech-cat-grid">'+qaCatCounts().map(c=>'<button class="tech-cat" data-act="qa-open-category" data-cat="'+qaEsc(c.name)+'"><strong>'+c.count+'</strong><span>'+qaEsc(c.name)+'</span></button>').join('')+'</div></section>'+
 '<section class="panel"><h3>Execution evidence</h3>'+
 '<div class="tech-evidence-line"><div><strong>Live safe checks</strong><small>Runs on demand in this browser</small></div>'+qaBadge(actual.length?proofCount+' / '+actual.length+' passed':'Not run')+'</div>'+
 '<div class="tech-evidence-line"><div><strong>GitHub Actions</strong><small>Repository workflow and test logs</small></div>'+qaBadge(latestRun?latestRun.conclusion||latestRun.status:'Not fetched')+'</div>'+
 '<div class="tech-evidence-line"><div><strong>Manual QA</strong><small>Human-entered observations and attachments</small></div>'+qaBadge(manualRan+' / '+cases().length+' executed')+'</div>'+
 '<div class="actions"><button class="btn alt" data-act="qa-go-ci">Open CI evidence</button><button class="btn alt" data-act="qa-go-runner">Run safe live checks</button></div></section></div>'+
 '<section class="panel"><h3>Engineering walkthrough for hiring managers</h3>'+
 '<div class="tech-walkthrough">'+
 '<div><strong>01 · Inspect a business rule</strong><p>Open a real test function and verify its input, assertion and source location.</p></div>'+
 '<div><strong>02 · Execute a safe check</strong><p>Run live read-only HTTP or deterministic engine checks and inspect actual responses.</p></div>'+
 '<div><strong>03 · Inspect CI history</strong><p>Verify the exact workflow, commit, conclusion and logs in GitHub Actions.</p></div>'+
 '<div><strong>04 · Record QA evidence</strong><p>Complete a manual case, capture observed behavior, link a defect and export the result.</p></div></div></section></section>';
}
function qaCatalog(){
 const source=C.technicalCases||[];
 const filtered=qaTechFilter==='All'?source:source.filter(x=>x.category===qaTechFilter);
 return '<section class="tech-workbench"><h2>Technical test catalog</h2><p>Actual tests and assertions extracted from version-controlled source files. The catalog is a reviewable inventory; execution statuses are obtained from CI or real live runs, never inferred from source code.</p>'+
 '<div class="tech-controls"><label>Test category<select id="qa-tech-category"><option>All</option>'+qaCategories.map(cat=>'<option '+(qaTechFilter===cat?'selected':'')+'>'+qaEsc(cat)+'</option>').join('')+'</select></label>'+
 '<span class="fine">'+filtered.length+' of '+source.length+' sourced tests</span></div>'+
 '<div class="tech-source-list">'+filtered.map(t=>'<details class="panel tech-source"><summary><span class="tech-source-title"><strong>'+qaEsc(t.id)+'</strong> '+qaEsc(t.title)+'</span><span>'+qaBadge(t.category)+'</span></summary>'+
 '<div class="tech-source-body"><div class="tech-tags"><span>'+qaEsc(t.framework)+'</span><span>'+qaEsc(t.file)+'</span><span>Line '+qaEsc(t.line)+'</span></div>'+
 '<p><b>Actual assertion / technical check from source</b></p><pre>'+qaEsc(t.excerpt||'See source for implementation')+'</pre>'+
 '<p class="fine">Linked source reference is inspectable. CI results are shown in the separate CI & artifacts section; test code alone is not evidence of execution.</p>'+
 '<div class="cardlinks"><a href="'+qaSrcLink(t)+'" target="_blank" rel="noopener noreferrer">View exact source line ↗</a><a href="'+qaCiWorkflowLink((C.workflows||[])[0]?.path)+'" target="_blank" rel="noopener noreferrer">CI workflows ↗</a></div></div></details>').join('')+'</div>'+
 (filtered.length?'':'<div class="note">No source-backed tests in this category yet; this is a visibility gap, not a pass.</div>')+'</section>';
}
async function qaRefreshCi(){
 if(qaCiBusy)return;
 qaCiBusy=true;qaCiError='';draw();
 try{
   const url='https://api.github.com/repos/sachintechpro/'+encodeURIComponent(C.repository)+'/actions/runs?per_page=45';
   const r=await fetch(url,{cache:'no-store',headers:{'Accept':'application/vnd.github+json'}});
   if(!r.ok)throw Error('GitHub API HTTP '+r.status+(r.status===403?' (rate limit or access restriction)':''));
   const body=await r.json();
   if(!Array.isArray(body.workflow_runs))throw Error('GitHub response has no workflow_runs array');
   qaCiRuns=body.workflow_runs.map(x=>({
     name:String(x.name||''),path:String(x.path||''),status:String(x.status||''),
     conclusion:String(x.conclusion||''),head_sha:String(x.head_sha||''),
     run_started_at:String(x.run_started_at||x.created_at||''),html_url:String(x.html_url||'')
   }));
   qaCiAt=new Date().toISOString();
 }catch(err){qaCiError=String(err?.message||err);qaCiRuns=null;}
 finally{qaCiBusy=false;draw();}
}
function qaCiView(){
 const workflows=C.workflows||[];
 const fetchState=qaCiBusy?'Checking GitHub Actions…':qaCiError?'Unable to verify CI: '+qaCiError:Array.isArray(qaCiRuns)?'Last checked: '+new Date(qaCiAt).toLocaleString():'No API request made yet — CI status unknown';
 const relevant=Array.isArray(qaCiRuns)?qaCiRuns.filter(r=>workflows.some(w=>w.path===r.path)).slice(0,14):[];
 return '<section class="tech-workbench"><h2>CI executions, code provenance & artifacts</h2><p>Evidence is fetched directly from the public GitHub Actions API, not from manually maintained pass counters. Click the run link for logs, failures, artifacts and commit details.</p>'+
 '<div class="tech-ci-header"><span class="fine" role="status">'+qaEsc(fetchState)+'</span><button class="btn" data-act="qa-refresh-ci" '+(qaCiBusy?'disabled':'')+'>'+ (qaCiBusy?'Checking…':'Refresh actual CI status')+'</button></div>'+
 '<div class="grid">'+workflows.map(w=>{const run=qaCiResult(w.path);return '<article class="panel"><div class="row"><strong>'+qaEsc(w.name)+'</strong>'+qaBadge(run?run.conclusion||run.status:'Not checked')+'</div>'+
 '<p>'+qaEsc(w.description||'Repository workflow')+'</p><p class="fine">Workflow: '+qaEsc(w.path)+'</p>'+
 (run?'<p class="fine">Started '+qaEsc(run.run_started_at)+' · '+qaEsc(run.head_sha.slice(0,10))+'</p>':'<p class="fine">No verified result loaded for this workflow.</p>')+
 '<div class="cardlinks"><a href="'+qaCiWorkflowLink(w.path)+'" target="_blank" rel="noopener noreferrer">Workflow history ↗</a> '+qaCiLink(run)+'</div></article>'}).join('')+'</div>'+
 '<div class="panel"><h3>Recent real workflow runs</h3>'+
 (relevant.length?'<div class="tablewrap"><table><thead><tr><th>Workflow</th><th>Outcome</th><th>Git SHA</th><th>Run started</th><th>Evidence</th></tr></thead><tbody>'+relevant.map(r=>'<tr><td>'+qaEsc(r.name)+'</td><td>'+qaBadge(r.conclusion||r.status)+'</td><td><code>'+qaEsc(r.head_sha.slice(0,10))+'</code></td><td>'+qaEsc(r.run_started_at)+'</td><td>'+qaCiLink(r)+'</td></tr>').join('')+'</tbody></table></div>':'<p class="fine">No verified workflow runs loaded. Refresh to check GitHub; do not infer that a test passed.</p>')+
 '</div><div class="panel"><h3>Artifacts and failure investigation</h3><p>GitHub Actions run details provide step logs and available downloaded artifacts. Failed runs remain visible alongside later successful runs, showing debugging and regression history.</p>'+
 '<p class="fine">Source files used by these workflows are listed in the catalog. An existing source file does not imply it was executed; verify the workflow steps on GitHub.</p>'+
 '<a class="btn alt" href="'+qaEsc(C.ciUrl)+'" target="_blank" rel="noopener noreferrer">View repository actions and artifacts ↗</a></div></section>';
}
function qaQualityGates(){
 const manual=cases(),runs=state.executions,latestRuns=new Map();
 for(const r of runs)if(!latestRuns.has(r.caseId))latestRuns.set(r.caseId,r);
 const passed=[...latestRuns.values()].filter(r=>r.status==='Passed').length;
 const failed=[...latestRuns.values()].filter(r=>r.status==='Failed').length;
 const blocked=[...latestRuns.values()].filter(r=>r.status==='Blocked').length;
 const live=Object.values(state.auto||{});
 const failures=live.filter(r=>r.status==='Failed').length;
 const requiredSources=C.technicalCases||[];
 const reqs=C.requirements.map(r=>{
   const relevant=manual.filter(c=>c.req===r.id), executed=relevant.filter(c=>latestRuns.has(c.id)).length;
   return {r,relevant,executed}
 });
 const gate=failed||failures?'NO-GO: failures require triage': 'EVIDENCE INCOMPLETE: no release sign-off';
 return '<section class="tech-workbench"><h2>Requirement traceability & quality gates</h2><p>Reconcile business acceptance criteria with designed manual cases, actually recorded executions and the source-backed automation catalog. These are distinct evidence types.</p>'+
 '<div class="panel"><div class="row"><h3>Risk-based release recommendation</h3>'+qaBadge(failed||failures?'Failed checks exist':'Not signed off')+'</div>'+
 '<p><strong>'+qaEsc(gate)+'</strong></p>'+
 '<div class="tech-gate-metrics"><span>'+passed+' manual passed</span><span>'+failed+' manual failed</span><span>'+blocked+' manual blocked</span><span>'+failures+' live-check failures</span><span>'+requiredSources.length+' sourced tests (not pass count)</span></div>'+
 '<p class="fine">Final production approval requires business/UAT sign-off, review of all failed or unexecuted critical cases, CI evidence, environment controls and documented residual-risk acceptance.</p></div>'+
 '<div class="panel"><h3>Requirement-to-test traceability</h3><div class="tablewrap"><table><thead><tr><th>Requirement</th><th>Risk</th><th>Designed cases</th><th>Manual execution</th><th>Acceptance status</th></tr></thead><tbody>'+reqs.map(({r,relevant,executed})=>'<tr><td><strong>'+qaEsc(r.id)+'</strong><div class="fine">'+qaEsc(r.title)+'</div></td><td>'+qaBadge(r.risk)+'</td><td>'+relevant.length+'<div class="fine">'+qaEsc(relevant.map(c=>c.id).join(', '))+'</div></td><td>'+executed+' / '+relevant.length+'</td><td>'+qaBadge(executed===relevant.length&&relevant.length?'Executed (review verdicts)':'Coverage not complete')+'</td></tr>').join('')+'</tbody></table></div></div>'+
 '<div class="panel"><h3>Environment, execution scope & known gaps</h3>'+
 '<p><b>Technology:</b> '+qaEsc((C.suites||[]).map(s=>s.framework).filter((x,i,a)=>a.indexOf(x)===i).join(' · '))+'</p>'+
 '<p><b>Safe visitor execution:</b> Existing live-runner GET/API contract checks and pure deterministic engine calls (as configured). No data-changing CI tests run against shared Render environments.</p>'+
 '<p><b>CI test provenance:</b> '+qaEsc((C.workflows||[]).map(w=>w.name).join(' · '))+'</p>'+
 '<p><b>Known limitations:</b> '+qaEsc(C.caveats)+'</p>'+
 '<p><b>Coverage gaps:</b> '+qaEsc(qaCategories.filter(cat=>!requiredSources.some(t=>t.category===cat)).join('; ')||'All categories represented in source (verify CI coverage separately)')+'</p>'+
 '<div class="actions"><button class="btn alt" data-act="qa-go-catalog">Inspect sourced tests</button><button class="btn alt" data-act="qa-go-ci">Verify CI execution</button></div></div></section>';
}

const panels={engineering:qaEngineering,catalog:qaCatalog,ci:qaCiView,gates:qaQualityGates,requirements:renderReq,cases:listCases,manual,automation:auto,defects,report};
function draw(){document.getElementById('app').innerHTML=panels[tab]();document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===tab)))}
function switchTab(t){tab=t;note('');draw();window.scrollTo({top:document.querySelector('.tabs').offsetTop-15,behavior:'smooth'})}
function readByKey(obj,path){return String(path||'').split('.').filter(Boolean).reduce((o,k)=>o?.[k],obj)}
async function execute(t){const start=performance.now(),when=new Date().toISOString();let passed=false,actual={},request={},assertion='';try{
if(t.kind==='http'){const path=t.path;request={method:'GET',path,credentials:'omit',expectedStatus:t.expectStatus};const r=await fetch(path,{method:'GET',credentials:'omit',cache:'no-store',redirect:'follow'});const ct=r.headers.get('content-type')||'';let body=null,text='';if(ct.includes('json')){try{body=await r.json()}catch(e){text='Invalid JSON: '+e.message}}else{text=(await r.text()).slice(0,15000)};actual={status:r.status,contentType:ct,preview:body===null?text.slice(0,900):JSON.stringify(body).slice(0,900)};passed=r.status===t.expectStatus;assertion='HTTP '+r.status+' expected '+t.expectStatus;if(passed&&t.contains){passed=(text||JSON.stringify(body)).includes(t.contains);assertion+='; body contains '+JSON.stringify(t.contains)+': '+passed}if(passed&&t.expectKey){const val=readByKey(body,t.expectKey);passed=val!==undefined&&(!t.expectType||typeof val===t.expectType);assertion+='; '+t.expectKey+' '+t.expectType+': '+passed}}
else if(t.kind==='esm'){request={module:t.module,method:t.fn,expectedProperty:t.expectKey};const mod=await import(t.module+'?qa='+encodeURIComponent(when));const fn=mod[t.fn];if(typeof fn!=='function')throw Error('Export '+t.fn+' unavailable');const out=fn();const v=readByKey(out,t.expectKey);actual={property:t.expectKey,value:v,keys:Object.keys(out||{}).slice(0,15)};passed=v!==undefined&&(!t.expectType||typeof v===t.expectType);assertion='Imported real engine and evaluated '+t.expectKey+': '+passed}
else throw Error('Unsupported automated test type');
}catch(e){actual={error:e.message};assertion='Test execution error: '+e.message}
return {status:passed?'Passed':'Failed',request,actual,assertion,time:when,elapsed:+(performance.now()-start).toFixed(1)}
}
async function runAll(ids){if(running)return;running=true;note('Running safe read-only checks…');draw();for(const t of C.automatic.filter(x=>ids.includes(x.id))){state.auto[t.id]=await execute(t);save();draw()}running=false;draw();const fail=ids.filter(id=>state.auto[id]?.status==='Failed').length;note('Executed '+ids.length+' real checks; '+fail+' failed. View technical proof for details.')}
function dl(name,content,mime){const blob=new Blob([content],{type:mime});const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),12000)}
function csvVal(v){return '"'+String(v==null?'':v).replaceAll('"','""')+'"'}
async function storeFile(file){return new Promise((resolve,reject)=>{const r=indexedDB.open('qa-bench-evidence:'+C.slug,1);r.onupgradeneeded=()=>r.result.createObjectStore('files',{keyPath:'id'});r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result,id=Date.now().toString(36)+Math.random().toString(36).slice(2,6);const tx=db.transaction('files','readwrite');tx.objectStore('files').put({id,blob:file});tx.oncomplete=()=>{db.close();resolve(id)};tx.onerror=()=>reject(tx.error)}})}
async function openFile(id){return new Promise((resolve,reject)=>{const r=indexedDB.open('qa-bench-evidence:'+C.slug,1);r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result;if(!db.objectStoreNames.contains('files')){db.close();reject(Error('No stored files'));return}const req=db.transaction('files').objectStore('files').get(id);req.onsuccess=()=>{db.close();resolve(req.result?.blob)};req.onerror=()=>reject(req.error)}})}
document.addEventListener('click',async e=>{const tabNode=e.target.closest('[data-tab]');if(tabNode){switchTab(tabNode.dataset.tab);return}const btn=e.target.closest('[data-act]');if(!btn)return;const a=btn.dataset.act;
if(a==='qa-open-category'){qaTechFilter=btn.dataset.cat;switchTab('catalog')}
else if(a==='qa-go-catalog'){switchTab('catalog')}
else if(a==='qa-go-ci'){switchTab('ci')}
else if(a==='qa-go-runner'){switchTab('automation')}
else if(a==='qa-refresh-ci'){await qaRefreshCi()}
else if(a==='req'){showCase=btn.dataset.id;switchTab('cases')}else if(a==='all-cases'){showCase='';draw()}else if(a==='open-case'){selected=btn.dataset.id;switchTab('manual')}else if(a==='run-all'){await runAll(C.automatic.map(x=>x.id))}else if(a==='run-one'){await runAll([btn.dataset.id])}else if(a==='reset-auto'){state.auto={};save();draw();note('Automated results reset. No application data changed.')}
else if(a==='add-case'){document.getElementById('new-case').innerHTML='<form class="panel" id="custom-form"><h3>Author a manual test case</h3><label>Requirement<select name="req">'+C.requirements.map(r=>'<option>'+esc(r.id)+'</option>').join('')+'</select></label><label>Title<input name="title" required maxlength="130"></label><label>Preconditions<textarea name="pre" required></textarea></label><label>Steps<textarea name="steps" rows="4" required></textarea></label><label>Expected result<textarea name="expected" required></textarea></label><label>Level<input name="level" value="Functional / E2E" required></label><button class="btn">Save case</button></form>'}
else if(a==='log-defect'){switchTab('defects');document.getElementById('new-defect').innerHTML='<form class="panel" id="defect-form"><h3>Log defect</h3><label>Test case<select name="caseId">'+cases().map(c=>'<option>'+esc(c.id)+'</option>').join('')+'</select></label><label>Title<input name="title" required maxlength="130"></label><label>Severity<select name="severity"><option>Critical</option><option>High</option><option selected>Medium</option><option>Low</option></select></label><label>Reproduction steps, expected versus actual<textarea name="description" rows="4" required></textarea></label><button class="btn">Save defect</button></form>'}
else if(a==='view-evidence'){try{const f=await openFile(btn.dataset.id);if(!f)throw Error('File missing from this browser');const u=URL.createObjectURL(f);window.open(u,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(u),60000)}catch(err){note('Evidence unavailable: '+err.message)}}
else if(a==='export-json'){dl(C.slug+'-qa-report.json',JSON.stringify({application:C.name,exported:new Date().toISOString(),source:'tester-entered browser-local QA and actual read-only checks',requirements:C.requirements,testCases:cases(),manualExecutions:state.executions,automatedResults:state.auto,defects:state.defects,evidenceMetadata:state.evidence,limitations:C.caveats},null,2),'application/json')}
else if(a==='export-csv'){const rows=[['Test ID','Status','Timestamp','Actual Result','Notes'],...state.executions.map(x=>[x.caseId,x.status,x.time,x.actual,x.notes])];dl(C.slug+'-qa-executions.csv',rows.map(x=>x.map(csvVal).join(',')).join('\r\n'),'text/csv')}})
document.addEventListener('change',async e=>{if(e.target.id==='qa-tech-category'){qaTechFilter=e.target.value;draw();return}if(e.target.id==='case-select'){selected=e.target.value;draw()}if(e.target.hasAttribute('data-defect')){const d=state.defects.find(x=>x.id===e.target.dataset.defect);if(d){d.status=e.target.value;save();draw()}}if(e.target.id==='evidence-upload'){const files=[...e.target.files];let saved=0;for(const f of files){if(f.size>15*1024*1024){note('Each file must be 15 MB or smaller.');continue}try{const id=await storeFile(f);state.evidence.unshift({id,name:f.name,size:f.size,type:f.type,time:new Date().toISOString(),caseId:selected});saved++}catch(err){note('Could not store '+f.name+': '+err.message)}}if(saved){save();note(saved+' attachment(s) stored in this browser.')}}});
document.addEventListener('submit',e=>{const f=e.target;if(!['manual-form','custom-form','defect-form'].includes(f.id))return;e.preventDefault();const d=Object.fromEntries(new FormData(f).entries());
if(f.id==='manual-form'){if(!d.status||!String(d.actual||'').trim())return;state.executions.unshift({caseId:selected,status:d.status,actual:d.actual,notes:d.notes||'',time:new Date().toISOString()});save();draw();note('Tester-entered manual result saved. This is not an independently executed automated test.')}
if(f.id==='custom-form'){const id='CUSTOM-'+String(state.customCases.length+1).padStart(3,'0');state.customCases.push({id,req:d.req,title:d.title,level:d.level,priority:'P1',pre:d.pre,steps:d.steps,expected:d.expected});selected=id;save();switchTab('manual');note('Custom manual case saved in your browser.')}
if(f.id==='defect-form'){state.defects.unshift({id:'DEF-'+Date.now().toString(36).toUpperCase(),caseId:d.caseId,title:d.title,severity:d.severity,description:d.description,status:'Open',time:new Date().toISOString()});save();draw();note('Defect recorded. Add supporting evidence from Manual QA.')}});
document.getElementById('project-title').textContent=C.name+' QA Bench';document.getElementById('project-sub').textContent=C.domain;document.getElementById('app-link').href=C.url;document.getElementById('source-link').href=C.sourceUrl;document.getElementById('ci-link').href=C.ciUrl;
draw();
})();
