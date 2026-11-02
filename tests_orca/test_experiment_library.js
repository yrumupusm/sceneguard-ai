'use strict';
const assert = require('node:assert/strict');
const {catalogItems, filteredItems, isInputSheet, evidencePriority, reviewWarning} = require('../webapp/app.js');
const data = {experiments:[
  {experiment_id:'EXP-0001', slot:'unassigned', title:'기준선', created_at:'2026-01-01'},
  {experiment_id:'EXP-0002', slot:'slot1', title:'비교 결과', created_at:'2026-01-02'}
], assignments:[
  {experiment_id:'EXP-0002', slot:'slot1', title:'비교 배정', assigned_at:'2026-01-02'},
  {experiment_id:'EXP-0003', slot:'slot2', title:'대기 중', assigned_at:'2026-01-03'}
]};
assert.deepEqual(catalogItems(data).map(x=>x.id), ['EXP-0003','EXP-0002','EXP-0001']);
assert.equal(catalogItems(data)[1].assignment.title, '비교 배정');
assert.deepEqual(filteredItems(data,'비교','registered').map(x=>x.id), ['EXP-0002']);
assert.deepEqual(filteredItems(data,'exp-0003','pending').map(x=>x.id), ['EXP-0003']);
assert.equal(filteredItems(data,'비교','pending').length, 0);
assert.equal(isInputSheet({kind:'image',label:'실제 모델 입력 검수 시트'}), true);
assert.equal(isInputSheet({kind:'image',label:'실제 processor 입력 10프레임 표시'}), true);
assert.equal(isInputSheet({kind:'image',label:'원본 / 전체 / 고정 ROI 비교'}), false);
assert.equal(isInputSheet({kind:'video',label:'입력 시트 비교'}), false);
assert.ok(evidencePriority({label:'누락 사례'}) < evidencePriority({label:'일반 근거'}));
assert.match(reviewWarning('stale'), /현재 원문·측정치와 다릅니다/);
assert.match(reviewWarning('unverified'), /확인할 수 없습니다/);
assert.equal(reviewWarning('current'), '');
console.log('experiment library sorting, filtering and evidence classification passed');

// A matching catalog import does not make an independently bound review current.
const vm = require('node:vm'), fs = require('node:fs');
class Element {
  constructor(tag) { this.tagName = tag; this.dataset = {}; this.children = []; this.textContent = ''; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute() {}
}
const detail = new Element('article');
const ctx = vm.createContext({console, fetch:async()=>({ok:true, json:async()=>({
  experiment_id:'EXP-TEST', title:'Fixture', summary:'Summary',
  source_integrity:{report_match:true, metrics_match:true}, review_integrity:'stale', metrics:[], evidence:[]
})})});
vm.runInContext(fs.readFileSync('webapp/app.js','utf8'),ctx);
ctx.document = {querySelector:()=>detail, querySelectorAll:()=>[], createElement:tag=>new Element(tag)};
vm.runInContext("catalogData={experiments:[{experiment_id:'EXP-TEST',slot:'unassigned'}],assignments:[]}",ctx);
vm.runInContext("selectReport('EXP-TEST')",ctx).then(()=>{
  assert.ok(detail.children.some(x => /이전 검토가 현재 원문·측정치와 다릅니다/.test(x.textContent)));
  assert.ok(!detail.children.some(x => /등록 당시와 다릅니다/.test(x.textContent)));
  console.log('stale review warning shown independently of matching catalog hashes');
}).catch(e=>{console.error(e); process.exitCode=1;});
