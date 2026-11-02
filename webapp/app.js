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
  wrap.append(node('p', `표시 범위: 0–${displayNumber(max)} ${unit}`, 'muted'));
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
  const out = node('div', undefined, 'graphs');
  // A single scoped value per graph avoids implying unrelated metrics are comparable.
  metrics.filter(m => typeof m.value === 'number' && Number.isFinite(m.value) && m.value >= 0 && m.unit && m.scope && m.scope !== '미확인')
    .forEach(m => out.append(graph([m], m.unit, `${m.scope} · 표본 수: ${measured(m.sample_n)}`)));
  return out;
}

function reviewWarning(state) {
  if (state === 'current') return '';
  return state === 'stale' ? '이전 검토가 현재 원문·측정치와 다릅니다. 재검토가 필요합니다.' : '이전 검토와 현재 원문·측정치의 연결을 확인할 수 없습니다. 재검토가 필요합니다.';
}
function isInputSheet(item) {
  return item.kind === 'image' && /(?:입력.*(?:시트|표본|프레임)|(?:시트|표본).*입력|contact\s*sheet|processor 입력)/i.test(item.label || '');
}
function evidencePriority(item) {
  return /실패|누락|오류|오탐|잘못|failure|miss|error/i.test(item.label || '') ? 0 :
    /비교|대조|성공|복원|success|comparison|compare|\s\/\s/i.test(item.label || '') ? 1 : 2;
}
function appendEvidence(parent, items) {
  items.forEach(item => {
    const block = node('div', undefined, 'evidence');
    block.append(node('strong', item.label || '이름 없는 근거'));
    if (!item.available) block.append(node('p', '파일을 사용할 수 없습니다.'));
    else if (item.kind === 'video') {
      const video = node('video'); video.controls = true; video.preload = 'none';
      video.src = `/artifacts/${encodeURIComponent(item.artifact_id)}`; block.append(video);
    } else if (item.kind === 'image') {
      const image = node('img'); image.loading = 'lazy'; image.alt = item.label || '근거 이미지';
      image.src = `/artifacts/${encodeURIComponent(item.artifact_id)}`; block.append(image);
    }
    parent.append(block);
  });
}

async function selectReport(id) {
  const item = (catalogData.experiments || []).find(x => x.experiment_id === id && x.slot === selectedSlot);
  if (!item) return selectPending(id);
  const request = ++selectionRequest;
  selectedReport = id; storageSet('selected-report', id); storageSet('selected-slot', selectedSlot);
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
    const presentation = d.presentation || {};
    detail.replaceChildren(node('p', `${d.synthetic || assignment?.synthetic ? 'TEST · ' : ''}${d.experiment_id}`, 'eyebrow'), node('h2', d.title));
    const states = {completed_with_recorded_limitations: '실행 완료 · 한계 기록', succeeded: '완료', failed: '실패', inconclusive: '판단 보류', accepted_for_comparison: '비교 검토 완료', needs_revision: '보완 필요', blocked: '차단', AI_draft: 'AI 검수 초안', adoption_on_hold: '기본 채택 보류', rejected: '미채택'};
    detail.append(node('p', `실행: ${states[d.execution_status] || show(d.execution_status)} · 검토: ${states[d.review_status] || show(d.review_status)} · 결정: ${states[d.decision_status] || show(d.decision_status)}`, 'muted'));
    if (Object.values(d.source_integrity || {}).includes(false)) detail.append(node('p', '원문 또는 측정치가 등록 당시와 다릅니다. 재검토가 필요합니다.', 'integrity-warning'));
    const warning = reviewWarning(d.review_integrity);
    if (warning) detail.append(node('p', warning, 'integrity-warning'));
    heading(detail, '실험 목적').append(node('p', presentation.purpose || '실험 목적을 확인할 수 없습니다.'));
    heading(detail, '이전 문제와 변경').append(node('p', presentation.change || '이전 문제와 변경 사항을 확인할 수 없습니다.'));
    heading(detail, '결론').append(node('p', presentation.conclusion || d.summary || '결론을 확인할 수 없습니다.'));
    const section = heading(detail, '실측값과 범위');
    section.append(node('p', '각 값은 이 실험에서 기록한 범위에만 적용됩니다. 미측정은 0이 아닙니다.', 'muted'));
    const metrics = d.metrics || [];
    if (!metrics.length) section.append(node('p', '등록된 측정값이 없습니다.'));
    const list = node('ul', undefined, 'metric-list');
    metrics.forEach(m => list.append(node('li', `${show(m.label)}: ${measured(m.value)} ${show(m.unit)} · 표본 수 ${measured(m.sample_n)} · ${show(m.scope)}`)));
    const measuredDetails = node('details'); measuredDetails.append(node('summary', `전체 측정값과 범위 (${metrics.length})`), list);
    const comparisons = Array.isArray(presentation.comparisons) ? presentation.comparisons : [];
    if (comparisons.length) {
      for (const comparison of comparisons) {
        section.append(node('h4', comparison.title), graph(comparison.values, comparison.unit, comparison.scope));
      }
    } else section.append(graphs(metrics.slice(0, 4)));
    section.append(measuredDetails);
    const evidence = heading(detail, '대표 근거');
    evidence.append(node('p', presentation.evidence_note || '등록된 자료의 원래 설명을 표시합니다. 성공이나 실패 여부는 각 설명과 보고서에서 확인해 주세요.', 'muted'));
    const items = d.evidence || [];
    const visible = items.filter(item => !isInputSheet(item)).sort((a, b) => evidencePriority(a) - evidencePriority(b));
    const inputs = items.filter(isInputSheet);
    if (!items.length) evidence.append(node('p', '등록된 근거 파일이 없습니다.'));
    if (items.length && !visible.length) evidence.append(node('p', '등록된 자료는 아래 입력 자료에서 확인할 수 있습니다.'));
    appendEvidence(evidence, visible.slice(0, 4));
    if (visible.length > 4) {
      const more = node('details'); more.append(node('summary', `나머지 근거 보기 (${visible.length - 4})`));
      appendEvidence(more, visible.slice(4)); evidence.append(more);
    }
    if (inputs.length) {
      const sheets = node('details'); sheets.append(node('summary', `원본 입력 시트 보기 (${inputs.length})`));
      appendEvidence(sheets, inputs); evidence.append(sheets);
    }
    if (id === 'EXP-0036') addIncidentFlows(detail, request);
    if (id === 'EXP-0037' || id === 'EXP-0040' || id === 'EXP-0041' || id === 'EXP-0042' || id === 'EXP-0044' || id === 'EXP-0045' || id === 'EXP-0046' || id === 'EXP-0047' || id === 'EXP-0048' || id === 'EXP-0049') addFinishFlows(detail, request, id);
    heading(detail, '한계').append(node('p', presentation.limitations || (d.limitations || []).join(' · ') || '기록된 한계를 확인할 수 없습니다.'));
    heading(detail, '다음 단계').append(node('p', presentation.next_steps || d.next_step || '다음 단계를 확인할 수 없습니다.'));
    const refs = heading(detail, '참고 자료');
    const references = Array.isArray(presentation.references) ? presentation.references : [];
    if (!references.length) refs.append(node('p', '등록된 참고 자료가 없습니다.'));
    references.forEach(ref => {
      const p = node('p');
      if (ref.url && /^(https?:\/\/|\/(?!\/))/i.test(ref.url)) {
        const link = node('a', ref.label || ref.url); link.href = ref.url; link.rel = 'noopener noreferrer'; p.append(link);
      } else p.append(node('span', ref.label || '참고 자료'));
      if (ref.application) p.append(node('span', ` · ${ref.application}`));
      refs.append(p);
    });
  } catch {
    if (request === selectionRequest) detail.replaceChildren(node('p', '등록된 보고서를 불러올 수 없습니다.'));
  }
}


