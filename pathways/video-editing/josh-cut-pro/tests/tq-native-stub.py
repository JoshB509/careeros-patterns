"""Tariq's native edit commands (tq_*) against the Premiere stub, in Chrome.

    python tests/tq-native-stub.py

MOCK ONLY. This proves the panel code builds the planned sequence from pieces of the master, puts the
good mic on A1 in sync, refuses to overwrite, and that a master key change reaches every piece in the
stub's model. It cannot prove Ultra Key pixels, real nesting, save and reopen, or export in Premiere.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / 'panel'
RESOLVE = Path(r'E:\Videos\DaJoshiResolve')
sys.path.insert(0, str(RESOLVE))
from dajoshi import edit_plan as ep  # noqa: E402
from studio.edit_flow import verify_readback  # noqa: E402

TPS = ep.TICKS_PER_SECOND
F = TPS // 30
PAGE = '<html><body><div id="activity"></div><div id="link"></div><div id="linkText"></div><div id="seq"></div><button id="open"></button></body></html>'
FAKE_HELPER = """
window.JOSH_HELPER='http://stub';
window.fetch=async (url,opt)=>{
  const path=url.replace('http://stub','');
  const body=(x)=>({ok:true,status:200,json:async()=>x});
  if(path.startsWith('/bridge/poll')){await new Promise(r=>setTimeout(r,60000));return body({call:null})}
  if(path==='/probe')return body({probe:{ok:true,premiere:'26.0-stub',strategy:{recipe:'shrink-slide',slide:'move',out_adjust:'0'}}});
  return body({ok:true});
};
"""


def main():
    sr = 16000
    # keep 3-20 s, 30.5-61.2 s, 100-130 s of mic time; mic runs 2 s ahead of the camera
    keeps = [[3 * sr, 20 * sr], [int(30.5 * sr), int(61.2 * sr)], [100 * sr, 130 * sr]]
    mapping = ep.output_map(keeps, sr, 2.0, F)
    plan = dict(project_id='t', proposal_id='p', proposal_digest='d', revision=1,
                camera_path=r'E:\Videos\DaJoshiCut\tests\sample-5min.mp4', mic_path=r'E:\Videos\DaJoshiCut\tests\sample-5min-mic.wav',
                master='GREEN_MASTER', sequence_name='CLEAN_CUT_r01', map=mapping, map_digest=ep.digest(mapping))
    results = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(channel='chrome')
        page = b.new_page()
        page.set_content(PAGE)
        page.add_script_tag(content=FAKE_HELPER)
        page.add_script_tag(path=str(HERE / 'ppro-stub.js'))
        page.add_script_tag(path=str(HERE / 'tq-stub-ext.js'))
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.add_script_tag(path=str(PANEL / 'index.js'))
        assert not errors, errors
        ev = lambda js: page.evaluate(js)
        results['probe'] = ev("COMMANDS.tq_probe({master:'GREEN_MASTER'})")
        results['key_before'] = ev("COMMANDS.tq_master_read({master:'GREEN_MASTER'})")
        results['build'] = ev(f"COMMANDS.tq_build_cut({{plan:{json.dumps(plan)}}})")
        try:
            ev(f"COMMANDS.tq_build_cut({{plan:{json.dumps(plan)}}})")
            results['second_build_refused'] = False
        except Exception as e:  # noqa: BLE001
            results['second_build_refused'] = 'already exists' in str(e)
        pieces = [p for p in mapping['pieces'] if p['kind'] == 'source']
        mids = [str((p['out_start'] + p['out_end']) // 2) for p in pieces]
        frames = lambda prefix: ev(f"COMMANDS.tq_export_frames({{sequence:'CLEAN_CUT_r01',times:{json.dumps(mids)},dir:'E:/test',prefix:'{prefix}'}}).then(()=>window.FRAMES)")
        before = frames('before')
        results['set'] = ev("COMMANDS.tq_master_set({master:'GREEN_MASTER',param:'Choke',value:3})")
        after = frames('after')
        shadow_after = ev("window.MASTER_KEYS.shadowKey.params.map(p=>p.value)")
        results['save'] = ev("COMMANDS.tq_save()")
        results['assemble'] = ev("COMMANDS.tq_assemble({cut:'CLEAN_CUT_r01',sequence:'FINAL_ASSEMBLY_r01'})")
        results['export'] = ev("COMMANDS.tq_export({sequence:'FINAL_ASSEMBLY_r01',output:'E:/test/out.mp4'})")
        results['overlaps_during_build'] = ev("window.OVERLAPS.filter(o=>o.seq==='CLEAN_CUT_r01')")
        b.close()
    build = results['build']
    checks = dict(
        probe_ok=results['probe'].get('ok'), presenter_track=results['probe'].get('presenter_track'), shadow_track=results['probe'].get('shadow_track'),
        readback_problems=verify_readback(plan, build),
        pieces_are_master_nests=build.get('nest'),
        mic_pieces=len([a for a in build['audio'] if a['role'] == 'mic']), planned=len(pieces),
        no_camera_audio=not any(a['role'] == 'camera' for a in build['audio']),
        second_build_refused=results['second_build_refused'],
        key_change_reached_every_piece=all(after[f'E:/test/after-{i:03d}.png']['keyed'] != before[f'E:/test/before-{i:03d}.png']['keyed']
                                           and after[f'E:/test/after-{i:03d}.png']['source'] == 'GREEN_MASTER' for i in range(len(pieces))),
        picture_at_right_source_time=[round(before[f'E:/test/before-{i:03d}.png']['src_time'] - (p['camera_in'] + p['camera_out']) / 2 / TPS, 4) for i, p in enumerate(pieces)],
        shadow_key_untouched=shadow_after == [45, 20, 0],
        saved=results['save'].get('saved'), export_started=results['export'].get('started'),
        overlaps_during_build=len(results['overlaps_during_build']))
    out = HERE / 'tq-native-stub-receipt.json'
    out.write_text(json.dumps(dict(scope='MOCK ONLY, Premiere stub in Chrome', checks=checks, results=results), indent=1, default=str), encoding='utf-8')
    print(json.dumps(checks, indent=1))
    ok = (checks['probe_ok'] and not checks['readback_problems'] and checks['pieces_are_master_nests'] and checks['no_camera_audio']
          and checks['second_build_refused'] and checks['key_change_reached_every_piece'] and checks['shadow_key_untouched']
          and all(abs(x) < 1 / 30 for x in checks['picture_at_right_source_time']))
    print('PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
