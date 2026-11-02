'use strict';
const assert = require('node:assert/strict'), vm = require('node:vm'), fs = require('node:fs');
class Element {
  constructor(tag) { this.tagName=tag.toUpperCase(); this.dataset={}; this.children=[]; this.listeners={}; this.isConnected=true; this.currentTime=0; this.textContent=''; }
  append(...items) { for (const item of items) item.parent=this; this.children.push(...items); }
  remove() { if (this.parent) this.parent.children=this.parent.children.filter(x=>x!==this); }
  addEventListener(name,fn) { this.listeners[name]=fn; }
  fire(name) { this.listeners[name]?.(); }
}
const storage=new Map(); let requests=0;
const ctx=vm.createContext({console,localStorage:{getItem:k=>storage.get(k) ?? null,setItem:(k,v)=>storage.set(k,v)},fetch:()=>{requests++; throw Error('no comparison claim');}});
vm.runInContext(fs.readFileSync(require.resolve('../webapp/app.js'),'utf8'),ctx);
ctx.document={createElement:tag=>new Element(tag)};
const cid='incident-aaaaaaaaaaaaaaaaaaaaaaaa';
const base={incident_id:cid,gate_id:'G',status:'침입 의심',first_alert_pts:1,first_confirmation_pts:null,unresolved_event_ids:['a'],released_event_ids:[],confirmed_event_ids:[],automatic_status:'침입 의심'};
const confirmed={...base,first_confirmation_pts:3,unresolved_event_ids:[],confirmed_event_ids:['a'],automatic_status:'침입 확인'};
ctx.fixture={contract:'incident_lifecycle_v1',source_window:[0,5],media_artifact_id:'v',timeline:[{incident_id:cid,decision_time_pts:1,card:base},{incident_id:cid,decision_time_pts:3,card:confirmed}],notification_intents:[{incident_id:cid,decision_time_pts:1,kind:'suspicion',notification_key:'s'},{incident_id:cid,decision_time_pts:3,kind:'confirmation',notification_key:'c'}]};
ctx.holder=new Element('div'); vm.runInContext("renderIncidentFlow(holder,'x',fixture)",ctx);
const video=ctx.holder.children[2], cards=ctx.holder.children[4];
video.currentTime=2; video.fire('seeked'); assert.match(cards.children[0].children[1].textContent,/첫 자동 확인 없음/); assert.doesNotMatch(cards.children[0].children[2].textContent,/확인 의도/);
video.currentTime=3; video.fire('timeupdate'); assert.match(cards.children[0].children[1].textContent,/첫 자동 확인 3\.000초 · 확인 알림 의도 3\.000초/); assert.match(cards.children[0].children[2].textContent,/확인 의도 3\.000초/);
ctx.document.querySelector=()=>({querySelector:()=>video});
vm.runInContext("selectedReport='EXP-0047'; selectedSlot='slot3'; loadedFingerprint='old'; catalogData={experiments:[{experiment_id:'EXP-0047',slot:'slot3'}]}; refreshSelectedIfChanged()",ctx);
assert.equal(vm.runInContext('pendingRefresh',ctx),true); assert.equal(video.currentTime,3);
ctx.reload=new Element('div'); vm.runInContext("renderIncidentFlow(reload,'x',fixture)",ctx);
assert.equal(ctx.reload.children[2].currentTime,3); assert.match(ctx.reload.children[4].children[0].children[2].textContent,/확인 의도/);
video.currentTime=0; video.fire('seeking'); assert.equal(cards.children.length,0);
video.currentTime=2; video.fire('seeked'); assert.doesNotMatch(cards.children[0].children[2].textContent,/확인 의도/);
video.currentTime=3; video.fire('timeupdate'); assert.equal((cards.children[0].children[2].textContent.match(/확인 의도/g)||[]).length,1); assert.equal(requests,0);
const cid2='incident-bbbbbbbbbbbbbbbbbbbbbbbb';
ctx.two={...ctx.fixture,timeline:[...ctx.fixture.timeline,{incident_id:cid2,decision_time_pts:3,card:{...confirmed,incident_id:cid2}}],notification_intents:[...ctx.fixture.notification_intents,{incident_id:cid2,decision_time_pts:3,kind:'confirmation',notification_key:'second'}]};
ctx.pair=new Element('div'); vm.runInContext("renderIncidentFlow(pair,'pair',two)",ctx);
ctx.pair.children[2].currentTime=3;ctx.pair.children[2].fire('seeked');
assert.equal(ctx.pair.children[4].children.length,2);
assert.doesNotMatch(ctx.pair.children[4].children[0].children[2].textContent,/ · c/);
assert.doesNotMatch(ctx.pair.children[4].children[1].children[2].textContent,/second/);
assert.equal(requests,0);
console.log('EXP47 causal playback, rewind, polling, reload and isolated intents passed');
