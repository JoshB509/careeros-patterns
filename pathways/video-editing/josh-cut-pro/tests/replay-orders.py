"""Replay Clean cut and Flubs on a real recording in both orders, starting from the untouched timeline.

  python tests\\replay-orders.py <project folder> <silences job folder name> <apply job folder name>

The timeline is the whole recording on V1 and its mic on A1 at the offset from the job. Each order is run
through the panel code against the stub with Josh's sequence timebase. It reports clips, mic sync, the final
length and any moment two clips overlapped (in Premiere that would overwrite a clip).
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

D = Path(sys.argv[1])
clean = json.loads((D / sys.argv[2] / 'result.json').read_text(encoding='utf-8'))
flubs = json.loads((D / sys.argv[3] / 'result.json').read_text(encoding='utf-8'))
off = float(json.loads((D / sys.argv[3] / 'request.json').read_text(encoding='utf-8'))['audio_offset'])
length = clean.get('source_seconds') or 775.0
# the mic starts -off seconds into the camera recording, so it sits that far along the timeline with an in point of 0
raw = [dict(track='V1', start=0.0, end=length, **{'in': 0.0}), dict(track='A1', start=max(0.0, -off), end=length, **{'in': max(0.0, off)})]
panel = (Path(__file__).resolve().parent.parent / 'panel' / 'preview.html').as_uri()
failed = False

for name, order in [('Flubs then Clean cut', [flubs, clean]), ('Clean cut then Flubs', [clean, flubs])]:
    with sync_playwright() as p:
        b = p.chromium.launch(channel='chrome', args=['--allow-file-access-from-files'])
        pg = b.new_page(); errs = []
        pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: print('    ', m.text) if m.text.startswith('SLIVER') else None)
        pg.add_init_script('window.JOSH_HELPER="http://127.0.0.1:9"; window.STUB_TIMEBASE="8467191533"; window.STUB_VIDEO=%s; '
                           'window.STUB_MIC="E:\\\\mic.wav"; window.STUB_ITEMS=%s;' % (json.dumps(flubs['video']), json.dumps(raw)))
        pg.goto(panel); pg.wait_for_timeout(400)
        print(name)
        for r in order:
            o = pg.evaluate("""async ([a, off]) => {
              const proj = await ppro.Project.getActiveProject(), seq = await proj.getActiveSequence();
              window.OVERLAPS.length = 0;
              let res, err = null;
              try { res = await cutInPlace(proj, seq, a, { recipe: 'shrink-slide', slide: 'move', out_adjust: '0' }); } catch (e) { err = e.message; }
              const s = window.ACTIVE(), v = s.items.filter((i) => i.kind === 'v'), m = s.items.filter((i) => i.kind === 'a');
              let bad = 0, tiny = 0;
              for (const x of v) {
                const y = m.find((z) => Math.abs(z._start - x._start) < 0.02 && Math.abs(z._end - x._end) < 0.02);
                if (y && Math.abs((y._in - x._in) - off) > 0.02) bad++;
              }
              for (const x of s.items) if (x._end - x._start < 0.5 / 30) { tiny++; console.log('SLIVER ' + x.kind + x.track + ' ' + x._start.toFixed(4) + '-' + x._end.toFixed(4) + ' in ' + x._in.toFixed(4)); }
              return { err, cuts: res && res.cuts, clips: v.length, mic: m.length, out_of_sync: bad, shorter_than_a_frame: tiny,
                       overlaps: window.OVERLAPS.filter((q) => q.seq === s.name).length, length: Math.round(Math.max(...v.map((x) => x._end)) * 10) / 10 };
            }""", [dict(remove=r['remove'], video=r['video'], label='test'), off])
            print('  ', o)
            failed = failed or bool(o['err'] or o['out_of_sync'] or o['overlaps'] or o['shorter_than_a_frame'])
        if errs: print('   page errors', errs); failed = True
        b.close()
print('FAILED' if failed else 'PASSED')
