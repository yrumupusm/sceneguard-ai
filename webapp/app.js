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
let selectedReport = 'EXP-0007';
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
  const request = ++selectionRequest;
  selectedReport = id;
  document.querySelectorAll('nav button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
  const detail = $('#detail');
  detail.replaceChildren(node('p', '보고서를 불러오는 중입니다.'));
  try {
    const response = await fetch(`/api/experiments/${encodeURIComponent(id)}`);
    if (!response.ok) throw new Error('Unavailable');
    const d = await response.json();
    if (request !== selectionRequest) return;
    detail.replaceChildren(node('p', d.experiment_id, 'eyebrow'), node('h2', d.title), node('p', d.summary));
    detail.append(node('p', `실험 모델: ${show(d.evaluated_model)} · 과거 작업자 모델: ${show(d.agent_model_effective)}`, 'muted'));
    const states = {completed_with_recorded_limitations: '실행 완료 · 한계 기록', AI_draft: 'AI 검수 초안', adoption_on_hold: '기본 채택 보류'};
    detail.append(node('p', [d.execution_status, d.review_status, d.decision_status].map(x => states[x] || show(x)).join(' / '), 'muted'));
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

function selectSlot(id) {
  document.querySelectorAll('.slot').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.slot === id)));
  $('#history').hidden = id !== 'unassigned';
  if (id === 'unassigned') selectReport(selectedReport);
  else {
    selectionRequest++;
    $('#detail').replaceChildren(node('h2', '아직 배정된 실험이 없습니다.'),
      node('p', '새 비교 실험은 시작하지 않았습니다. 기존 보고서는 미배정 카드에서 확인할 수 있습니다.'));
  }
}

async function refreshStatus() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error('Unavailable');
    const state = await response.json();
    const labels = {connected: '연결됨', disconnected: '연결 끊김', stale: '관측 오래됨', unverified: '미검증'};
    $('#status').textContent = `Orca 조회: ${labels[state.state] || '미검증'} · 마지막 관측: ${show(state.observed_at)}`;
  } catch { $('#status').textContent = 'Orca 조회: 연결 상태 확인 불가'; }
}

async function init() {
  try {
    const response = await fetch('/api/catalog');
    if (!response.ok) throw new Error('Unavailable');
    catalogData = await response.json();
    const coordinator = catalogData.roles.coordinator;
    const card = node('div', undefined, 'card');
    card.append(node('h3', coordinator.label), node('p', `${coordinator.model} · ${coordinator.effort}`),
      node('p', coordinator.note, 'muted'));
    $('#coordinator').replaceChildren(card);
    [...catalogData.roles.slots, {id: 'unassigned', label: '미배정', note: '기존 실험 7개 · 읽기 전용'}].forEach(item => {
      const button = node('button', undefined, 'card slot'); button.dataset.slot = item.id;
      button.append(node('h3', item.label));
      if (item.model) button.append(node('p', `예정: ${item.model} · ${item.effort}`));
      button.append(node('p', item.id === 'unassigned' ? item.note : '실험 미배정', 'muted'));
      button.addEventListener('click', () => selectSlot(item.id)); $('#slots').append(button);
    });
    (catalogData.roles.setup_workers || []).forEach(item => $('#workers').append(node('p',
      `${show(item.role)} · ${show(item.model)} · ${show(item.effort)} · ${show(item.status)}`)));
    catalogData.experiments.filter(item => item.slot === 'unassigned').forEach(item => {
      const button = node('button', item.experiment_id); button.dataset.id = item.experiment_id;
      button.addEventListener('click', () => selectReport(item.experiment_id)); $('#experiments').append(button);
    });
    selectSlot('unassigned');
    await refreshStatus(); setInterval(refreshStatus, 15000);
  } catch { $('#detail').textContent = '카탈로그를 불러올 수 없습니다.'; $('#status').textContent = 'Orca 조회: 미검증'; }
}
init();
