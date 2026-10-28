'use strict';
// Isolated DOM fixture for the real probe: hidden text is not an opened report.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const source = execFileSync('python3', ['-c',
  "import ast,pathlib;t=ast.parse(pathlib.Path('orchestration/verify_delivery.py').read_text());print(next(n.value.value for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='BROWSER_JS' for x in n.targets)))"
], {encoding:'utf8'});
async function probe(opens) {
  const expected = {id:'TEST-visible', slot:'slot1', origin:'http://127.0.0.1:8766', execution:'inconclusive', metrics:[], graphs:0, videos:[], source_hashes:{}, poll_wait_ms:0};
  let ticks=0;
  const disclosure = {open:false, querySelector:()=>({click(){if(opens)disclosure.open=true;}})};
  const report = {textContent:'Synthetic report', closest:()=>disclosure, scrollIntoView(){}, getBoundingClientRect:()=>({height:disclosure.open?20:0})};
  const detail = {dataset:{id:expected.id,result:'registered',executionStatus:expected.execution,sourceHashes:'{}'},
    querySelector(selector){return selector==='table'?{rows:[{}]}:selector==='.original-report'?report:{textContent:'Synthetic review'};}, querySelectorAll:()=>[]};
  const slot = {dataset:{slot:'slot1',id:expected.id},click(){},textContent:'TEST fixture'};
  const document = {querySelector:selector=>selector==='#detail'?detail:{textContent:'TEST'},querySelectorAll:()=>[slot]};
  return vm.runInNewContext(source.replace('EXPECTED',JSON.stringify(expected)), {
    document, location:{origin:expected.origin}, refresh:async()=>{}, Date:{now:()=>{ticks+=1000;return ticks;}}, setTimeout:fn=>{fn();},
  });
}
(async()=>{
  assert.equal(JSON.parse(await probe(true)).report_opened,true);
  await assert.rejects(probe(false), /Report remains hidden/);
  console.log('report disclosure acceptance fixtures passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
