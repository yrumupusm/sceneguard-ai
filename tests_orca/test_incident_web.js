'use strict';
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
class Element {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.dataset = {}; this.children = []; this.listeners = {}; this.isConnected = true; this.paused = true; this.seeking = false; this.currentTime = 0; this.textContent = ''; }
  append(...items) { for (const item of items) item.parent = this; this.children.push(...items); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter(x => x !== this); }
  replaceChildren(...items) { this.children = items; }
  setAttribute() {}
  addEventListener(name, fn) { this.listeners[name] = fn; }
  dispatchEvent(event) { this.lastEvent = event; }
  fire(name) { this.listeners[name]?.(); }
  pause() { this.paused = true; }
}
const ctx = vm.createContext({console, setTimeout:()=>0, clearTimeout:()=>{}, CustomEvent:class { constructor(type, init) { this.type=type; this.detail=init.detail; } }});
vm.runInContext(fs.readFileSync(require.resolve('../webapp/app.js'), 'utf8'), ctx);
ctx.document = {createElement:tag => new Element(tag)};
const claims = new Set();
ctx.fetch = async (url, opts) => { const key = JSON.parse(opts.body).notification_key; const claimed = !claims.has(key); claims.add(key); return {ok:true,json:async()=>({claimed})}; };
const key = 'notify:incident-aaaaaaaaaaaaaaaaaaaaaaaa';
const card = {incident_id:'incident-aaaaaaaaaaaaaaaaaaaaaaaa', gate_id:'C3_fence', status:'침입 의심', first_alert_pts:11, last_alert_pts:11, alert_count:1, track_ids:[1], event_ids:['a']};
const updated = {...card, last_alert_pts:12, alert_count:2, track_ids:[1,2], event_ids:['a','b']};
ctx.fixture = {source_window:[10,20],media_artifact_id:'clip',events:[{event_id:'a',decision_time_pts:11,source_ref:{source_pointer:'/events/0',raw_id:1}},{event_id:'b',decision_time_pts:12,source_ref:{source_pointer:'/events/1',raw_id:2}}],timeline:[{decision_time_pts:11,incident_id:card.incident_id,notify:true,notification_key:key,card},{decision_time_pts:12,incident_id:card.incident_id,notify:false,card:updated}]};
ctx.holder = new Element('div');
vm.runInContext("renderIncidentFlow(holder, '007', fixture)",ctx);
const [heading,video,clock,counter,cards,toast] = ctx.holder.children;
async function tick() { await new Promise(resolve => setImmediate(resolve)); }
(async () => {
  video.currentTime = 1.5; video.seeking = true; video.fire('seeking'); video.seeking = false; video.fire('seeked');
  assert.equal(claims.size, 0); assert.match(counter.textContent, /개별 알림 1개/);
  video.currentTime = 0; video.seeking = true; video.fire('seeking'); video.seeking = false; video.fire('seeked');
  assert.match(counter.textContent, /개별 알림 0개/); assert.equal(cards.children.length, 0);
  video.paused = false; video.currentTime = 1.1; video.fire('timeupdate'); await tick();
  assert.equal(claims.size,1); assert.equal(toast.dataset.paintedCount,'1'); assert.equal(toast.lastEvent.type,'incident-toast-painted');
  assert.match(cards.children[0].children[1].textContent, /관련 알림 1개/);
  const cardNode = cards.children[0]; const detailNode = cardNode.children[2]; detailNode.open = true;
  video.currentTime=1.3; video.fire('timeupdate'); assert.equal(cards.children[0], cardNode); assert.equal(detailNode.open, true);
  video.currentTime=2.1; video.fire('timeupdate'); await tick();
  assert.equal(cards.children[0], cardNode); assert.equal(detailNode.open, true);
  assert.equal(toast.dataset.paintedCount,'1'); assert.match(cards.children[0].children[1].textContent, /관련 알림 2개/);
  ctx.document.querySelector = () => ({querySelector:()=>video});
  vm.runInContext("selectedReport='EXP-0036'; selectedSlot='slot3'; loadedFingerprint='old'; catalogData={experiments:[{experiment_id:'EXP-0036',slot:'slot3'}]}; refreshSelectedIfChanged()",ctx);
  assert.equal(cards.children[0], cardNode); assert.equal(detailNode.open, true); assert.equal(vm.runInContext('pendingRefresh',ctx), true);
  cardNode.children[3].fire('click'); assert.equal(video.paused, true); assert.equal(video.currentTime, 0);
  video.seeking=true; video.fire('seeking'); video.seeking=false; video.fire('seeked'); await tick();
  assert.equal(toast.dataset.paintedCount,'1'); video.paused=false;
  video.currentTime=0; video.seeking=true; video.fire('seeking'); video.seeking=false; video.fire('seeked');
  video.currentTime=1.1; video.fire('timeupdate'); await tick();
  assert.equal(toast.dataset.paintedCount,'1'); assert.match(cards.children[0].children[1].textContent, /관련 알림 1개/);
  ctx.document.querySelector = () => ({querySelector:()=>video});
  vm.runInContext("selectedReport='EXP-0036'; selectedSlot='slot3'; loadedFingerprint='old'; catalogData={experiments:[{experiment_id:'EXP-0036',slot:'slot3'}]}; refreshSelectedIfChanged()",ctx);
  assert.equal(cards.children.length, 1);
  assert.equal(vm.runInContext('pendingRefresh',ctx), true); assert.equal(video.currentTime,1.1); assert.equal(video.paused,false);
  ctx.fullHolder = new Element('div');
  ctx.fullFixture = {...ctx.fixture, media_start_pts:0};
  vm.runInContext("renderIncidentFlow(fullHolder, 'full', fullFixture)", ctx);
  const fullVideo = ctx.fullHolder.children[1];
  assert.equal(fullVideo.currentTime, 10);
  const automaticFirst = {...card, automatic_status:'침입 의심', automatic_confirmation:false, first_confirmation_pts:null, decision_source:'automatic_rule', human_verified:false};
  const automaticSecond = {...updated, automatic_status:'침입 확인', automatic_confirmation:true, first_confirmation_pts:12, decision_source:'automatic_rule', human_verified:false};
  ctx.autoHolder = new Element('div');
  ctx.autoFixture = {...ctx.fixture, notification_enabled:false, experiment:'EXP-0044', timeline:[
    {...ctx.fixture.timeline[0],card:automaticFirst}, {...ctx.fixture.timeline[1],card:automaticSecond}]};
  vm.runInContext("renderIncidentFlow(autoHolder, 'exp44', autoFixture)",ctx);
  const autoVideo=ctx.autoHolder.children[1], autoCards=ctx.autoHolder.children[4];
  autoVideo.currentTime=1.5; autoVideo.fire('seeked');
  assert.match(autoCards.children[0].children[0].textContent,/침입 의심 · 자동/);
  assert.doesNotMatch(autoCards.children[0].children[1].textContent,/첫 자동 확인/);
  autoVideo.currentTime=2.1; autoVideo.fire('seeked');
  assert.match(autoCards.children[0].children[0].textContent,/침입 확인 · 자동/);
  assert.match(autoCards.children[0].children[1].textContent,/첫 자동 확인 12\.000초/);
  autoVideo.currentTime=1.5; autoVideo.fire('seeked');
  assert.match(autoCards.children[0].children[0].textContent,/침입 의심 · 자동/);
  assert.doesNotMatch(autoCards.children[0].children[1].textContent,/첫 자동 확인/);
  const birthEvent = {event_id:'b', decision_time_pts:12, source_ref:{collection:'inside_birth_events',source_pointer:'/inside_birth_events/b',raw_id:null,segment:0}, source_event:{birth_pts:11.9,first_actual_bbox:[1,2,3,4],current_actual_bbox:[2,3,4,5]}};
  ctx.birthFixture = {...ctx.autoFixture, experiment:'EXP-0045', contract:'group_all_then_notify_v1', events:[ctx.fixture.events[0],birthEvent], timeline:[{...ctx.autoFixture.timeline[0],card:{...automaticFirst,notification_eligible:true,first_notification_pts:11,review_only_event_ids:[]}}, {...ctx.autoFixture.timeline[1],card:{...automaticSecond,notification_eligible:true,first_notification_pts:11,review_only_event_ids:[]}}]};
  ctx.birthHolder = new Element('div');
  vm.runInContext("renderIncidentFlow(birthHolder, 'exp45', birthFixture)",ctx);
  const birthVideo=ctx.birthHolder.children[1], birthCards=ctx.birthHolder.children[4];
  birthVideo.currentTime=1.5; birthVideo.fire('seeked');
  assert.equal(birthCards.children[0].children[2].children[1].children.length,1);
  birthVideo.currentTime=2.1; birthVideo.fire('seeked');
  assert.match(birthCards.children[0].children[2].children[1].children[1].textContent,/첫 실제 관측 11\.900초/);
  birthVideo.currentTime=1.5; birthVideo.fire('seeked');
  assert.equal(birthCards.children[0].children[2].children[1].children.length,1);
  const portalEvent = {...birthEvent, source_event:{...birthEvent.source_event, birth_site:{geometry_kind:'projected_gate_emergence_v1', portal_center_inside:true, portal_box_overlap:0.75}}};
  ctx.portalFixture = {...ctx.birthFixture, experiment:'EXP-0046', events:[ctx.fixture.events[0],portalEvent]};
  ctx.portalHolder = new Element('div');
  vm.runInContext("renderIncidentFlow(portalHolder, 'exp46', portalFixture)",ctx);
  const portalVideo=ctx.portalHolder.children[1], portalCards=ctx.portalHolder.children[4];
  portalVideo.currentTime=1.5; portalVideo.fire('seeked');
  assert.equal(portalCards.children[0].children[2].children[1].children.length,1);
  portalVideo.currentTime=2.1; portalVideo.fire('seeked');
  const portalText=portalCards.children[0].children[2].children[1].children[1].textContent;
  assert.match(portalText,/첫 실제 관측 11\.900초/);
  assert.match(portalText,/문 구역 새 관측/);
  assert.doesNotMatch(portalText,/portal_center_inside|portal_box_overlap/);
  portalVideo.currentTime=1.5; portalVideo.fire('seeked');
  assert.equal(portalCards.children[0].children[2].children[1].children.length,1);
  fullVideo.currentTime = 11; fullVideo.fire('seeked');
  ctx.fullHolder.children[4].children[0].children[3].fire('click');
  assert.equal(fullVideo.currentTime, 10);
  const registrations = [
    {id:'first',source_label:'007',view_label:'분석',source_window:[48,68],provenance_label:'저장 결과 재생'},
    {id:'second',source_label:'007',view_label:'분석',source_window:[68,105],provenance_label:'캐시 분석'},
    {id:'third',source_label:'030',view_label:'기준',source_window:[84,100],provenance_label:'저장 결과 재생'},
  ];
  const storage = new Map([['review-view:EXP-0037','분석']]);
  ctx.localStorage = {getItem:key=>storage.get(key) ?? null, setItem:(key,value)=>storage.set(key,value)};
  ctx.fetch = async url => ({ok:true,json:async()=>url === '/api/incident-registrations?experiment_id=EXP-0037' ? registrations : {id:url}});
  ctx.finishDetail = new Element('div');
  vm.runInContext("selectionRequest=99; renderIncidentFlow=(holder,id,data)=>{holder.dataset.rendered=id}; addFinishFlows(finishDetail,99)",ctx);
  await tick(); await tick();
  const section=ctx.finishDetail.children[0];
  const source=section.children[1].children[0], view=section.children[2].children[0], selectedHolder=section.children.find(e=>e.className==='incident-flow');
  assert.equal(view.value,'first'); assert.equal(selectedHolder.dataset.rendered,'first');
  assert.match(view.children[1].textContent,/68–105초 · 캐시 분석/);
  view.value='second'; view.fire('change'); await tick();
  assert.equal(selectedHolder.dataset.rendered,'second'); assert.equal(storage.get('review-view:EXP-0037'),'second');
  source.value='030'; source.fire('change'); await tick();
  assert.equal(view.value,'third'); assert.equal(selectedHolder.dataset.rendered,'third');
  console.log('incident playback, seek, silent update, receipt, poll and registration selector fixtures passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
