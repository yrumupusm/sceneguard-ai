const test = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../webapp/terminology.js');
const cases = [
  ['자동 확인','침입 검출'], ['자동확인','침입 검출'],
  ['침입 확인 · 자동','침입 검출'], ['침입 확인(자동)','침입 검출'],
  ['침입 자동 확인','침입 검출'], ['침입 확인','침입 검출'],
  ['자동 침입 확인','침입 검출'], ['자동침입확인','침입 검출'],
  ['자동 확인으로 전환','침입 검출로 전환'],
  ['침입 확인(자동)으로 전환','침입 검출로 전환'],
  ['침입 확인 · 자동으로 전환','침입 검출로 전환'],
  ['침입 검출으로 전환','침입 검출로 전환'],
  ['침입 의심 / 의심 해제','침입 의심 / 의심 해제'],
  ['automatic_confirmation / confirmation','automatic_confirmation / confirmation']
];
for (const [before, after] of cases) test(before, () => assert.equal(ui.text(before),after));
test('normalization is idempotent for all display variants', () => {
  for (const [before, after] of cases) {
    assert.equal(ui.text(ui.text(before)), after);
  }
});
test('non-string values and stored records stay unchanged', () => {
  const record = {automatic_confirmation:true,status:'침입 확인',count:37};
  const snapshot = JSON.stringify(record);
  assert.equal(ui.text(record),record);
  assert.equal(ui.text(null),null);
  assert.equal(ui.text(37),37);
  assert.equal(ui.text(record.status),'침입 검출');
  assert.equal(JSON.stringify(record),snapshot);
});
function element(tag, children=[]) {
  const node = {nodeType:1,tagName:tag,childNodes:children,attrs:{},
    getAttribute(key){ return this.attrs[key] ?? null; },
    setAttribute(key,value){ this.attrs[key]=value; }};
  for (const child of children) child.parentNode = node;
  return node;
}
function txt(value){ return {nodeType:3,nodeValue:value}; }
test('text and accessibility labels update without rebuilding video nodes', () => {
  const title=txt('자동 확인 24→37건');
  const video=element('VIDEO');video.currentTime=12.5;
  const body=element('BODY',[element('P',[title]),video]);
  body.attrs['aria-label']='침입 확인 · 자동';
  ui.visit(body);ui.visit(body);
  assert.equal(title.nodeValue,'침입 검출 24→37건');
  assert.equal(body.attrs['aria-label'],'침입 검출');
  assert.equal(body.childNodes[1],video);
  assert.equal(video.currentTime,12.5);
});
test('review inputs, code and editable text are not rewritten', () => {
  for (const tag of ['TEXTAREA','INPUT','CODE','PRE','SCRIPT','STYLE']) {
    const value=txt('자동 확인');const parent=element(tag,[value]);
    ui.visit(parent);ui.visit(value);
    assert.equal(value.nodeValue,'자동 확인');
  }
  const value=txt('자동 확인');const editable=element('DIV',[value]);
  editable.isContentEditable=true;ui.visit(editable);
  assert.equal(value.nodeValue,'자동 확인');
});
