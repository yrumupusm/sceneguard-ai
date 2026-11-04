"""Display-only metric localization; never rewrites measured values or records."""
import json
from pathlib import Path

SCOPES = json.loads(Path(__file__).with_name('metric_scopes_ko.json').read_text())
UNITS = {
    'count': '개', 'seconds': '초', 's': '초', 'boxes': '박스', 'box': '박스',
    'frames': '프레임', 'frame': '프레임', 'cards': '카드', 'rows': '행',
    'candidates': '후보', 'candidate': '후보', 'token': '토큰', 'tokens': '토큰',
    'GiB': 'GiB', 'MiB': 'MiB', 'bytes': '바이트', 'ms': '밀리초',
    'window': '시간창', 'windows': '시간창', 'ratio': '비율', 'fraction': '비율',
    'estimated joints': '추정 관절', 'source_seconds': '원본 초', 'evidence': '근거',
    'view conditions': '보기 조건', 'heuristic_score': '규칙 점수', '%': '%',
    'runs': '실행', 'videos': '영상', 'seconds/frame': '초/프레임', 'calls': '호출',
    'cases': '사례', 'notices': '알림', 'events': '사건', 'clip': '클립', 'clips': '클립',
    'frame/s': '프레임/초', 'fps': '프레임/초', 'seconds/window': '초/시간창',
    'forwards': '순전파', 'IDs': '추적 ID', 'reconnections': '재연결',
    'incidents': '사건', 'results': '결과', 'rule_decisions': '규칙 판정',
    'observation runs': '관측열', 'intents': '알림 의도', 'source': '원본', 'sources': '원본',
    'test cases': '시험 사례', 'tests': '시험', 'test': '시험',
    'seconds/load': '초/적재', 'loads': '적재', 'patches': '패치',
    'embeddings': '외형 특징', 'handoffs': '관측 인계', 'source proposals': '원본 후보',
    'rule confirmations': '규칙 확인', 'audit_rows': '감사 행', 'jobs': '작업',
    'gate_seconds': '문 주변 관찰 초', 'variants': '설정', 'epoch': '학습 회차',
    'per hour': '회/시간', 'notices/hour': '알림/시간', 'wall/source': '실행 시간/원본 시간',
    'not_closed': '미종료', 'unmeasured': '', 'not established': '',
    'unevaluated': '', 'not measured': '',
    # Later reports already store localized units; preserve their display verbatim.
    '건': '건', '개': '개', '초': '초', '미측정': '미측정',
    '원본 초': '원본 초', '비율': '비율', '프레임': '프레임',
    '회': '회', 'px': 'px', '배': '배',
}


def label_ko(label):
    text = str(label or '이름 없는 측정값')
    text = text.replace('공식 사건 TP', '공식 기준 잡은 사건')
    text = text.replace('공식 사건 FP', '공식 기준 잘못 잡은 사건')
    text = text.replace('공식 사건 FN', '공식 기준 놓친 사건')
    return text.replace('Final behavior FPR', '최종 행동 오탐률')


def group_title(scope, metrics):
    # Headings organize reading; the exact translated scope below supplies meaning.
    if scope.startswith('Official reference'):
        return '공식 사건 기준 평가'
    if any(s in scope for s in ('whole-source execution', 'Whole original execution', 'Whole-source inventory')):
        return '실행 현황'
    if any(s in scope for s in ('false first notices', 'First notification intents', 'not deployment estimate', 'not proof of operational safety')):
        return '정상 구간의 첫 알림'
    units = {m.get('unit') for m in metrics}
    if units <= {'s', 'seconds', 'ms', 'seconds/frame', 'seconds/window', 'seconds/load', 'wall/source'}:
        return '처리 시간과 비용'
    if units <= {'GiB', 'MiB', 'bytes'}:
        return '메모리와 저장량'
    if all(m.get('value') is None for m in metrics):
        return '미측정 항목'
    return '측정 조건'


def metric_groups(metrics):
    groups = {}
    for m in metrics:
        scope = m.get('scope') or '측정 범위가 기록되지 않았습니다.'
        group = groups.setdefault(scope, {'scope': scope, 'scope_text': SCOPES.get(scope, scope), 'metrics': []})
        group['metrics'].append(dict(m, display_label=label_ko(m.get('label')),
                                      display_unit=UNITS.get(m.get('unit'), m.get('unit') or '')))
    for group in groups.values():
        group['title'] = group_title(group['scope'], group['metrics'])
    return list(groups.values())
