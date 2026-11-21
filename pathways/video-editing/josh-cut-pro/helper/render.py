"""Render one press of the deck to a clip, with or without transparency.

This is the engine's renderer (dajoshi.animation) with one addition. With
alpha on, the page renders on a transparent background and is encoded as
ProRes 4444 with alpha, so the camera on the track below shows through the
PiP hole, the open half of a half-and-half shot, and around key word pops
and lower thirds. The clock, the scene isolation and the hold handle are the
engine's own, so an opaque render here matches the engine frame for frame.

Run as: python render.py request.json
"""
import hashlib, json, sys, uuid
from pathlib import Path

from dajoshi.animation import CLOCK, render_contract, prepare_scene
from dajoshi.media import check, run
from dajoshi.timing import rate

ALPHA_STYLE = 'html,body,#stage{background:transparent!important}'


def hole_style(hole, border):
    """A see-through window cut into the whole page at hole [x, y, w, h] (1920 by 1080 layout pixels), for decks
    that keep a solid background and only a placeholder where the camera goes (Josh's house deck: #pip, #half).
    The PiP window gets Josh Cut Pro's 6px gold border and drop shadow, drawn outside the window."""
    x, y, w, h = [float(v) for v in hole]
    # body's background is painted on the canvas, outside any mask, so clear it. The scenes carry their own.
    css = ('html,body{background:transparent!important}'
           'body{-webkit-mask-image:linear-gradient(#000,#000),linear-gradient(#000,#000);'
           f'-webkit-mask-size:100% 100%,{w}px {h}px;-webkit-mask-position:0 0,{x}px {y}px;'
           '-webkit-mask-repeat:no-repeat;-webkit-mask-composite:xor;mask-composite:exclude}'
           '#pip,#half{visibility:hidden!important}')
    if border:
        css += (f'html::after{{content:"";position:fixed;left:{x - 6}px;top:{y - 6}px;width:{w}px;height:{h}px;'
                'border:6px solid #f5c21b;box-shadow:0 18px 40px rgba(0,0,0,.28),0 4px 10px rgba(0,0,0,.18);'
                'pointer-events:none;z-index:2147483647}')
    return css


def encode_args(ffmpeg, fps_text, frames_dir, tail, total, out, alpha):
    head = [ffmpeg, '-v', 'error', '-nostdin', '-y', '-framerate', fps_text, '-i', str(frames_dir / '%06d.png'),
            '-vf', 'tpad=stop_mode=clone:stop_duration=' + str(tail), '-frames:v', str(total), '-an']
    if alpha:
        # qscale keeps the file size sane. The held frames are identical, so they compress well.
        return head + ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-alpha_bits', '16',
                       '-qscale:v', '9', '-vendor', 'apl0', str(out)]
    return head + ['-c:v', 'libx264', '-threads', '2', '-preset', 'fast', '-crf', '20', '-pix_fmt', 'yuv420p',
                   '-movflags', '+faststart', str(out)]


def render(deck, beat, previous, frames, fps, out, job, ffmpeg, contract=None, alpha=False, scale=1, hole=None, border=False):
    from playwright.sync_api import sync_playwright
    out = Path(out); fps_text = str(rate(fps)); fps = float(rate(fps))
    c = render_contract(contract, frames, fps_text); check(job); blocked = []; failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True, args=['--disable-background-networking', '--disable-component-update',
                                                                            '--disable-sync', '--no-first-run'])
        try:
            # The deck is laid out at 1920 by 1080. scale draws it at the sequence's own size (2 for a 4K sequence),
            # so text and lines stay sharp instead of being blown up in Premiere.
            context = browser.new_context(viewport={'width': c['width'], 'height': c['height']}, device_scale_factor=scale,
                                          service_workers='block', offline=True)

            def route(r):
                if r.request.url.startswith(('http:', 'https:', 'ws:', 'wss:')): blocked.append(r.request.url); r.abort()
                else: r.continue_()
            context.route('**/*', route); context.add_init_script(CLOCK)
            page = context.new_page(); page.on('pageerror', lambda e: failed.append(str(e)))
            page.on('requestfailed', lambda r: failed.append(r.url))
            page.goto(Path(deck).resolve().as_uri(), wait_until='load')
            page.evaluate('Promise.all([...document.fonts].map(f=>f.load())).then(()=>document.fonts.ready).then(()=>true)')
            fonts = page.evaluate('[...document.fonts].map(f=>({family:f.family,status:f.status}))')
            if blocked or failed or any(f['status'] != 'loaded' for f in fonts):
                raise ValueError('HTML has failed/external assets, fonts or script errors: ' + str(dict(blocked=blocked, errors=failed, fonts=fonts)))
            if not page.evaluate('typeof window.go==="function"'): raise ValueError('HTML does not expose window.go(beat)')
            if alpha and hole:
                page.add_style_tag(content=hole_style(hole, border))
            elif alpha:
                page.add_style_tag(content=ALPHA_STYLE)
                page.evaluate("document.body.classList.add('alpha')")
            base = prepare_scene(page, beat, previous, c)
            raw = out.with_name(out.stem + '.frames-' + uuid.uuid4().hex[:8]); raw.mkdir()
            motion_frames = min(frames, max(1, c['motion_frames'] - c['phase_frames']))
            hashes = []
            for n in range(motion_frames):
                check(job); phase = min(c['phase_frames'] + n, c['motion_frames'] - 1)
                page.evaluate('(t)=>{__dj.jump(t);__djIsolate();__dj.freeze()}', base + phase * 1000 / fps)
                png = page.screenshot(type='png', omit_background=alpha); (raw / ('%06d.png' % n)).write_bytes(png)
                if n in [0, motion_frames - 1]: hashes.append(hashlib.sha256(png).hexdigest())
            if failed: raise ValueError('HTML runtime failure: ' + str(failed))
            tail = (frames - motion_frames + c['handle_frames']) / fps
            partial = out.with_name(out.stem + '.partial' + out.suffix)
            run(encode_args(ffmpeg, fps_text, raw, tail, frames + c['handle_frames'], partial, alpha), job, 'Encode beat ' + str(beat))
            partial.replace(out)
            report = dict(beat=beat, previous=previous, alpha=alpha, hole=hole, border=border, fonts=fonts, errors=failed, frame_hashes=hashes,
                          frame_directory=str(raw), motion_frames=motion_frames, duration_frames=frames,
                          hold_handle_seconds=c['handle_frames'] / fps, contract=c,
                          source_sha256=hashlib.sha256(Path(deck).read_bytes()).hexdigest())
            out.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            return report
        finally:
            browser.close()


if __name__ == '__main__':
    render(**json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
