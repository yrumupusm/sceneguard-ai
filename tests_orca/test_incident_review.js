'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(tag) { this.tagName=tag.toUpperCase(); this.dataset={}; this.children=[]; this.listeners={}; this.value=''; this.textContent=''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=children; }
  setAttribute() {}
  addEventListener(type, fn) { this.listeners[type]=fn; }
  dispatchEvent(event) { this.lastEvent=event; }
}
const ctx=vm.createContext({console, CustomEvent:class {constructor(type, options){this.type=type;this.detail=options.detail;}}});
vm.runInContext(fs.readFileSync(require.resolve('../webapp/app.js'),'utf8'),ctx);
ctx.document={createElement:tag=>new Element(tag)};
let posts=0;
const saved={version:1,status:'침입 의심',reviewer:'first',note:'old',updated_utc:'2026-10-30T00:00:00+00:00'};
ctx.fetch=async (url, opts) => opts.method === 'POST'
  ? (++posts === 1 ? {ok:false,status:409,json:async()=>({review:saved,history:[saved]})}
    : {ok:true,status:200,json:async()=>({review:{...saved,version:2},history:[saved,{...saved,version:2}]})})
  : {ok:true,json:async()=>({review:null,history:[]})};
ctx.block=new Element('div');
vm.runInContext("addReview(block, 'fixture', 'incident-aaaaaaaaaaaaaaaaaaaaaaaa', 'sha', 'session')",ctx);
const panel=ctx.block.children[0];
const [,status,reviewer,note,save,message,current,,history]=panel.children;
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  status.value='침입 확인'; reviewer.value='second'; note.value='<img> draft';
  await save.listeners.click();
  assert.match(message.textContent,/최신 상태/); assert.equal(note.value,'<img> draft'); assert.equal(reviewer.value,'second');
  assert.match(current.textContent,/버전 1/); assert.equal(history.children[0].textContent.includes('old'),true);
  await save.listeners.click();
  assert.match(message.textContent,/저장되었습니다/); assert.equal(panel.lastEvent.type,'incident-review-saved'); assert.equal(panel.lastEvent.detail.version,2);
  let finishGet;
  ctx.fetch=()=>new Promise(resolve=>{finishGet=resolve;});
  ctx.block=new Element('div');
  vm.runInContext("addReview(block, 'fixture', 'incident-bbbbbbbbbbbbbbbbbbbbbbbb', 'sha', 'session')",ctx);
  const [,pendingStatus,pendingReviewer,pendingNote,pendingSave]=ctx.block.children[0].children;
  assert.equal(pendingSave.disabled,true);
  pendingNote.value='pending draft'; pendingNote.listeners.input();
  finishGet({ok:true,json:async()=>({review:saved,history:[saved]})});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(pendingNote.value,'pending draft'); assert.equal(pendingReviewer.value,'first');
  assert.equal(pendingStatus.value,'침입 의심'); assert.equal(pendingSave.disabled,false);
  ctx.fetch=async (url, opts)=>opts.method === 'POST'
    ? {ok:false,status:409,json:async()=>({detail:'bundle changed; reload the card'})}
    : {ok:true,json:async()=>({review:null,history:[]})};
  ctx.block=new Element('div');
  vm.runInContext("addReview(block, 'fixture', 'incident-cccccccccccccccccccccccc', 'sha', 'session')",ctx);
  const [,,,staleNote,staleSave,staleMessage]=ctx.block.children[0].children;
  await new Promise(resolve=>setImmediate(resolve));
  staleNote.value='keep this'; await staleSave.listeners.click();
  assert.equal(staleNote.value,'keep this'); assert.match(staleMessage.textContent,/새로고침/);
  console.log('review conflict preserves draft, history and save event fixtures passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
