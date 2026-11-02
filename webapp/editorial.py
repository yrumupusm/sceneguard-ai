"""Reviewed, source-bound editorial examples; never modifies experiment records."""
import hashlib


def enrich(source, item, result):
    if item.get('experiment_id') != 'EXP-0049' or hashlib.sha256(source.encode()).hexdigest() != '5a7dd42983f42f8b2267b7e480bcdc2421e276fd70b1d95d0f21d277f0fbe855':
        return result
    result = dict(result)
    result.update(
        purpose='문 주변에서 계속 이어지는 한 상황이 여러 사건 카드와 반복 의심 알림으로 나뉘는 문제를 줄이고자 했다.',
        change='EXP-0048의 개별 침입·해제 판단은 유지했다. 현재 문 주변의 실제 관측이 있으면 사건을 유지하고, 관측이 3초간 없을 때 관찰을 종료하도록 사건 묶음만 바꿨다.',
        limitations='007·030의 이미 검토한 개발 구간 비교다. 카드 감소는 침입 검출 정확도 향상이 아니다. 실제 해제 사례가 없어 해제 성능은 미검증이다. 오검출이 사건을 오래 유지하거나 검출 공백이 사건을 나눌 수 있다.',
        comparisons=[{'title': f'{video} 사건 카드', 'unit': '개', 'scope': '같은 저장 관측·같은 선택 구간. 카드 수는 사람 수나 정확도가 아님.', 'values': [{'label': 'EXP-0048', 'value': 2}, {'label': 'EXP-0049', 'value': 1}]} for video in ['007', '030']],
    )
    return result
