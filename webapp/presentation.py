"""Conservative, read-only prose excerpts for the experiment viewer.

This is a presentation adapter, not an evaluator or an abstractive summarizer.
Markdown is parsed locally; references are never fetched or treated as evidence
that a method was applied. Original documents and catalog values stay untouched.
"""
import ipaddress
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


UNAVAILABLE = {
    'purpose': '자동 발췌에서 목적·가설을 확인하지 못했습니다.',
    'change': '자동 발췌에서 변경·설정을 확인하지 못했습니다.',
    'conclusion': '카탈로그에 결론 요약이 기록되지 않았습니다.',
    'limitations': '자동 발췌에서 원문·카탈로그의 한계를 확인하지 못했습니다.',
    'next_steps': '자동 발췌에서 원문·카탈로그의 다음 단계를 확인하지 못했습니다.',
}
APPLICATION_UNAVAILABLE = '자동 발췌에서는 적용 맥락을 확인하지 못했습니다.'
EVIDENCE_NOTE = (
    '목적·변경은 원문의 해당 절에서 발췌했습니다. 결론은 등록된 카탈로그 요약이며, '
    '한계·다음 단계는 해당 절이 없으면 카탈로그 기록을 사용합니다. '
    '목적·변경 절이 없는 경우 원문 도입부를 별도로 표시할 수 있습니다. '
    '코드·표·해시·내부 경로는 생략하며 발췌에 모든 조건과 한계가 포함되지는 않습니다. '
    '참고 링크는 원문 인용이며 외부 내용·적용 여부를 검증하지 않았습니다. '
    '전체 원문·측정치·출처 무결성·검토 상태를 함께 확인하세요.'
)
_HEADINGS = {
    'purpose': re.compile(r'목적|가설|질문|\b(?:purpose|hypothesis|objective|question)\b', re.I),
    'change': re.compile(r'변경|바뀐|설정|고정.*(?:조건|입력|방법|변화)|비교 조건|데이터·설정|'
                         r'방법과 사전 선택|고정한 방법|고정 방식|실행 전 고정|비교 구성|'
                         r'\b(?:change[sd]?|setup|configuration|frozen comparison)\b', re.I),
    'limitations': re.compile(r'한계|제한|\b(?:limits?|limitations?|caveats?)\b', re.I),
    'next_steps': re.compile(r'다음|남은 (?:작업|결정|확인|전달|검수)|'
                             r'\b(?:next(?: steps?)?|remaining work|future work)\b', re.I),
}
_TECHNICAL_HEADING = re.compile(r'실행 명령|해시|재현|\b(?:commands?|hash|reproduction)\b', re.I)
_URL = re.compile(r'https?://[^\s<>\[\]"\u0000-\u001f]+', re.I)
_HASH = re.compile(r'\b(?=[0-9a-f]{7,64}\b)(?=[0-9a-f]*[a-f])[0-9a-f]+\b', re.I)
# Restrict to recognizable file paths; numeric ratios such as 6/7 are prose.
_PATH = re.compile(
    r'(?<!\w)(?:[A-Za-z]:[\\/]|(?:\.{0,2}/)|'
    r'(?:docs|records|runtime|outputs|data|configs|scripts|webapp|tests|sceneguard|orchestration)[\\/])[^\s,;<>]+|'
    r'\b[A-Za-z_.][\w.-]*(?:/[\w.-]+)+/|'
    r'\b[\w.-]+(?:/[\w.{}-]+)+\.(?:jsonl?|md|py|mp4|png|jpe?g|ya?ml|txt)\b', re.I)
_COMMAND = re.compile(r'^\s*(?:\$\s|python[\d.]*\s|pip\s|git\s|curl\s|uvicorn\s|orca-ide\s)', re.I)


def _clean(text):
    if re.search(r'<\s*/?\s*[a-zA-Z][^>]*>|\b(?:javascript|vbscript|data|file):', text, re.I):
        return ''
    text = _URL.sub('', text)
    text = _PATH.sub('', text)
    text = _HASH.sub('', text)
    text = ''.join(c for c in text if not unicodedata.category(c).startswith('C') or c.isspace())
    text = re.sub(r'\s+', ' ', text).strip(' \t:：;；·,，-—')
    return text if re.search(r'[^\W\d_]', text) else ''


def _plain(inline):
    """Skip raw HTML paragraphs entirely, including script bodies and attributes."""
    children = inline.children or []
    if any(t.type == 'html_inline' for t in children):
        return ''
    def content(token):
        if token.type == 'text':
            return token.content
        if token.type == 'code_inline':
            # State names, model names and literal values carry meaning. Keep
            # these; omit executable expressions, paths, commands and hashes.
            if re.search(r'[;{}()]', token.content) or _COMMAND.match(token.content):
                return ' '
            if re.fullmatch(r'[-+]?\d+(?:[.,]\d+)*(?:%|[eE][-+]?\d+)?', token.content.strip()):
                return token.content.strip()
            return _clean(token.content) or ' '
        return ' ' if token.type in ('softbreak', 'hardbreak') else ''
    value = ''.join(content(t) for t in children)
    return '' if _COMMAND.match(value) else _clean(value)


def _excerpt(blocks):
    """Keep complete blocks, never cut a sentence before its qualification."""
    selected = []
    for block in blocks:
        if not block or block in selected:
            continue
        if len(block) > 1200:
            continue
        if selected and sum(map(len, selected)) + len(block) > 1200:
            break
        selected.append(block)
        if len(selected) == 3:
            break
    return ' '.join(selected)


