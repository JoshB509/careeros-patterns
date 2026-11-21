"""Drive the app and the stubbed panel through Clean cut, Flubs and Animations on one open sequence.

The stub sequence has the camera clip on V1 (no camera sound) and the mic WAV on A1, two seconds late.
Every cut has to keep the mic in sync on every slice, save a backup first, and leave the work on the same sequence.
Start a helper on a spare port with an empty projects folder and the mock Claude first, then:
  python tests\\ui-inplace.py 47821 <projects folder> <folder for screenshots>
"""
import hashlib, json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

PORT = int(sys.argv[1]); PROJECTS = Path(sys.argv[2]); OUT = Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
HERE = Path(__file__).resolve().parent
VIDEO = HERE / 'sample-5min.mp4'
PANEL = (HERE.parent / 'panel' / 'preview.html').as_uri()
MIC_LATE = 2.0

# the transcript is of the mic, which starts two seconds into the camera recording
key = hashlib.sha1(str(VIDEO.resolve()).lower().encode()).hexdigest()[:8]
proj = PROJECTS / ('sample-5min-' + key); proj.mkdir(parents=True, exist_ok=True)
segs = json.loads((HERE / 'sample-5min-transcript.json').read_text(encoding='utf-8'))
for s in segs:
    s['start'] -= MIC_LATE; s['end'] -= MIC_LATE
    for w in s.get('words', []): w['start'] -= MIC_LATE; w['end'] -= MIC_LATE
segs = [s for s in segs if s['start'] >= 0]
(proj / 'transcript.json').write_text(json.dumps(segs), encoding='utf-8')

failed = []
def check(cond, what):
    print(('  ok    ' if cond else '  FAIL  ') + what)
    if not cond: failed.append(what)


def state(plug):
    return plug.evaluate("""() => { const s = ACTIVE(); const items = s.items.map((i) => ({ k: i.kind, t: i.track, s: i._start, e: i._end, i: i._in, p: i.clip.path || '' }));
      const bins = []; const walk = (b, path) => b.kids.forEach((k) => { if (k.kids) walk(k, path + '/' + k.name); else bins.push(path + '/' + k.name); });
      walk(window.SEQS.length ? { kids: [] } : { kids: [] }, '');
      return { name: s.name, items, seqs: SEQS.map((q) => q.name) }; }""")


def in_sync(st):
    v = sorted([i for i in st['items'] if i['k'] == 'v' and i['t'] == 0], key=lambda x: x['s'])
    a = sorted([i for i in st['items'] if i['k'] == 'a' and i['t'] == 0], key=lambda x: x['s'])
    bad = 0
    for x in v:
        m = next((y for y in a if abs(y['s'] - x['s']) < 0.02 and abs(y['e'] - x['e']) < 0.02), None)
        # mic time = camera time minus two seconds, wherever the slice sits
        if not m or abs((m['i'] - x['i']) + MIC_LATE) > 0.02: bad += 1
    gaps = sum(1 for p, q in zip(v, v[1:]) if q['s'] - p['e'] > 0.02)
    return len(v), len(a), bad, gaps


def wait_toast(app, ms=600000):
    app.wait_for_function("() => document.querySelector('#ring').className === 'hidden'", timeout=ms)
    return app.inner_text('#toastMsg')


