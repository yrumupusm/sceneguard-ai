'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
class Element {
  constructor(tag){this.tagName=tag;this.children=[];this.textContent='';}
  append(...xs){this.children.push(...xs);}
  setAttribute(){}
}
const ctx=vm.createContext({console});
vm.runInContext(fs.readFileSync('webapp/app.js','utf8'),ctx);
ctx.document={createElement:t=>new Element(t),createElementNS:(_,t)=>new Element(t)};
const walk=e=>[e,...e.children.flatMap(walk)];
const metrics=[{label:'전체',display_label:'전체',value:45,display_unit:'영상',sample_n:45},
  {label:'실행',display_label:'실행',value:2,display_unit:'영상',sample_n:45},
  {label:'오탐',display_label:'오탐',value:0,display_unit:'사건',sample_n:2},
  {label:'정확도',display_label:'정확도',value:null,display_unit:'비율',sample_n:null}];
ctx.metrics=metrics;ctx.groups=[{title:'실행 현황',scope_text:'정확도가 아닌 실행 범위입니다.',metrics}];
ctx.section=new Element('section');ctx.comparisons=[];
vm.runInContext('renderMetrics(section,metrics,groups,comparisons)',ctx);
let nodes=walk(ctx.section);
assert.equal(nodes.filter(e=>e.tagName==='svg').length,0);
assert.equal(nodes.filter(e=>e.tagName==='tbody')[0].children.length,4);
assert.ok(nodes.some(e=>e.tagName==='td'&&e.textContent==='0 사건'));
assert.ok(nodes.some(e=>e.tagName==='td'&&e.textContent==='미측정'));
assert.equal(vm.runInContext('displayNumber(184300)',ctx),'184,300');
assert.equal(vm.runInContext('displayNumber(4.868586524375387)',ctx),'4.869');
assert.equal(vm.runInContext('displayNumber(0.0000001)',ctx),'1.00e-7');
assert.equal(vm.runInContext('metricText({value:1,display_unit:"비율"})',ctx),'1 비율');
ctx.section=new Element('section');
ctx.comparisons=[{title:'같은 조건의 카드',unit:'개',scope:'같은 관측',values:[{label:'이전',value:2},{label:'이후',value:1}]}];
vm.runInContext('renderMetrics(section,metrics,groups,comparisons)',ctx);
assert.equal(walk(ctx.section).filter(e=>e.tagName==='svg').length,1);
assert.equal(metrics[3].value,null);
console.log('metric summaries/tables preserve zero/null/small values; only explicit comparisons draw charts');
