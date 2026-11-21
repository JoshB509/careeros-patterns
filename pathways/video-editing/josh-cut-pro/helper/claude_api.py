"""Minimal Claude API client (standard library only, streaming)."""
import json, os, re, threading, time, urllib.request, urllib.error

API_URL = os.environ.get('DAJOSHI_CLAUDE_URL', 'https://api.anthropic.com/v1/messages')


class ClaudeError(Exception):
    pass


# Dollars per million tokens: input, output, cache write (5 minute), cache hit.
# From platform.claude.com/docs/en/about-claude/pricing, October 2026.
PRICES = {
    'claude-fable-5-1': (10.0, 50.0, 12.5, 0.25),
    'claude-opus-5-5': (4.0, 20.0, 5.0, 0.20),
    'claude-sonnet-5-5': (2.0, 10.0, 2.5, 0.10),
    'claude-haiku-5-5': (0.10, 0.50, 0.125, 0.01),
}
HAIKU_LONG = (0.50, 2.50, 0.625, 0.05)  # Haiku prompts over 100,000 tokens

_METER = dict(lock=threading.Lock(), calls=[])


def cost_of(model, usage):
    inp = usage.get('input_tokens', 0); out = usage.get('output_tokens', 0)
    cw = usage.get('cache_creation_input_tokens', 0) or 0; cr = usage.get('cache_read_input_tokens', 0) or 0
    price = PRICES.get(model)
    if price is None:
        price = next((v for k, v in PRICES.items() if model.startswith(k.rsplit('-', 2)[0])), PRICES['claude-opus-5-5'])
    if model.startswith('claude-haiku') and inp + cw + cr > 100000:
        price = HAIKU_LONG
    return (inp * price[0] + out * price[1] + cw * price[2] + cr * price[3]) / 1e6


REPLY_DIR = None   # set by the helper: every raw reply is kept here, newest 40


def keep_reply(model, text):
    """Save a raw reply, so a reply that can't be read can be looked at and isn't paid for twice."""
    if not REPLY_DIR: return
    try:
        os.makedirs(REPLY_DIR, exist_ok=True)
        name = os.path.join(REPLY_DIR, '%s-%s.txt' % (time.strftime('%Y%m%d-%H%M%S'), model))
        with open(name, 'w', encoding='utf-8') as f: f.write(text)
        old = sorted(os.listdir(REPLY_DIR))
        for n in old[:-40]: os.remove(os.path.join(REPLY_DIR, n))
    except Exception:
        pass


def meter_reset():
    with _METER['lock']: _METER['calls'] = []


def meter_total():
    """What Claude has cost since the last reset: dollars, calls and token counts."""
    with _METER['lock']: calls = list(_METER['calls'])
    tok = lambda k: sum(c['usage'].get(k, 0) or 0 for c in calls)
    return dict(dollars=round(sum(c['dollars'] for c in calls), 4), calls=len(calls),
                input_tokens=tok('input_tokens'), output_tokens=tok('output_tokens'),
                cache_write_tokens=tok('cache_creation_input_tokens'), cache_read_tokens=tok('cache_read_input_tokens'),
                models=sorted({c['model'] for c in calls}))


def _record(model, usage):
    with _METER['lock']:
        _METER['calls'].append(dict(model=model, usage=usage, dollars=cost_of(model, usage)))