function storageGet(key) { try { return localStorage.getItem(key); } catch { return null; } }
function storageSet(key, value) { try { localStorage.setItem(key, value); } catch { /* storage optional */ } }

async function addFinishFlows(detail, request, experimentId = 'EXP-0037') {
  const section = heading(detail, experimentId === 'MVP-0002' ? '근거 보기' : '사건 카드 재생과 검토');
  section.dataset.section = 'incident-flows';
  try {
    const response = await fetch(`/api/incident-registrations?experiment_id=${encodeURIComponent(experimentId)}`, {cache:'no-store'});
    if (!response.ok) throw Error('unavailable');
    const entries = await response.json();
    if ((experimentId !== 'MVP-0002' && request !== selectionRequest) || !section.isConnected) return;
    if (experimentId === 'MVP-0002') entries.reverse();
    if (!entries.length) { section.append(node('p', '등록된 카드 자료가 없습니다.')); return; }
    if (experimentId === 'EXP-0040' || experimentId === 'EXP-0041') section.append(node('p', '제안에서 통지 제외된 알림은 검토 전용으로 남으며 침입 아님 확정이 아닙니다.', 'muted'));
    if (experimentId === 'EXP-0042') section.append(node('p', '새 후보만 보기는 기존 소실 의심이 빠진 진단용입니다. 결합 보기에는 기존 오탐도 포함됩니다.', 'muted'));
    const source = node('select'); source.dataset.exp37Source = '';
    const view = node('select'); view.dataset.exp37View = '';
    const holder = node('div', undefined, 'incident-flow');
    const sources = [...new Set(entries.map(e => e.source_label))];
    for (const label of sources) { const opt = node('option', label); opt.value = label; source.append(opt); }
    const sourceKey = experimentId === 'MVP-0002' ? 'mvp-source' : 'exp37-source';
    const viewKey = experimentId === 'MVP-0002' ? 'mvp-view' : 'exp37-view';
    const defaultEntry = experimentId === 'MVP-0002' ? entries.find(e => e.default) : null;
    source.value = sources.includes(storageGet(sourceKey)) ? storageGet(sourceKey) : (defaultEntry?.source_label || sources[0]);
    const sourceLabel = node('label', '영상 선택 '); sourceLabel.append(source);
    const viewLabel = node('label', '결과 선택 '); viewLabel.append(view);
    section.append(sourceLabel, viewLabel, holder);
    let epoch = 0;
    async function display() {
      const current = ++epoch;
      const entry = entries.find(e => e.source_label === source.value && e.id === view.value);
      if (!entry) return;
      storageSet(sourceKey, source.value); storageSet(viewKey, view.value);
      for (const oldVideo of (holder.querySelectorAll?.('video') || [])) { oldVideo.pause(); oldVideo.removeAttribute('src'); oldVideo.load(); }
      holder.dataset.bundle = entry.id; holder.replaceChildren(node('p', '카드 자료를 불러오는 중입니다.'));
      try {
        const r = await fetch(`/api/incidents/${encodeURIComponent(entry.id)}`, {cache:'no-store'});
        if (!r.ok) throw Error('unavailable');
        const data = await r.json();
        if (current !== epoch || !holder.isConnected) return;
        holder.replaceChildren(); renderIncidentFlow(holder, entry.id, data);
      } catch { if (current === epoch) holder.textContent = '카드 자료를 사용할 수 없습니다.'; }
    }
    function chooseViews() {
      const choices = entries.filter(e => e.source_label === source.value);
      view.replaceChildren();
      for (const entry of choices) {
        const range = entry.source_window ? ` · ${entry.source_window[0]}–${entry.source_window[1]}초` : '';
        const opt = node('option', `${entry.view_label}${range} · ${entry.provenance_label}`); opt.value = entry.id; view.append(opt);
      }
      const saved = storageGet(viewKey);
      view.value = (choices.find(e => e.id === saved) || choices.find(e => e.view_label === saved) || choices.find(e => e.default) || choices[0]).id;
      display();
    }
    source.addEventListener('change', chooseViews); view.addEventListener('change', display); chooseViews();
  } catch { if (experimentId === 'MVP-0002' || request === selectionRequest) section.append(node('p', '등록된 카드 자료를 불러올 수 없습니다.')); }
}

