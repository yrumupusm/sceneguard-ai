'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(tag) { this.tagName=tag.toUpperCase(); this.children=[]; this.dataset={}; this.listeners={}; this.currentTime=0; this.textContent=''; this.isConnected=true; }
  append(...items) { for (const item of items) { if (item.parent) item.remove(); item.parent=this; } this.children.push(...items); }
  remove() { if (this.parent) this.parent.children=this.parent.children.filter(e=>e!==this); }
  addEventListener(name,fn) { this.listeners[name]=fn; }
  fire(name) { this.listeners[name]?.(); }
  focus() {}
  pause() { this.paused=true; }
}
const ctx=vm.createContext({document:{createElement:tag=>new Element(tag)},console});
vm.runInContext(fs.readFileSync(require.resolve('../webapp/app.js'),'utf8').replace(/if \(typeof document !== 'undefined'\) \{[\s\S]*$/, ''),ctx);
const base={incident_id:'activity-1',first_alert_pts:11,first_confirmation_pts:null,automatic_status:'침입 의심',observation_status:'open',observation_closed_pts:null,last_gate_observation_pts:11,unresolved_event_ids:['x'],released_event_ids:[],confirmed_event_ids:[]};
const confirmed={...base,automatic_status:'침입 확인',first_confirmation_pts:12,confirmed_event_ids:['x'],unresolved_event_ids:[]};
const closed={...confirmed,observation_status:'closed',observation_closed_pts:15};
ctx.data={experiment:'MVP-0002',contract:'gate_activity_episodes_v1',source_window:[10,20],media_start_pts:10,media_artifact_id:'vid',source_label:'source',view_label:'분석',provenance_label:'저장 검출 기반 분석',timeline:[{incident_id:base.incident_id,decision_time_pts:11,card:base},{incident_id:base.incident_id,decision_time_pts:12,card:confirmed},{incident_id:base.incident_id,decision_time_pts:15,card:closed}],notification_intents:[]};
ctx.holder=new Element('div'); vm.runInContext("renderLifecycleFlow(holder,'mvp',data)",ctx);
const video=ctx.holder.children.find(e=>e.tagName==='VIDEO');
const index=ctx.holder.children.find(e=>e.className==='incident-index');
assert.match(index.children[2].children[0].textContent,/사건1/);
index.children[2].children[2].fire('click'); assert.equal(video.currentTime,2); assert.equal(video.paused,true);
const cards=ctx.holder.children.find(e=>e.dataset.activityActive); const history=ctx.holder.children.find(e=>e.dataset.activityHistory);
video.currentTime=1.1; video.fire('seeked'); assert.match(cards.children[0].children[0].textContent,/침입 의심/);
video.currentTime=2.1; video.fire('seeked'); assert.match(cards.children[0].children[0].textContent,/침입 확인 · 자동/);
const active=cards.children[0];
video.currentTime=5.1; video.fire('seeked'); assert.equal(history.children[0],active); assert.match(active.children[1].textContent,/관찰 종료 15\.000초/);
video.currentTime=0; video.fire('seeked'); assert.equal(history.children.length,0);
ctx.empty=new Element('div'); ctx.emptyData={...ctx.data,timeline:[],notification_intents:[]}; vm.runInContext("renderLifecycleFlow(empty,'empty',emptyData)",ctx);
assert.ok(ctx.empty.children.some(e=>e.textContent==='분석 완료 · 사건 없음'));
console.log('MVP timeline, closure, rewind, and empty-result rendering passed');
