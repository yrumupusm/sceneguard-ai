'use strict';
const $ = selector => document.querySelector(selector);
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = text;
  if (className) element.className = className;
  return element;
};
const show = value => value === null || value === undefined || value === '' ? '미확인' : String(value);
const measured = value => value === null || value === undefined ? '미측정' : String(value);
const displayNumber = value => Number.isInteger(value) ? String(value) : value.toFixed(3);
let catalogData;
let statusData = {};
let selectedSlot = 'unassigned';
let selectedReport = null;
let loadedFingerprint = null;
let pendingRefresh = false;
let selectionRequest = 0;

function heading(parent, title) {
  const section = node('section');
  section.append(node('h3', title));
  parent.append(section);
  return section;
}

function graph(metrics, unit, scope) {
  const wrap = node('div', undefined, 'graph');
  wrap.append(node('strong', unit), node('p', scope, 'muted'));
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 480 ${metrics.length * 34 + 12}`);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `측정값 그래프: ${unit}`);
  const max = Math.max(...metrics.map(m => m.value), 1);
  metrics.forEach((metric, index) => {
    const y = index * 34 + 20;
    const label = document.createElementNS(ns, 'text');
    label.setAttribute('x', '0'); label.setAttribute('y', y);
    label.textContent = metric.label; svg.append(label);
    const bar = document.createElementNS(ns, 'rect');
    bar.setAttribute('x', '160'); bar.setAttribute('y', y - 13);
    bar.setAttribute('width', String(metric.value / max * 210));
    bar.setAttribute('height', '14'); svg.append(bar);
    const text = document.createElementNS(ns, 'text');
    text.setAttribute('x', '375'); text.setAttribute('y', y);
    text.textContent = displayNumber(metric.value); svg.append(text);
  });
  wrap.append(svg);
  return wrap;
}

function graphs(metrics) {
  const groups = new Map();
  metrics.forEach(metric => {
    if (typeof metric.value !== 'number' || !Number.isFinite(metric.value) || metric.value < 0) return;
    const key = JSON.stringify([metric.unit || '단위 없음', metric.scope || '범위 미확인']);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(metric);
  });
  const out = node('div', undefined, 'graphs');
  [...groups.entries()].slice(0, 2).forEach(([key, values]) => out.append(graph(values, ...JSON.parse(key))));
  return out;
}

async function selectReport(id) {
  const item = (catalogData.experiments || []).find(x => x.experiment_id === id && x.slot === selectedSlot);
  if (!item) return selectPending(id);
  const request = ++selectionRequest;
  selectedReport = id;
  loadedFingerprint = JSON.stringify(item);
  pendingRefresh = false;
  document.querySelectorAll('nav button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
  const detail = $('#detail');
  detail.replaceChildren(node('p', '보고서를 불러오는 중입니다.'));
  try {
    const response = await fetch(`/api/experiments/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error('Unavailable');
    const d = await response.json();
    if (request !== selectionRequest) return;
    detail.dataset.id = id; detail.dataset.result = 'registered'; detail.dataset.executionStatus = show(d.execution_status);
    const assignment = (catalogData.assignments || []).find(x => x.slot === selectedSlot && x.experiment_id === id);
    detail.replaceChildren(node('p', `${d.synthetic || assignment?.synthetic ? 'TEST · ' : ''}${d.experiment_id}`, 'eyebrow'), node('h2', d.title), node('p', d.summary));
    detail.append(node('p', `실험 모델: ${show(d.evaluated_model)} · 작업자 모델: ${show(d.agent_model_effective)}`, 'muted'));
    const states = {completed_with_recorded_limitations: '실행 완료 · 한계 기록', AI_draft: 'AI 검수 초안', adoption_on_hold: '기본 채택 보류'};
    detail.append(node('p', `기록된 실험 실행: ${states[d.execution_status] || show(d.execution_status)} · 검토: ${states[d.review_status] || show(d.review_status)} · 결정: ${states[d.decision_status] || show(d.decision_status)}`, 'muted'));
    if (Object.values(d.source_integrity || {}).includes(false)) {
      detail.append(node('p', '원문 또는 측정치가 검토 당시와 다릅니다. 재검토가 필요합니다.', 'integrity-warning'));
    }
    const section = heading(detail, '실측값과 범위');
    section.append(node('p', '미측정은 0이 아닙니다. 실험마다 표본과 처리 범위가 달라 성능 순위로 비교하지 않습니다.', 'muted'));
    const box = node('div', undefined, 'table-wrap');
    const table = node('table'); const head = node('tr');
    ['지표', '값', '단위', '표본 수', '측정 범위'].forEach(text => head.append(node('th', text)));
    table.append(head);
    (d.metrics || []).forEach(metric => {
      const row = node('tr');
      [metric.label, measured(metric.value), show(metric.unit), measured(metric.sample_n), show(metric.scope)]
        .forEach(text => row.append(node('td', text)));
      table.append(row);
    });
    box.append(table); section.append(box, graphs(d.metrics || []));
    const evidence = heading(detail, '로컬 근거 영상과 이미지');
    if (!d.evidence?.length) evidence.append(node('p', '등록된 근거 파일이 없습니다. 원문 보고서를 확인해 주세요.'));
    (d.evidence || []).forEach(item => {
      const block = node('div', undefined, 'evidence');
      block.append(node('strong', item.label));
      if (!item.available) block.append(node('p', '파일을 사용할 수 없습니다.'));
      else if (item.kind === 'video') {
        const video = node('video'); video.controls = true; video.preload = 'none';
        video.src = `/artifacts/${encodeURIComponent(item.artifact_id)}`; block.append(video);
      } else if (item.kind === 'image') {
        const image = node('img'); image.loading = 'lazy'; image.alt = item.label;
        image.src = `/artifacts/${encodeURIComponent(item.artifact_id)}`; block.append(image);
      }
      evidence.append(block);
    });
    heading(detail, '담당 의견').append(node('p', show(d.worker_opinion)));
    const review = heading(detail, '총괄 검토');
    review.dataset.section = 'review';
    if (d.review_html) {
      const content = node('div'); content.innerHTML = d.review_html; review.append(content);
    } else review.append(node('p', '별도 검토가 없습니다.'));
    heading(detail, '다음 작업').append(node('p', show(d.next_step)));
    const limits = heading(detail, '한계'); (d.limitations || []).forEach(text => limits.append(node('p', text)));
    const technical = node('details'); technical.append(node('summary', '원문과 출처 · 기술 상세'));
    technical.append(node('pre', JSON.stringify({
      report_path: d.report_path, report_sha256: d.report_sha256, metrics_path: d.metrics_path,
      review_path: d.review_path, source_integrity: d.source_integrity,
      execution_status: d.execution_status, review_status: d.review_status, decision_status: d.decision_status,
      metrics: d.metrics,
    }, null, 2)));
    const original = node('div', undefined, 'original-report'); original.innerHTML = d.report_html;
    technical.append(original); detail.append(technical);
  } catch {
    if (request === selectionRequest) detail.replaceChildren(node('p', '등록된 보고서를 불러올 수 없습니다.'));
  }
}