function addReview(block, bundleId, incidentId, bundleSha, sessionId) {
  const panel = node('details'); panel.dataset.reviewPanel = incidentId;
  const openKey = `review-open:${bundleId}:${bundleSha}:${incidentId}`;
  panel.open = storageGet(openKey) === 'true';
  panel.addEventListener('toggle', () => storageSet(openKey, String(panel.open)));
  panel.append(node('summary', '수동 검토 및 이력'));
  const status = node('select'); status.dataset.reviewStatus = incidentId;
  for (const text of ['침입 의심', '침입 확인', '침입 아님', '판단 불가']) { const o = node('option', text); o.value = text; status.append(o); }
  const reviewer = node('input'); reviewer.dataset.reviewer = incidentId; reviewer.placeholder = '검토자'; reviewer.maxLength = 128;
  const note = node('textarea'); note.dataset.reviewNote = incidentId; note.placeholder = '메모'; note.maxLength = 2000;
  const save = node('button', '검토 저장'); save.dataset.reviewSave = incidentId;
  save.disabled = true;
  const message = node('p'); message.dataset.reviewMessage = incidentId; message.setAttribute('role', 'status');
  const history = node('ol'); history.dataset.reviewHistory = incidentId;
  const current = node('p'); current.dataset.reviewCurrent = incidentId;
  panel.append(status, reviewer, note, save, message, current, node('p', '변경 이력'), history); block.append(panel);
  let version = 0;
  const edited = new Set();
  for (const field of [status, reviewer, note]) {
    field.addEventListener('input', () => edited.add(field));
    field.addEventListener('change', () => edited.add(field));
  }
  const url = `/api/incidents/${encodeURIComponent(bundleId)}/reviews/${encodeURIComponent(incidentId)}`;
  function showState(data, fill) {
    version = data.review?.version || 0;
    current.textContent = data.review ? `저장된 검토: ${data.review.status} · ${data.review.reviewer} · 버전 ${version} · ${data.review.updated_utc} (UTC) · ${data.review.note}` : '저장된 검토 없음';
    history.replaceChildren();
    for (const item of data.history) history.append(node('li', `버전 ${item.version} · ${item.status} · ${item.reviewer} · ${item.updated_utc} (UTC) · ${item.note}`));
    if (fill && data.review) {
      for (const [field, value] of [[status, data.review.status], [reviewer, data.review.reviewer], [note, data.review.note]]) {
        if (!edited.has(field)) field.value = value;
      }
    }
  }
  fetch(`${url}?bundle_sha256=${encodeURIComponent(bundleSha)}&session_id=${encodeURIComponent(sessionId)}`, {cache:'no-store'}).then(r => {
    if (r.status === 409) { message.textContent = '카드 자료가 변경되었습니다. 작성 중인 내용을 복사하고 페이지를 새로고침하세요.'; return null; }
    if (!r.ok) throw Error(); return r.json();
  }).then(data => { if (data) { showState(data, true); save.disabled = false; } }).catch(() => { message.textContent = '검토를 불러오지 못했습니다. 작성 중인 내용을 복사하고 페이지를 새로고침하세요.'; });
  save.addEventListener('click', async () => {
    save.disabled = true;
    try {
      const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status:status.value, reviewer:reviewer.value, note:note.value, expected_version:version, bundle_sha256:bundleSha, session_id:sessionId})});
      if (r.status === 409) { const state = await r.json(); if (Object.hasOwn(state, 'history')) { showState(state, false); message.textContent = '다른 수정이 저장되어 최신 상태를 불러왔습니다. 작성 중인 내용은 유지됩니다. 확인 후 다시 저장하세요.'; } else { message.textContent = '카드 자료가 변경되었습니다. 작성 중인 내용을 복사하고 페이지를 새로고침하세요.'; } return; }
      if (!r.ok) throw Error();
      showState(await r.json(), false); message.textContent = '검토가 저장되었습니다.';
      panel.dispatchEvent(new CustomEvent('incident-review-saved', {bubbles:true, detail:{incidentId, version}}));
    } catch { message.textContent = '검토 저장에 실패했습니다. 입력을 확인하세요.'; }
    finally { save.disabled = false; }
  });
}

