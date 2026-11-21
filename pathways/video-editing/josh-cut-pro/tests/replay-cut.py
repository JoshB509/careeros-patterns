"""Replay a real cut through the panel code against the stub, and report any moment clips overlapped.

  python tests\\replay-cut.py <last-cut.json> <job folder with result.json>

The timeline comes from a cut log (every clip after the last cut that finished) and the cut from a job's
result.json, so a cut that went wrong in Premiere can be run again here step by step.
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

log = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
result = json.loads((Path(sys.argv[2]) / 'result.json').read_text(encoding='utf-8'))
mic = next((c['file'] for c in log['clips'] if c['track'].startswith('A')), 'mic.wav')
setup = ('window.JOSH_HELPER = "http://127.0.0.1:9";'
         'window.STUB_TIMEBASE = "8467191533"; window.STUB_VIDEO = %s; window.STUB_MIC = %s; window.STUB_ITEMS = %s;'
         % (json.dumps(result['video']), json.dumps('E:\\mic\\' + mic), json.dumps(log['clips'])))
panel = (Path(__file__).resolve().parent.parent / 'panel' / 'preview.html').as_uri()

with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', args=['--allow-file-access-from-files'])
    pg = b.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.add_init_script(setup)
    pg.goto(panel); pg.wait_for_timeout(500)
    out = pg.evaluate("""async (args) => {
      const proj = await ppro.Project.getActiveProject(), seq = await proj.getActiveSequence();
      const before = seq.items.length;
      let res, err = null;
      try { res = await cutInPlace(proj, seq, args, { recipe: 'shrink-slide', slide: 'move', out_adjust: '0' }); }
      catch (e) { err = e.message; }
      const a = window.ACTIVE();
      return { before, after: a.items.length, res, err, overlaps: window.OVERLAPS.filter((o) => o.seq === a.name).slice(0, 15),
               count: window.OVERLAPS.filter((o) => o.seq === a.name).length };
    }""", dict(remove=result['remove'], video=result['video'], label='Flubs'))
    print(json.dumps(out, indent=1)[:4000])
    print('page errors', errs)
    b.close()
