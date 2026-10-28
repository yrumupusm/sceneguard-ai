'use strict';
const assert = require('node:assert/strict');
const {nativeObservation, resultFor, slotItems, observationText} = require('../webapp/app.js');
const now = Date.now();
const assignment = {experiment_id: 'TEST-1', slot: 'slot1', run_id: 'r', task_id: 't', dispatch_id: 'd', synthetic: true};
const worker = {task_id: 't', dispatch_id: 'd', stage: {state: 'done'}, liveness: {state: 'exited'}, outcome: 'succeeded'};
const status = {state: 'connected', connected: true, stale: false, observed_at: new Date(now).toISOString(), stale_after_seconds: 45, run_id: 'r', workers: [worker]};
assert.equal(nativeObservation(assignment, status, now), worker);
for (const bad of [{state:'stale'}, {connected:false}, {stale:true}, {run_id:'other'}, {workers:[]}, {workers:[{...worker, dispatch_id:'other'}]}, {workers:[worker, worker]}, {observed_at:new Date(now - 46000).toISOString()}]) {
  assert.equal(nativeObservation(assignment, {...status, ...bad}, now), null);
}
assert.equal(nativeObservation({...assignment, task_id:null}, status, now), null);
const data = {assignments:[assignment], experiments:[{experiment_id:'TEST-1', slot:'slot1'}, {experiment_id:'EXP-0007', slot:'unassigned'}]};
assert.equal(slotItems({experiments:[]}, 'slot1').length, 0);
assert.equal(slotItems({...data, experiments:[]}, 'slot1')[0].result, null);
assert.equal(slotItems(data, 'slot1')[0].result.experiment_id, 'TEST-1');
assert.equal(resultFor(data, 'slot2', 'TEST-1'), null);
assert.equal(slotItems(data, 'unassigned')[0].id, 'EXP-0007');
assert.equal(observationText(null), '미확인');
assert.equal(observationText(worker), '작업자 완료');
assert.equal(observationText({...worker, outcome:'failed'}), '작업자 실패');
assert.equal(observationText({outcome:'in_progress', stage:{activity:'working'}, liveness:{verdict:'live'}}), '진행 중');
assert.equal(observationText({outcome:'in_progress', stage:{activity:'working'}, liveness:{verdict:'unverifiable'}}), '생존 상태 미확인');
console.log('card state fixture assertions passed');
