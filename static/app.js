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
 const brief=project.creative_brief;$('restaurantWorkspaceBrief').hidden=!brief;$('restaurantWorkspaceBrief').textContent=brief?`本次创作：${brief.shop} · ${brief.intent_name} · ${brief.intent==='restaurant'?'饭店介绍，搭配菜品：':''}${brief.product}。${brief.intent==='signature'&&brief.capture_mode==='finished'?'成品路线：请准备门头、环境并确认地址。':''}以下信息仍需核实与确认。`:'';
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
  let state = {category:'', intent:'', shop:'', subject:'', captureMode:'process'};
  let queuedBrief = null;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
    if (saved && typeof saved === 'object') {
      state = {
        category:categories.some(item => item.id === saved.category) ? saved.category : '',
        intent:goals.some(item => item.id === saved.intent) ? saved.intent : '',
        shop:typeof saved.shop === 'string' ? saved.shop.slice(0,60) : '',
        subject:typeof saved.subject === 'string' ? saved.subject.slice(0,60) : '',
        captureMode:saved.captureMode === 'finished' ? 'finished' : 'process'
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
  const guideVersion='restaurant-shooting-v2-2026-11-03';
  const selectedBrief = () => ({version:2, guide_version:guideVersion, industry:'restaurant', category:state.category, category_name:category().name, intent:state.intent, intent_name:intent().short, capture_mode:state.intent==='signature'?state.captureMode:'finished', goal:state.intent==='signature'&&state.captureMode==='finished'?'visit':intent().goal, shop:clean(state.shop), product:clean(state.subject)});

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
    byId('selectionCaption').textContent = selected?.id === 'restaurant' ? `搭配展示：${clean(state.subject) || '待填写菜品'}` : selected ? `本次重点：${selected.short}${selected.id==='signature'&&state.captureMode==='finished'?' · 成品路线（需地址）':''}` : '选好方向，就能看到对应的拍摄清单。';
    byId('briefInvalidText').hidden = !invalidText(state.shop + state.subject);
    const missing = !category() ? '先选一种饭店类型' : !selected ? '再选这次的宣传目标' : !clean(state.shop) ? '填写你的饭店名称' : !clean(state.subject) ? selected.label.replace('？','') : invalidText(state.shop + state.subject) ? '请修改包含不可见字符的文字' : '已选好，接下来看看怎么拍';
    byId('selectionHint').textContent = missing;
    byId('startBriefBtn').disabled = !complete();
    byId('selectionSteps').textContent = complete() ? '准备就绪' : `${Number(Boolean(category())) + Number(Boolean(selected)) + Number(Boolean(selected && clean(state.shop) && clean(state.subject)))}/3 已完成`;
    persist();
  }

  // These are researched capture proposals, not calibrated automatic acceptance rules.
  const guideSources={
    'DY-OFFICIAL':{title:'抖音生活服务：美食新手拍摄指引',url:'https://life.douyin.com/support/content/124147?menu=1&spaceId=123',scope:'历史官方文字指引，检索文本核对'},
    'DY-MOVE':{title:'抖音：基础运镜教你拍美食大片',url:'https://jingxuan.douyin.com/m/video/7646349339363900038',scope:'公开页面与局部画面观察'},
    'B-TECH':{title:'二麦科技：五个美食拍摄技巧',url:'https://www.bilibili.com/video/BV1xb411C7Z2/',scope:'公开页面与局部画面观察'},
    'B-HOME':{title:'弗弗的Young：餐饮店拍摄实践',url:'https://www.bilibili.com/video/BV1sP4y1379S/',scope:'专业案例片段，降低器材要求后改编'},
    'B-HOTPOT':{title:'苏州大时代传媒：火锅店怎么拍',url:'https://www.bilibili.com/video/BV1qbcLeAEux/',scope:'公开页面与摆盘片段观察'},
    'B-GRILL':{title:'烤肉店宣传片案例',url:'https://www.bilibili.com/video/BV1B54y1C7M4/',scope:'公开页面与烤制片段观察'},
    'B-NOODLES':{title:'泽泽面道：面馆宣传片',url:'https://www.bilibili.com/video/BV1BE411r7Es/',scope:'公开页面、品牌与制作片段观察'},
    'B-BREAKFAST':{title:'友谊早餐店：门店记录',url:'https://www.bilibili.com/video/BV1YsxMzbEQH/',scope:'门店与价目表片段观察，非效果实证'},
    'B-SNACK':{title:'KC宣传片：汉堡产品案例',url:'https://www.bilibili.com/video/BV16xvneuEPB/',scope:'层叠食品片段，不能代表所有小吃'},
    'DY-STRUCTURE':{title:'老许说餐饮：宣传内容讲解',url:'https://www.douyin.com/video/7507502564683025721',scope:'创作者讲解片段，非商户转化数据'}
  };
  // Each tuple is [task title, action, camera position, visible manual check].
  const foodProfiles={
    home:{signal:'主料、酱汁与上桌的真实层次',unit:'盘／份',source:'B-HOME',avoid:'别只拍火焰和厨师；不要为了好看给成品添加售卖时没有的配料。',
      hero:['主料和整盘，一起看清','把{main}放在干净桌面，盘子留完整，主料朝镜头，停稳后拍。','从桌面斜上方拍；侧面有光即可，不要求复杂暗调。','主料、配菜和餐盘关系清楚，不被反光或热气遮住。'],
      detail:['看一块主料的真实质地','用干净餐具夹起一小块熟食，停一下再放回；不适合夹起的菜就换侧面近景。','手机固定在盘边斜前方，对焦食物，手只做一个动作。','主料始终清楚；画面只能证明看得见的质地，不能证明味道。'],
      process:['记录翻炒、浇汁或出锅','得到允许后，固定拍一个真实的翻炒、浇汁或出锅动作，动作前后各留一秒。','站在员工通道外的侧面，不把手机伸到锅口上方。','看清食物从锅到盘或汁落到菜上的完整变化，员工手臂不持续遮挡。'],
      package:['这桌套餐，到底包含什么','把「{dish}」实际包含的菜、主食和饮品一次摆齐，留出各盘边界。','能俯拍就俯拍；桌子较大时从斜上方拍，别用超广角把边缘拉长。','每项菜品都能辨认，盘数与套餐说明相符，不混入额外赠菜。'],
      space:['一桌饭坐在哪里吃','拍「{shop}」一张实际餐桌及相邻通道，展示日常用餐布局。','固定在用餐区一侧，保持桌边和竖线平直。','桌椅、通道关系清楚，不用挤满画面制造热闹。'],
      service:['菜从哪里端上桌','方便且得到允许时，只拍一盘菜被端到真实餐桌；不用顾客配合表演。','机位对桌面和餐盘，尽量不拍人脸。','动作完整、餐盘明确，不把端菜当成后厨制作证据。']},
    hotpot:{signal:'锅底状态、食材盘与涮后质地',unit:'盘／份／锅',source:'B-HOTPOT',avoid:'蒸汽盖住食物就换角度；顾客涮菜、夹菜属于食用展示，不能当后厨制作。',
      hero:['锅底与主推食材同框','拍{main}与实际锅底的关系；若主推的是锅底，保留锅沿和一盘真实搭配食材。','斜上方固定机位，镜头避开最浓的蒸汽，不贴近热锅。','能区分锅底与食材，不是一整片白雾或只有沸腾水面。'],
      detail:['食材涮好以后是什么样','用餐具夹起已熟的主推食材，停在锅边可对焦的位置，再放回盘中。','固定在锅边斜侧面，锅沿或食材盘保留在画面里。','熟食形态和质地清楚，手与筷子不遮住主体；不拍入口表情代替产品。'],
      process:['后厨备料或锅底制作','仅在得到允许时，记录员工切配、装盘或调制锅底中的一个真实动作。','侧面固定，远离刀具、热油和出餐通道。','员工的实际制作动作完整；顾客涮煮不能填入这项。'],
      package:['锅底、荤素与份数拍齐','把「{dish}」的锅底、荤菜、素菜和其他实际包含项摆齐，不叠盘遮挡。','斜上方固定拍全桌；摆不下可分两条，不能只给一角冒充全套。','锅底是否包含、各盘及数量看得明白，与套餐内容一致。'],
      space:['看清桌距与实际用餐区','拍「{shop}」的锅桌、座位与通道；若想展示排烟设施，只记录实际设备外观。','在过道边缘固定拍，不站进服务路线。','桌椅布局可辨认；设备外观不能证明无烟或排烟效果。'],
      service:['上锅或上菜的真实一刻','得到允许后拍员工把锅或菜盘放到桌上的过程，也可改拍取餐／调料区。','对准桌面固定，避免顾客正脸和锅口热气。','看清服务动作，不通过快放宣称上菜速度。']},
    barbecue:{signal:'烤好表面、真实火候与串盘数量',unit:'串／盘／份',source:'B-GRILL',avoid:'不要只剩火焰、油烟或红色滤镜；不要求拿手机贴近烤架，也不拍未熟肉入口。',
      hero:['先看烤好的成品','把{main}的熟成品摆在实际售卖餐具里，烤痕或表面朝向镜头。','从略低的斜侧面拍，避开强红灯，让食物颜色接近日常所见。','能认出卖的是什么，表层细节清楚，不被烟盖住。'],
      detail:['烤痕、撒料或熟食切面','挑一个真实细节：翻看熟串、展示烤痕，或切开适合切的熟肉；不要几个动作同时做。','手机固定，焦点放在熟食表面，保留盘或串签作为参照。','表面与内部若出现都清楚，不用滤镜伪造油光或焦色。'],
      process:['拍一次翻面、刷料或出炉','得到允许后，从烤架侧面记录员工翻面、刷料或把熟串移到盘中的一个完整动作。','与热源保持距离，固定机位，不追着火焰移动。','能看到实际烤制／出炉变化，不把顾客拿串当制作。'],
      package:['串数、盘数与搭配分开摆','把「{dish}」按实际串数、盘数摆清楚，饮品和小菜只放套餐实际包含的。','斜上方固定，尽量让串签和盘边可辨认。','能看清不同品类和数量；不重复摆盘制造更多串。'],
      space:['夜宵坐在哪里，通道在哪','记录「{shop}」实际开放的室内或外摆用餐区，别把邻店座位拍成自己的。','先选照明稳定的位置，固定拍桌椅与通道。','座位归属、桌距和环境可辨认；夜景不应暗到只剩灯牌。'],
      service:['从出餐口到餐盘','拍熟串交到实际餐盘或取餐台上的动作，也可拍真实点单口。','画面对准餐盘／柜台，少拍人脸。','产品与交付方式清楚，不摆拍排队或拥挤。']},
    noodles:{signal:'面条形态、汤与浇头的关系',unit:'碗／份',source:'B-NOODLES',avoid:'只拍一小撮悬空面不能说明整碗；顾客拌面、挑面不是后厨制作。',
      hero:['面、汤和浇头同一碗看清','把{main}完整放在桌面，整理实际售卖时就有的浇头，保留碗沿。','从斜上方拍，既看到汤面也看到浇头高度。','面条／米粉、汤或酱、主要浇头可辨认，没有只剩热气。'],
      detail:['挑起少量面，再回到碗里','用餐具从{main}中挑起少量面或粉，停在能对焦的位置，再自然放回。','固定斜侧机位，碗留在画面中，不边挑边移动手机。','能看清条形与浇头，动作完整，不倒放或拉伸伪造弹性。'],
      process:['捞面、浇汤或加浇头','经允许，拍员工从捞起面到入碗，或浇汤、加浇头中的一个完整环节。','固定在工作台侧面，不跨过热汤或妨碍出餐。','看得到动作与食物的变化；拍食客吃面不能替代。'],
      package:['主碗、配菜与饮品都交代','把「{dish}」中的主碗、小菜、饮品逐一摆齐，按真实份数展示。','斜上方固定拍，主碗不遮住小碟与饮品。','可辨认每项搭配和实际数量，不拿超大展示碗冒充日常份量。'],
      space:['堂食位和取餐口看明白','在「{shop}」拍实际桌位及取餐口／点单台，突出这家店的真实用餐方式。','固定在一侧，保留座位、通道或柜台关系。','能区分堂食与取餐区域；没有堂食就明确只拍取餐场景。'],
      service:['一碗面怎样交到顾客手里','拍员工把完成的一碗放在出餐台，或拍真实自取台；不用顾客表演。','机位对准碗和出餐台，保持连续。','碗和取餐方式清楚，不通过剪辑保证几分钟出餐。']},
    breakfast:{signal:'一份早餐的组成与取餐场景',unit:'个／份／碗／杯',source:'B-BREAKFAST',avoid:'别把摆拍热闹、快放或多次出餐剪成真实速度承诺；粥类不必硬拍掰开动作。',
      hero:['一份早餐，主食搭配摆清楚','把{main}按真实售卖方式摆好；有主食、粥或饮品就同框展示实际包含项。','从斜上方固定拍，保留碗、杯与主食之间的位置关系。','顾客能辨认这一份吃到什么，包装或热气没有盖住主体。'],
      detail:['馅料、断面或粥里食材','包点／饼可掰开熟成品展示内部；粥类改拍舀起少量实际食材，选择适合本品的一种动作。','固定近景，焦点在断面或勺中食物，保留原餐具参照。','内部或食材清楚；不是每种早餐都要求拉丝、爆汁或冒汽。'],
      process:['开笼、起锅或装碗','得到允许后，拍员工开笼、起锅、装碗或打包中的一个实际环节，保留前后动作。','固定侧面，避开蒸汽、热油与高峰期通道。','看清操作与成品的关系，不用顾客拆包装当制作。'],
      package:['套餐里几个、几碗、几杯','把「{dish}」的主食、饮品与小菜按实际数量摆齐，杯口和包装不互相遮挡。','俯拍或斜上方固定拍，选择能看清数量的角度。','主食个数、饮品杯数及搭配可辨认，额外加购不混入。'],
      space:['点单、取餐和座位在哪里','拍「{shop}」的点单／取餐口；有实际堂食区时补出座位与通道。','从顾客可站的位置固定拍，不挡点单与取餐。','能理解来店后的实际动线，没有座位就不表现堂食。'],
      service:['一次真实打包或取餐','拍一份实际早餐装好并放到取餐台的动作；不要求凑排队或重复出餐。','固定对准包装与取餐台，不拍顾客正脸。','餐品与交付过程可辨认，不用快放制造速度。']},
    snack:{signal:'真实份装、表面与内部层次',unit:'份／盒／串／个',source:'B-SNACK',avoid:'汉堡等层叠食品只是参照；炸串、甜品各拍自己的结构，不要求所有小吃拉丝或爆汁。',
      hero:['先认出这份小吃是什么','把{main}放在实际售卖的纸盒、盘或串签上，保留完整份装。','斜侧拍立体小吃，俯拍平铺小吃，选能看清主体的一种机位。','主体与份装清楚，没有只拍局部却看不出卖什么。'],
      detail:['拍它真正有的表面或内部','熟食可掰开／切开展示内部；串类拍熟成品表层，甜品拍实际切面，选适合本品的一种。','固定近景，对焦切面或表层，不连续变焦。','结构层次可辨认，展示状态与实际售卖一致，不添加假馅料。'],
      process:['记录真实起锅或装盒','经允许拍员工起锅、拌料、装盒等实际制作／出品动作，前后各多留一秒。','固定在操作台侧面，避开热油与工具，不让手一直遮住。','看清员工如何完成这份小吃，顾客拿起食物不算制作。'],
      package:['盒数、串数和口味要看清','把「{dish}」按实际盒数、串数和口味分组摆齐，酱料只放实际包含的。','俯拍或斜上方固定拍，盒边／串签不要重叠遮挡。','不同项与数量可区分，不把不同订单拼成一个套餐。'],
      space:['看清档口和真实取餐区','拍「{shop}」的档口、柜台及取餐位置；只有外带时就展示实际外带场景。','从顾客正常站立的位置固定拍，保留柜台和可识别标志。','档口归属与取餐位置明确，不借邻摊环境冒充自己的。'],
      service:['装盒完成，怎样取走','拍一份实际小吃装盒并交到取餐台；不拍顾客拿走后的吃播充当制作。','固定对准餐盒和柜台，避免人脸。','成品与包装、交付方式对应，不用包装暗示并不存在的赠品。']}
  };

  function buildShootingGuide(brief){
    const profile=foodProfiles[brief.category];
    if(!profile||!goals.some(g=>g.id===brief.intent))throw Error('请选择有效的饭店类型和宣传目标。');
    const finished=brief.intent==='signature'&&brief.capture_mode==='finished';
    const values={dish:brief.product,shop:brief.shop,main:brief.intent==='offer'?`「${brief.product}」里的主菜`:`「${brief.product}」`};
    const text=value=>String(value).replace(/\{(dish|shop|main)\}/g,(_,key)=>values[key]);
    const shot=(key,role,required,purpose)=>{
      const row=profile[key];
      const alternatives={hero:'换到光线更稳定的桌面重拍，先保证完整认得出产品，再追求装饰和运镜。',detail:'不适合夹起／切开时，换一个能看清实际质地的固定角度，不强造拉丝、爆汁。',process:'无法进入后厨时，切换上方“不拍后厨”路线；不能把吃播、夹菜或成品静物标为制作。',package:'桌面摆不下可分两条补齐组成；每项都要对应同一真实套餐，不能省略或额外加菜。',space:'没有堂食就改拍真实档口／取餐场景；不借用其他门店或虚构包间。',service:'拍摄不方便就跳过这条选拍，改用已拍的实际用餐／取餐场景。'};
      return {id:`${brief.category}.${brief.intent}.${key}`,title:row[0],role,required,purpose,copy:text(row[1]),camera:row[2],check:row[3],alternative:alternatives[key],avoid:profile.avoid,duration:key==='process'?'原片约 8 秒，动作完整':'原片建议 6–8 秒',edit:'剪辑参考 2–4 秒'};
    };
    const location={id:`${brief.category}.${brief.intent}.location`,title:brief.category==='snack'?'摊号、入口和邻近标志':'招牌、入口和一个找店参照',role:'门头',required:brief.intent!=='signature'||finished,purpose:'让感兴趣的顾客能辨认这家店。',copy:brief.category==='snack'?`拍清「${brief.shop}」实际摊号／招牌与取餐入口；没有固定门头时，保留自己的可识别标志。`:`站在店外固定拍「${brief.shop}」的招牌和入口；位置难找时另补一个真实路口／楼层参照。`,camera:'先固定机位拍清，再决定是否补缓慢移动；不强制超广角或航拍。',check:'文字、入口与参照物清楚，地址由商家另行确认；不把邻店招牌当自己的。',alternative:'拍不到完整门头可分拍真实招牌与入口，并填写来源明确的地址；不拼接别家门店。',avoid:'街景只能帮助辨认，不能自动证明营业时间、免费停车或具体距离。',duration:'原片建议 6–8 秒',edit:'剪辑参考 2–4 秒'};
    const portion={id:`${brief.category}.${brief.intent}.portion`,title:`看清实际${profile.unit}与份装`,role:'商品',required:false,purpose:'补足全景里看不清的数量和份装信息。',copy:`用实际售卖餐具展示「${brief.product}」的${profile.unit}，必要时分组补一条；不额外加量。`,camera:'保留餐具边界，角度不要刻意拉大前景；不强制出镜人脸。',check:'实际份装／数量可辨认，并与商家确认信息相符；画面不证明“吃到撑”。',alternative:'完整套餐画面已经看清数量时可跳过；仍模糊时重摆、分组补拍，不猜数量。',avoid:profile.avoid,duration:'原片建议 6–8 秒',edit:'剪辑参考 2–3 秒'};
    let tasks,order;
    if(brief.intent==='offer'){
      tasks=[shot('package','商品',true,'先讲清这个套餐包含什么。'),shot('hero','商品',true,'用主菜吸引注意，同时保持与套餐对应。'),shot('detail','商品',true,'补充主菜在全景里看不到的真实细节。'),portion,location];
      order='套餐全貌 → 主菜与质感 → 组成／份量 → 完整优惠信息 → 门店位置';
    }else if(brief.intent==='restaurant'){
      tasks=[shot('hero','商品',true,'先用一道实际菜品说明这家店卖什么。'),shot('space','环境',true,'让顾客判断这里怎样用餐或取餐。'),shot('service','环境',false,'补充交付方式，避免只有空房间。'),location,shot('detail','商品',false,'用另一种景别收回到菜品，避免重复扫环境。')];
      order='菜品／用餐场景引入 → 实际空间与服务 → 门店识别和位置';
    }else if(finished){
      tasks=[shot('hero','商品',true,'先认出主推菜品。'),shot('detail','商品',true,'用成品的真实质感替代无法拍到的后厨信息。'),portion,shot('space','环境',true,'提供实际用餐／取餐场景。'),location];
      order='成品全貌 → 质感细节 → 用餐／取餐场景 → 门店识别和位置';
    }else{
      tasks=[shot('hero','商品',true,'开头先让顾客认出想尝的主角。'),shot('process','制作',true,'展示有权限拍摄的实际制作变化。'),shot('detail','商品',true,'用不同景别补足食物细节。'),shot('space','环境',true,'补充这道菜所在的用餐／取餐场景。'),location];
      order='成品吸引 → 制作变化 → 质感细节 → 用餐场景（门店识别选拍）';
    }
    const backendGoal=finished?'visit':goals.find(g=>g.id===brief.intent).goal;
    const facts=brief.intent==='offer'?['店名、套餐实际名称','套餐每项组成与实际数量','现价、完整使用条件与有效期','来源明确的门店地址']:backendGoal==='visit'?['店名与实际展示的菜品','来源明确的门店地址','营业／服务／菜品特点仅核实后填写']:['店名与具体菜名','菜品特点仅核实后填写，不凭画面猜口味'];
    const sourceIds=['DY-OFFICIAL','B-TECH',profile.source,'DY-MOVE'];
    if(brief.intent==='offer')sourceIds.push('DY-STRUCTURE');
    return {version:guideVersion,recipeId:`${brief.category}.${brief.intent}${finished?'.finished':''}`,signal:profile.signal,backendGoal,tasks,order,facts,sourceIds,
      setup:['竖屏 9:16，普通 SDR；1080p 可作起点，当前本地版不接受 HDR／杜比视界。','先擦镜头、清理无关杂物，选稳定光线；先固定机位，动作前后各留约一秒。','原片建议 6–8 秒；当前单个剪辑片段最多 8 秒。长过程拆成若干独立动作拍，不加速员工操作，也不靠倒放伪造变化。','只拍本次门店与同一真实菜品／套餐，展示状态和售卖一致；不拼其他店、其他订单的画面。'],
      modeNote:finished?'成品路线使用“到店”结构，需要门头／入口、实际环境和地址；没有制作镜头也不会把吃播冒充制作。':'必拍用于准备当前工作台所需用途；选拍只补充信息。拍完仍需逐段查看、核实并确认。'};
  }
  window.restaurantGuideLibrary={version:guideVersion,build:buildShootingGuide};

  function renderGuide() {
    const brief=selectedBrief(),guide=buildShootingGuide(brief),tasks=guide.tasks;
    byId('guideCategory').textContent=`饭店 / ${brief.category_name} / ${brief.intent_name} · 试拍版`;
    byId('guideTitle').textContent=brief.intent==='restaurant'?`让顾客认识「${brief.shop}」`:`这次，拍好「${brief.product}」`;
    const required=tasks.filter(task=>task.required).length;
    byId('guideSubtitle').textContent=`${brief.shop} · ${required} 项必拍 + ${tasks.length-required} 项选拍 · 重点：${guide.signal}`;
    byId('guideObject').textContent=brief.intent==='restaurant'?brief.shop:brief.product;
    byId('guideGoal').textContent=brief.intent_name;
    byId('captureModeWrap').hidden=brief.intent!=='signature';
    byId('captureMode').value=state.captureMode;
    byId('guideCaptureNote').textContent=guide.modeNote;
    byId('guideSetup').innerHTML=guide.setup.map(line=>`<li>${escape(line)}</li>`).join('');
    byId('guideOrder').textContent=guide.order;
    byId('guideChecklist').innerHTML=tasks.map((task,index)=>`<article class="shoot-task" data-shot-key="${escape(task.id)}" data-required="${task.required}"><div class="shoot-task-index">${String(index+1).padStart(2,'0')}</div><div class="shoot-task-body"><div class="shoot-task-top"><span>${escape(task.role)}镜头 · ${task.required?'必拍':'选拍'}</span><span>${escape(task.duration)}</span></div><h2>${escape(task.title)}</h2><p class="shoot-purpose">为什么拍：${escape(task.purpose)}</p><p>${escape(task.copy)}</p><p class="shoot-camera">机位：${escape(task.camera)}</p><div class="shoot-check"><span>自查</span><span>${escape(task.check)}</span></div><details class="shoot-more"><summary>拍不到／没拍好怎么办</summary><p>替代：${escape(task.alternative)}</p><p>避坑：${escape(task.avoid)}</p><p>${escape(task.edit)}，只是剪辑参考，不是原素材合格判定。</p></details></div></article>`).join('');
    byId('guideFactsList').innerHTML=guide.facts.map(line=>`<li>${escape(line)}</li>`).join('');
    byId('guideFactsNote').textContent='这些是拍摄与剪辑建议，实际方案需进入工作台复核。自查要点不代表系统已检测通过，也没有证明宣传效果最优。';
    byId('guideSources').innerHTML=guide.sourceIds.map(id=>{const source=guideSources[id];return `<li><a href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.title)} ↗</a><small>${escape(source.scope)}</small></li>`;}).join('');
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
      if (state.intent !== button.dataset.restaurantIntent) { state.subject = ''; state.captureMode='process'; }
      state.intent = button.dataset.restaurantIntent;
      byId('briefSubject').value = state.subject;
      updateSelection();
    };
  });
  byId('briefShop').value = state.shop;
  byId('briefSubject').value = state.subject;
  byId('briefShop').oninput = event => { state.shop = event.target.value; updateSelection(); };
  byId('briefSubject').oninput = event => { state.subject = event.target.value; updateSelection(); };
  byId('captureMode').onchange=event=>{state.captureMode=event.target.value==='finished'?'finished':'process';persist();renderGuide();};
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