// Lifecycle playback is a comparison: intents are shown, never delivered or claimed.
function renderLifecycleFlow(holder, id, data) {
  holder.append(node('h3', `${data.source_label || id} · ${data.view_label || '상태 비교'}`));
  holder.append(node('p', data.experiment === 'MVP-0002' ? '자동 판정과 수동 검토는 별개입니다. 알림 의도는 외부로 발송하지 않습니다. 관측 연결은 동일인 확인이 아닙니다.' : '자동 의심 해제는 수동 침입 아님 판정이 아닙니다. 알림 의도는 비교 기록이며 발송하지 않습니다. 같은 시각의 여러 카드는 인원 수를 뜻하지 않으며, 관측 연결은 동일인 확인이 아닙니다.', 'muted'));
  const video = node('video'); video.controls = true; video.preload = 'metadata';
  video.dataset.incidentVideo = id; video.src = `/artifacts/${encodeURIComponent(data.media_artifact_id)}`;
  const clock = node('p'); clock.dataset.incidentClock = id;
  const cards = node('div'); cards.dataset.incidentCards = id;
  const activity = data.contract === 'gate_activity_episodes_v1';
  if (data.experiment === 'MVP-0002') holder.append(node('p', '원본 근거 영상 · 박스나 예측 표시 없음', 'muted'));
  holder.append(video, clock);
  if (data.experiment === 'MVP-0002' && !data.timeline.length) holder.append(node('p', '분석 완료 · 사건 없음'));
  const mvp = data.experiment === 'MVP-0002';
  if (mvp) holder.append(node('p', `분석 완료 · ${data.provenance_label} · ${data.source_window[0]}–${data.source_window[1]}초`, 'muted'));
  if (activity) holder.append(node('h4', mvp ? '진행 중 사건' : '진행 중 관찰'));
  holder.append(cards);
  let history, resolutions;
  if (activity) {
    cards.dataset.activityActive = id;
    history = node('div'); history.dataset.activityHistory = id;
    holder.append(node('h4', mvp ? '종료 이력' : '종료된 관찰 이력'), history);
    if (data.experiment !== 'MVP-0002') { resolutions = node('div'); resolutions.dataset.sourceResolutions = id; holder.append(resolutions); }
    holder.append(node('p', mvp ? '문 주변 관찰 종료는 의심 해제나 현장 안전을 뜻하지 않습니다.' : '관찰 종료는 의심 해제가 아닙니다. 원본 EXP48 해소 기록의 사건 ID는 이전 카드의 출처입니다.', 'muted'));
  }
  let routing;
  if (data.experiment === 'EXP-0048' && data.observation_audit) {
    routing = node('div'); routing.dataset.outcomeRouting = id; holder.append(routing);
    const audit = node('details'); audit.dataset.observationAudit = id;
    audit.append(node('summary', `전체 저장 관측 감사 (${data.observation_audit.records.length}개 관측열)`));
    audit.append(node('p', '종료 후 진단이며 사람 수나 독립 표본이 아닙니다. 의심 없음은 해제 성공이 아니며 일반 보행 여부는 원본 확인이 필요합니다. 박스 이동은 상태 판정 근거가 아닙니다.', 'muted'));
    for (const row of data.observation_audit.records) {
      audit.append(node('p', `${row.run_id} · ${row.first_pts.toFixed(3)}–${row.last_pts.toFixed(3)}초 · ${row.state_category} · 종료 사유 ${row.endpoint_assessment.reason || 'not_evaluated'} · 박스 이동 진단 ${row.box_motion_diagnostic.direction} · 크기 변화 비율 ${row.box_motion_diagnostic.box_scale_ratio?.toFixed(2) ?? '없음'} (부분 신체 가능) · 사건 근거 ${row.event_ids.join(', ') || '없음'}`));
    }
    holder.append(audit);
  }
  const [start, end] = data.source_window, mediaStart = data.media_start_pts ?? start;
  const stateId = `${id}:${data.bundle_sha256}`;
  const saved = storageGet(`incident-time:${stateId}`);
  video.currentTime = saved !== null && Number.isFinite(Number(saved)) ? Number(saved) : start - mediaStart;
  const cardNodes = new Map();
  function render() {
    const pts = Math.max(start, Math.min(end, mediaStart + video.currentTime));
    clock.textContent = `원본 시각 ${pts.toFixed(3)}초`;
    if (routing) routing.textContent = '후속 결과 귀속 (현재 시각까지): ' + (data.outcome_routing.filter(r => r.decision_time_pts <= pts + 1e-9).map(r => `${r.decision_time_pts.toFixed(3)}초 · ${r.reason} · 사건 ${r.owner_incident_id || '없음'} · 선택 ${r.selected_event_ids.join(', ') || '없음'} · 제외 ${r.excluded_event_ids.join(', ') || '없음'}`).join(' / ') || '없음');
    if (resolutions) resolutions.textContent = '원본 EXP48 해소 기록 (현재 시각까지, 이전 카드 ID): ' + (data.source_resolution_log.filter(r => r.decision_time_pts <= pts + 1e-9).map(r => `${r.decision_time_pts.toFixed(3)}초 · ${r.kind || '기록'} · 원본 사건 ${r.owner_incident_id || r.incident_id || '없음'} · 근거 ${(r.event_ids || []).length}개`).join(' / ') || '없음');
    const snapshots = new Map();
    for (const row of data.timeline) { if (row.decision_time_pts > pts + 1e-9) break; snapshots.set(row.incident_id, row.card); }
    for (const [cid, entry] of cardNodes) if (!snapshots.has(cid)) { entry.block.remove(); entry.attached = false; }
    for (const card of snapshots.values()) {
      let entry = cardNodes.get(card.incident_id);
      if (!entry) {
        const block = node('div', undefined, 'incident-card'); block.dataset.incidentId = card.incident_id;
        const title = node('strong'), summary = node('p'), notices = node('p');
        notices.dataset.lifecycleIntents = card.incident_id;
        let debug;
        if (mvp) {
          const evidence = node('button', '근거 보기');
          evidence.addEventListener('click', () => {
            const snapshot = data.timeline.find(row => row.incident_id === card.incident_id);
            if (snapshot) { video.currentTime = Math.max(0, snapshot.decision_time_pts - mediaStart); video.focus(); }
          });
          const details = node('details'); details.append(node('summary', '알림 및 근거 상세'));
          debug = node('p'); details.append(notices, debug);
          block.append(title, summary, evidence, details);
        } else block.append(title, summary, notices);
        if (data.bundle_sha256) addReview(block, id, card.incident_id, data.bundle_sha256, data.session_id);
        entry = {block, title, summary, notices, debug, attached:false}; cardNodes.set(card.incident_id, entry);
      }
      const target = activity && card.observation_status === 'closed' ? history : cards;
      if (!entry.attached || entry.target !== target) { target.append(entry.block); entry.attached = true; entry.target = target; }
      const own = data.notification_intents.filter(n => n.incident_id === card.incident_id && n.decision_time_pts <= pts + 1e-9);
      const fmt = value => value == null ? '없음' : `${value.toFixed(3)}초`;
      if (mvp) {
        entry.title.textContent = card.automatic_status === '침입 확인' ? '침입 확인 · 자동' : card.automatic_status;
        entry.summary.textContent = `첫 의심 ${fmt(card.first_alert_pts)} · 첫 자동 확인 ${fmt(card.first_confirmation_pts)} · 문 주변 관찰 ${card.observation_status === 'open' ? '중' : '종료'}${card.observation_status === 'closed' ? ' ' + fmt(card.observation_closed_pts) : ''}`;
        entry.notices.textContent = own.map(n => `${n.kind === 'confirmation' ? '확인' : '의심'} 의도 ${fmt(n.decision_time_pts)} · ${n.notification_key}`).join(' / ') || '알림 의도 없음';
        entry.debug.textContent = `개별 근거: 미결 ${card.unresolved_event_ids.length} · 해제 ${card.released_event_ids.length} · 확인 ${card.confirmed_event_ids.length} · 최근 문 관측 ${fmt(card.last_gate_observation_pts)}`;
      } else {
      entry.title.textContent = `${card.automatic_status} · 자동 · ${card.gate_id} (원래 상태: ${card.status})`;
      const own = data.notification_intents.filter(n => n.incident_id === card.incident_id && n.decision_time_pts <= pts + 1e-9);
      const fmt = value => value == null ? '없음' : `${value.toFixed(3)}초`;
      const suspicion = own.find(n => n.kind === 'suspicion');
      const confirmation = own.find(n => n.kind === 'confirmation');
      entry.summary.textContent = `첫 의심 ${fmt(card.first_alert_pts)} · 의심 알림 의도 ${fmt(suspicion?.decision_time_pts)} · 첫 자동 확인 ${fmt(card.first_confirmation_pts)} · 확인 알림 의도 ${fmt(confirmation?.decision_time_pts)} · 미결 ${card.unresolved_event_ids.length} · 해제 ${card.released_event_ids.length} · 확인 ${card.confirmed_event_ids.length}`;
      if (activity) entry.summary.textContent += ` · 관찰 ${card.observation_status === 'open' ? '진행 중' : '종료'} · 최근 문 관측 ${fmt(card.last_gate_observation_pts)} · 관찰 종료 ${fmt(card.observation_closed_pts)}${card.observation_close_reason ? ' (' + card.observation_close_reason + ')' : ''} · 원본 사건 ${card.source_incident_ids.join(', ') || '없음'} · 문 관측 참조 ${JSON.stringify(card.last_gate_observation_refs)}`;
      entry.notices.textContent = own.map(n => `${n.kind === 'confirmation' ? '확인' : '의심'} 의도 ${fmt(n.decision_time_pts)} · ${n.notification_key}`).join(' / ') || '알림 의도 없음';
      }
    }
  }
  for (const name of ['seeking', 'seeked', 'timeupdate']) video.addEventListener(name, () => { storageSet(`incident-time:${stateId}`, String(video.currentTime)); render(); });
  render();
}