def call(api_key, model, system, user, max_tokens=16000, temperature=None, cache_system=True, on_progress=None, timeout=900):
    """Send one message and return the full text reply. Retries transient errors."""
    if not api_key:
        raise ClaudeError('No Claude API key saved. Add it in the panel settings first.')
    sys_blocks = [{'type': 'text', 'text': system}]
    if cache_system:
        sys_blocks[0]['cache_control'] = {'type': 'ephemeral'}
    body = {'model': model, 'max_tokens': max_tokens, 'system': sys_blocks, 'stream': True,
            'messages': [{'role': 'user', 'content': user}]}
    if temperature is not None:
        body['temperature'] = temperature
    data = json.dumps(body).encode('utf-8')
    last = None
    for attempt in range(4):
        req = urllib.request.Request(API_URL, data=data, method='POST', headers={
            'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
        try:
            text, usage, stop = _stream(req, timeout, on_progress)
            if usage: _record(model, usage)
            if not text:
                raise ClaudeError('Claude API stream ended without any text')
            keep_reply(model, text)
            if stop == 'max_tokens':
                raise ClaudeError('Claude ran out of room before finishing (max_tokens). Try again or raise the limit in config.json.')
            return text
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'replace')[:600]
            last = ClaudeError('Claude API error %s: %s' % (e.code, detail))
            if e.code in (400, 401, 403, 404):
                raise last
        except (urllib.error.URLError, TimeoutError, ConnectionError, ClaudeError) as e:
            last = e if isinstance(e, ClaudeError) else ClaudeError('Could not reach the Claude API: %s' % e)
            if isinstance(e, ClaudeError) and 'overloaded' not in str(e).lower() and 'stream ended' not in str(e).lower():
                raise
        time.sleep(4 * (attempt + 1))
    raise last


def _stream(req, timeout, on_progress):
    parts, stop, usage = [], None, {}
    received = 0
    with urllib.request.urlopen(req, timeout=timeout) as res:
        for raw in res:
            line = raw.decode('utf-8', 'replace').strip()
            if not line.startswith('data:'):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            ev = json.loads(payload)
            kind = ev.get('type')
            if kind == 'content_block_delta' and ev['delta'].get('type') == 'text_delta':
                parts.append(ev['delta']['text']); received += len(ev['delta']['text'])
                if on_progress and received % 4000 < len(ev['delta']['text']):
                    on_progress(received)
            elif kind == 'message_start':
                usage.update(ev.get('message', {}).get('usage') or {})
            elif kind == 'message_delta':
                stop = ev.get('delta', {}).get('stop_reason')
                usage.update(ev.get('usage') or {})
            elif kind == 'error':
                raise ClaudeError('Claude API error: %s' % ev.get('error', {}).get('message', ev))
    return ''.join(parts), usage, stop


def _fix_svgs(text, drop=False):
    """Re-escape every SVG string, or empty it. A double quote inside an SVG attribute breaks the JSON around it."""
    out, pos = [], 0
    for m in re.finditer(r'"(sketch_svg|svg)"\s*:\s*"', text):
        if m.start() < pos: continue
        end = text.find('</svg>', m.end())
        if end < 0: continue
        close = text.find('"', end + 6)
        if close < 0: continue
        body = text[m.end():end + 6]
        body = body.replace('\\"', '"').replace('\\n', '\n')
        out.append(text[pos:m.end()])
        out.append('' if drop else body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', ''))
        pos = close
    out.append(text[pos:])
    return ''.join(out)


def _no_trailing_commas(text):
    return re.sub(r',\s*([}\]])', r'\1', text)


def extract_json(text, salvage=None, need=None):
    """Pull the JSON object out of a reply, tolerating code fences or a sentence around it.

    If it doesn't parse, it's repaired here for free before giving up: line breaks inside strings are allowed,
    SVG sketches are re-escaped, stray commas go, and then the sketches are dropped. With salvage set to a key
    such as 'animations', every object in that list that still parses and has the field need is kept."""
    m = re.search(r'```(?:json)?\s*(\{.*\})\s*```', text, re.S)
    candidate = m.group(1) if m else text[text.find('{'): text.rfind('}') + 1]
    first = None
    for fix in (lambda t: t, _fix_svgs, lambda t: _no_trailing_commas(_fix_svgs(t)), lambda t: _no_trailing_commas(_fix_svgs(t, drop=True))):
        try:
            return json.loads(fix(candidate), strict=False)
        except Exception as e:
            first = first or e
    if salvage:
        kept = []
        for drop in (False, True):   # keep the sketches if the rest still parses with them
            kept = [o for o in _salvage(_no_trailing_commas(_fix_svgs(candidate, drop=drop)), salvage) if not need or need in o]
            if kept: break
        if kept: return {salvage: kept, 'salvaged': True}
    raise ClaudeError('Claude replied, but not with valid JSON (%s). Start of reply: %s' % (first, text[:300]))


def _salvage(text, key):
    """Every object in the list under key that parses on its own."""
    start = text.find('"%s"' % key)
    if start < 0: return []
    i = text.find('[', start)
    dec, kept = json.JSONDecoder(strict=False), []
    while i >= 0:
        i = text.find('{', i + 1)
        if i < 0: break
        try:
            obj, end = dec.raw_decode(text, i)
            if isinstance(obj, dict): kept.append(obj); i = end - 1
        except Exception:
            continue
    return kept


def extract_section(text):
    m = re.search(r'<section\b.*</section>', text, re.S)
    if not m:
        raise ClaudeError('Claude did not return a <section> for the animation. Start of reply: %s' % text[:300])
    return m.group(0)
