"""Drive the helper through clean cut, flubs, animations and a recut, and check the layers come back.

The panel isn't involved, so this applies each cut to a list of timeline spans itself, the same way the
panel cuts the open sequence in place, and sends the new spans with the next request.

Run a helper on a spare port with a mock Claude first, for example:
  set DAJOSHI_CUT_PORT=47821 & set DAJOSHI_CUT_PROJECTS=<empty folder> & set DAJOSHI_CUT_STYLES=<empty folder>
  set DAJOSHI_CLAUDE_URL=http://127.0.0.1:47999/v1/messages
  python helper\\dajoshi_cut.py --serve
then: python tests\\layers-flow.py 47821
"""
import json, sys, time, urllib.request
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 47821
HERE = Path(__file__).resolve().parent
VIDEO = str(HERE / 'sample-5min.mp4')
TIMELINE = [dict(start=0.0, **{'in': 0.0, 'out': 280.0})]
BASE = dict(video=VIDEO, audio=None, audio_offset=None, range=[0, 280], name='Sequence 01',
            transcript=str(HERE / 'sample-5min-transcript.json'))


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request('http://127.0.0.1:%d%s' % (PORT, path), data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(r, timeout=1200) as f: return json.loads(f.read())


def run(stage, **extra):
    t0 = time.time()
    job = call('/run', dict(BASE, stage=stage, spans=TIMELINE, **extra))['job']
    while True:
        time.sleep(1); v = call('/job/' + job)
        if v['state'] not in ('running', 'queued'): break
    if v['state'] != 'complete': raise SystemExit('%s failed: %s\n%s' % (stage, v['error'], '\n'.join(v['log'])))
    print('%-9s %5.1fs  %s' % (stage, time.time() - t0, v['message']))
    return v['result'], v['log']


def cut(spans, remove):
    """What the panel does to the open sequence: take the source ranges out and close the gaps."""
    pieces = []
    for sp in spans:
        parts = [[sp['in'], sp['out']]]
        for a, b in remove:
            parts = [q for x, y in parts for q in ([[x, y]] if b <= x or a >= y else [[x, a]] * (a > x) + [[b, y]] * (b < y))]
        pieces += [p for p in parts if p[1] - p[0] > 1 / 30.0]
    out, t = [], 0.0
    for x, y in pieces:
        out.append(dict(start=round(t, 4), **{'in': x, 'out': y})); t += y - x
    return out


def check(cond, what):
    print(('  ok    ' if cond else '  FAIL  ') + what)
    if not cond: check.failed = True
check.failed = False


call('/prefs', dict(keep_layers=True, animations_own_sequence=False))
run('prepare')
r, _ = run('silences', settings=dict(preset='paced'))
check(r['remove'] and r['cuts'] > 5 and not r['has_layers'], 'a first clean cut returns what to remove and has no layers (%d cuts)' % r['cuts'])
TIMELINE = cut(TIMELINE, r['remove'])
run('flubs')
flubs = call('/flubs?video=' + urllib.request.quote(VIDEO))
r, _ = run('apply', removed=flubs['proposed'])
check(r['remove'] and r['words'] == len(flubs['proposed']), 'flubs return only the flub words to remove (%d ranges)' % len(r['remove']))
TIMELINE = cut(TIMELINE, r['remove'])

ANIM = dict(types=['full', 'pip', 'half'], often='medium', rich='designed', style='josh-house',
            pip_shape='tall-box', pip_side='right', half_side='left')
run('shotlist', instructions='', anim=ANIM)
r, log = run('build', anim=ANIM)
lay = r.get('layers') or []
anims = [l for l in lay if l['kind'] == 'animation']; cams = [l for l in lay if l['kind'] == 'camera_copy']
check(len(anims) >= 4 and all(l['track'] == 4 for l in anims), '%d animation clips on V5' % len(anims))
check(cams and all(l['track'] == 3 and l.get('framing') for l in cams), '%d camera copies on V4 with framing' % len(cams))
check(all(Path(l['path']).exists() for l in anims), 'every animation clip was rendered')
kinds = {l['name'].split(' press')[0]: Path(l['path']).suffix for l in anims}
check(sorted(kinds.values()) == ['.mov', '.mov', '.mp4'], 'PiP and half and half render with alpha, full screen without (%s)' % kinds)
end = sum(s['out'] - s['in'] for s in TIMELINE) * 30
check(all(0 <= l['start_f'] and l['start_f'] + l['out_f'] - l['in_f'] <= end + 1 for l in lay), 'layers sit inside the cut')
before = {(l['name']): l['start_f'] for l in anims}

r2, _ = run('silences', settings=dict(preset='energetic'))
check(r2['has_layers'], 'a second clean cut knows there are layers to put back')
TIMELINE = cut(TIMELINE, r2['remove'])
r3, log3 = run('layers')
anims2 = [l for l in r3['layers'] if l['kind'] == 'animation']
check(len(anims2) == len(anims), 'the layers job puts every animation back (%d)' % len(anims2))
check(r3.get('layer_note', '').startswith('Put back'), 'the toast says so: "%s"' % r3.get('layer_note'))
check(any(before[l['name']] != l['start_f'] for l in anims2 if l['name'] in before), 'the animations moved with the new cut')
check(not any('Rendering animation' in x for x in log3), 'the recut reused the cached renders')

plan = call('/project?video=' + urllib.request.quote(VIDEO))['shotlist']['animations']
pip_no = next(a['number'] for a in plan if a['type'] == 'pip')
pip_presses = sum(1 for l in anims2 if l['name'].startswith('Animation %d ' % pip_no))
r5, log5 = run('build', anim=dict(ANIM, pip_shape='large-circle', pip_side='left'))
rendered = [x for x in log5 if 'Rendering animation' in x]
check(len(rendered) == pip_presses and all('animation %d,' % pip_no in x for x in rendered),
      'a new PiP shape re-renders only the PiP presses (%d of %d)' % (len(rendered), len(anims2)))
check(not any('Claude cost' in x for x in log5), 'and Claude isn\'t asked again')

call('/styles/save', dict(style=dict(name='Test night', fonts='house', colors='midnight', motion='bouncy', look='bold')))
r6, log6 = run('build', anim=dict(ANIM, style='test-night'))
check(len([x for x in log6 if 'Rendering animation' in x]) == len(anims2), 'a new style re-renders every press')

run('shotlist', instructions='', anim=dict(ANIM, types=['end']))
plan = call('/project?video=' + urllib.request.quote(VIDEO))['shotlist']['animations']
total = sum(s['out'] - s['in'] for s in TIMELINE)
check(len(plan) == 1 and plan[0]['type'] == 'end', 'only one end screen is kept (%d)' % len(plan))
at = plan[0]['at']; secs = int(at.split(':')[0]) * 60 + int(at.split(':')[1])
check(secs >= total - 21, 'the end screen starts in the last 20 seconds (%s of %.0fs)' % (at, total))

call('/prefs', dict(keep_layers=False))
r7, _ = run('silences', settings=dict(preset='paced'))
check(not r7['has_layers'], 'with the switch off a cut doesn\'t ask for the layers back')
call('/prefs', dict(keep_layers=True, animations_own_sequence=True))
r8, _ = run('build')
check(r8['sequence_name'].endswith('Josh Cut Animations') and not r8.get('layers'), 'the old separate sequence still works')
call('/prefs', dict(keep_layers=True, animations_own_sequence=False))
print('FAILED' if check.failed else 'All checks passed')