// Saved timeline snapshots are presented at their original decision PTS.
async function addIncidentFlows(detail, request) {
  const section = heading(detail, '사건 카드 재생');
  section.dataset.section = 'incident-flows';
  section.append(node('p', '개별 알림을 묶은 검토 단위입니다. 알림 수는 인원 수가 아니며 침입 확정이나 오탐 제거를 뜻하지 않습니다.', 'muted'));
  for (const id of ['007', '030']) {
    const holder = node('div', undefined, 'incident-flow'); holder.dataset.bundle = id;
    section.append(holder);
    try {
      const response = await fetch(`/api/incidents/${id}`, {cache: 'no-store'});
      if (!response.ok) throw new Error('unavailable');
      const data = await response.json();
      if (request !== selectionRequest || !holder.isConnected) return;
      renderIncidentFlow(holder, id, data);
    } catch {
      if (request === selectionRequest) holder.textContent = `${id} 카드 자료를 사용할 수 없습니다.`;
    }
  }
}
function renderIncidentFlow(holder, id, data) {
  if (data.contract === 'incident_lifecycle_v1' || data.contract === 'incident_outcome_scope_v1' || data.contract === 'gate_activity_episodes_v1') return renderLifecycleFlow(holder, id, data);
  holder.append(node('h3', `${data.source_label || id} · ${data.view_label || '기존 비교 영상'}`));
  const video = node('video'); video.controls = true; video.preload = 'metadata';
  video.dataset.incidentVideo = id; video.src = `/artifacts/${encodeURIComponent(data.media_artifact_id)}`;
  const clock = node('p'); clock.dataset.incidentClock = id;
  const counter = node('p'); counter.dataset.incidentCounter = id;
  const cards = node('div'); cards.dataset.incidentCards = id;
  const isComparison41 = data.contract === 'group_all_then_notify_v1';
  const reviewHistory = node('details'); reviewHistory.dataset.reviewOnly = id;
  const reviewSummary = node('summary', '검토 전용 사건 0개');
  const reviewCards = node('div'); reviewHistory.append(reviewSummary, reviewCards);
  const toast = node('div', '', 'incident-toast'); toast.dataset.incidentToast = id;
  toast.dataset.paintedCount = '0'; toast.hidden = true; toast.setAttribute('role', 'status');
  holder.append(video, clock, counter, cards, toast);
  if (isComparison41) holder.append(reviewHistory);
  if (data.provenance_label) holder.append(node('p', `출처: ${data.provenance_label}`, 'muted'));
  if (data.review_only_alerts) {
    const only = node('details'); only.dataset.reviewOnly = id;
    only.append(node('summary', `검토 전용 알림 ${data.review_only_alerts.length}개`));
    if (!data.review_only_alerts.length) only.append(node('p', '검토 전용 알림 없음'));
    for (const e of data.review_only_alerts) only.append(node('p', `${e.decision_time_pts.toFixed(3)}초 · ${e.source_ref.source_pointer} · ${e.event_id}`));
    holder.append(only);
  }
  const events = new Map(data.events.map(e => [e.event_id, e]));
  const [start, end] = data.source_window;
  const mediaStart = data.media_start_pts ?? start;
  let previous = start, generation = 0, timer;
  const pending = new Set();
  const cardNodes = new Map();
  const stateId = `${id}:${data.bundle_sha256 || 'legacy'}`;
  const savedTime = storageGet(`incident-time:${stateId}`);
  video.currentTime = savedTime !== null && Number.isFinite(Number(savedTime)) ? Number(savedTime) : start - mediaStart;
  function render(pts) {
    const snapshots = new Map(); let raw = 0;
    for (const item of data.timeline) {
      if (item.decision_time_pts > pts + 1e-9) break;
      snapshots.set(item.incident_id, item.card); raw++;
    }
    clock.textContent = `원본 시각 ${pts.toFixed(3)}초`;
    const eligible = [...snapshots.values()].filter(card => card.notification_eligible);
    const reviews = [...snapshots.values()].filter(card => !card.notification_eligible);
    counter.textContent = isComparison41 ? `전체 후보 ${raw}개 · 전체 사건 ${snapshots.size}개 · 통지 사건 ${eligible.length}개` : `개별 알림 ${raw}개 · 사건 카드 ${snapshots.size}개`;
    if (isComparison41) reviewSummary.textContent = `검토 전용 사건 ${reviews.length}개`;
    for (const [cardId, entry] of cardNodes) {
      if (!snapshots.has(cardId)) { entry.block.remove(); entry.attached = false; }
    }
    for (const card of snapshots.values()) {
      let entry = cardNodes.get(card.incident_id);
      if (!entry) {
        const block = node('div', undefined, 'incident-card'); block.dataset.incidentId = card.incident_id;
        const title = node('strong'), summary = node('p'), details = node('details'), list = node('ul');
        const evidence = node('button', '근거 시점 보기'); evidence.dataset.incidentSeek = card.incident_id;
        evidence.addEventListener('click', () => { video.pause(); video.currentTime = Math.max(start, card.first_alert_pts - 3) - mediaStart; });
        const savedDetails = storageGet(`incident-details:${stateId}:${card.incident_id}`);
        details.open = savedDetails === null ? ['EXP-0042', 'EXP-0045', 'EXP-0046'].includes(data.experiment) : savedDetails === 'true';
        details.addEventListener('toggle', () => storageSet(`incident-details:${stateId}:${card.incident_id}`, String(details.open)));
        details.append(node('summary', ['EXP-0042', 'EXP-0045', 'EXP-0046'].includes(data.experiment) ? '후보 발생 시각과 참조' : '원래 알림 참조'), list);
        block.append(title, summary, details, evidence);
        entry = {block, title, summary, details, list, fingerprint: null};
        entry.attached = false;
        if (data.bundle_sha256) addReview(block, id, card.incident_id, data.bundle_sha256, data.session_id);
        cardNodes.set(card.incident_id, entry);
      }
      const target = isComparison41 && !card.notification_eligible ? reviewCards : cards;
      if (!entry.attached || entry.target !== target) { target.append(entry.block); entry.target = target; }
      entry.attached = true;
      const fingerprint = JSON.stringify(card);
      if (entry.fingerprint === fingerprint) continue;
      entry.fingerprint = fingerprint;
      entry.title.textContent = card.decision_source === 'automatic_rule'
        ? `${card.automatic_status} · 자동 · ${card.gate_id} (원래 상태: ${card.status})`
        : `${card.status} · ${card.gate_id}`;
      entry.summary.textContent = `${data.experiment === 'EXP-0042' ? '후보 ' : ''}${card.first_alert_pts.toFixed(3)}~${card.last_alert_pts.toFixed(3)}초 · 관련 알림 ${card.alert_count}개 · 추적 ID ${card.track_ids.join(', ') || '없음'}` + (isComparison41 ? ` · 첫 통지 ${card.first_notification_pts === null ? '없음' : card.first_notification_pts.toFixed(3) + '초'}` : '');
      if (card.decision_source === 'automatic_rule' && card.first_confirmation_pts !== null) entry.summary.textContent += ` · 첫 자동 확인 ${card.first_confirmation_pts.toFixed(3)}초`;
      entry.list.replaceChildren();
      for (const eventId of card.event_ids) {
        const event = events.get(eventId); const ref = event.source_ref;
        const candidateKind = ['EXP-0045', 'EXP-0046'].includes(data.experiment) ? (ref.collection === 'inside_birth_events' ? (data.experiment === 'EXP-0046' ? '문 구역 새 관측' : '안쪽 새 관측') : '기존 후보') + ' · ' : data.experiment === 'EXP-0042' ? (ref.collection === 'transition_events' ? '새 후보 발생' : '기존 후보 발생') + ' · ' : '';
        const birth = ref.collection === 'inside_birth_events' ? event.source_event : null;
        const birthInfo = birth ? ` · 첫 실제 관측 ${birth.birth_pts.toFixed(3)}초 · 첫 박스 ${JSON.stringify(birth.first_actual_bbox)} · 판단 시 실제 박스 ${JSON.stringify(birth.current_actual_bbox)}` : '';
        const portalInfo = birth?.birth_site?.geometry_kind === 'projected_gate_emergence_v1' ? ` · 구역 내 중심 (portal_center_inside) ${birth.birth_site.portal_center_inside} · 박스 겹침 (portal_box_overlap) ${birth.birth_site.portal_box_overlap}` : '';
        entry.list.append(node('li', `${candidateKind}${event.decision_time_pts.toFixed(3)}초 · ${ref.source_pointer}${birthInfo}${portalInfo} · raw ID ${show(ref.raw_id)} · segment ${show(ref.segment)} · event ${eventId}${isComparison41 && card.review_only_event_ids.includes(eventId) ? ' · 검토 전용' : ''}`));
      }
    }
  }
  async function notify(item, epoch) {
    if (pending.has(item.notification_key)) return;
    pending.add(item.notification_key);
    try {
      const response = await fetch(`/api/incidents/${id}/claim`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({notification_key: item.notification_key})});
      const receipt = response.ok ? await response.json() : null;
      if (receipt?.claimed && epoch === generation && holder.isConnected && !video.paused && !video.seeking) {
        toast.textContent = `침입 의심 · ${item.card.gate_id}`; toast.hidden = false;
        toast.dataset.paintedCount = String(Number(toast.dataset.paintedCount) + 1);
        toast.dataset.notificationKey = item.notification_key;
        toast.dispatchEvent(new CustomEvent('incident-toast-painted', {bubbles: true, detail: {notificationKey: item.notification_key}}));
        clearTimeout(timer); timer = setTimeout(() => { toast.hidden = true; }, 3000);
      }
    } catch { /* no delivery claim on network error */ }
    finally { pending.delete(item.notification_key); }
  }
  video.addEventListener('seeking', () => { generation++; previous = Math.max(start, Math.min(end, mediaStart + video.currentTime)); render(previous); });
  video.addEventListener('seeked', () => { previous = Math.max(start, Math.min(end, mediaStart + video.currentTime)); render(previous); });
  video.addEventListener('timeupdate', () => {
    const pts = Math.max(start, Math.min(end, mediaStart + video.currentTime));
    if (!video.paused && !video.seeking && pts >= previous) {
      for (const item of data.timeline) {
        if ((data.notification_enabled ?? (id === '007' || id === '030')) && item.notify && item.decision_time_pts > previous + 1e-9 && item.decision_time_pts <= pts + 1e-9) notify(item, generation);
      }
    }
    previous = pts; storageSet(`incident-time:${stateId}`, String(video.currentTime)); render(pts);
  });
  render(Math.max(start, Math.min(end, mediaStart + video.currentTime)));
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
function catalogItems(data) {
  const items = new Map();
  (data.experiments || []).forEach(result => items.set(result.experiment_id, {id: result.experiment_id, result}));
  (data.assignments || []).forEach(assignment => {
    const existing = items.get(assignment.experiment_id);
    if (!existing) items.set(assignment.experiment_id, {id: assignment.experiment_id, assignment});
    else if (!existing.assignment || assignment.slot === existing.result?.slot) existing.assignment = assignment;
  });
  const timestamp = item => Date.parse(item.result?.created_at || item.assignment?.assigned_at || '') || 0;
  return [...items.values()].sort((a, b) => timestamp(b) - timestamp(a) || b.id.localeCompare(a.id, undefined, {numeric:true}));
}
function filteredItems(data, query, status) {
  const search = query.trim().toLocaleLowerCase();
  return catalogItems(data).filter(item => {
    const text = `${item.id} ${item.result?.title || item.assignment?.title || ''}`.toLocaleLowerCase();
    return (!search || text.includes(search)) && (status === 'all' || (item.result ? 'registered' : 'pending') === status);
  });
}
function renderChoices() {
  const nav = $('#experiments'); nav.replaceChildren();
  const items = filteredItems(catalogData, $('#experiment-search').value, $('#experiment-status').value);
  $('#experiment-count').textContent = `${items.length}개 실험 · 최신 등록순 (날짜는 기록 시각)`;
  if (!items.length) nav.append(node('p', '조건에 맞는 실험이 없습니다.', 'muted'));
  items.forEach(item => {
    const button = node('button', undefined, 'experiment-card'); button.dataset.id = item.id;
    button.dataset.slot = item.result?.slot || item.assignment?.slot || 'unassigned';
    button.dataset.result = item.result ? 'registered' : 'pending';
    button.setAttribute('aria-pressed', String(item.id === selectedReport));
    button.append(node('span', `${item.assignment?.synthetic || item.result?.synthetic ? 'TEST · ' : ''}${item.id}`, 'experiment-id'),
      node('strong', show(item.result?.title || item.assignment?.title)),
      node('span', item.result ? '결과 등록' : '결과 미등록', 'result-badge'));
    const date = item.result?.created_at || item.assignment?.assigned_at;
    if (date) button.append(node('span', `기록 ${date.slice(0, 10)}`, 'muted'));
    button.addEventListener('click', () => {
      selectedSlot = button.dataset.slot;
      item.result ? selectReport(item.id) : selectPending(item.id);
      renderChoices();
    });
    nav.append(button);
  });
}
function selectPending(id) {
  selectionRequest++; selectedReport = id; storageSet('selected-report', id); storageSet('selected-slot', selectedSlot); loadedFingerprint = null; pendingRefresh = false;
  const assignment = (catalogData.assignments || []).find(x => x.slot === selectedSlot && x.experiment_id === id);
  const detail = $('#detail'); detail.dataset.id = id; detail.dataset.result = 'pending';
  delete detail.dataset.executionStatus;
  const taskState = node('p', `배정 상태: ${observationText(nativeObservation(assignment, statusData))}`, 'muted');
  taskState.dataset.pendingObservation = 'true';
  detail.replaceChildren(node('p', `${assignment?.synthetic ? 'TEST · ' : ''}${id}`, 'eyebrow'),
    node('h2', show(assignment?.title)), node('p', '결과가 아직 등록되지 않았습니다. 실험 실행·검토·결정 상태는 미확인입니다.'),
    taskState);
  if (id === 'EXP-0036') addIncidentFlows(detail, selectionRequest);
  if (id === 'EXP-0037' || id === 'EXP-0040' || id === 'EXP-0041' || id === 'EXP-0042' || id === 'EXP-0044' || id === 'EXP-0045' || id === 'EXP-0046' || id === 'EXP-0047' || id === 'EXP-0048' || id === 'EXP-0049') addFinishFlows(detail, selectionRequest, id);
  renderChoices();
}
function updatePendingObservation() {
  const detail = $('#detail');
  if (detail.dataset.result !== 'pending') return;
  const target = detail.querySelector('[data-pending-observation]');
  const assignment = (catalogData.assignments || []).find(x => x.slot === selectedSlot && x.experiment_id === selectedReport);
  if (target) target.textContent = `배정 상태: ${observationText(nativeObservation(assignment, statusData))}`;
}
function refreshSelectedIfChanged() {
  if (!selectedReport) return;
  const result = (catalogData.experiments || []).find(x => x.experiment_id === selectedReport);
  if (result) selectedSlot = result.slot;
  if (!result) { if (loadedFingerprint !== null) selectPending(selectedReport); return; }
  if (JSON.stringify(result) === loadedFingerprint) return;
  const hasMedia = $('#detail').querySelector('video');
  if (hasMedia) { pendingRefresh = true; return; }
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
      const items = catalogItems(catalogData);
      const chosen = items.find(x => x.id === storageGet('selected-report')) || items[0];
      renderChoices();
      if (chosen) {
        selectedSlot = chosen.result?.slot || chosen.assignment?.slot || 'unassigned';
        chosen.result ? selectReport(chosen.id) : selectPending(chosen.id);
        renderChoices();
      }
    } else { renderChoices(); refreshSelectedIfChanged(); }
  } else if (!catalogData) $('#detail').textContent = '카탈로그를 불러올 수 없습니다.';
  else {
    statusData = {};
    $('#status').textContent += ' · 목록 조회 실패: 이전 목록, 작업 상태 미확인';
    renderChoices();
  }
  if (catalogData && selectedReport && !resultFor(catalogData, selectedSlot, selectedReport) && $('#detail').dataset.result !== 'pending') selectPending(selectedReport);
  if (catalogData && selectedReport) updatePendingObservation();
}
if (typeof module !== 'undefined') module.exports = {nativeObservation, resultFor, slotItems, observationText, catalogItems, filteredItems, isInputSheet, evidencePriority, reviewWarning};
if (typeof document !== 'undefined') {
  document.addEventListener('pause', event => { if (event.target.tagName === 'VIDEO' && pendingRefresh) refreshSelectedIfChanged(); }, true);
  document.addEventListener('ended', event => { if (event.target.tagName === 'VIDEO' && pendingRefresh) refreshSelectedIfChanged(); }, true);
  $('#experiment-search').addEventListener('input', () => { if (catalogData) renderChoices(); });
  $('#experiment-status').addEventListener('change', () => { if (catalogData) renderChoices(); });
  addFinishFlows($('#mvp-view'), selectionRequest, 'MVP-0002');
  refresh(); setInterval(refresh, 15000);
}