// Native status is usable only for an exact, fresh, connected observation.
function nativeObservation(assignment, status, now = Date.now()) {
  const age = now - Date.parse(status?.observed_at);
  if (!assignment || !assignment.run_id || !assignment.task_id || !assignment.dispatch_id ||
      status?.state !== 'connected' || status.connected !== true || status.stale !== false ||
      status.run_id !== assignment.run_id || !Number.isFinite(age) || age < 0 ||
      !Number.isFinite(status.stale_after_seconds) || age > status.stale_after_seconds * 1000) return null;
  const matches = (status.workers || []).filter(w => w.task_id === assignment.task_id && w.dispatch_id === assignment.dispatch_id);
  return matches.length === 1 ? matches[0] : null;
}
function resultFor(data, slot, id) {
  return (data.experiments || []).find(x => x.slot === slot && x.experiment_id === id) || null;
}
function slotItems(data, slot) {
  const assignments = (data.assignments || []).filter(x => x.slot === slot);
  const results = (data.experiments || []).filter(x => x.slot === slot);
  return [...assignments.map(a => ({id: a.experiment_id, assignment: a, result: resultFor(data, slot, a.experiment_id)})),
    ...results.filter(r => !assignments.some(a => a.experiment_id === r.experiment_id)).map(r => ({id: r.experiment_id, result: r}))];
}
function observationText(observation) {
  if (!observation) return '미확인';
  if (observation.outcome === 'succeeded') return '작업자 완료';
  if (observation.outcome === 'failed') return '작업자 실패';
  if (observation.liveness?.verdict === 'exited') return '작업자 종료 · 결과 미확인';
  if (observation.liveness?.verdict !== 'live') return '생존 상태 미확인';
  if (observation.outcome === 'in_progress') return observation.stage?.activity === 'working' ? '진행 중' : '응답 대기';
  return '미확인';
}
function renderSlots() {
  const slots = ['slot1', 'slot2', 'slot3'].map(id => (catalogData.roles.slots || []).find(x => x.id === id) || {id, label: id});
  slots.push({id: 'unassigned', label: '미배정'});
  const container = $('#slots'); container.replaceChildren();
  slots.forEach(slot => {
    const items = slotItems(catalogData, slot.id);
    const button = node('button', undefined, 'card slot'); button.dataset.slot = slot.id;
    button.dataset.result = String(items.filter(x => x.result).length);
    button.setAttribute('aria-pressed', String(selectedSlot === slot.id));
    button.append(node('h3', slot.label), node('p', `배정 ${items.filter(x => x.assignment).length} · 등록 결과 ${items.filter(x => x.result).length}`, 'muted'));
    const states = [...new Set(items.filter(x => x.assignment).map(x => observationText(nativeObservation(x.assignment, statusData))))];
    button.dataset.status = states.length ? states.join(' / ') : '미배정';
    button.append(node('p', `작업: ${button.dataset.status}`, 'task-status'));
    if (items.some(x => x.assignment?.synthetic || x.result?.synthetic)) button.append(node('strong', 'TEST · 합성 확인'));
    button.addEventListener('click', () => selectSlot(slot.id)); container.append(button);
  });
}
function renderChoices() {
  const nav = $('#experiments'); nav.replaceChildren();
  const slot = (catalogData.roles.slots || []).find(x => x.id === selectedSlot);
  $('#slot-title').textContent = `${slot?.label || '미배정'} · 배정 및 등록 결과`;
  slotItems(catalogData, selectedSlot).forEach(item => {
    const observed = nativeObservation(item.assignment, statusData);
    const button = node('button'); button.dataset.id = item.id; button.dataset.slot = selectedSlot;
    button.dataset.status = observed ? 'observed' : 'unverified';
    button.dataset.result = item.result ? 'registered' : 'pending';
    button.setAttribute('aria-pressed', String(item.id === selectedReport));
    const synthetic = item.assignment?.synthetic || item.result?.synthetic;
    button.append(node('strong', `${synthetic ? 'TEST · ' : ''}${item.id} · ${show(item.assignment?.title || item.result?.title)}`),
      node('span', item.result ? ' · 결과 등록' : ' · 결과 미등록'));
    if (item.assignment) button.append(node('p', `Orca 작업: ${observationText(observed)}`, 'muted'));
    button.addEventListener('click', () => item.result ? selectReport(item.id) : selectPending(item.id));
    nav.append(button);
  });
}
function selectPending(id) {
  selectionRequest++; selectedReport = id; loadedFingerprint = null; pendingRefresh = false;
  const assignment = (catalogData.assignments || []).find(x => x.slot === selectedSlot && x.experiment_id === id);
  const detail = $('#detail'); detail.dataset.id = id; detail.dataset.result = 'pending';
  delete detail.dataset.executionStatus;
  detail.replaceChildren(node('p', `${assignment?.synthetic ? 'TEST · ' : ''}${id}`, 'eyebrow'),
    node('h2', show(assignment?.title)), node('p', '결과가 아직 등록되지 않았습니다. 보고서와 실험 실행·검토·결정 상태는 미확인입니다.'),
    node('p', `Orca 작업: ${observationText(nativeObservation(assignment, statusData))}`, 'muted'),
    node('p', `요청 모델: ${show(assignment?.agent_model_requested)} · 실효 모델: ${show(assignment?.agent_model_effective)} · 실효 effort: ${show(assignment?.reasoning_effective)}`, 'muted'));
  renderChoices();
}
function selectSlot(id) {
  selectedSlot = id; selectedReport = null; loadedFingerprint = null; pendingRefresh = false;
  renderSlots(); renderChoices();
  const items = slotItems(catalogData, id);
  const first = items.find(x => x.id === 'EXP-0007') || items[0];
  if (first) first.result ? selectReport(first.id) : selectPending(first.id);
  else { selectionRequest++; const detail = $('#detail'); detail.dataset.id = ''; detail.dataset.result = 'empty'; delete detail.dataset.executionStatus;
    detail.replaceChildren(node('h2', '배정이나 등록된 결과가 없습니다.')); }
}
function refreshSelectedIfChanged() {
  if (!selectedReport) return;
  const result = resultFor(catalogData, selectedSlot, selectedReport);
  if (!result) { if (loadedFingerprint !== null) selectPending(selectedReport); return; }
  if (JSON.stringify(result) === loadedFingerprint) return;
  const playing = [...$('#detail').querySelectorAll('video')].some(v => !v.paused && !v.ended);
  if (playing) { pendingRefresh = true; return; }
  selectReport(selectedReport);
}
async function refresh() {
  const [catalog, status] = await Promise.allSettled(['/api/catalog', '/api/status'].map(async url => {
    const response = await fetch(url, {cache: 'no-store'}); if (!response.ok) throw new Error('Unavailable'); return response.json();
  }));
  statusData = status.status === 'fulfilled' ? status.value : {};
  const labels = {connected: '연결됨', disconnected: '연결 끊김', stale: '관측 오래됨', unverified: '미검증'};
  $('#status').textContent = `Orca 조회: ${labels[statusData.state] || '미검증'} · 마지막 관측: ${show(statusData.observed_at)}`;
  if (catalog.status === 'fulfilled') {
    const first = !catalogData; catalogData = catalog.value;
    if (first) {
      const coordinator = catalogData.roles.coordinator;
      const card = node('div', undefined, 'card');
      card.append(node('h3', coordinator.label), node('p', `${coordinator.model} · ${coordinator.effort}`), node('p', coordinator.note, 'muted'));
      $('#coordinator').replaceChildren(card);
      (catalogData.roles.setup_workers || []).forEach(item => $('#workers').append(node('p', `${show(item.role)} · ${show(item.model)} · ${show(item.effort)} · ${show(item.status)}`)));
      selectSlot('unassigned');
    } else { renderSlots(); renderChoices(); refreshSelectedIfChanged(); }
  } else if (!catalogData) $('#detail').textContent = '카탈로그를 불러올 수 없습니다.';
  if (catalogData && selectedReport && !resultFor(catalogData, selectedSlot, selectedReport)) selectPending(selectedReport);
}
if (typeof module !== 'undefined') module.exports = {nativeObservation, resultFor, slotItems, observationText};
if (typeof document !== 'undefined') {
  document.addEventListener('pause', event => { if (event.target.tagName === 'VIDEO' && pendingRefresh) refreshSelectedIfChanged(); }, true);
  document.addEventListener('ended', event => { if (event.target.tagName === 'VIDEO' && pendingRefresh) refreshSelectedIfChanged(); }, true);
  refresh(); setInterval(refresh, 15000);
}
