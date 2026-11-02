const $=id=>document.getElementById(id);
const onlinePreview=window.LINJING_PREVIEW_MODE===true;
const names={shop:'店名',product:'具体商品名称',product_detail:'商品特点（可选）',address:'门店地址',offer:'优惠及完整使用条件',validity:'有效期'};
const factExamples={shop:'例如：梧桐咖啡（请填实际店名）',product:'例如：生椰拿铁，而不只是“咖啡”',product_detail:'例如：使用椰乳；只填已核实的特点，不写推测',address:'填写真实门店地址',offer:'填写价格和完整使用条件',validity:'填写完整起止日期'};
const tags={storefront:'门头 / 路线',product:'商品',process:'制作过程',interior:'环境',person:'人物',other:'待判断 / 其他'};
const cta={visit:'到店前，请确认营业情况。',attract:'感兴趣可以先收藏。',promo:'参与前，请核对活动条件。'};
let project=blank(),plan=null,busy=false,revision=0,statusTimer,reviewRecords=JSON.parse(localStorage.getItem('linjing-reviews')||'[]');
function blank(){return {name:onlinePreview?'在线预览草稿':'真实店铺项目',goal:'visit',synthetic:false,facts:Object.keys(names).map(k=>({id:k,kind:k,value:'',source:'',confirmed:false})),shots:[]};}
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const directionControls=/[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/g;
const visibleControls=value=>value.replace(directionControls,c=>'[U+'+c.codePointAt(0).toString(16).toUpperCase().padStart(4,'0')+']');
function quarantineFact(f){if(visibleControls(f.value)!==f.value){f.original_value=f.value;f.value=visibleControls(f.value);f.text_review_value=f.value;f.confirmed=false;f.text_issue='包含隐藏方向控制字符，已用[U+…]标记显示。请重新填写可见文字并确认；原文已保留。';}else if(f.text_review_value!==f.value)delete f.text_issue;}
function refreshFactWarnings(){const message='部分事实含隐藏方向字符，已保留原文并取消确认，请重新填写。';const detailsMessage='商品名称或确认状态已变化，商品特点已保留但取消确认，请按当前商品重新核对。';const product=project.facts.find(f=>f.kind==='product'&&f.confirmed);const staleDetails=project.facts.some(f=>f.kind==='product_detail'&&f.value.trim()&&(!f.confirmed||f.product_ref?.id!==product?.id||f.product_ref?.value!==product?.value));project.warnings=(project.warnings||[]).filter(w=>w!==message&&(w!==detailsMessage||staleDetails));if(project.facts.some(f=>f.text_issue))project.warnings.push(message);$('projectWarnings').textContent=project.warnings.join(' ');$('projectWarnings').hidden=!project.warnings.length;}
const reviewWindow=s=>`${s.review_start??s.start},${s.review_end??s.end}`;
const shotTiming=s=>(s.review_start!==undefined&&Math.abs(s.start-s.review_start)>.001?`原片 ${s.start.toFixed(1)}–${s.end.toFixed(1)}s · 复核 ${s.review_start.toFixed(1)}–${s.review_end.toFixed(1)}s`:`${s.start.toFixed(1)}–${s.end.toFixed(1)}s`);
function status(text,error=false,sticky=false){clearTimeout(statusTimer);$('status').textContent=text;$('status').className='status'+(error?' error':'');$('status').hidden=false;if(!sticky)statusTimer=setTimeout(()=>$('status').hidden=true,6500);}
async function request(path,obj){if(onlinePreview)throw Error('当前是在线页面预览，素材处理与视频生成请在本地版使用。');const r=await fetch(path,obj===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});const result=await r.json();if(!r.ok)throw Error(result.error||'请求未成功');return result;}
async function task(path,obj){if(busy)throw Error('请等待当前任务完成。');busy=true;buttons();try{const res=await request(path,obj);return await watch(res.job_id);}finally{busy=false;buttons();}}
async function watch(id){for(;;){const j=await request('/api/jobs/'+id);if(j.status==='done'){status('处理完成');return j.result;}if(j.status==='error')throw Error(j.message);status(j.message,false,true);await new Promise(r=>setTimeout(r,1000));}}
function buttons(){
 document.querySelectorAll('#facts input,#goal,#method,#shots select,#shots input,#shots button,.projectbar button,.projectbar input,#videoFiles,#labelsFile,#contextBtn').forEach(el=>el.disabled=busy);
 $('demoBtn').disabled=busy;$('planBtn').disabled=busy;$('newBtn').disabled=busy;$('localAnalyzeBtn').disabled=busy||!project.shots.length;$('renderBtn').disabled=busy||!plan?.renderable;$('busyHint').hidden=!busy;
 document.querySelectorAll('#plan button').forEach(el=>el.disabled=busy||(el.dataset.up!==undefined&&+el.dataset.up===0)||(el.dataset.down!==undefined&&+el.dataset.down===plan?.segments.length-1));
 if(onlinePreview)document.querySelectorAll('#demoBtn,#saveBtn,#planBtn,#renderBtn,#localAnalyzeBtn,#videoFiles,#projectFile,#labelsFile,#contextBtn').forEach(el=>el.disabled=true);
}
function showOnlinePreview(){
 $('onlinePreviewNotice').hidden=false;
 document.querySelector('header .local').innerHTML='<i></i> 在线页面预览';
 $('demoBtn').textContent='模拟案例（本地版）';$('newBtn').textContent='新建页面草稿';$('saveBtn').textContent='保存项目（本地版）';$('exportProjectBtn').textContent='导出页面草稿';
 const upload=document.querySelector('label[for="videoFiles"]');upload.classList.add('preview-disabled');upload.setAttribute('aria-disabled','true');upload.querySelector('strong').textContent='素材上传请使用本地版';upload.querySelector('span:last-of-type').textContent='在线预览可以查看页面与拍摄流程，不接收素材';
 $('modelStatus').textContent='在线预览不运行素材分析；完整处理功能请在本地版使用。';
 $('voiceStatus').textContent='在线预览不运行配音和视频生成。';
 document.querySelector('footer span:last-child').textContent='在线预览 · 不上传素材';
}
async function projectForExport(){return onlinePreview?{...structuredClone(project),preview_only:true}:locked(()=>request('/api/export-project',{project,plan:plan?.renderable?plan:null,method:$('method').value}));}
function resetResult(){$('result').hidden=true;$('preview').pause();$('preview').removeAttribute('src');$('preview').load();}
function applyProject(value){const edit=value.saved_edit;project=value;delete project.saved_edit;revision++;resetResult();plan=edit?.plan||null;if(edit?.method)$('method').value=edit.method;draw();}
function invalidate(){revision++;plan=null;resetResult();renderPlan();}
function revokeProductDetails(){project.facts.forEach((f,i)=>{if(f.kind==='product_detail'){f.confirmed=false;delete f.product_ref;const checkbox=$('facts').querySelector(`[data-confirm="${i}"]`);if(checkbox)checkbox.checked=false;}});}
async function locked(fn){if(busy)throw Error('请等待当前处理完成，再编辑项目。');busy=true;buttons();try{return await fn();}finally{busy=false;buttons();}}
function draw(){
 if(!project.facts.some(f=>f.kind==='product_detail')){let id='product_detail';while(project.facts.some(f=>f.id===id))id+='_';project.facts.push({id,kind:'product_detail',value:'',source:'',confirmed:false});}
 $('projectName').textContent=project.name;$('syntheticBadge').hidden=!project.synthetic;$('goal').value=project.goal;
 const brief=project.creative_brief;$('restaurantWorkspaceBrief').hidden=!brief;$('restaurantWorkspaceBrief').textContent=brief?`本次创作：${brief.shop} · ${brief.intent_name} · ${brief.intent==='restaurant'?'饭店介绍，搭配菜品：':''}${brief.product}。以下信息仍需核实与确认。`:'';
 $('projectWarnings').textContent=(project.warnings||[]).join(' ');$('projectWarnings').hidden=!project.warnings?.length;
 project.facts.forEach(quarantineFact);
 refreshFactWarnings();
 $('facts').innerHTML=project.facts.map((f,i)=>`<div class="fact"><div class="fact-top"><span>${esc(names[f.kind])}</span><label><input type="checkbox" data-confirm="${i}" ${f.confirmed?'checked':''}>已确认</label></div>${f.kind==='product_detail'?'<p class="hint">先确认具体商品名称，再核对这款商品的特点。改名后特点需要重新确认。</p>':''}<input aria-label="${esc(names[f.kind])}" value="${esc(f.value)}" data-value="${i}" maxlength="100" placeholder="${esc(factExamples[f.kind]||'填写真实信息')}"><p class="warning" data-text-warning="${i}" ${f.text_issue?'':'hidden'}>${esc(f.text_issue||'')}</p><input class="source" aria-label="${esc(names[f.kind])}来源" data-source="${i}" value="${esc(f.source)}" placeholder="来源，例如店主当面确认 / 价目表"></div>`).join('');
 $('facts').querySelectorAll('[data-value]').forEach(el=>el.oninput=()=>{const i=+el.dataset.value,f=project.facts[i];f.value=el.value;f.confirmed=false;quarantineFact(f);refreshFactWarnings();if(el.value!==f.value)el.value=f.value;const warning=$('facts').querySelector(`[data-text-warning="${i}"]`);warning.textContent=f.text_issue||'';warning.hidden=!f.text_issue;$('facts').querySelector(`[data-confirm="${i}"]`).checked=false;if(f.kind==='product'){revokeProductDetails();project.shots.forEach(s=>s.product_binding=null);drawShots();}invalidate();});
 $('facts').querySelectorAll('[data-source]').forEach(el=>el.oninput=()=>{const i=+el.dataset.source;project.facts[i].source=el.value;project.facts[i].confirmed=false;$('facts').querySelector(`[data-confirm="${i}"]`).checked=false;if(project.facts[i].kind==='product')revokeProductDetails();invalidate();});
 $('facts').querySelectorAll('[data-confirm]').forEach(el=>el.onchange=()=>{const f=project.facts[+el.dataset.confirm];if(el.checked&&f.text_review_value===f.value){el.checked=false;return status('请重新填写可见文字，移除[U+…]标记后再确认；不要直接沿用原来的金额确认。',true,true);}if(el.checked&&(!f.value.trim()||!f.source.trim())){el.checked=false;return status('确认前请填写信息和来源。',true);}if(el.checked&&f.kind==='product_detail'){const product=project.facts.find(x=>x.kind==='product'&&x.confirmed);if(!product){el.checked=false;return status('请先填写并确认具体商品名称，再确认该商品的特点。',true);}f.product_ref={id:product.id,value:product.value};}f.confirmed=el.checked;if(f.kind==='product'&&!f.confirmed)revokeProductDetails();refreshFactWarnings();invalidate();});
 drawShots();renderPlan();
}
function drawShots(){
 $('shotCount').textContent=project.shots.length+' 个镜头';
 if(!project.shots.length){$('shots').innerHTML='<div class="empty"><span>▧</span><p>真实画面，是创作的起点。</p><small>添加素材，或先体验一个明确标记的模拟案例。</small></div>';return;}
 const product=project.facts.find(f=>f.kind==='product');
 $('shots').innerHTML=project.shots.map((s,i)=>{
  const c=s.local_candidate;
  const binding=s.product_binding?.confirmed&&s.product_binding.fact_id===product?.id&&s.product_binding.value===product?.value;
  return `<article class="shot"><img src="${esc(s.thumb)}" alt="${esc(s.name)}的抽帧"><div class="shot-body"><div class="shot-name" title="${esc(s.name)}">${esc(s.name)}</div><div class="shot-meta">${shotTiming(s)} · 质量 ${Math.round(s.quality*100)}/100</div>${s.unavailable||s.semantic_issue||s.quality_issues?.length?`<p class="warning">${esc(s.unavailable||s.semantic_issue||(s.quality_issues||[]).join('；'))}</p>`:''}<details><summary>查看本段视频与抽帧</summary><video controls preload="none" style="width:100%" src="/media/${esc(s.media_id)}/${s.review_url?'review.mp4':'source.mp4'}#t=${s.review_url?reviewWindow(s):`${s.start},${s.end}`}"></video><div>${(s.frames||[]).map(f=>`<img style="width:30%;height:auto" src="${esc(f.url)}" alt="${f.time}秒抽帧">`).join('')}</div></details><select aria-label="镜头${i+1}标签" data-tag="${i}">${Object.entries(tags).map(([k,n])=>`<option value="${k}" ${s.tags.includes(k)?'selected':''}>${n}</option>`).join('')}</select>${c?`<p class="candidate">本地 AI：${c.abstained?'暂不判断':esc(tags[c.suggested_tag])}<br>${esc(c.description)}<br>相似度不是正确概率</p>`:s.label_source==='model_candidate'?`<p class="candidate">外部模型候选 · 未校准分数 ${s.confidence??'未提供'}<br>${esc(s.description||'')}</p>`:''}<label class="shot-confirm"><input type="checkbox" data-shot-confirm="${i}" ${s.confirmed?'checked':''}>我已查看并确认标签</label>${s.tags.includes('product')?`<label class="shot-confirm"><input type="checkbox" data-product-confirm="${i}" ${binding?'checked':''}>画面商品确实是：${esc(product?.value||'请先填写商品名称')}</label>`:''}<button class="quiet" data-remove="${i}" aria-label="移除镜头${i+1}">移除这个镜头</button></div></article>`;
 }).join('');
 $('shots').querySelectorAll('[data-tag]').forEach(el=>el.onchange=()=>{const s=project.shots[+el.dataset.tag];s.tags=[el.value];s.confirmed=false;s.product_binding=null;s.label_source='human_candidate';invalidate();drawShots();});
 $('shots').querySelectorAll('[data-shot-confirm]').forEach(el=>el.onchange=guard(()=>confirmShot(+el.dataset.shotConfirm,'purpose',el.checked)));
 $('shots').querySelectorAll('[data-product-confirm]').forEach(el=>el.onchange=guard(()=>confirmShot(+el.dataset.productConfirm,'product',el.checked)));
 $('shots').querySelectorAll('[data-remove]').forEach(el=>el.onclick=()=>{project.shots.splice(+el.dataset.remove,1);invalidate();drawShots();});
 buttons();
}
async function confirmShot(index,mode,checked){invalidate();try{const data=await locked(()=>request('/api/confirm-shot',{project,shot_id:project.shots[index].id,mode,checked}));project.shots[index]=data.shot;}finally{drawShots();}}
function renderPlan(){
 if(!plan){$('plan').innerHTML='<div class="empty compact"><p>每段文案都会关联事实，<br>每个镜头都会关联用途。</p></div>';buttons();return;}
 $('plan').innerHTML=plan.segments.map((s,i)=>`<article class="plan-segment"><div class="seg-top"><span>${String(i+1).padStart(2,'0')} / ${esc(tags[s.role])}</span><span><button aria-label="上移第${i+1}段" data-up="${i}" ${i===0?'disabled':''}>↑</button><button aria-label="下移第${i+1}段" data-down="${i}" ${i===plan.segments.length-1?'disabled':''}>↓</button></span></div><p>${esc(s.text)}</p>${s.clips?`<p class="hint">${s.clips.length}个片段 · 共${s.clips.reduce((n,c)=>n+c.end-c.start,0).toFixed(1)}秒 · 同一段旁白连续播放一次</p>`:''}<div class="evidence">${esc(s.reason)}<br>事实引用：${s.fact_ids.map(x=>esc(names[project.facts.find(f=>f.id===x)?.kind]||x)).join('、')||'通用引导语，不增加商户事实'}</div></article>`).join('')+(plan.missing.length?`<div class="warning"><strong>还差这些证据</strong><br>${plan.missing.map(esc).join('<br>')}</div>`:'<div class="ok">✓ 必需信息与镜头齐全，可进入人工确认和渲染。</div>');
 if(plan.copy_notes?.length)$('plan').insertAdjacentHTML('afterbegin',`<p class="hint">${plan.copy_notes.map(esc).join('<br>')}</p>`);
 if(plan.pacing)$('plan').insertAdjacentHTML('afterbegin',`<p class="hint">目标 15–30 秒${plan.renderable?` · 预计 ${plan.segments.reduce((n,s)=>n+(s.clips||[s]).reduce((v,c)=>v+c.end-c.start,0),0).toFixed(1)} 秒`:''} · 保留已选动态画面，旁白结束后继续展示</p>`);
 $('plan').querySelectorAll('[data-up]').forEach(b=>b.onclick=()=>reorder(+b.dataset.up,-1));$('plan').querySelectorAll('[data-down]').forEach(b=>b.onclick=()=>reorder(+b.dataset.down,1));buttons();
}
async function reorder(i,delta){if(busy)return;revision++;const line=cta[plan.goal];const last=plan.segments.at(-1);if(last.text.endsWith(line))last.text=last.text.slice(0,-line.length);[plan.segments[i],plan.segments[i+delta]]=[plan.segments[i+delta],plan.segments[i]];plan.segments.at(-1).text+=line;plan.renderable=false;resetResult();try{const checked=await locked(()=>request('/api/validate',{project,plan}));plan=checked.plan;}catch(e){plan.missing=[e.message];status(e.message,true);}renderPlan();}
function download(name,content,type='application/json'){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([content],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
function guard(fn){return async(...a)=>{try{await fn(...a);}catch(e){status(e.message,true);}};}
$('goal').onchange=()=>{project.goal=$('goal').value;invalidate();};$('method').onchange=invalidate;
$('demoBtn').onclick=guard(async()=>{project=await task('/api/demo',{});invalidate();draw();status('模拟案例已载入。可以切换目标、检查顺序，再生成视频。');});
$('newBtn').onclick=()=>{project=blank();invalidate();draw();status('已开始空白真实项目。之前保存的项目可通过导入恢复。');};
$('planBtn').onclick=guard(async()=>{const started=revision;status('正在测量实际旁白时长并选择能放下文案的镜头…',false,true);const checked=await locked(()=>request('/api/plan',{project,method:$('method').value}));if(started!==revision)return status('项目信息已变化，请重新编排。',true);plan=checked;renderPlan();status(plan.renderable?'方案和配音时长检查已通过，请核对内容。':'发现缺失或不可用信息，请查看提示。');});
$('renderBtn').onclick=guard(async()=>{const started=revision;const data=await task('/api/render',{project:structuredClone(project),plan:structuredClone(plan)});if(started!==revision)return status('项目信息已变化，旧版本成片未载入，请重新生成。',true);showResult(data);});
$('localAnalyzeBtn').onclick=guard(async()=>{const started=revision;const analyzed=await task('/api/local-analyze',{project:structuredClone(project)});if(started!==revision)return status('项目信息已变化，旧分析结果已忽略，请重试。',true);project=analyzed;invalidate();draw();const summary=project.vision_analysis?.summary;status(summary?`本地分析：成功 ${summary.succeeded}，失败 ${summary.failed}，跳过 ${summary.skipped}。所有标签待确认；请逐段查看视频，失败素材可重新上传或移除。`:'本地 AI 分析完成。所有标签待确认；请查看完整视频后确认。',false,true);});
function showResult(data){$('result').hidden=false;$('preview').src=data.video;$('preview').poster=data.cover;$('videoDownload').href=data.video;$('reportDownload').href=data.report;$('bundleDownload').href=data.bundle;
 const m=data.metrics;$('resultMeta').textContent=`${m.synthetic?'模拟技术样片 · ':''}${m.metadata.duration.toFixed(1)} 秒 · ${m.metadata.width} × ${m.metadata.height} · 本次处理 ${m.elapsed_seconds.toFixed(1)} 秒 · 付费 API 调用 ${m.api_calls} 次`;
 $('timings').innerHTML=m.timings.map(t=>`<div class="timing">${t.start.toFixed(1)}–${t.end.toFixed(1)}s / ${esc(t.text)}${t.held_frame_seconds>0?` / 末帧停留 ${t.held_frame_seconds}s`:''}</div>`).join('');$('result').scrollIntoView({behavior:'smooth',block:'start'});}
$('saveBtn').onclick=guard(async()=>{const r=await locked(()=>request('/api/save',{project,plan:plan?.renderable?plan:null,method:$('method').value}));status(r.plan_saved?'项目与剪辑方案已保存，重开会重新核验并恢复当前顺序。':'素材与事实已保存；当前没有可恢复的有效剪辑方案。');});
$('exportProjectBtn').onclick=guard(async()=>{const packed=await projectForExport();download('linjing-project.json',JSON.stringify(packed,null,2));});
$('projectFile').onchange=guard(async e=>{const f=e.target.files[0];if(!f)return;const restored=await locked(async()=>request('/api/reconcile',{project:JSON.parse(await f.text())}));applyProject(restored);status(plan?'已导入项目并重新核验剪辑方案，顺序已恢复。':'项目已导入并核对素材；失效确认或方案请重新完成。');e.target.value='';});
$('videoFiles').onchange=guard(async e=>{
 if(onlinePreview)throw Error('在线预览不接收视频，请在本地版上传素材。');
 const files=[...e.target.files];if(!files.length)return;if(busy)throw Error('请等待当前处理完成。');
 // Keep the current edit and preview until the first real asset is usable.
 const uploadProject=project.synthetic?blank():project;let switchedProject=false;
 busy=true;buttons();const results={success:[],failed:[],skipped:[]};
 try{for(const f of files){
  try{
   if(f.size>200*1024*1024)throw Error('超过200MB');
   const digest=await crypto.subtle.digest('SHA-256',await f.arrayBuffer());
   const key=f.name+':'+f.size+':'+Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
   if((uploadProject.upload_records||[]).some(r=>r.key===key&&uploadProject.shots.some(s=>s.media_id===r.media_id&&!s.unavailable))){results.skipped.push(f.name);continue;}
   status('正在上传：'+f.name,false,true);
   const r=await fetch('/api/upload?name='+encodeURIComponent(f.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f});
   const response=await r.json();if(!r.ok)throw Error(response.error||'上传未成功');
   const asset=await watch(response.job_id);if(!Array.isArray(asset.shots)||!asset.shots.length)throw Error('未分析到可查看的镜头，请重新导出视频后重试。');
   uploadProject.shots.push(...asset.shots);(uploadProject.upload_records??=[]).push({key,media_id:asset.id});
   if(project!==uploadProject){project=uploadProject;switchedProject=true;}
   results.success.push(f.name);invalidate();draw();
  }catch(err){results.failed.push({name:f.name,reason:err.message});}
 }
 const failures=results.failed.map(x=>x.name+'：'+x.reason).join('；');
 const retained=!results.success.length&&results.failed.length?'原项目与剪辑方案已保留。':'';
 status(`上传完成：成功 ${results.success.length}，失败 ${results.failed.length}，跳过已上传 ${results.skipped.length}。${retained}${switchedProject?'已开始真实项目，模拟素材未混入。':''}${failures?'失败文件：'+failures:'请查看素材后确认用途。'}`,Boolean(results.failed.length),true);
 }finally{busy=false;buttons();e.target.value='';}
});
$('contextBtn').onclick=guard(async()=>{if(!project.shots.length)throw Error('请先添加素材。');const res=await request('/api/context',{project});const a=document.createElement('a');a.href=res.url;a.download='linjing-context.zip';a.click();status(`已导出 ${res.frames} 张抽帧及标注提示词。发给模型前，请确认素材可以分享。`);});
$('labelsFile').onchange=guard(async e=>{const f=e.target.files[0];if(!f)return;const labels=JSON.parse(await f.text());const res=await request('/api/labels',{project,candidates:labels});for(const item of res.labels){const s=project.shots.find(s=>s.id===item.shot_id);Object.assign(s,item,{label_source:'model_candidate',confirmed:false});}invalidate();drawShots();status('候选标签已导入，需要逐个查看并确认。');e.target.value='';});
function switchTab(which){$('workspace').hidden=which!=='work';$('research').hidden=which!=='research';$('workTab').classList.toggle('active',which==='work');$('researchTab').classList.toggle('active',which==='research');}
$('workTab').onclick=()=>switchTab('work');$('researchTab').onclick=guard(async()=>{switchTab('research');if(onlinePreview){$('benchmark').textContent='在线预览不读取本地测试记录。验证方法与结果说明请查看代码仓库。';updateReviews();return;}const b=await request('/api/benchmark');$('benchmark').innerHTML=b.cases?`<div class="bench-big">${b.passed}<small> / ${b.total} 个用例通过</small></div><p class="hint">${esc(b.scope)} · ${esc(b.created_at)}</p><div class="case-list">${b.cases.map(c=>`${c.passed?'✓':'✗'} ${esc(c.name)}`).join('<br>')}</div>`:'尚未运行约束测试';updateReviews();});
function updateReviews(){$('reviewCount').textContent=`当前浏览器已保存 ${reviewRecords.length} 条复核记录。保存于浏览器，建议及时导出。`;}
$('reviewForm').onsubmit=e=>{e.preventDefault();const record=Object.fromEntries(new FormData(e.target));record.created_at=new Date().toISOString();reviewRecords.push(record);localStorage.setItem('linjing-reviews',JSON.stringify(reviewRecords));updateReviews();status('复核记录已保存。');};
$('exportReviewsBtn').onclick=()=>{const keys=['sample_id','reviewer_id','data_type','correctness','alignment','naturalness','edit_seconds','publish','notes','created_at'];const quote=x=>'"'+String(x??'').replace(/^[=+@-]/,"'$&").replace(/"/g,'""')+'"';download('linjing-reviews.csv','\ufeff'+[keys.join(','),...reviewRecords.map(r=>keys.map(k=>quote(r[k])).join(','))].join('\r\n'),'text/csv;charset=utf-8');};
const workspaceReady=guard(async()=>{draw();if(onlinePreview){showOnlinePreview();return;}const health=await request('/api/health');$('modelStatus').textContent=health.local_vision?.ready?`本地模型${health.local_vision.state==='loaded'?'已加载':'文件已校验 · 首次分析时加载'} · 素材不上传云端 · 候选需人工确认`:`${health.local_vision?.reason||'本地模型未就绪'} 可先手工标注。`;$('voiceStatus').textContent=health.voice?.ready?'Vivian · 本地轻快女声 · 720 × 1280 · MP4。首次生成需加载声音，请稍候。':(health.voice?.reason||'本地女声尚未就绪，请检查配音环境。');const saved=await request('/api/saved');if(saved){applyProject(saved);if(!$('workspace').hidden)status(plan?'已恢复项目和剪辑顺序，并重新通过核验。':'已恢复上次保存的素材与事实，请检查方案提示。');}else draw();})();

// The entry flow supplies a draft; it never supplies fact or material confirmation.
window.linjingStudio={
 ready:workspaceReady,
 isBusy:()=>busy,
 hasContent:()=>Boolean(project.shots.length||project.facts.some(f=>f.value.trim())),
 matchesBrief:brief=>Boolean(project.creative_brief&&Object.keys(brief).every(key=>project.creative_brief[key]===brief[key])),
 async startRestaurant(brief,backup=false){
  await workspaceReady;
  if(busy)throw Error('请等待当前处理完成，再开始新的创作。');
  if(backup){
   const packed=await projectForExport();
   download('邻镜智作-开始新创作前的项目备份.json',JSON.stringify(packed,null,2));
  }
  const next=blank();next.name=`${brief.shop} · ${brief.intent_name}`;next.goal=brief.goal;next.creative_brief=structuredClone(brief);
  next.facts.find(f=>f.kind==='shop').value=brief.shop;
  next.facts.find(f=>f.kind==='product').value=brief.product;
  project=next;$('method').value='evidence';invalidate();draw();
  status('已进入本次创作。店名和菜品已带入，请补充来源并逐项确认。');
 }
};

/* Restaurant discovery and shooting briefs. No fact is confirmed by this flow. */
(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const storageKey = 'linjing-restaurant-home-v1';
  const categories = [
    {id:'home', name:'家常炒菜', note:'一盘好菜，热气上桌', icon:'wok', action:'翻炒、浇汁或出锅'},
    {id:'hotpot', name:'火锅', note:'锅底、食材与涮煮', icon:'pot', action:'下锅或涮煮'},
    {id:'barbecue', name:'烧烤', note:'烤制细节与成品', icon:'grill', action:'翻面或撒料'},
    {id:'noodles', name:'粉面', note:'汤底、浇头与一碗面', icon:'bowl', action:'浇汤或加浇头'},
    {id:'breakfast', name:'早餐快餐', note:'一份早餐，一顿好饭', icon:'steam', action:'装盘或出餐'},
    {id:'snack', name:'小吃', note:'小份美味，近看细节', icon:'snack', action:'制作或装盘'}
  ];
  const goals = [
    {id:'signature', name:'推荐一道菜', short:'菜品推荐', description:'让顾客看见这道菜，想来尝一尝。', label:'想推荐哪道菜？', placeholder:'例如：砂锅牛肉、手工牛肉面', goal:'attract', number:'01'},
    {id:'offer', name:'推广一个套餐', short:'套餐推广', description:'展示套餐搭配，再说清优惠信息。', label:'想推广哪个套餐？', placeholder:'例如：双人烤鱼套餐、工作日午餐套餐', goal:'promo', number:'02'},
    {id:'restaurant', name:'介绍我的饭店', short:'门店介绍', description:'让顾客了解门店、菜品和用餐环境。', label:'搭配展示哪道菜？', placeholder:'例如：本店红烧肉（门店介绍会展示菜品）', goal:'visit', number:'03'}
  ];
  const icons = {
    wok:'<path d="M5 17h22c-1 8-5 12-11 12S6 25 5 17Z"/><path d="m26 19 7-5M10 11c-3-4 3-4 0-8m7 8c-3-4 3-4 0-8"/>',
    pot:'<path d="M7 15h22v9a6 6 0 0 1-6 6H13a6 6 0 0 1-6-6Zm-4 4h4m22 0h4M6 12h24M15 8h6M13 4v3m10-3v3"/>',
    grill:'<path d="M5 20h26M7 25h22M9 31l3-6m15 6-3-6M8 7l18 10M13 4l18 10M5 12l18 10"/><path d="m12 6-3 5m10-1-3 5m10-1-3 5"/>',
    bowl:'<path d="M5 18h26c-1 8-6 12-13 12S6 26 5 18ZM14 33h8M11 12c-4-5 4-5 0-10m8 10c-4-5 4-5 0-10m8 10c-4-5 4-5 0-10"/>',
    steam:'<path d="M5 18h26v10H5Zm0 5h26M7 18c0-5 4-8 11-8s11 3 11 8M13 5v2m10-2v2M5 31h26"/><path d="M15 13v3m6-3v3"/>',
    snack:'<path d="m9 12 19 4-5 14-10-2Zm3-6 7 8m4-9 1 10M7 31h22M11 19l3 1m4 3 3 1"/>'
  };
  let state = {category:'', intent:'', shop:'', subject:''};
  let queuedBrief = null;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
    if (saved && typeof saved === 'object') {
      state = {
        category:categories.some(item => item.id === saved.category) ? saved.category : '',
        intent:goals.some(item => item.id === saved.intent) ? saved.intent : '',
        shop:typeof saved.shop === 'string' ? saved.shop.slice(0,60) : '',
        subject:typeof saved.subject === 'string' ? saved.subject.slice(0,60) : ''
      };
    }
  } catch (_) { /* A restricted browser can still use the complete flow. */ }

  function persist() {
    try { sessionStorage.setItem(storageKey, JSON.stringify(state)); } catch (_) {}
  }
  const category = () => categories.find(item => item.id === state.category);
  const intent = () => goals.find(item => item.id === state.intent);
  const clean = value => value.trim().replace(/\s+/g, ' ');
  const invalidText = value => /[\u0000-\u001f\u007f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/.test(value);
  const complete = () => Boolean(category() && intent() && clean(state.shop) && clean(state.subject) && !invalidText(state.shop + state.subject));
  const selectedBrief = () => ({version:1, industry:'restaurant', category:state.category, category_name:category().name, intent:state.intent, intent_name:intent().short, goal:intent().goal, shop:clean(state.shop), product:clean(state.subject)});

  function updateGreeting() {
    const hour = new Date().getHours();
    byId('timeGreeting').textContent = hour >= 5 && hour < 11 ? '早上好，' : hour >= 11 && hour < 18 ? '中午好，' : '晚上好，';
  }

  function updateSelection() {
    const selected = intent();
    document.querySelectorAll('[data-restaurant-category]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.restaurantCategory === state.category));
    });
    document.querySelectorAll('[data-restaurant-intent]').forEach(button => {
      button.setAttribute('aria-pressed', String(button.dataset.restaurantIntent === state.intent));
    });
    byId('briefFields').hidden = !selected;
    byId('briefSubjectLabel').textContent = selected?.label || '想宣传的具体内容';
    byId('briefSubject').placeholder = selected?.placeholder || '';
    byId('briefSubjectHelp').textContent = selected?.id === 'restaurant' ? '这条视频以饭店为主角，也会展示一道菜，帮助顾客了解你。' : '写下实际名称；价格、特点和优惠条件可以在工作台补充确认。';
    byId('selectionCategory').textContent = category()?.name || '待选择';
    byId('selectionGoal').textContent = selected?.short || '待选择';
    byId('selectionObject').textContent = !selected ? '还没想好也没关系，从左边开始。' : selected.id === 'restaurant' ? clean(state.shop) || '你的饭店' : clean(state.subject) || (selected.id === 'offer' ? '你的套餐' : '你的招牌菜');
    byId('selectionShop').textContent = clean(state.shop) || '填写店名，让这次创作属于你。';
    byId('selectionCaption').textContent = selected?.id === 'restaurant' ? `搭配展示：${clean(state.subject) || '待填写菜品'}` : selected ? `本次重点：${selected.short}` : '选好方向，就能看到对应的拍摄清单。';
    byId('briefInvalidText').hidden = !invalidText(state.shop + state.subject);
    const missing = !category() ? '先选一种饭店类型' : !selected ? '再选这次的宣传目标' : !clean(state.shop) ? '填写你的饭店名称' : !clean(state.subject) ? selected.label.replace('？','') : invalidText(state.shop + state.subject) ? '请修改包含不可见字符的文字' : '已选好，接下来看看怎么拍';
    byId('selectionHint').textContent = missing;
    byId('startBriefBtn').disabled = !complete();
    byId('selectionSteps').textContent = complete() ? '准备就绪' : `${Number(Boolean(category())) + Number(Boolean(selected)) + Number(Boolean(selected && clean(state.shop) && clean(state.subject)))}/3 已完成`;
    persist();
  }

  function shootingTasks(brief) {
    const selectedCategory = categories.find(item => item.id === brief.category);
    const dish = brief.product;
    const shop = brief.shop;
    if (brief.intent === 'offer') return [
      {title:'套餐完整亮相', role:'商品', duration:'6–8 秒', copy:`把「${dish}」实际包含的菜品摆在一起，手机竖着，整套入镜后固定拍摄。`, check:'全部菜品看得清，不遮挡，不遗漏套餐内容。'},
      {title:'主菜近看', role:'商品', duration:'6–8 秒', copy:'选套餐里的一道主菜，靠近一些，停稳手机，拍清食材和成品细节。', check:'主体清楚，避免来回变焦或快速晃动。'},
      {title:'另一道搭配', role:'商品', duration:'6–8 秒', copy:'换一个角度，展示套餐里的另一道菜或饮品，固定拍摄。', check:'与上一条展示不同内容，均为实际套餐组成。'},
      {title:'找到你的店', role:'门头', duration:'6–8 秒', copy:`站在店外，把「${shop}」的招牌和入口一起拍清楚。`, check:'文字可辨认，入口完整；上传后再确认地址和活动条件。'}
    ];
    if (brief.intent === 'restaurant') return [
      {title:'先认识这家店', role:'门头', duration:'6–8 秒', copy:`从门外固定拍摄「${shop}」的招牌与入口，让顾客能辨认位置。`, check:'招牌清楚、入口完整，尽量避开遮挡。'},
      {title:'一道菜认识你', role:'商品', duration:'6–8 秒', copy:`把「${dish}」放在桌面上，整盘入镜，停稳后连续拍摄。`, check:'菜品清晰，桌面整洁，盘子没有被切掉。'},
      {title:'看看用餐空间', role:'环境', duration:'6–8 秒', copy:'站在用餐区一侧，用一个固定镜头展示桌椅、通道和空间。', check:'能看出空间布局，避免快速扫拍。'},
      {title:'再看一个角落', role:'环境', duration:'6–8 秒', copy:'选择另一个实际用餐区域或座位细节，换一个固定角度拍摄。', check:'与上一条画面不同，尽量避开顾客正脸。'}
    ];
    return [
      {title:'这道菜，先亮相', role:'商品', duration:'6–8 秒', copy:`把「${dish}」放在干净桌面上，手机竖着，整盘入镜后固定拍摄。`, check:'主体清晰、完整入镜，背景没有明显杂物。'},
      {title:'记录制作动作', role:'制作', duration:'8 秒左右', copy:`选「${selectedCategory.action}」中的一个实际动作，固定手机，从动作开始前拍到结束后。`, check:'拍完整个动作，手和工具不要一直挡住主体。'},
      {title:'靠近一点看细节', role:'商品', duration:'6–8 秒', copy:`换一个近一些的角度，展示「${dish}」的食材或成品细节，停稳后再拍。`, check:'重要食材清楚，避免过近导致失焦。'},
      {title:'用餐的地方', role:'环境', duration:'6–8 秒', copy:`在「${shop}」用餐区选一个角度，固定拍摄桌面和周围环境。`, check:'画面稳定，展示实际用餐环境。'}
    ];
  }

  function renderGuide() {
    const brief = selectedBrief();
    const tasks = shootingTasks(brief);
    byId('guideCategory').textContent = `饭店 / ${brief.category_name} / ${brief.intent_name}`;
    byId('guideTitle').textContent = brief.intent === 'restaurant' ? `让顾客认识「${brief.shop}」` : `这次，拍好「${brief.product}」`;
    byId('guideSubtitle').textContent = `${brief.shop} · ${brief.intent_name} · ${tasks.length} 个拍摄任务`;
    byId('guideObject').textContent = brief.intent === 'restaurant' ? brief.shop : brief.product;
    byId('guideGoal').textContent = brief.intent_name;
    byId('guideOrder').textContent = brief.intent === 'offer' ? '套餐全貌 → 菜品细节 → 门店位置' : brief.intent === 'restaurant' ? '门店位置 → 菜品展示 → 用餐环境' : '成品展示 → 制作过程 → 用餐环境';
    byId('guideChecklist').innerHTML = tasks.map((task, index) => `<article class="shoot-task"><div class="shoot-task-index">${String(index+1).padStart(2,'0')}</div><div class="shoot-task-body"><div class="shoot-task-top"><span>${escape(task.role)}镜头</span><span>${escape(task.duration)}</span></div><h2>${escape(task.title)}</h2><p>${escape(task.copy)}</p><div class="shoot-check"><span aria-hidden="true">✓</span><span>${escape(task.check)}</span></div></div></article>`).join('');
    byId('guideFactsNote').textContent = brief.intent === 'offer' ? '套餐价格、活动有效期、使用条件和地址，将在工作台由你补充并确认。' : brief.intent === 'restaurant' ? '店名、菜品和地址会带入后续工作台；填写内容仍需你核实确认。' : '店名和菜名会带入后续工作台；制作方式、菜品特点仍需你核实确认。';
  }

  const originalResearch = byId('researchTab').onclick;
  const views = {home:'home', workspace:'workspace', research:'research', shooting:'shooting'};
  function route() {
    byId('status').hidden = true;
    const hash = location.hash.slice(1);
    let view = hash === 'workspace' ? 'workspace' : hash === 'research' ? 'research' : hash.startsWith('shoot/') ? 'shooting' : 'home';
    if (view === 'shooting' && (!complete() || hash !== `shoot/${state.intent}`)) {
      history.replaceState(null, '', '#home');
      view = 'home';
    }
    Object.entries(views).forEach(([key, id]) => { byId(id).hidden = key !== view; });
    byId('homeTab').classList.toggle('active', view === 'home' || view === 'shooting');
    byId('workTab').classList.toggle('active', view === 'workspace');
    byId('researchTab').classList.toggle('active', view === 'research');
    if (view === 'shooting') renderGuide();
    if (view === 'research') originalResearch();
    if (view === 'home') updateGreeting();
    document.title = `${view === 'home' ? '今天要宣传什么？' : view === 'shooting' ? intent().short+' · 拍摄清单' : view === 'workspace' ? '创作工作台' : '研究与验证'} · 邻镜智作`;
    window.scrollTo({top:0, behavior:'instant'});
    const heading = byId(views[view]).querySelector('h1');
    if (heading) { heading.tabIndex = -1; heading.focus({preventScroll:true}); }
  }
  function navigate(view) {
    const next = view === 'shooting' ? `shoot/${state.intent}` : view;
    if (location.hash !== '#'+next) history.pushState(null, '', '#'+next);
    route();
  }

  byId('restaurantCategories').innerHTML = categories.map(item => `<button type="button" class="restaurant-category" data-restaurant-category="${item.id}" aria-pressed="false"><svg viewBox="0 0 36 36" aria-hidden="true">${icons[item.icon]}</svg><span><strong>${item.name}</strong><small>${item.note}</small></span><span class="choice-dot" aria-hidden="true"></span></button>`).join('');
  byId('restaurantGoals').innerHTML = goals.map(item => `<button type="button" class="restaurant-goal" data-restaurant-intent="${item.id}" aria-pressed="false"><span class="goal-number">${item.number}</span><strong>${item.name}</strong><span>${item.description}</span><span class="goal-arrow" aria-hidden="true">↗</span></button>`).join('');
  document.querySelectorAll('[data-restaurant-category]').forEach(button => {
    button.onclick = () => { state.category = button.dataset.restaurantCategory; updateSelection(); };
  });
  document.querySelectorAll('[data-restaurant-intent]').forEach(button => {
    button.onclick = () => {
      if (state.intent !== button.dataset.restaurantIntent) state.subject = '';
      state.intent = button.dataset.restaurantIntent;
      byId('briefSubject').value = state.subject;
      updateSelection();
    };
  });
  byId('briefShop').value = state.shop;
  byId('briefSubject').value = state.subject;
  byId('briefShop').oninput = event => { state.shop = event.target.value; updateSelection(); };
  byId('briefSubject').oninput = event => { state.subject = event.target.value; updateSelection(); };
  byId('restaurantForm').onsubmit = event => {
    event.preventDefault();
    if (complete()) navigate('shooting');
  };
  byId('homeTab').onclick = () => navigate('home');
  byId('workTab').onclick = () => navigate('workspace');
  byId('researchTab').onclick = () => navigate('research');
  byId('editBriefBtn').onclick = () => navigate('home');
  byId('continueProjectBtn').onclick = () => navigate('workspace');
  byId('cancelStartBtn').onclick = () => byId('projectReplaceDialog').close();
  byId('returnProjectBtn').onclick = () => { byId('projectReplaceDialog').close(); navigate('workspace'); };

  async function startProject(backup) {
    if (!queuedBrief) return;
    await window.linjingStudio.startRestaurant(queuedBrief, backup);
    queuedBrief = null;
    byId('projectReplaceDialog').close();
    navigate('workspace');
  }
  byId('backupStartBtn').onclick = async () => {
    const button = byId('backupStartBtn');
    button.disabled = true;
    try { await startProject(true); } catch (error) { status(error.message, true); } finally { button.disabled = false; }
  };
  byId('openRestaurantEditorBtn').onclick = async () => {
    const button = byId('openRestaurantEditorBtn');
    button.disabled = true;
    try {
      await window.linjingStudio.ready;
      if (window.linjingStudio.isBusy()) throw Error('当前工作台正在处理素材，请稍后再开始。');
      const brief = selectedBrief();
      if (window.linjingStudio.matchesBrief(brief)) return navigate('workspace');
      queuedBrief = brief;
      if (window.linjingStudio.hasContent()) byId('projectReplaceDialog').showModal();
      else await startProject(false);
    } catch (error) { status(error.message, true); } finally { button.disabled = false; }
  };
  window.addEventListener('hashchange', route);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) updateGreeting(); });
  setInterval(updateGreeting, 60000);
  updateGreeting();
  updateSelection();
  route();
})();
