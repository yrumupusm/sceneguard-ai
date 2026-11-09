'use strict';
const $=id=>document.getElementById(id);
let data, frames=[], index=0, revision, boxes=[], dirty=false, timer=null, drawing=null, image=new Image(), generation=0, saving=false, imageReady=false;
const canvas=$('canvas'), ctx=canvas.getContext('2d');
const copy=x=>JSON.parse(JSON.stringify(x));
function stop(){if(timer)clearInterval(timer);timer=null;$('play').textContent='재생';}
function changed(){stop();dirty=true;$('status').value='draft';$('confirmed').checked=false;$('empty').checked=false;$('message').textContent='수정 내용을 저장해 주세요.';}
function frame(){return frames[index];}
function controls(){for(const e of document.querySelectorAll('button,input,select,textarea'))e.disabled=saving||!imageReady||e.dataset.adopted==='true';for(const id of ['prev','next','reload'])$(id).disabled=saving;for(const b of $('cases').children)b.disabled=saving;}
function visibleCandidates(){return frame().candidates.filter(c=>(c.kind==='original'?$('showOriginal').checked:$('showModel').checked)&& (c.kind==='original'||$('showLow').checked||c.score>=.5));}
function outline(xy,color,text,dash=[]){ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=3;ctx.setLineDash(dash);ctx.strokeRect(xy[0],xy[1],xy[2]-xy[0],xy[3]-xy[1]);ctx.font='22px sans-serif';ctx.fillText(text,xy[0]+2,Math.max(23,xy[1]-4));ctx.setLineDash([]);}
function draw(){if(!imageReady||!image.complete||!image.naturalWidth)return;ctx.drawImage(image,0,0);for(const c of visibleCandidates())outline(c.xyxy,c.kind==='original'?'#39ffff':'#ffb347',c.label,[7,5]);for(let i=0;i<boxes.length;i++)outline(boxes[i].xyxy,'#3bff75',`확인 ${i+1}`);if(drawing)outline(drawing,'#fff','추가');}
function row(text){const d=document.createElement('div');d.className='row';const s=document.createElement('span');s.textContent=text;d.append(s);return d;}
function button(text,action){const b=document.createElement('button');b.textContent=text;b.onclick=action;return b;}
function lists(){
 $('candidates').replaceChildren();for(const c of visibleCandidates()){
  const d=row(c.label+(c.score==null?'':` · 점수 ${c.score.toFixed(3)}`));
  const b=button(boxes.some(x=>x.source_id===c.id)?'채택됨':'이 박스 채택',()=>{changed();boxes.push({id:crypto.randomUUID(),source_id:c.id,xyxy:copy(c.xyxy)});lists();draw();});
  b.disabled=boxes.some(x=>x.source_id===c.id);b.dataset.adopted=String(b.disabled);d.append(b);$('candidates').append(d);
 }
 $('selected').replaceChildren();boxes.forEach((box,i)=>{
  const d=row(`${i+1}번`);box.xyxy.forEach((v,k)=>{const n=document.createElement('input');n.type='number';n.step='0.1';n.value=v.toFixed(1);n.setAttribute('aria-label',`${i+1}번 ${['왼쪽','위','오른쪽','아래'][k]}`);n.onchange=()=>{changed();box.xyxy[k]=Number(n.value);draw();};d.append(n);});
  d.append(button('삭제',()=>{changed();boxes.splice(i,1);lists();draw();}));$('selected').append(d);
 });
}
function progress(){const counts={complete:0,incomplete:0,uncertain:0,draft:0,pending:0};for(const f of data.frames)counts[(data.revisions[f.frame_id]||{}).status||'pending']++;$('progress').textContent=`총 ${data.frames.length}프레임 · 확인 완료 ${counts.complete} · 누락 남음 ${counts.incomplete} · 판단 어려움 ${counts.uncertain} · 수정 중 ${counts.draft} · 미확인 ${counts.pending}`;}
function openFrame(next,force=false){
 if(saving)return;
 if(!force&&dirty&&!confirm('저장하지 않은 수정 내용을 버리고 이동할까요?'))return;
 index=Math.max(0,Math.min(frames.length-1,next));dirty=false;drawing=null;const f=frame();revision=copy(data.revisions[f.frame_id]);boxes=copy(revision.boxes);
 $('status').value=revision.status==='pending'?'draft':revision.status;$('confirmed').checked=revision.status==='complete'&&revision.confirmed===true;$('empty').checked=revision.empty_confirmed===true;$('note').value=revision.note||'';
 if(revision.reviewer)$('reviewer').value=revision.reviewer;
 $('seek').max=frames.length-1;$('seek').value=index;$('clock').textContent=`${f.source_label||('라벨 '+f.case_number)} · 원본 ${f.source_pts.toFixed(3)}초 · ${index+1}/${frames.length}`;
 $('reviewInstruction').hidden=!f.review_instruction;$('reviewInstruction').textContent=f.review_instruction||'';
 $('contextPanel').hidden=!f.context_media;const context=$('contextVideo');context.pause();
 if(f.context_media){context.src='/context/'+encodeURIComponent(f.context_media);}else{context.removeAttribute('src');}
 $('message').textContent=revision.version?`저장된 수정 ${revision.version}차`:'아직 저장하지 않은 프레임';
 const own=++generation;imageReady=false;ctx.clearRect(0,0,canvas.width,canvas.height);image=new Image();image.onload=()=>{if(own!==generation)return;imageReady=true;canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;controls();lists();draw();};image.onerror=()=>{if(own===generation)$('message').textContent='원본 이미지를 읽지 못했습니다. 이 프레임은 저장할 수 없습니다.';};image.src='/images/'+encodeURIComponent(f.frame_id);lists();controls();progress();
}
function selectCase(n){if(saving)return;if(dirty&&!confirm('저장하지 않은 수정 내용을 버리고 영상을 바꿀까요?'))return;stop();frames=data.frames.filter(f=>f.case_number===n);for(const b of $('cases').children)b.classList.toggle('active',Number(b.dataset.case)===n);openFrame(0,true);}
function point(e){const r=canvas.getBoundingClientRect();return [Math.max(0,Math.min(canvas.width,(e.clientX-r.left)/r.width*canvas.width)),Math.max(0,Math.min(canvas.height,(e.clientY-r.top)/r.height*canvas.height))];}
canvas.onpointerdown=e=>{if(saving||!imageReady||!$('drawMode').checked)return;changed();const p=point(e);drawing=[...p,...p];canvas.setPointerCapture(e.pointerId);};
canvas.onpointermove=e=>{if(!drawing)return;drawing.splice(2,2,...point(e));draw();};
canvas.onpointerup=()=>{if(!drawing)return;const [x,y,u,v]=drawing;drawing=null;if(Math.abs(x-u)>=2&&Math.abs(y-v)>=2)boxes.push({id:crypto.randomUUID(),source_id:null,xyxy:[Math.min(x,u),Math.min(y,v),Math.max(x,u),Math.max(y,v)]});lists();draw();};
canvas.onpointercancel=()=>{drawing=null;draw();};
$('prev').onclick=()=>{stop();openFrame(index-1);};$('next').onclick=()=>{stop();openFrame(index+1);};$('seek').oninput=()=>{stop();const n=Number($('seek').value);$('seek').value=index;openFrame(n);};
$('play').onclick=()=>{if(timer){stop();return;}if(dirty){$('message').textContent='수정 내용을 먼저 저장해 주세요.';return;}timer=setInterval(()=>{if(index===frames.length-1){stop();return;}openFrame(index+1);},1000/3);$('play').textContent='일시정지';};
for(const id of ['showOriginal','showModel','showLow'])$(id).onchange=()=>{lists();draw();};
for(const id of ['status','confirmed','empty','note','reviewer'])$(id).onchange=()=>{stop();dirty=true;};
$('save').onclick=async()=>{if(saving||!imageReady)return;stop();saving=true;controls();const id=frame().frame_id;try{
 const body={expected_version:revision.version,reviewer:$('reviewer').value,status:$('status').value,boxes,note:$('note').value,confirmed:$('confirmed').checked,empty_confirmed:$('empty').checked};
 const r=await fetch('/api/frames/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await r.json();if(!r.ok)throw Error(result.error);
 data.revisions[id]=result;revision=copy(result);dirty=false;$('message').textContent=`저장 완료 · ${result.version}차 수정`;progress();
 }catch(e){$('message').textContent='저장 실패: '+e.message;}finally{saving=false;controls();lists();}};
$('reload').onclick=async()=>{if(saving)return;if(dirty&&!confirm('저장하지 않은 내용을 버리고 다시 읽을까요?'))return;stop();const own=generation;saving=true;controls();try{const r=await fetch('/api/package');const latest=await r.json();if(!r.ok)throw Error(latest.error);if(latest.package_sha256!==data.package_sha256)throw Error('자료가 변경됐습니다. 화면을 새로 열어 주세요.');if(own!==generation)return;data=latest;saving=false;openFrame(index,true);}catch(e){$('message').textContent=e.message;}finally{saving=false;lists();controls();}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
(async()=>{try{const r=await fetch('/api/package');data=await r.json();if(!r.ok)throw Error(data.error);for(const n of [...new Set(data.frames.map(f=>f.case_number))]){const f=data.frames.find(f=>f.case_number===n);const b=button(f.case_label||`라벨 ${n}`,()=>selectCase(n));b.dataset.case=n;$('cases').append(b);}if(data.frames.some(f=>f.evaluation_role==='protected_school_regression_only')){document.querySelector('h1').textContent='학교 영상 · 비교용 사람 박스 검수';document.querySelector('main>p').textContent='학습에 쓰지 않는 학교 비교 자료입니다. 화면에 보이는 사람 모두를 한 사람당 박스 하나로 표시해 주세요. 참고 박스는 정답이 아닙니다. 없는 박스는 직접 그려 주세요. 완전히 가린 몸은 추측하지 말고, 경계가 판단되지 않으면 판단 어려움으로 저장해 주세요. 프레임마다 모든 사람 확인 체크 + 확인 완료 상태를 선택한 뒤 저장합니다.';}selectCase(data.frames[0].case_number);}catch(e){$('message').textContent='자료를 열지 못했습니다: '+e.message;}})();