with sync_playwright() as p:
    args = ['--disable-web-security', '--allow-file-access-from-files']
    try: b = p.chromium.launch(channel='chrome', args=args)
    except Exception: b = p.chromium.launch(channel='msedge', args=args)
    plug = b.new_page(viewport={'width': 260, 'height': 130}); perr = []
    plug.on('pageerror', lambda e: perr.append(str(e)))
    plug.add_init_script("window.JOSH_HELPER = 'http://127.0.0.1:%d'" % PORT)
    plug.goto(PANEL)
    app = b.new_page(viewport={'width': 600, 'height': 780}); aerr = []
    app.on('pageerror', lambda e: aerr.append(str(e)))
    app.goto('http://127.0.0.1:%d/app/' % PORT); app.wait_for_timeout(3500)
    src = app.evaluate('() => S.src')
    check(src and src['mic_track'] == 0 and not src['audio_tracks'][0]['same'], 'the mic on A1 is picked to listen to')
    check(src and abs(src['audio_tracks'][0]['offset'] + MIC_LATE) < 0.01, 'the mic offset is read from the timeline (%s)' % (src and src['audio_tracks'][0]['offset']))
    app.screenshot(path=str(OUT / 'home.png'))

    # Clean cut
    app.click('[data-go=clean]'); app.wait_for_timeout(6000)
    app.screenshot(path=str(OUT / 'clean.png'))
    app.click('#main')
    app.wait_for_selector('#steps li.on', timeout=5000)
    app.screenshot(path=str(OUT / 'progress.png'))
    check(app.locator('#steps li').count() >= 5, 'the progress screen shows the steps')
    msg = wait_toast(app); print('clean toast:', msg)
    check(app.locator('#steps').count() == 0, 'the progress screen goes away when it finishes')
    log = json.loads((proj / 'last-cut.json').read_text(encoding='utf-8'))
    check(not log['report']['gaps'] and not log['report']['overlaps'], 'the cut log shows no gaps or overlaps (%d clips)' % len(log['clips']))
    st = state(plug); v, a, bad, gaps = in_sync(st)
    check(st['name'] == 'Sequence 01', 'the cut stays on the open sequence (%s)' % st['name'])
    check(v > 5 and v == a and bad == 0, 'every slice keeps the mic in sync (%d video, %d mic, %d out)' % (v, a, bad))
    check(gaps == 0, 'the gaps close up')
    check(any('before Clean cut' in n for n in st['seqs']), 'a backup was saved first (%s)' % st['seqs'])
    probe = json.loads((PROJECTS / 'premiere-probe.json').read_text(encoding='utf-8'))
    check(probe.get('ok') and probe['strategy']['slide'] == 'move' and probe['tests']['recipe']['exact'], 'the Premiere check ran and the shrink-then-slide recipe came out exact')
    check('Josh Cut Pro check' not in ' '.join(st['seqs']), 'the check cleaned up its copy')
    first = v

    # Flubs on the same, already cut sequence
    app.click('#back'); app.wait_for_timeout(800); app.click('[data-go=flubs]'); app.wait_for_timeout(1500)
    app.click('#main'); app.wait_for_timeout(1000); wait_toast(app)
    app.wait_for_timeout(800)
    app.screenshot(path=str(OUT / 'flubs.png'))
    app.click('#main'); app.wait_for_timeout(1000)
    msg = wait_toast(app); print('flubs toast:', msg)
    st = state(plug); v, a, bad, gaps = in_sync(st)
    check(st['name'] == 'Sequence 01' and v > first, 'flubs cut further into the same sequence (%d to %d slices)' % (first, v))
    check(v == a and bad == 0 and gaps == 0, 'still in sync with no gaps (%d out)' % bad)
    check(sum(1 for n in st['seqs'] if 'before' in n) == 2, 'a second backup was saved')

    # Animations onto the same sequence
    app.click('#back'); app.wait_for_timeout(800); app.click('[data-go=anim]'); app.wait_for_timeout(1500)
    check(app.inner_text('#main') == 'Plan the animations' and not app.is_disabled('#main'), 'with no plan the gold button plans')
    app.click('#main'); app.wait_for_timeout(1000); wait_toast(app)
    if 'on' not in (app.get_attribute('[data-type-chip=pip]', 'class') or ''):
        app.click('[data-type-chip=pip]'); app.wait_for_timeout(800)
    app.evaluate('() => hideToast()')
    cam = app.locator('[data-camdrag]'); cam.scroll_into_view_if_needed(); app.wait_for_timeout(2500)
    check(app.locator('.camimg').evaluate('(i) => i.naturalWidth > 0'), 'the PiP shape shows a still of you straight away')
    app.evaluate("() => { document.querySelector('[data-camdrag]').dataset.mark = 'same'; }")
    app.click('[data-nudge=in]'); app.wait_for_timeout(800)
    check(app.evaluate("() => document.querySelector('[data-camdrag]').dataset.mark === 'same'"), "a nudge moves you without redrawing the screen")
    cam.scroll_into_view_if_needed(); app.wait_for_timeout(300)
    before = app.evaluate('() => S.pip.shift'); left0 = app.locator('.camimg').evaluate('(i) => i.offsetLeft')
    box = cam.bounding_box(); x0, y0 = box['x'] + box['width'] * .5, box['y'] + box['height'] * .5
    app.mouse.move(x0, y0); app.mouse.down(); app.mouse.move(x0 - 15, y0, steps=5)
    mid = app.locator('.camimg').evaluate('(i) => i.offsetLeft'); box2 = cam.bounding_box()
    app.mouse.up(); app.wait_for_timeout(1500)
    after = app.evaluate('() => S.pip.shift')
    check(after > before and mid < left0, 'dragging left moves you left inside the shape, live (shift %.3f to %.3f)' % (before, after))
    check(abs(box2['x'] - box['x']) < 1, 'the shape itself stays put while you drag')
    saved = app.evaluate("async () => (await (await fetch('/project?video=' + encodeURIComponent(S.src.video))).json()).pip.shift")
    check(abs(saved - after) < 1e-6, 'the framing is saved')
    app.screenshot(path=str(OUT / 'pip-drag.png'))
    mic_before = sorted((round(i['s'], 3), round(i['e'], 3), round(i['i'], 3)) for i in state(plug)['items'] if i['k'] == 'a')
    app.click('#main'); app.wait_for_timeout(1000)
    msg = wait_toast(app); print('build toast:', msg)
    st = state(plug)
    v5 = sum(1 for i in st['items'] if i['k'] == 'v' and i['t'] == 4)
    v4 = [i for i in st['items'] if i['k'] == 'v' and i['t'] == 3]
    check(v5 >= 4, '%d animation clips on V5 of the same sequence' % v5)
    mic_after = sorted((round(i['s'], 3), round(i['e'], 3), round(i['i'], 3)) for i in st['items'] if i['k'] == 'a')
    check(mic_after == mic_before, 'building animations leaves the mic on A1 exactly as it was')
    v1 = [i for i in st['items'] if i['k'] == 'v' and i['t'] == 0]
    match = all(any(abs((c['i'] - c['s']) - (x['i'] - x['s'])) < 0.02 and x['s'] - 0.02 <= c['s'] and c['e'] <= x['e'] + 0.02 for x in v1) for c in v4)
    check(v4 and match, '%d camera copies on V4, each showing what V1 shows at that moment' % len(v4))

    # A second clean cut lifts the animations, cuts, and puts them back
    app.click('#back'); app.wait_for_timeout(800); app.click('[data-go=clean]'); app.wait_for_timeout(5000)
    app.click('[data-pace=energetic]'); app.wait_for_timeout(2500)
    app.click('#main'); app.wait_for_timeout(1000)
    msg = wait_toast(app); print('second clean toast:', msg)
    st = state(plug); v, a, bad, gaps = in_sync(st)
    v5b = sum(1 for i in st['items'] if i['k'] == 'v' and i['t'] == 4)
    check(bad == 0 and gaps == 0, 'a second clean cut keeps sync (%d slices)' % v)
    check(v5b == v5 or 'Put back' in msg, 'the animations went back on (%d on V5)' % v5b)
    app.screenshot(path=str(OUT / 'clean-2.png'))

    app.click('#gear'); app.wait_for_timeout(800); app.screenshot(path=str(OUT / 'settings.png'))
    print('panel errors', perr, 'app errors', aerr[:5])
    check(not perr and not aerr, 'no script errors')
    print('FAILED: ' + '; '.join(failed) if failed else 'PASSED')
    b.close()
