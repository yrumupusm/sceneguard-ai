'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element {
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.value='';this.checked=false;this.dataset={};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(){}
  addEventListener(name,fn){this.listeners[name]=fn;}
}
const calls=[]; const ctx=vm.createContext({console});
vm.runInContext(fs.readFileSync('webapp/app.js','utf8'),ctx);
ctx.document={createElement:t=>new Element(t),createTextNode:t=>({textContent:t})};
ctx.fetch=async (url,opts={})=>{calls.push({url,opts});return {ok:true,json:async()=>({review:null,history:[]})};};
ctx.parent=new Element('div'); ctx.data={session_id:'session',bundle_sha256:'sha'};
(async()=>{
  vm.runInContext("addAssessment(parent,'bundle',data)",ctx);
  await new Promise(resolve=>setImmediate(resolve));
  const panel=ctx.parent.children[0], group=panel.children[1];
  assert.equal(group.children[1].children[0].checked,true);
  assert.equal(group.children[3].children[0].checked,false);
  const save=panel.children.find(x=>x.tagName==='BUTTON'); await save.listeners.click();
  let body=JSON.parse(calls.at(-1).opts.body);assert.equal(body.status,'unreviewed');assert.equal(body.time_pts,null);
  ctx.parent=new Element('div'); vm.runInContext("addAssessment(parent,'bundle',data,'incident')",ctx);
  await new Promise(resolve=>setImmediate(resolve));
  const incident=ctx.parent.children[0];
  for(const group of [incident.children[1],incident.children[2]]) assert.equal(group.children[1].children[0].checked,true);
  const incidentSave=incident.children.find(x=>x.tagName==='BUTTON'); await incidentSave.listeners.click();
  body=JSON.parse(calls.at(-1).opts.body);assert.equal(body.event_assessment,'unreviewed');assert.equal(body.bbox_quality,'unreviewed');
  assert.match(calls.at(-1).url,/assessments\/incident$/);
  // A note typed before GET resolves must not reset untouched saved assessments.
  let resolveLoad;
  ctx.fetch=(url,opts={})=>{
    calls.push({url,opts});
    if(opts.method==='POST') return Promise.resolve({ok:true,json:async()=>({review:null,history:[]})});
    return new Promise(resolve=>{resolveLoad=resolve;});
  };
  ctx.parent=new Element('div'); vm.runInContext("addAssessment(parent,'bundle',data,'incident')",ctx);
  const pending=ctx.parent.children[0], draft=pending.children.flatMap(x=>x.tagName==='LABEL'?x.children:[x]).find(x=>x.tagName==='TEXTAREA');
  draft.value='new note'; pending.listeners.input({target:draft});
  resolveLoad({ok:true,json:async()=>({review:{version:4,event_assessment:'correct_event',bbox_quality:'good',reviewer:'existing',note:'old note'},history:[]})});
  await new Promise(resolve=>setImmediate(resolve));
  await pending.children.find(x=>x.tagName==='BUTTON').listeners.click();
  body=JSON.parse(calls.at(-1).opts.body);
  assert.equal(body.note,'new note'); assert.equal(body.reviewer,'existing'); assert.equal(body.expected_version,4);
  assert.equal(body.event_assessment,'correct_event'); assert.equal(body.bbox_quality,'good');
  ctx.fetch=async()=>({ok:true,json:async()=>({items:[{kind:'suspicion',decision_time_pts:12,frame:{pts:11.8},available:true,boxes:[{bbox:[0,0,1,1]}],image_url:'/evidence.jpg'},{kind:'confirmation',decision_time_pts:null,available:false,reason:'no_automatic_confirmation'},{kind:'suspicion',decision_time_pts:12,available:true,boxes:[],image_url:'/plain.jpg'}]})});
  ctx.parent=new Element('div'); vm.runInContext("addBoxEvidence(parent,'bundle',data,'incident')",ctx);
  await new Promise(resolve=>setImmediate(resolve));
  const evidence=ctx.parent.children[0].children[0];
  assert.match(evidence.children[0].textContent,/12\.000초/); assert.match(evidence.children[1].textContent,/11\.800초/); assert.equal(evidence.children[2].src,'/evidence.jpg'); assert.match(ctx.parent.children[0].children[1].children[1].textContent,/자동 확인이 없습니다/);
  const plain=ctx.parent.children[0].children[2]; assert.match(plain.children[1].textContent,/저장된 사건 박스가 없습니다/); plain.children[2].listeners.error(); assert.match(plain.children[3].textContent,/불러오지 못했습니다/);
  console.log('separate assessments default to unreviewed, persist, and show evidence frame time passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