def _safe_external_url(value):
    """Accept explicit public HTTP(S) destinations without credentials or controls."""
    try:
        decoded = unquote(value)
        if any(c.isspace() or unicodedata.category(c).startswith('C') for c in decoded):
            return None
        if any(c in value for c in '<>"\\'):
            return None
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower().rstrip('.')
        if parsed.scheme.lower() not in ('http', 'https') or not host or parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port is not None and not 0 < parsed.port < 65536:
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            if ('.' not in host or host.endswith(('.localhost', '.local', '.internal', '.test', '.invalid'))
                    or all(re.fullmatch(r'(?:\d+|0x[0-9a-f]+)', part) for part in host.split('.'))):
                return None
            if not re.fullmatch(r'[a-z0-9.-]+', host) or any(not p or p.startswith('-') or p.endswith('-') for p in host.split('.')):
                return None
        return value
    except ValueError:
        return None


def _references(tokens):
    references, seen = [], set()

    def add(url, label='', context=''):
        url = _safe_external_url(url)
        if not url or url in seen:
            return
        seen.add(url)
        application = APPLICATION_UNAVAILABLE
        if context and len(context) <= 1200 and re.search(
                r'사용|적용|구현|가져|수정|변경|재사용|\b(?:applied|adapted|vendored|implemented|used)\b', context, re.I):
            application = '원문 맥락: ' + context
        references.append({'label': _clean(label) or urlsplit(url).hostname,
                           'url': url, 'application': application})

    for token in tokens:
        if token.type != 'inline' or any(t.type == 'html_inline' for t in token.children or []):
            continue
        children = token.children or []
        context = _plain(token)
        in_link = False
        for index, child in enumerate(children):
            if child.type == 'link_open':
                in_link = True
                label = []
                for following in children[index + 1:]:
                    if following.type == 'link_close':
                        break
                    if following.type == 'text':
                        label.append(following.content)
                add(child.attrGet('href') or '', ''.join(label), context)
            elif child.type == 'link_close':
                in_link = False
            elif child.type == 'text' and not in_link:
                for match in _URL.finditer(child.content):
                    add(match.group().rstrip('.,;:!?)]}'), context=context)
    return references


def presentation(source, item):
    """Return an optional API projection without changing either input."""
    md = MarkdownIt('commonmark', {'html': True, 'linkify': False}).enable('table')
    tokens = md.parse(source)
    blocks = {key: [] for key in _HEADINGS}
    headings, table_depth, list_depth = [], 0, 0
    introduction = []
    saw_section = False
    for index, token in enumerate(tokens):
        if token.type == 'heading_open':
            level = int(token.tag[1:])
            saw_section = saw_section or level >= 2
            title = _plain(tokens[index + 1])
            # The report title identifies the experiment; it is not a section
            # and must not turn following worker/date metadata into a synopsis.
            fields = [field for field, pattern in _HEADINGS.items() if pattern.search(title)] if level >= 2 else []
            while headings and headings[-1][0] >= level:
                headings.pop()
            # A nested command/reproduction section must not leak into its parent.
            if not fields and _TECHNICAL_HEADING.search(title):
                fields = ['technical']
            headings.append((level, fields))
        elif token.type == 'table_open':
            table_depth += 1
        elif token.type == 'table_close':
            table_depth -= 1
        elif token.type in ('bullet_list_open', 'ordered_list_open'):
            list_depth += 1
        elif token.type in ('bullet_list_close', 'ordered_list_close'):
            list_depth -= 1
        elif token.type == 'inline' and not table_depth and (index == 0 or tokens[index - 1].type != 'heading_open'):
            fields = next((fields for _, fields in reversed(headings) if fields), [])
            value = _plain(token)
            if not saw_section and not list_depth and re.search(
                    r'비교|관찰|확인|실행|모델|평가|목적|가설|\b(?:model|experiment|comparison|baseline)\b', value, re.I):
                introduction.append(value)
            for field in fields:
                if field in blocks and value:
                    blocks[field].append(value)

    def catalog_prose(value):
        if not isinstance(value, str):
            return ''
        parsed = md.parse(value)
        # Catalog prose can contain untrusted Markdown too; tables/code/HTML
        # are not a fallback route around report sanitization.
        table = False
        values = []
        for token in parsed:
            if token.type == 'table_open':
                table = True
            elif token.type == 'table_close':
                table = False
            elif token.type == 'inline' and not table:
                values.append(_plain(token))
        return _excerpt(values)

    result = {key: _excerpt(value) for key, value in blocks.items()}
    result['conclusion'] = catalog_prose(item.get('summary'))
    limits = item.get('limitations')
    if not result['limitations'] and isinstance(limits, list):
        result['limitations'] = _excerpt([catalog_prose(value) for value in limits])
    if not result['next_steps']:
        result['next_steps'] = catalog_prose(item.get('next_step'))
    for key, fallback in UNAVAILABLE.items():
        result[key] = result[key] or fallback
    intro = _excerpt(introduction[:1])
    if intro:
        for key in ('purpose', 'change'):
            if result[key] == UNAVAILABLE[key]:
                result[key] += ' 원문 도입부: ' + intro
                break
    result['references'] = _references(tokens)
    result['evidence_note'] = EVIDENCE_NOTE
    return result
