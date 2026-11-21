"""DaJoshi Cut helper.

A small local server for the DaJoshi Cut Premiere panel. It listens on
127.0.0.1 only and drives the DaJoshiResolve engine (local Whisper, acoustic
analysis, HTML beat rendering, XMEML export). It never edits anything inside
DaJoshiResolve. The only thing that leaves the PC is text sent to the Claude API.

  Pass 1  clean     transcribe, Claude strikes repeats and flubs, sounds and long
                    pauses are cut from the audio, sequence "1 Clean cut"
  Pass 2  shotlist  Claude plans the animations from the clean transcript and your
                    notes, with a concept sketch per animation, for review
  Pass 3  build     Claude writes each animation into the house deck, each press is
                    rendered as a clip and placed, sequence "2 Animations"
"""
import concurrent.futures, hashlib, json, os, re, sys, threading, time, traceback, uuid
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG_PATH = ROOT / 'config.json'
SECRETS = ROOT / 'secrets.json'
CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf-8-sig')) if CONFIG_PATH.exists() else {}
ENGINE = Path(os.environ.get('DAJOSHI_ENGINE') or CONFIG.get('engine') or r'E:\Videos\DaJoshiResolve').resolve()
PROJECTS = Path(os.environ.get('DAJOSHI_CUT_PROJECTS') or CONFIG.get('projects') or (ROOT / 'Projects')).resolve()
PORT = int(os.environ.get('DAJOSHI_CUT_PORT') or CONFIG.get('port', 47820))
MODELS = dict(clean='claude-sonnet-5-5', shotlist='claude-opus-5-5', deck='claude-opus-5-5')
MODELS.update(CONFIG.get('models', {}))
VERSION = '0.9.0'

sys.path.insert(0, str(ENGINE)); sys.path.insert(0, str(HERE))
os.environ['PYTHONPATH'] = str(ENGINE) + (os.pathsep + os.environ['PYTHONPATH'] if os.environ.get('PYTHONPATH') else '')

import claude_api, cleancut, deck, layers, pip, prompts, style  # noqa: E402
claude_api.REPLY_DIR = str(PROJECTS / 'claude-replies')

SUFFIX = ' - Josh Cut'
OLD_SUFFIXES = (' - DaJoshi Cut',)
LABELS = {'silences': 'Josh Cut', 'apply': 'Josh Cut', 'build': 'Josh Cut Animations'}
APP_NAME = 'Josh Cut Pro'


# ---------------------------------------------------------------- utilities

def read_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write_json(p, v):
    p = Path(p); tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding='utf-8'); tmp.replace(p)


def fingerprint(path):
    p = Path(path).resolve(); s = p.stat()
    return dict(path=str(p), size=s.st_size, mtime_ns=s.st_mtime_ns)


def api_key():
    if os.environ.get('ANTHROPIC_API_KEY'): return os.environ['ANTHROPIC_API_KEY']
    return read_json(SECRETS).get('api_key') if SECRETS.exists() else None


def engine_settings():
    s = read_json(ENGINE / 'settings.json'); s.update(CONFIG.get('settings_override', {}))
    return s


def engine():
    from dajoshi import timing, media, export, animation, script_align
    return dict(timing=timing, media=media, export=export, animation=animation, script_align=script_align)


def safe_name(text):
    return re.sub(r'[^A-Za-z0-9 _.-]+', '', text).strip() or 'video'


def norm(text):
    return re.findall(r"[a-z0-9']+", text.lower().replace('\u2019', "'"))


def tc(sec):
    sec = max(0, int(round(sec))); return '%d:%02d' % (sec // 60, sec % 60)


# ---------------------------------------------------------------- jobs

class Job:
    def __init__(self, stage, request):
        self.id = uuid.uuid4().hex[:10]; self.stage = stage; self.request = request
        self.state = 'queued'; self.message = 'Waiting to start'; self.log = []
        self.result = None; self.error = None; self.dir = None; self.started = time.time(); self.cost = None

    def say(self, message):
        self.message = message
        self.log.append(time.strftime('%H:%M:%S ') + message); del self.log[:-200]
        print('[%s] %s' % (self.id, message), flush=True)

    def view(self):
        return dict(id=self.id, stage=self.stage, state=self.state, message=self.message, log=self.log[-30:],
                    result=self.result, error=self.error, elapsed_seconds=round(time.time() - self.started, 1),
                    cost=self.cost if CONFIG.get('show_costs', True) else None)


JOBS = {}
BUSY = threading.Lock()


def project_dir(video):
    fp = fingerprint(video)
    key = hashlib.sha1(fp['path'].lower().encode()).hexdigest()[:8]
    d = PROJECTS / ('%s-%s' % (safe_name(Path(video).stem), key)); d.mkdir(parents=True, exist_ok=True)
    fresh_start(d)
    return d


FRESH = set()   # recordings already started fresh since the app window last opened
CHOICES = ['project.json', 'flubs.json', 'shotlist.json', 'shotlist.md', 'pip-preview.png']


def fresh_start(proj):
    """Every time the app window opens, each recording starts fresh.

    Josh's earlier choices (silence settings, flub picks, the shot list, animation settings) move into a
    _superseded folder. What's worked out from the file alone stays, as long as the file hasn't changed:
    the decoded audio, the transcript and Claude's read of it, plus rendered animations."""
    if str(proj) in FRESH: return
    FRESH.add(str(proj))
    here = [n for n in CHOICES if (proj / n).exists()]
    if not here: return
    old = proj / ('_superseded-' + time.strftime('%Y%m%d-%H%M%S')); old.mkdir(exist_ok=True)
    for n in here: (proj / n).replace(old / n)
    _CTX.clear()


def project_state(proj):
    p = proj / 'project.json'
    return read_json(p) if p.exists() else dict(stages={})


def save_state(proj, state):
    write_json(proj / 'project.json', state)


# ---------------------------------------------------------------- shared prep

def prepare(job, req, need_dir=True, need_words=True):
    e = engine(); media = e['media']; timing = e['timing']; settings = engine_settings()
    video_path = Path(req['video']).resolve()
    audio_path = Path(req.get('audio') or video_path).resolve()
    for label, p in [('video', video_path), ('audio', audio_path)]:
        if not p.is_file(): raise ValueError('Cannot find the %s file: %s' % (label, p))
    proj = project_dir(video_path)
    state = project_state(proj)
    sources = dict(video=fingerprint(video_path), audio=fingerprint(audio_path))
    if state.get('sources') and state['sources'] != sources:
        old = proj / ('_superseded-' + time.strftime('%Y%m%d-%H%M%S')); old.mkdir()
        for name in ['project.json', 'transcript.json', 'microphone.f32', 'reference.f32', 'sync.json',
                     'clean-decision.json', 'shotlist.json', 'flubs.json']:
            if (proj / name).exists(): (proj / name).replace(old / name)
        state = dict(stages={})
    state['sources'] = sources; state.setdefault('stages', {})
    if req.get('spans'): state['timeline'] = req['spans']
    if req.get('frame'): state['frame'] = [int(x) for x in req['frame']]
    save_state(proj, state)

    stage_dir = None
    if need_dir:
        stage_dir = proj / ('%s-%s' % (time.strftime('%Y%m%d-%H%M%S'), job.stage)); stage_dir.mkdir(parents=True)
        job.dir = stage_dir; write_json(stage_dir / 'request.json', req)
    work = stage_dir or proj

    try:
        from worker import guard_recording
        guard_recording()
    except ImportError:
        pass

    job.say('Reading media headers')
    video = media.probe(video_path); audio = media.probe(audio_path)
    if not video['fps']: raise ValueError('The video file has no picture track')
    if not audio['channels']: raise ValueError('The audio file has no sound track')
    from xml.etree import ElementTree as ET
    e['export'].xml_rate(ET.Element('preflight'), video['fps'])
    fps = video['fps']

    import numpy as np
    if (proj / 'microphone.f32').exists():
        mic = np.fromfile(proj / 'microphone.f32', dtype='<f4')
    else:
        job.say('Decoding the microphone audio')
        mic = media.decode(audio['path'], proj / 'microphone.f32', work, settings['ffmpeg'])

    if Path(audio['path']) == Path(video['path']):
        sync = dict(verified=True, offset_seconds=0, method='Embedded camera audio')
    elif req.get('audio_offset') is not None:
        sync = dict(verified=True, offset_seconds=float(req['audio_offset']), method='Taken from how the clips line up on the timeline')
    elif (proj / 'sync.json').exists():
        sync = read_json(proj / 'sync.json')
    else:
        job.say('Syncing the microphone to the camera')
        if not video['channels']: raise ValueError('The camera file has no audio to sync the separate microphone against')
        cam = media.decode(video['path'], proj / 'reference.f32', work, settings['ffmpeg'])
        sync = media.sync(cam, mic); write_json(proj / 'sync.json', sync)
    if not sync['verified']:
        raise ValueError('The microphone and camera audio could not be synced with confidence. See sync.json in the project folder.')
    offset = timing.frame(sync['offset_seconds'], fps) / float(timing.rate(fps))
    if state.get('timeline_offset') != offset:
        state['timeline_offset'] = offset; save_state(proj, state)

    if req.get('transcript') and not (proj / 'transcript.json').exists():
        write_json(proj / 'transcript.json', read_json(req['transcript']))
    words = None
    if need_words:
        segments = ensure_transcript(proj, mic, settings, job)
        words = [dict(w, segment_start=i == 0) for s in segments for i, w in enumerate(s.get('words', []))]
        if not words: raise ValueError('The transcript has no word timings')
    elif not (proj / 'transcript.json').exists():
        start_transcription(proj, mic, settings)

    return dict(proj=proj, state=state, stage_dir=stage_dir, video=video, audio=audio, fps=fps, frame=state.get('frame') or [1920, 1080],
                mic=mic, sync=sync, offset=offset, words=words, settings=settings, e=e)


# ---------------------------------------------------------------- transcription (fast, can run in the background)

TRANSCRIBING = {}   # project folder -> dict(thread, progress, error)
TLOCK = threading.Lock()


def whisper_attempts(settings):
    """Ways to run Whisper, fastest first. The one that last worked on this PC goes first."""
    w = CONFIG.get('whisper', {})
    path = w.get('model') or settings['model']
    cores = os.cpu_count() or 4
    threads = int(w.get('threads') or max(2, cores - 2))
    beam = str(w.get('beam_size', 1))
    attempts = []
    if w.get('device', 'auto') in ('auto', 'cuda'):
        attempts.append(('cuda', 'float16', threads, '1', beam))
    if w.get('device', 'auto') in ('auto', 'cpu'):
        attempts += [('cpu', 'int8', threads, '1', beam), ('cpu', 'int8', min(4, threads), '0', beam)]
    good = PROJECTS / 'whisper-ok.json'
    if good.exists():
        last = tuple(read_json(good).get('attempt', []))
        if last in attempts: attempts.remove(last); attempts.insert(0, last)
    return path, attempts


def transcribe_in_child(proj, settings, status):
    """Try each way in its own process. A crash only ends that attempt."""
    import subprocess
    mic = proj / 'microphone.f32'; out = proj / 'transcript.json'
    path, attempts = whisper_attempts(settings)
    try: (proj / 'transcript.json.progress').unlink()
    except Exception: pass
    env = dict(os.environ, KMP_DUPLICATE_LIB_OK='TRUE')
    errors = []
    for attempt in attempts:
        device, ctype, threads, batched, beam = attempt
        status['how'] = '%s%s' % ('graphics card' if device == 'cuda' else 'processor', ', batched' if batched == '1' else '')
        logf = proj / 'transcribe.log'
        with open(logf, 'ab') as log:
            log.write(('\n--- %s %s threads=%s batched=%s\n' % (device, ctype, threads, batched)).encode())
            child = subprocess.Popen([sys.executable, str(HERE / 'transcribe_worker.py'), str(mic), str(out), str(path),
                                      device, ctype, str(threads), batched, beam], stdout=log, stderr=log, env=env,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            status['child'] = child
            while child.poll() is None:
                time.sleep(1)
                try: status['progress'] = int((proj / 'transcript.json.progress').read_text() or 0)
                except Exception: pass
                if status.get('stop'): child.kill(); raise RuntimeError('stopped because a different recording was opened')
        if child.returncode == 0 and out.exists():
            write_json(PROJECTS / 'whisper-ok.json', dict(attempt=list(attempt)))
            print('Transcribed on the %s' % status['how'], flush=True)
            return
        tail = logf.read_text(encoding='utf-8', errors='replace').strip().splitlines()[-1:] or ['no message']
        errors.append('%s: %s' % (status['how'], tail[0][-200:]))
        print('Transcription on the %s did not work (%s), trying the next way' % (status['how'], tail[0][-200:]), flush=True)
    raise RuntimeError('every way of running Whisper failed. ' + ' | '.join(errors))


def start_transcription(proj, mic, settings):
    """One transcription at a time. Opening a different recording stops the old one."""
    key = str(proj)
    with TLOCK:
        t = TRANSCRIBING.get(key)
        if t and t['thread'].is_alive(): return t
        for other_key, other in TRANSCRIBING.items():
            if other_key != key and other['thread'].is_alive():
                other['stop'] = True
                child = other.get('child')
                if child and child.poll() is None: child.kill()
        status = dict(progress=0, error=None, started=time.time())
        def work():
            try:
                transcribe_in_child(proj, settings, status)
                status['progress'] = 100
            except Exception as ex:
                status['error'] = str(ex); traceback.print_exc()
        th = threading.Thread(target=work, daemon=True); status['thread'] = th
        TRANSCRIBING[key] = status; th.start()
        return status


def made_on(f):
    """When a cached file was made, for the app to say what it's reusing."""
    return time.strftime('%d %b %H:%M', time.localtime(f.stat().st_mtime)).lstrip('0') if f.exists() else None


def transcript_status(proj):
    if (proj / 'transcript.json').exists(): return dict(state='ready', progress=100)
    t = TRANSCRIBING.get(str(proj))
    if not t: return dict(state='none', progress=0)
    if t['error']: return dict(state='failed', progress=t['progress'], error=t['error'])
    return dict(state='running', progress=t['progress'], how=t.get('how', ''))


def ensure_transcript(proj, mic, settings, job):
    f = proj / 'transcript.json'
    if not f.exists():
        status = start_transcription(proj, mic, settings)
        while status['thread'].is_alive():
            job.say('Transcribing the recording on this PC (%d%%)' % status['progress']); time.sleep(1.5)
        if status['error']:
            TRANSCRIBING.pop(str(proj), None)
            raise ValueError('Transcription failed: ' + status['error'])
    segs = read_json(f)
    return segs.get('segments', segs) if isinstance(segs, dict) else segs


def timeline_mapping(ctx, req=None):
    """The cut map for the sequence open in Premiere, from the recording's clips on it.

    spans are the clips of the recording on the timeline, each as start (sequence seconds) and in/out (source seconds).
    The panel reads them fresh with every request, and the last ones are kept in project.json."""
    spans = (req or {}).get('spans') or ctx['state'].get('timeline')
    if not spans: raise ValueError('Open the sequence with your recording on it in Premiere first')
    timing = ctx['e']['timing']; r = timing.rate(ctx['fps']); fps = float(r)
    out = []
    for sp in sorted(spans, key=lambda x: float(x['start'])):
        si, so, oi = int(round(float(sp['in']) * fps)), int(round(float(sp['out']) * fps)), int(round(float(sp['start']) * fps))
        if so <= si: continue
        out.append(dict(source_in_frame=si, source_out_frame=so, out_in_frame=oi, out_out_frame=oi + so - si,
                        audio_in_seconds=si / fps + ctx['offset'], audio_out_seconds=so / fps + ctx['offset']))
    if not out: raise ValueError('The recording has no clips on the open sequence')
    return dict(version=1, fps=str(r), audio_minus_video_seconds=float(ctx['offset']),
                duration_frames=max(x['out_out_frame'] for x in out), spans=out)


def removal(keeps, lo, hi):
    """Source seconds to take out of the timeline: everything between lo and hi that isn't kept."""
    out, p = [], lo
    for a, b in sorted(keeps):
        if b <= p: continue
        if a > p: out.append([p, min(a, hi)])
        p = max(p, b)
    if p < hi: out.append([p, hi])
    return [[round(a, 4), round(b, 4)] for a, b in out if b - a > .0005]


def on_timeline(remove, spans):
    """How much of what's on the timeline a removal takes out, and how many gaps it makes."""
    total = sum(float(s['out']) - float(s['in']) for s in spans)
    gone, gaps = 0.0, 0
    for s in spans:
        lo, hi = float(s['in']), float(s['out'])
        for a, b in remove:
            x, y = max(a, lo), min(b, hi)
            if y - x > .02: gone += y - x; gaps += 1   # slivers under a frame aren't cuts the panel makes
    return dict(source_seconds=round(total, 1), removed_seconds=round(gone, 1), output_seconds=round(total - gone, 1), cuts=gaps)


def cut_result(job, ctx, req, remove, flags, extra=None):
    """What the panel needs to cut the open sequence in place, and a record of it in the project."""
    spans = req.get('spans') or []
    if not spans and req.get('range'): spans = [{'start': 0, 'in': float(req['range'][0]), 'out': float(req['range'][1])}]
    stats = on_timeline(remove, spans) if spans else {}
    rate = ctx['e']['timing'].rate(ctx['fps'])
    result = dict(stage=job.stage, remove=remove, video=str(Path(ctx['video']['path'])), sequence_name=req.get('name'),
                  fps=str(rate), fps_num=rate.numerator, fps_den=rate.denominator, has_layers=keep_layers(ctx['proj']),
                  markers=[dict(kind=f['kind'], reason=f['reason'], source_seconds=f['source_seconds']) for f in flags], **stats)
    result.update(extra or {})
    if ctx.get('stage_dir'): write_json(ctx['stage_dir'] / 'result.json', result)
    state = project_state(ctx['proj'])
    key = 'clean' if job.stage == 'silences' else 'flubs_applied'
    state.setdefault('stages', {})[key] = dict(dir=str(ctx['stage_dir'] or ''), sequence_name=req.get('name') or '',
                                               xml='', created=time.strftime('%Y-%m-%d %H:%M:%S'))
    state.setdefault('cuts', []).append(dict(stage=job.stage, when=time.strftime('%Y-%m-%d %H:%M:%S'), sequence=req.get('name'),
                                             removed_seconds=stats.get('removed_seconds')))
    del state['cuts'][:-50]
    save_state(ctx['proj'], state)
    return result


def finish(job, ctx, keeps, decisions, flags, shots, post=None, name=None, label=None, with_layers=False):
    e = ctx['e']; timing = e['timing']; video = ctx['video']; audio = ctx['audio']; stage_dir = ctx['stage_dir']
    job.say('Building the Premiere sequence')
    mapping = timing.build_map(keeps, ctx['fps'], ctx['offset'], video['duration'], audio['duration'])
    lay = None
    if with_layers and ctx.get('words'):
        job.say('Working out where the animations and other layers go')
        lay = place_layers(job, ctx, mapping)
        flags = flags + lay['flags']
        write_json(stage_dir / 'layers.json', lay)
    mapping.update(source_video=video, source_audio=audio, sync=ctx['sync'])
    for f in flags:
        f['out_frame'] = timing.map_source(mapping, f['source_seconds']) if 'source_seconds' in f else None
    write_json(stage_dir / 'keeps.json', keeps); write_json(stage_dir / 'timing_map.json', mapping)
    write_json(stage_dir / 'decisions.json', decisions); write_json(stage_dir / 'flags.json', flags)
    if shots: write_json(stage_dir / 'shots.json', shots)
    xml = e['export'].export_xml(stage_dir, mapping, video, audio, shots, flags)
    seq_name = '%s - %s' % (safe_name(name or Path(video['path']).stem), label or LABELS[job.stage])
    data = Path(xml).read_text(encoding='utf-8')
    data = data.replace('<name>DaJoshiResolve - EDITABLE DRAFT</name>', '<name>%s</name>' % seq_name, 1)
    extra = {}
    if post:
        data, extra = post(data, mapping)
        from dajoshi.interchange import validate
        write_json(stage_dir / 'xml_validation_final.json', validate(data.encode('utf-8')))
    named = stage_dir / (seq_name + '.xml'); named.write_text(data, encoding='utf-8')
    fps = float(timing.rate(ctx['fps']))
    result = dict(xml=str(named), sequence_name=seq_name, stage=job.stage, folder=str(stage_dir),
                  output_seconds=round(mapping['duration_frames'] / fps, 2), source_seconds=round(float(video['duration']), 2),
                  cuts=len(decisions), markers=sum(1 for f in flags if f.get('out_frame') is not None),
                  shots=len([s for s in shots if s.get('asset')]), **extra)
    result['fps'] = str(timing.rate(ctx['fps']))
    result['audio_offset'] = float(ctx['offset'])
    rate = timing.rate(ctx['fps'])
    result['fps_num'], result['fps_den'] = rate.numerator, rate.denominator
    result['spans'] = [dict(start=sp['out_in_frame'] / fps, src_in=sp['source_in_frame'] / fps, src_out=sp['source_out_frame'] / fps,
                            start_f=sp['out_in_frame'], in_f=sp['source_in_frame'], out_f=sp['source_out_frame'])
                       for sp in mapping['spans']]
    if lay:
        result.update(layers=lay['clips'], layer_note=lay['note'], layer_counts=lay['counts'], layers_dropped=lay['dropped'])
    write_json(stage_dir / 'result.json', result)
    state = project_state(ctx['proj'])
    key = 'clean' if job.stage in ('silences', 'apply') else job.stage
    state.setdefault('stages', {})[key] = dict(dir=str(stage_dir), keeps=keeps, xml=str(named), sequence_name=seq_name,
                                                    created=time.strftime('%Y-%m-%d %H:%M:%S'), **extra)
    if key == 'clean' and not (lay and lay['counts']['full']): state['stages'].pop('build', None)
    save_state(ctx['proj'], state)
    return result


# ---------------------------------------------------------------- pass 1: clean cut

PRESETS = {
    'calm': dict(max_pause=.80, pad_before=.14, pad_after=.18),
    'measured': dict(max_pause=.55, pad_before=.10, pad_after=.13),
    'paced': dict(max_pause=.40, pad_before=.08, pad_after=.10),
    'energetic': dict(max_pause=.25, pad_before=.05, pad_after=.07),
}


def silence_settings(state, req=None):
    s = dict(threshold_db=None, cut_sounds=True, preset='paced'); s.update(PRESETS['paced']); s.update(CONFIG.get('clean', {}))
    s.update(state.get('silence_settings', {}))
    if req and req.get('settings'):
        given = req['settings']
        if given.get('preset') in PRESETS: s.update(PRESETS[given['preset']])
        s.update({k: v for k, v in given.items() if k in s})
    return s


def audio_levels(ctx):
    if 'db' not in ctx:
        ctx['db'] = cleancut.db_profile(ctx['mic'])
        ctx['levels'] = cleancut.levels(ctx['db'])
    return ctx['db'], ctx['levels']


def plan_cut(ctx, req, removed):
    settings = silence_settings(ctx['state'], req)
    db, (floor, speech, auto) = audio_levels(ctx)
    thr = auto if settings.get('threshold_db') in (None, '', 'auto') else float(settings['threshold_db'])
    sound, dropped = cleancut.acoustic_keeps(db, thr, speech, settings)
    off = ctx['offset']
    keeps = [[a - off, b - off] for a, b in sound]
    if removed and ctx.get('words'):
        e = 10 ** (db / 20.0)
        cuts = cleancut.word_cuts(ctx['words'], removed, e, 10 ** (thr / 20.0))
        keeps = ctx['e']['timing'].subtract(keeps, [[a - off, b - off] for a, b in cuts])
    dur = float(ctx['video']['duration'])
    keeps = [[max(0.0, a), min(dur, b)] for a, b in keeps if min(dur, b) > max(0.0, a)]
    if req.get('range'):
        lo, hi = map(float, req['range'])
        keeps = [[max(a, lo), min(b, hi)] for a, b in keeps if min(b, hi) > max(a, lo)]
        source = hi - lo
    else:
        source = dur
    if not keeps: raise ValueError('Those settings would cut everything. Lower the noise threshold.')
    kept = sum(b - a for a, b in keeps)
    return dict(keeps=keeps, settings=settings, threshold=thr, auto_db=round(auto, 1),
                stats=dict(cuts=max(0, len(keeps) - 1), removed_seconds=round(source - kept, 1),
                           output_seconds=round(kept, 1), source_seconds=round(source, 1), sounds=dropped,
                           threshold_db=round(thr, 1)))


def remember_source(ctx, req):
    """The first sequence a recording is cut from is the original; later cuts always start from it."""
    state = ctx['state']
    if req.get('name') and not str(req['name']).endswith((SUFFIX,) + OLD_SUFFIXES):
        state['source'] = {k: req.get(k) for k in ('video', 'audio', 'audio_offset', 'range', 'name')}
        save_state(ctx['proj'], state)


def word_flags(ctx, groups):
    words = ctx['words'] or []; flags = []
    for r in groups:
        a, b = r['from'], r['to']
        if not 0 <= a <= b < len(words): continue
        said = ' '.join(w['word'].strip() for w in words[a:b + 1])
        flags.append(dict(kind='cut ' + str(r.get('why', 'flub')), reason='Removed: "%s"' % said[:200],
                          source_seconds=max(0.0, float(words[a]['start']) - ctx['offset'] - .08)))
    return flags


def run_prepare(job, req):
    ctx = prepare(job, req, need_dir=False, need_words=False)
    plan = plan_cut(ctx, req, [])
    return dict(stage='prepare', settings=plan['settings'], auto_db=plan['auto_db'], stats=plan['stats'])


def has_layers(proj):
    """True when this recording has built animations or planned angle shots or B-roll to put back after a recut."""
    try:
        data = read_json(proj / 'shotlist.json') if (proj / 'shotlist.json').exists() else None
        if built_animations(data): return True
        return any(layers.load_plan(proj, k)['items'] for k in layers.PLANS)
    except Exception:
        traceback.print_exc(); return False


def keep_layers(proj):
    return prefs().get('keep_layers', True) and has_layers(proj)


def run_silences(job, req):
    ctx = prepare(job, req, need_words=False)
    state = ctx['state']
    if req.get('settings'):
        state['silence_settings'] = silence_settings(state, req); save_state(ctx['proj'], state)
    job.say('Finding the silences, breaths and noises')
    plan = plan_cut(ctx, req, [])
    remove = removal(plan['keeps'], 0.0, float(ctx['video']['duration']))
    return cut_result(job, ctx, req, remove, [], dict(sounds=plan['stats']['sounds'], threshold_db=plan['stats']['threshold_db']))


def run_flubs(job, req):
    ctx = prepare(job, req, need_dir=False); words = ctx['words']; proj = ctx['proj']
    e_prof, thr = cleancut.energy_profile(ctx['mic'])
    text = cleancut.annotate(words, e_prof, thr)
    digest = hashlib.sha1((text + MODELS['clean'] + prompts.CLEAN_SYSTEM).encode()).hexdigest()
    cache = proj / 'clean-decision.json'
    if cache.exists() and read_json(cache).get('digest') == digest and not req.get('fresh'):
        removals = read_json(cache)['remove']; job.say('Reusing Claude\'s earlier read of this transcript')
    else:
        job.say('Claude is reading the transcript for repeats and flubs (%d words)' % len(words))
        reply = claude_api.call(api_key(), MODELS['clean'], prompts.CLEAN_SYSTEM,
                                'Transcript of the raw recording:\n\n' + text, max_tokens=16000,
                                on_progress=lambda n: job.say('Claude is marking the flubs (%d characters so far)' % n))
        removals = claude_api.extract_json(reply).get('remove', [])
        write_json(cache, dict(digest=digest, model=MODELS['clean'], remove=removals))
    clean = []
    for r in removals:
        a, b = int(r.get('from', -1)), int(r.get('to', -1))
        if 0 <= a <= b < len(words): clean.append({'from': a, 'to': b, 'why': str(r.get('why', 'flub'))})
    write_json(proj / 'flubs.json', dict(created=time.strftime('%Y-%m-%d %H:%M:%S'), remove=clean))
    return dict(stage='flubs', groups=len(clean), words=sum(r['to'] - r['from'] + 1 for r in clean))


def run_apply(job, req):
    ctx = prepare(job, req); state = ctx['state']; words = ctx['words']
    removed = sorted({int(i) for i in req.get('removed', []) if 0 <= int(i) < len(words)})
    groups, start = [], None
    for k, i in enumerate(removed):
        if start is None: start = i
        if k + 1 == len(removed) or removed[k + 1] != i + 1:
            groups.append({'from': start, 'to': i, 'why': 'flub'}); start = None
    state['removed_words'] = removed; state['removals'] = groups; save_state(ctx['proj'], state)
    job.say('Cutting %d words' % len(removed))
    db, (floor, speech, auto) = audio_levels(ctx)
    settings = silence_settings(state, req)
    thr = auto if settings.get('threshold_db') in (None, '', 'auto') else float(settings['threshold_db'])
    cuts = cleancut.word_cuts(words, removed, 10 ** (db / 20.0), 10 ** (thr / 20.0)) if removed else []
    off = ctx['offset']
    remove = [[round(max(0.0, a - off), 4), round(b - off, 4)] for a, b in ctx['e']['timing'].merge([[a, b] for a, b in cuts]) if b - off > 0]
    return cut_result(job, ctx, req, remove, word_flags(ctx, groups), dict(words=len(removed)))


# ---------------------------------------------------------------- pass 2: shot list

def kept_words(ctx, mapping):
    """Indexes of words that survive the clean cut, with their output time."""
    timing = ctx['e']['timing']; removed = set(ctx['state'].get('removed_words', [])); fps = float(timing.rate(ctx['fps']))
    out = []
    for i, w in enumerate(ctx['words']):
        if i in removed: continue
        f = timing.map_source(mapping, float(w['start']) - ctx['offset'])
        if f is not None: out.append((i, f / fps))
    return out


def clean_transcript(ctx, kept):
    lines, cur, words = [], [], ctx['words']
    for i, t in kept:
        if words[i].get('segment_start') and cur:
            lines.append(' '.join(cur)); cur = []
        if not cur: cur.append('[%s]' % tc(t))
        cur.append('#%d %s' % (i, words[i]['word'].strip()))
    if cur: lines.append(' '.join(cur))
    return '\n'.join(lines)


def snap_press(ctx, kept_idx, word, quote):
    """Make sure a press sits on a kept word whose text matches its quote."""
    words = ctx['words']; q = norm(quote)
    pos = {i: k for k, i in enumerate(kept_idx)}
    if not q:
        return word
    def score(k):
        span = ' '.join(words[kept_idx[j]]['word'] for j in range(k, min(len(kept_idx), k + len(q))))
        return SequenceMatcher(None, q, norm(span), autojunk=False).ratio()
    near = min(range(len(kept_idx)), key=lambda k: abs(kept_idx[k] - word)) if word not in pos else pos[word]
    best = max(range(max(0, near - 40), min(len(kept_idx), near + 41)), key=lambda k: (round(score(k), 2), -abs(k - near)))
    return kept_idx[best] if score(best) >= .5 else kept_idx[near]


ANIM_DEFAULTS = dict(types=['full', 'pip'], often='medium', rich='designed', style='josh-house',
                     pip_shape='tall-box', pip_side='right', half_side='left')


def anim_settings(state, given=None):
    """The Animations screen's choices for this recording: shot types, how often, how rich, style and layout."""
    s = dict(ANIM_DEFAULTS); s.update(state.get('anim', {}))
    for k, v in (given or {}).items():
        if k not in ANIM_DEFAULTS: continue
        if k == 'types': v = [t for t in prompts.SHOT_TYPES if t in (v or [])] or ['full']
        s[k] = v
    if s['often'] not in prompts.OFTEN: s['often'] = 'medium'
    if s['rich'] not in prompts.RICH: s['rich'] = 'designed'
    if s['pip_shape'] not in style.SHAPES: s['pip_shape'] = 'tall-box'
    if s['pip_side'] not in ('left', 'right'): s['pip_side'] = 'right'
    if s['half_side'] not in ('left', 'right'): s['half_side'] = 'left'
    return s


def pick_type(value, allowed):
    t = str(value or '').lower().strip()
    aliases = {'picture in picture': 'pip', 'full screen': 'full', 'fs': 'full', 'half and half': 'half', 'end screen': 'end',
               'key word': 'kw', 'keyword': 'kw', 'lower third': 'lt', 'title card': 'title'}
    t = aliases.get(t, t)
    if t in allowed: return t
    return 'full' if 'full' in allowed else allowed[0]


def tidy_animation(ctx, a, kept_idx, number, opts=None):
    opts = opts or ANIM_DEFAULTS
    a = dict(a); a['number'] = number
    a['type'] = pick_type(a.get('type'), opts['types'])
    if opts.get('rich', 'designed') != 'designed': a['rich'] = opts['rich']
    else: a.pop('rich', None)
    a['name'] = str(a.get('name', 'Animation %d' % number)).strip()[:80]
    a['description'] = str(a.get('description', '')).strip()
    presses = []
    for p in a.get('presses', []):
        w = snap_press(ctx, kept_idx, int(p.get('word', 0)), str(p.get('quote', '')))
        if presses and w <= presses[-1]['word']: continue
        presses.append(dict(word=w, quote=str(p.get('quote', '')).strip(), shows=str(p.get('shows', '')).strip()))
    if not presses: return None
    a['presses'] = presses
    end = int(a.get('end_word', presses[-1]['word']))
    a['end_word'] = max(end, presses[-1]['word'])
    a['sketch_svg'] = str(a.get('sketch_svg', ''))
    return a


def save_shotlist(ctx, data):
    write_json(ctx['proj'] / 'shotlist.json', data)
    write_markdown(ctx, data)


def write_markdown(ctx, data):
    words = ctx['words']; lines = ['# Shot list · %s' % Path(ctx['video']['path']).stem, '']
    if data.get('instructions'): lines += ['Notes given: %s' % data['instructions'], '']
    for a in data['animations']:
        lines.append('**Insert Animation %d** (%s) %s' % (a['number'], deck.TYPE_LABEL.get(a['type'], 'Full screen').lower(), a['name']))
        lines.append(a['description'])
        for k, p in enumerate(a['presses'], 1):
            lines.append('Press %d on "%s" (%s)' % (k, p['quote'], p['shows']))
        lines.append('Back to talking head after "%s"' % words[a['end_word']]['word'].strip()); lines.append('')
    (ctx['proj'] / 'shotlist.md').write_text('\n'.join(lines), encoding='utf-8')


def render_sketches(job, ctx, animations):
    folder = ctx['proj'] / 'sketches'; folder.mkdir(exist_ok=True)
    items = []
    for a in animations:
        svg = a.get('sketch_svg') or ''
        key = hashlib.sha1(svg.encode()).hexdigest()[:10]
        a['sketch'] = 'anim%02d-%s' % (a['number'], key)
        (folder / (a['sketch'] + '.svg')).write_text(svg, encoding='utf-8')
        if svg and not (folder / (a['sketch'] + '.png')).exists():
            items.append((svg, folder / (a['sketch'] + '.png')))
    if not items: return
    job.say('Drawing %d concept sketches' % len(items))
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try: browser = p.chromium.launch(channel='chrome', headless=True)
            except Exception: browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 960, 'height': 540})
            for svg, out in items:
                page.set_content('<html><body style="margin:0;background:#fff">%s</body></html>' % svg.replace(
                    '<svg', '<svg width="960" height="540" preserveAspectRatio="xMidYMid meet"', 1))
                page.screenshot(path=str(out))
            browser.close()
    except Exception as ex:
        job.say('Sketch images could not be drawn (%s); the panel will show the SVGs instead' % ex)


def tidy_plan(ctx, raw, kept, opts):
    """Clean Claude's animations, keep them in order and apart, and hold the end screen to the last 20 seconds."""
    kept_idx = [i for i, _ in kept]; at = dict(kept); total = kept[-1][1] if kept else 0
    animations, number = [], 1
    for a in sorted(raw, key=lambda x: (x.get('presses') or [{}])[0].get('word', 0)):
        t = tidy_animation(ctx, a, kept_idx, number, opts)
        if t and t['type'] == 'end':
            t = end_screen(t, kept, total)
            if any(x['type'] == 'end' for x in animations): t = None
        if t and (not animations or t['presses'][0]['word'] > animations[-1]['end_word']):
            animations.append(t); number += 1
    return animations


def end_screen(a, kept, total):
    """YouTube end screens can only run in the last 20 seconds, so the shot starts there at the earliest."""
    late = [i for i, t in kept if t >= total - 19.5]
    if not late: return a
    a = dict(a)
    presses = [p for p in a['presses'] if p['word'] >= late[0]]
    if not presses:
        first = dict(a['presses'][0]); first['word'] = late[0]; presses = [first]
    a['presses'] = presses; a['end_word'] = kept[-1][0]
    return a


def frequency_gap(animations, kept, opts):
    """How far the plan is from how often Josh asked for. Returns (target, gap seconds) or None when it's close enough."""
    if not kept: return None
    at = dict(kept); total = kept[-1][1]; minutes = total / 60.0
    count = len(animations); per = prompts.OFTEN[opts['often']][1]
    target = max(1, int(round(total / per)))
    if opts['often'] == 'heavy':
        edges = [0.0] + [x for a in animations for x in (at.get(a['presses'][0]['word'], 0), at.get(a['end_word'], 0))] + [total]
        gaps = [edges[i + 1] - edges[i] for i in range(0, len(edges) - 1, 2)]
        if gaps and max(gaps) > 55: return target, int(max(gaps))
    if opts['often'] == 'light':
        return (target, None) if count > target * 1.5 + 1 else None
    if count < target * .6 or count > target * 1.5 + 1: return target, None
    return None


def run_shotlist(job, req):
    ctx = prepare(job, req, need_dir=False)
    mapping = timeline_mapping(ctx, req)
    state = ctx['state']; opts = anim_settings(state, req.get('anim'))
    state['anim'] = opts; save_state(ctx['proj'], state)
    kept = kept_words(ctx, mapping)
    transcript = clean_transcript(ctx, kept)
    notes = (req.get('instructions') or '').strip()
    user = 'Video file: %s\n\n' % Path(ctx['video']['path']).stem
    if notes: user += 'Josh\'s notes for this video (follow them):\n%s\n\n' % notes
    user += 'Clean transcript:\n\n' + transcript
    system = prompts.shot_system(opts)
    job.say('Claude is planning the animations')
    reply = claude_api.call(api_key(), MODELS['shotlist'], system, user, max_tokens=48000,
                            on_progress=lambda n: job.say('Claude is writing the shot list (%d characters so far)' % n))
    parsed = claude_api.extract_json(reply, salvage='animations', need='presses')
    if parsed.get('salvaged'): job.say("Part of Claude's reply couldn't be read, so %d animations were kept from it" % len(parsed['animations']))
    animations = tidy_plan(ctx, parsed.get('animations', []), kept, opts)
    off = frequency_gap(animations, kept, opts)
    if off:
        target, gap = off
        job.say('Asking Claude to bring the plan closer to %s (%d animations, aiming for about %d)' % (opts['often'], len(animations), target))
        note = prompts.retarget_note(len(animations), target, kept[-1][1] / 60.0, prompts.OFTEN[opts['often']][0], gap)
        plan = [{k: v for k, v in a.items() if k not in ('sketch_svg', 'sketch')} for a in animations]
        reply2 = claude_api.call(api_key(), MODELS['shotlist'], system,
                                 user + '\n\nYour plan:\n' + json.dumps(plan, indent=1) + '\n\n' + note, max_tokens=48000,
                                 on_progress=lambda n: job.say('Claude is adjusting the shot list (%d characters so far)' % n))
        try: again = tidy_plan(ctx, claude_api.extract_json(reply2, salvage='animations', need='presses').get('animations', []), kept, opts)
        except claude_api.ClaudeError: again = []   # keep the first plan if the second reply can't be read
        if again:
            old = {json.dumps(a['presses']): a.get('sketch_svg') for a in animations}
            for a in again:
                if not a.get('sketch_svg'): a['sketch_svg'] = old.get(json.dumps(a['presses']), '')
            animations = again
    if not animations: raise ValueError('Claude did not return any usable animations')
    render_sketches(job, ctx, animations)
    data = dict(created=time.strftime('%Y-%m-%d %H:%M:%S'), instructions=notes, approved=False, animations=animations, settings=opts)
    save_shotlist(ctx, data)
    return dict(stage='shotlist', animations=len(animations), shotlist=str(ctx['proj'] / 'shotlist.md'))


def run_redo(job, req):
    ctx = prepare(job, req, need_dir=False)
    mapping = timeline_mapping(ctx, req)
    data = read_json(ctx['proj'] / 'shotlist.json')
    n = int(req['number']); target = next((a for a in data['animations'] if a['number'] == n), None)
    if not target: raise ValueError('No animation %d in the shot list' % n)
    kept = kept_words(ctx, mapping); kept_idx = [i for i, _ in kept]
    plan = [{k: v for k, v in a.items() if k not in ('sketch_svg', 'sketch')} for a in data['animations']]
    user = ('Clean transcript:\n\n%s\n\nThe current plan:\n%s\n\nRevise animation %d. Josh\'s note: %s' %
            (clean_transcript(ctx, kept), json.dumps(plan, indent=1), n, req.get('note') or 'Try a different idea.'))
    job.say('Claude is reworking animation %d' % n)
    opts = anim_settings(ctx['state'])
    reply = claude_api.call(api_key(), MODELS['shotlist'], prompts.redo_system(opts), user, max_tokens=12000)
    new = tidy_animation(ctx, claude_api.extract_json(reply), kept_idx, n, opts)
    if not new: raise ValueError('Claude did not return a usable animation')
    if new['type'] == 'end': new = end_screen(new, kept, kept[-1][1])
    render_sketches(job, ctx, [new])
    data['animations'] = [new if a['number'] == n else a for a in data['animations']]
    data['approved'] = False
    save_shotlist(ctx, data)
    return dict(stage='redo', number=n)


# ---------------------------------------------------------------- pass 3: build

def build_scene(ctx, a, transcript_lines):
    system = prompts.deck_system(a['type'], a.get('rich', 'designed')).replace('{css}', deck.prompt_css()).replace('{examples}', deck.examples())
    spec = dict(type=deck.TYPE_LABEL.get(a['type'], 'Full screen').lower(), name=a['name'],
                description=a['description'],
                presses=[dict(press=k, says=p['quote'], shows=p['shows']) for k, p in enumerate(a['presses'], 1)])
    user = ('Build this animation as one <section>.\n\n%s\n\nWhat he says around it:\n%s'
            % (json.dumps(spec, indent=1), transcript_lines))
    last = None
    for attempt in range(2):
        prompt = user if not last else user + '\n\nYour previous attempt was rejected: %s. Fix that.' % last
        reply = claude_api.call(api_key(), MODELS['deck'], system, prompt, max_tokens=16000)
        try:
            return deck.check_section(claude_api.extract_section(reply), len(a['presses']), a['type'])
        except Exception as ex:
            last = str(ex)
    raise ValueError('Animation %d could not be built: %s' % (a['number'], last))


def context_lines(ctx, a, kept):
    words = ctx['words']; idx = [i for i, _ in kept]
    lo = max(0, idx.index(a['presses'][0]['word']) - 40) if a['presses'][0]['word'] in idx else 0
    hi = min(len(idx), (idx.index(a['end_word']) if a['end_word'] in idx else lo + 120) + 20)
    return ' '.join(words[i]['word'].strip() for i in idx[lo:hi])


def run_build(job, req):
    ctx = prepare(job, req)
    mapping = timeline_mapping(ctx, req)
    keeps = [[sp['source_in_frame'] / float(ctx['e']['timing'].rate(ctx['fps'])), sp['source_out_frame'] / float(ctx['e']['timing'].rate(ctx['fps']))]
             for sp in mapping['spans']]
    data = read_json(ctx['proj'] / 'shotlist.json')
    animations = data['animations']
    kept = kept_words(ctx, mapping)
    scenes_dir = ctx['proj'] / 'scenes'; scenes_dir.mkdir(exist_ok=True)

    def one(a):
        f = scenes_dir / ('anim%02d-%s.html' % (a['number'], spec_digest(a)))
        if f.exists(): return a['number'], f.read_text(encoding='utf-8')
        html = build_scene(ctx, a, context_lines(ctx, a, kept)); f.write_text(html, encoding='utf-8')
        return a['number'], html

    job.say('Claude is building %d animations in the house style' % len(animations))
    sections, done = {}, 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(CONFIG.get('parallel_builds', 4))) as pool:
        for n, html in pool.map(one, animations):
            sections[n] = html; done += 1
            job.say('Built animation %d of %d' % (done, len(animations)))
    for a in animations: a['section'] = sections[a['number']]
    opts = anim_settings(ctx['state'], req.get('anim'))
    st = style.load(opts['style'])
    if style.missing_fonts(st):
        raise ValueError('The %s fonts aren\'t on this PC yet. Pick another style or font pairing.' % style.PAIRINGS[st['fonts']]['label'])
    title = Path(ctx['video']['path']).stem
    page, beats, keys = deck.assemble(title, animations, st, opts)
    for a in animations: a.pop('section', None)
    deck_path = ctx['proj'] / ('deck-%s.html' % time.strftime('%Y%m%d-%H%M%S'))
    deck_path.write_text(page, encoding='utf-8'); (ctx['proj'] / 'deck.html').write_text(page, encoding='utf-8')
    data['approved'] = True; data['built_deck'] = str(deck_path)
    data['beats'] = {str(n): list(b) for n, b in beats.items()}
    data['scene_keys'] = {str(n): k for n, k in keys.items()}
    data['built_specs'] = {str(a['number']): spec_digest(a) for a in animations}
    data['built_with'] = dict(style=opts['style'], pip_shape=opts['pip_shape'], pip_side=opts['pip_side'], half_side=opts['half_side'])
    data['version'] = layers.PLAN_VERSION
    write_json(ctx['proj'] / 'shotlist.json', data)
    state = project_state(ctx['proj']); state['anim'] = opts; save_state(ctx['proj'], state); ctx['state'] = state

    if prefs().get('animations_own_sequence'):
        # The old route lays the camera over an opaque render, so it only knows full screen and boxed PiP.
        shots, flags, dropped = animation_shots(ctx, mapping, data, alpha=False)
        kept_shots = [s for s in shots if s['layout'] in ('graphic', 'pip')]
        for s in shots:
            if s not in kept_shots:
                flags.append(dict(kind='animation skipped', reason='Animation %d is a %s, which only works on V5 of the Josh Cut sequence'
                                  % (s['animation'], deck.TYPE_LABEL[s['type']].lower()), source_seconds=0))
        shots = kept_shots
        render_shots(job, ctx, shots, deck_path)
        box = style.pip_box(opts)
        cfg = dict(pip_settings(ctx['state']), box=box['outer'])

        def post(xml_text, mp):
            text, n = pip.apply(xml_text, mp, shots, ctx['video'], cfg)
            return text, dict(pip_clips=n, deck=str(deck_path))
        return finish(job, ctx, keeps, [], flags, shots, post, name=req.get('name'))
    # The animations go on V5 of the open sequence, with camera copies on V4.
    return layer_result(job, ctx, mapping, dict(sequence_name=req.get('name')))


def layer_result(job, ctx, mapping, extra=None):
    job.say('Working out where the animations and other layers go')
    lay = place_layers(job, ctx, mapping)
    if ctx.get('stage_dir'): write_json(ctx['stage_dir'] / 'layers.json', lay)
    rate = ctx['e']['timing'].rate(ctx['fps'])
    result = dict(stage=job.stage, layers=lay['clips'], layer_note=lay['note'], layer_counts=lay['counts'], layers_dropped=lay['dropped'],
                  fps=str(rate), fps_num=rate.numerator, fps_den=rate.denominator, **(extra or {}))
    if job.stage == 'build':
        state = project_state(ctx['proj'])
        state.setdefault('stages', {})['build'] = dict(dir=str(ctx['stage_dir'] or ''), sequence_name=(extra or {}).get('sequence_name') or '',
                                                      xml='', created=time.strftime('%Y-%m-%d %H:%M:%S'))
        save_state(ctx['proj'], state)
    return result


def run_layers(job, req):
    """After a cut, put the animations back on their words in the open sequence."""
    ctx = prepare(job, req)
    return layer_result(job, ctx, timeline_mapping(ctx, req))


def spec_digest(a):
    parts = [a['type'], a['name'], a['description'], a['presses'], MODELS['deck']]
    if a.get('rich'): parts.append(a['rich'])
    return hashlib.sha1(json.dumps(parts).encode()).hexdigest()[:10]


def built_animations(data):
    """Animations from the shot list that have been built into the current deck."""
    if not data or not data.get('built_deck') or not Path(data['built_deck']).exists() or not data.get('beats'): return []
    specs = data.get('built_specs', {})
    return [a for a in data['animations'] if str(a['number']) in data['beats']
            and (not specs or specs.get(str(a['number'])) == spec_digest(a))]


def cut_view(ctx, mapping):
    return layers.Cut(ctx['e']['timing'], mapping, ctx['words'], ctx['offset'], ctx['state'].get('removed_words', []))


# shot type -> how the overlap planner ranks it
RESOLVE_KIND = dict(full='full', title='full', end='full', half='half', pip='pip', kw='overlay', lt='overlay')


def animation_shots(ctx, mapping, data, cut=None, alpha=True):
    """One shot per press, placed from the press words through the current cut.

    Returns the shots, marker flags for anything skipped, and the animations
    that were dropped because all their words have been cut."""
    cut = cut or cut_view(ctx, mapping); fps = cut.fps
    shots, flags, dropped = [], [], []
    animations = built_animations(data)
    starts = []
    for a in animations:
        w = cut.locate(a['presses'][0]['word'], a['end_word'])
        starts.append(w['lo'] if w else None)
    for j, a in enumerate(animations):
        whole = cut.locate(a['presses'][0]['word'], a['end_word'], 0, .25)
        if not whole:
            dropped.append(dict(kind=RESOLVE_KIND.get(a['type'], 'full'), number=a['number'], why='cut'))
            flags.append(dict(kind='animation skipped', reason='Animation %d falls in cut material' % a['number'],
                              source_seconds=cut.source(a['presses'][0]['word'])))
            continue
        cap = next((s for s in starts[j + 1:] if s is not None), None)
        end = min(whole['hi'], cap) if cap is not None else whole['hi']
        los = []
        for p in a['presses']:
            w = cut.locate(p['word'], a['end_word'])
            los.append(w['lo'] if w else None)
        beats = data['beats'][str(a['number'])]
        scene_key = (data.get('scene_keys') or {}).get(str(a['number']))
        see_through = alpha and a['type'] in deck.ALPHA
        mine = []
        for k, p in enumerate(a['presses']):
            lo = los[k]
            if lo is None: continue
            hi = next((x for x in los[k + 1:] if x is not None), end)
            if shots and lo < shots[-1]['out_end']: lo = shots[-1]['out_end']
            if hi <= lo: continue
            beat = beats[k]
            mine.append(dict(layout='pip' if a['type'] == 'pip' else 'graphic', type=a['type'], beat=beat, previous=beat - 1 if k else None,
                             out_start=lo, out_end=hi, animation=a['number'], press=k + 1, alpha=see_through,
                             key=[scene_key, k] if scene_key else None,
                             # The motion length stays the same whatever the press length, so a recut can reuse the render.
                             contract=dict(motion_frames=round(2.5 * fps), handle_frames=round(5 * fps),
                                           scene_selector='.scene', active_selector='.scene.on')))
        shots.extend(mine)
    return shots, flags, dropped


def render_scale(ctx):
    """How much bigger than 1920 by 1080 the open sequence is, so renders come out at its size."""
    return max(1, round(ctx['frame'][0] / 1920.0, 3))


def render_shots(job, ctx, shots, deck_path):
    """Render each press, reusing any cached render of that press that's long enough.

    Renders hold their last frame and add a hold handle, and new ones get two
    seconds of slack, so a recut that changes a press's length by a little
    usually needs no new render."""
    e = ctx['e']; settings = ctx['settings']; stage_dir = ctx['stage_dir']
    cache = ctx['proj'] / 'animation-cache'; cache.mkdir(exist_ok=True)
    deck_hash = hashlib.sha256(Path(deck_path).read_bytes()).hexdigest()[:16]
    fps = float(ctx['e']['timing'].rate(ctx['fps']))
    todo = []
    for s in shots:
        need = s['out_end'] - s['out_start']
        # A press is keyed by its own scene, the style and (for PiP and half and half) the layout, so changing
        # one animation or the PiP shape re-renders only what it touches. Older builds fall back to the whole deck.
        where = s.get('key') or [deck_hash, s['beat'], s['previous']]
        scale = render_scale(ctx)
        key = hashlib.sha1(json.dumps([where, s['contract'], str(ctx['fps']), s.get('alpha', False)] + ([scale] if scale != 1 else [])).encode()).hexdigest()[:12]
        stem = 'anim%02d-press%02d-%s' % (s['animation'], s['press'], key)
        ext = '.mov' if s.get('alpha') else '.mp4'
        have = sorted(((int(f.stem.rsplit('-', 1)[1][:-1]), f) for f in cache.glob(stem + '-*f' + ext)
                       if f.stem.rsplit('-', 1)[1][:-1].isdigit()), key=lambda x: x[0])
        hit = next((f for n, f in have if n >= need), None)
        if hit: s['asset'] = str(hit); continue
        frames = need + round(2 * fps)
        s['asset'] = str(cache / ('%s-%df%s' % (stem, frames + s['contract']['handle_frames'], ext)))
        todo.append((s, frames))
    for i, (s, frames) in enumerate(todo, 1):
        job.say('Rendering animation %d, press %d (%d of %d)' % (s['animation'], s['press'], i, len(todo)))
        request = stage_dir / ('render-%03d.json' % i)
        write_json(request, dict(deck=str(Path(deck_path).resolve()), beat=s['beat'], previous=s['previous'],
                                 frames=frames, fps=ctx['fps'], out=s['asset'], alpha=bool(s.get('alpha')), scale=render_scale(ctx),
                                 job=str(stage_dir), ffmpeg=settings['ffmpeg'], contract=s['contract']))
        e['media'].run([sys.executable, str(HERE / 'render.py'), str(request)], stage_dir,
                       'Render animation %d press %d' % (s['animation'], s['press']), timeout=900)


def place_layers(job, ctx, mapping):
    """Everything that sits on V2 to V6 of the Josh Cut sequence, worked out for this cut.

    Returns the clips for the panel to place, counts of what was put back and
    the items that had to be dropped."""
    proj = ctx['proj']; cut = cut_view(ctx, mapping); fps = cut.fps
    data = read_json(proj / 'shotlist.json') if (proj / 'shotlist.json').exists() else None
    shots, flags, dropped = animation_shots(ctx, mapping, data, cut) if data else ([], [], [])
    if shots:
        render_shots(job, ctx, shots, data['built_deck'])
    items = []
    for n in sorted({s['animation'] for s in shots}):
        mine = [s for s in shots if s['animation'] == n]
        items.append(dict(kind=RESOLVE_KIND.get(mine[0]['type'], 'full'), number=n,
                          lo=mine[0]['out_start'], hi=mine[-1]['out_end']))
    cameras = ctx['state'].get('cameras', {})
    for it in layers.angle_layers(cut, layers.load_plan(proj, 'angles'), cameras) + layers.broll_layers(cut, layers.load_plan(proj, 'broll')):
        if not it['where']: dropped.append(dict(kind=it['kind'], why='cut')); continue
        items.append(dict(it, lo=it['where']['lo'], hi=it['where']['hi']))
    kept, covered = layers.resolve(items, fps)
    dropped += covered

    clips = []
    built = (data or {}).get('built_with') or {}
    frames = {}
    for kind in ('pip', 'half'):
        box = style.camera_box(kind, built)
        frames[kind] = pip.framing(dict(pip_settings(ctx['state']), box=box, border=0), ctx['video']['width'], ctx['video']['height'])
        # framing works in 1920 by 1080 pixels. On a bigger sequence the camera has to be scaled up to match.
        frames[kind]['scale'] *= ctx['frame'][1] / 1080.0
    for s in shots:
        clips.append(dict(track=layers.TRACKS['animation'], kind='animation', path=s['asset'], start_f=s['out_start'],
                          in_f=0, out_f=s['out_end'] - s['out_start'], name='Animation %d press %d' % (s['animation'], s['press'])))
        if s['type'] in frames:
            # The camera copy on V4 shows through the hole or the open half of the animation above it.
            for p in cut.source_pieces(s['out_start'], s['out_end']):
                clips.append(dict(track=layers.TRACKS['camera'], kind='camera_copy', path=ctx['video']['path'],
                                  start_f=p['start_f'], in_f=p['src_f'], out_f=p['src_f'] + p['end_f'] - p['start_f'],
                                  framing=frames[s['type']], name='Camera for animation %d' % s['animation']))
    counts = dict(full=0, alt=0, broll=0)
    for it in kept:
        if it['kind'] in ('full', 'pip', 'half', 'overlay'): counts['full'] += 1; continue
        counts['alt' if it['kind'] in ('alt', 'demo') else 'broll'] += 1
        for piece in it['free']: clips.extend(layers.clips_for(cut, it, piece))
    return dict(clips=clips, counts=counts, dropped=[{k: v for k, v in d.items() if k in ('kind', 'number', 'why')} for d in dropped],
                flags=flags, note=layers.summary(counts, dropped))


PREFS_PATH = PROJECTS / 'prefs.json'
PREF_DEFAULTS = dict(keep_layers=True, animations_own_sequence=False)


def prefs():
    p = dict(PREF_DEFAULTS)
    if PREFS_PATH.exists():
        try: p.update(read_json(PREFS_PATH))
        except Exception: traceback.print_exc()
    return p


RUNNERS = dict(prepare=run_prepare, silences=run_silences, flubs=run_flubs, apply=run_apply,
               shotlist=run_shotlist, redo=run_redo, build=run_build, layers=run_layers)


COSTS = PROJECTS / 'claude-costs.csv'


def log_cost(job):
    """Note what Claude cost for this job, in the job and in Projects/claude-costs.csv."""
    c = claude_api.meter_total()
    if not c['calls']: return
    job.cost = c
    job.say('Claude cost about $%.2f (%d call%s, %s input and %s output tokens)' % (
        c['dollars'], c['calls'], '' if c['calls'] == 1 else 's',
        '{:,}'.format(c['input_tokens'] + c['cache_write_tokens'] + c['cache_read_tokens']), '{:,}'.format(c['output_tokens'])))
    try:
        new = not COSTS.exists()
        with open(COSTS, 'a', encoding='utf-8') as f:
            if new: f.write('when,stage,video,models,calls,input,cache_write,cache_read,output,dollars\n')
            video = (job.request.get('video') or {}).get('path', '') if isinstance(job.request.get('video'), dict) else str(job.request.get('video', ''))
            f.write('%s,%s,"%s",%s,%d,%d,%d,%d,%d,%.4f\n' % (
                time.strftime('%Y-%m-%d %H:%M'), job.stage, Path(video).name.replace('"', ''), ' '.join(c['models']), c['calls'],
                c['input_tokens'], c['cache_write_tokens'], c['cache_read_tokens'], c['output_tokens'], c['dollars']))
    except Exception:
        traceback.print_exc()


def cost_summary():
    """Totals from claude-costs.csv for the Settings screen."""
    import csv
    out = dict(month=0.0, total=0.0, jobs=0, videos=0, show=CONFIG.get('show_costs', True))
    if not COSTS.exists(): return out
    month = time.strftime('%Y-%m'); videos = set()
    with open(COSTS, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = float(row.get('dollars') or 0)
            out['total'] += d; out['jobs'] += 1; videos.add(row.get('video'))
            if (row.get('when') or '').startswith(month): out['month'] += d
    out['videos'] = len(videos); out['month'] = round(out['month'], 2); out['total'] = round(out['total'], 2)
    return out


def execute(job):
    with BUSY:
        job.state = 'running'
        claude_api.meter_reset()
        try:
            job.result = RUNNERS[job.stage](job, job.request)
            log_cost(job)
            job.state = 'complete'; job.say('Done')
        except Exception as ex:
            cancelled = type(ex).__name__ == 'Cancelled'
            log_cost(job)
            job.state = 'cancelled' if cancelled else 'failed'; job.error = str(ex)
            job.say(('Cancelled: ' if cancelled else 'Failed: ') + str(ex))
            if job.dir: (Path(job.dir) / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
            traceback.print_exc()


# ---------------------------------------------------------------- shot list views

def shotlist_view(video):
    proj = project_dir(video); f = proj / 'shotlist.json'
    if not f.exists(): return None
    data = read_json(f); state = project_state(proj)
    times = {}
    if state.get('timeline') and (proj / 'transcript.json').exists():
        try:
            segs = read_json(proj / 'transcript.json'); segs = segs.get('segments', segs) if isinstance(segs, dict) else segs
            words = [w for s in segs for w in s.get('words', [])]
            off = float(state.get('timeline_offset', 0))
            for a in data['animations']:
                t = float(words[a['presses'][0]['word']]['start']) - off
                hit = next((sp for sp in state['timeline'] if float(sp['in']) <= t < float(sp['out'])), None)
                times[a['number']] = tc(float(hit['start']) + t - float(hit['in'])) if hit else ''
        except Exception:
            traceback.print_exc()
    out = []
    for a in data['animations']:
        png = proj / 'sketches' / (a.get('sketch', '') + '.png')
        out.append(dict(number=a['number'], type=a['type'], type_label=deck.TYPE_LABEL.get(a['type'], 'Full screen'),
                        name=a['name'], description=a['description'],
                        presses=[dict(quote=p['quote'], shows=p['shows']) for p in a['presses']],
                        at=times.get(a['number'], ''),
                        sketch='/sketch?video=%s&name=%s&ext=%s' % (
                            quote(video), a.get('sketch', ''), 'png' if png.exists() else 'svg')))
    return dict(created=data.get('created'), instructions=data.get('instructions', ''), approved=data.get('approved', False),
                animations=out)


def shotlist_edit(body):
    proj = project_dir(body['video']); f = proj / 'shotlist.json'; data = read_json(f)
    if body.get('delete'):
        data['animations'] = [a for a in data['animations'] if a['number'] != int(body['delete'])]
        for k, a in enumerate(data['animations'], 1): a['number'] = k
    else:
        for a in data['animations']:
            if a['number'] == int(body['number']):
                for k in ('name', 'description'):
                    if k in body: a[k] = str(body[k]).strip()
                if body.get('type') in prompts.SHOT_TYPES: a['type'] = body['type']
    data['approved'] = False
    write_json(f, data)


# ---------------------------------------------------------------- quick views for the panel

class Quiet:
    stage = 'view'; dir = None
    def say(self, message): pass


_CTX = {}


def quick_ctx(req):
    """Cached context for live previews. Only works once the recording has been prepared."""
    key = json.dumps([req.get('video'), req.get('audio'), req.get('audio_offset')])
    hit = _CTX.get(key)
    proj = project_dir(req['video'])
    if hit and hit['state'].get('sources') == project_state(proj).get('sources'):
        hit['state'] = project_state(proj); return hit
    if not (proj / 'microphone.f32').exists():
        return None
    ctx = prepare(Quiet(), req, need_dir=False, need_words=False)
    _CTX.clear(); _CTX[key] = ctx
    return ctx


def make_pip_preview(video_path, state, out):
    """A still of Josh inside the PiP shape he picked, for the Animations screen."""
    video = engine()['media'].probe(Path(video_path).resolve())
    box = style.pip_box(anim_settings(state))
    pip.preview(dict(pip_settings(state), box=box['outer'], round=box['round']), video, engine_settings()['ffmpeg'], out)


def pip_settings(state):
    c = dict(pip.DEFAULT); c.update(CONFIG.get('pip', {})); c.update(state.get('pip', {}))
    return c


def flubs_view(video):
    proj = project_dir(video); state = project_state(proj)
    if not (proj / 'transcript.json').exists(): return None
    segs = read_json(proj / 'transcript.json'); segs = segs.get('segments', segs) if isinstance(segs, dict) else segs
    words = [dict(w=w['word'].strip(), p=i == 0, t=round(float(w['start']), 2)) for s in segs for i, w in enumerate(s.get('words', []))]
    proposal = read_json(proj / 'flubs.json') if (proj / 'flubs.json').exists() else None
    proposed = sorted({i for r in (proposal or {}).get('remove', []) for i in range(r['from'], r['to'] + 1)})
    return dict(words=words, proposed=proposed, groups=(proposal or {}).get('remove', []),
                applied=state.get('removed_words'), has_proposal=proposal is not None)


def style_preview(given, opts):
    """A looping sample deck in a style, for the live preview in the Styles editor."""
    st = style.clean(given)
    if style.missing_fonts(st): st = dict(st, fonts='house')
    sample = (style.KIT / 'sample-scenes.html').read_text(encoding='utf-8')
    kinds = {'fs': 'full', 'pip': 'pip', 'half': 'half', 'kw': 'kw', 'lt': 'lt'}
    animations = []
    for n, sec in enumerate(re.findall(r'<section.*?</section>', sample, re.S), 1):
        kind = kinds[re.search(r'class="scene (\w+)"', sec).group(1)]
        presses = max([int(x) for x in re.findall(r'data-b="(\d+)"', sec)] or [1])
        animations.append(dict(number=n, type=kind, name='Sample', presses=[{}] * presses, section=sec))
    page, beats, keys = deck.assemble('Style preview', animations, st, opts)
    loop = ('<script>(function(){const marks=new Set(%s);let n=1;go(n);setInterval(()=>{n=n>=TOTAL?1:n+1;'
            'if(marks.has(n))n=n>=TOTAL?1:n+1;go(n);},1400);})();</script>'
            % json.dumps([b[0] - 1 for b in beats.values()]))
    return page.replace('</body>', loop + '</body>', 1)


def anim_catalogue():
    return dict(types={k: v[0] for k, v in prompts.SHOT_TYPES.items()}, often={k: v[0] for k, v in prompts.OFTEN.items()},
                rich={k: v[0] for k, v in prompts.RICH.items()}, shapes=style.catalogue()['shapes'],
                styles={k: v['name'] for k, v in style.list_styles().items()})


# ---------------------------------------------------------------- bridge between the app window and Premiere

import queue
BRIDGE = dict(queue=queue.Queue(), waiting={}, plugin_seen=0.0, plugin_info={}, lock=threading.Lock())


def bridge_call(cmd, args, timeout=900):
    """Ask the Premiere plugin to do something and wait for its answer."""
    if time.time() - BRIDGE['plugin_seen'] > 8:
        raise RuntimeError('Premiere is not connected. Open Premiere and the Josh Cut Pro panel (Window > UXP Plugins).')
    call_id = uuid.uuid4().hex[:10]
    BRIDGE['progress'] = dict(phase='', text='', cmd=cmd)
    done = threading.Event(); box = {}
    BRIDGE['waiting'][call_id] = (done, box)
    BRIDGE['queue'].put(dict(id=call_id, cmd=cmd, args=args, expires_at_ms=int((time.time() + timeout) * 1000)))
    if not done.wait(timeout):
        BRIDGE['waiting'].pop(call_id, None)
        raise RuntimeError('Premiere did not answer in time. A command already started may still be running; check its result before retrying.')
    BRIDGE['waiting'].pop(call_id, None)
    if box.get('error'): raise RuntimeError(box['error'])
    return box.get('result')


def bridge_poll(info):
    BRIDGE['plugin_seen'] = time.time()
    if info: BRIDGE['plugin_info'] = info
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        try:
            call = BRIDGE['queue'].get(timeout=max(0.001, deadline - time.monotonic()))
        except queue.Empty:
            return None
        # Timed-out requests must not execute later when the panel reconnects.
        if call['id'] not in BRIDGE['waiting'] or call.get('expires_at_ms', float('inf')) <= time.time() * 1000:
            continue
        return call
    return None


def bridge_result(body):
    entry = BRIDGE['waiting'].get(body.get('id'))
    if entry:
        done, box = entry
        box.update(result=body.get('result'), error=body.get('error'))
        done.set()


def bridge_status():
    connected = time.time() - BRIDGE['plugin_seen'] < 8
    return dict(connected=connected, info=BRIDGE['plugin_info'] if connected else {})


# ---------------------------------------------------------------- the app window

APP_DIR = ROOT / 'app'
_FONTS = {}


def fonts_css():
    """The house fonts, lifted from the deck template so the app works offline."""
    if 'css' not in _FONTS:
        t = (ROOT / 'templates' / 'deck-template.html').read_text(encoding='utf-8')
        _FONTS['css'] = '\n'.join(re.findall(r'@font-face\s*\{[^}]*\}', t))
    return _FONTS['css']


def edge_path():
    import shutil
    for base in [os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LOCALAPPDATA')]:
        if base:
            p = Path(base) / 'Microsoft' / 'Edge' / 'Application' / 'msedge.exe'
            if p.exists(): return str(p)
    return shutil.which('msedge') or shutil.which('chrome') or shutil.which('chromium')


def open_app():
    """A window of its own: Edge in app mode, so it has no tabs or address bar."""
    import subprocess
    url = 'http://127.0.0.1:%d/app/' % PORT
    w, h = CONFIG.get('window', [600, 780])
    exe = edge_path()
    if not exe:
        import webbrowser; webbrowser.open(url); return 'browser'
    profile = ROOT / '.window'
    subprocess.Popen([exe, '--app=' + url, '--window-size=%d,%d' % (w, h), '--user-data-dir=' + str(profile),
                      '--no-first-run', '--no-default-browser-check', '--disable-features=Translate'],
                     creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return 'window'


def waveform(req, points=900):
    ctx = quick_ctx(req)
    if not ctx: return None
    db, (floor, speech, auto) = audio_levels(ctx)
    off = ctx['offset']
    lo, hi = (map(float, req['range']) if req.get('range') else (0.0, float(ctx['video']['duration'])))
    a, b = int(max(0, (lo + off) * 100)), int(max(0, (hi + off) * 100))
    seg = db[a:b]
    if not len(seg): return None
    n = max(1, len(seg) // points)
    usable = len(seg) // n * n
    peaks = seg[:usable].reshape(-1, n).max(axis=1)
    return dict(start=lo, end=hi, peaks=[round(float(x), 1) for x in peaks], floor=round(floor, 1), speech=round(speech, 1),
                auto_db=round(auto, 1))


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype); self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type'); self.send_header('Content-Length', str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def do_OPTIONS(self): self.send(204, {})

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}')

    def query(self):
        return {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}

    def do_GET(self):
        path = self.path.split('?')[0]; q = self.query()
        try:
            if path == '/health':
                try: engine(); ok, err = True, None
                except Exception as ex: ok, err = False, '%s: %s' % (type(ex).__name__, ex)
                return self.send(200, dict(ok=True, version=VERSION, engine=str(ENGINE), engine_ok=ok, engine_error=err,
                                           busy=BUSY.locked(), has_key=bool(api_key()), models=MODELS))
            if path == '/costs':
                return self.send(200, cost_summary())
            if path == '/prefs':
                return self.send(200, prefs())
            if path == '/probe':
                f = PROJECTS / 'premiere-probe.json'
                return self.send(200, dict(probe=read_json(f) if f.exists() else None))
            if path in ('/app', '/app/'):
                return self.send(200, (APP_DIR / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if path.startswith('/app/'):
                name = path[5:]
                if name == 'fonts.css': return self.send(200, fonts_css().encode(), 'text/css')
                f = (APP_DIR / name).resolve()
                if APP_DIR.resolve() not in f.parents or not f.is_file(): return self.send(404, dict(error='Not found'))
                kind = {'.css': 'text/css', '.js': 'application/javascript', '.svg': 'image/svg+xml', '.png': 'image/png',
                        '.ico': 'image/x-icon'}.get(f.suffix, 'application/octet-stream')
                return self.send(200, f.read_bytes(), kind)
            if path == '/bridge/poll':
                info = json.loads(q['info']) if q.get('info') else None
                return self.send(200, dict(call=bridge_poll(info)))
            if path == '/bridge/progress':
                return self.send(200, BRIDGE.get('progress') or {})
            if path == '/bridge/status':
                return self.send(200, bridge_status())
            if path == '/waveform':
                req = json.loads(q['req'])
                return self.send(200, waveform(req) or dict(ready=False))
            if path.startswith('/job/'):
                job = JOBS.get(path[5:])
                return self.send(200, job.view()) if job else self.send(404, dict(error='No such job'))
            if path == '/project':
                video = q.get('video')
                if not video or not Path(video).is_file(): return self.send(200, dict(stages={}, shotlist=None))
                state = project_state(project_dir(video))
                return self.send(200, dict(stages={k: dict(sequence_name=v['sequence_name'], xml=v['xml'], created=v['created'])
                                                   for k, v in state.get('stages', {}).items()},
                                           shotlist=shotlist_view(video),
                                           prepared=(project_dir(video) / 'microphone.f32').exists(),
                                           transcript=dict(transcript_status(project_dir(video)), made=made_on(project_dir(video) / 'transcript.json')),
                                           audio_read=made_on(project_dir(video) / 'microphone.f32'),
                                           source=state.get('source'),
                                           silence_settings=silence_settings(state), presets=PRESETS,
                                           has_flubs=(project_dir(video) / 'flubs.json').exists(),
                                           pip=pip_settings(state), anim=anim_settings(state), anim_catalogue=anim_catalogue()))
            if path == '/source' and q.get('seq'):
                for f in sorted(PROJECTS.glob('*/project.json'), key=lambda x: x.stat().st_mtime, reverse=True):
                    src = read_json(f).get('source')
                    if src and src.get('name') and q['seq'] in [safe_name(src['name']) + x for x in (SUFFIX,) + OLD_SUFFIXES]:
                        return self.send(200, dict(source=src))
                return self.send(200, dict(source=None))
            if path == '/source':
                video = q.get('video')
                if not video or not Path(video).is_file(): return self.send(200, dict(source=None))
                return self.send(200, dict(source=project_state(project_dir(video)).get('source')))
            if path == '/flubs':
                return self.send(200, flubs_view(q['video']) or dict(words=[], proposed=[], groups=[], applied=None, has_proposal=False))
            if path == '/camera-still':
                # a frame of the recording for the live PiP framing on the Animations screen. It comes from the file
                # alone, so it stays when the app starts fresh.
                proj = project_dir(q['video']); out = proj / 'camera-still.jpg'
                if not out.exists():
                    import subprocess
                    video = engine()['media'].probe(Path(q['video']).resolve())
                    t = min(30.0, float(video['duration']) / 2)
                    subprocess.run([engine_settings()['ffmpeg'], '-v', 'error', '-y', '-ss', '%.2f' % t, '-i', video['path'], '-frames:v', '1',
                                    '-vf', 'scale=960:-2', '-q:v', '3', str(out)], check=True, timeout=60,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                return self.send(200, out.read_bytes(), 'image/jpeg')
            if path == '/pip-preview':
                proj = project_dir(q['video']); out = proj / 'pip-preview.png'
                if not out.exists(): make_pip_preview(q['video'], project_state(proj), out)
                return self.send(200, out.read_bytes(), 'image/png')
            if path == '/styles':
                return self.send(200, dict(styles={k: style.describe(v) for k, v in style.list_styles().items()},
                                           catalogue=style.catalogue()))
            if path == '/style-preview':
                given = json.loads(q['style']) if q.get('style') else style.HOUSE
                if isinstance(given, str): given = style.load(given)
                opts = {k: q[k] for k in ('pip_shape', 'pip_side', 'half_side') if q.get(k)}
                return self.send(200, style_preview(given, opts).encode('utf-8'), 'text/html; charset=utf-8')
            if path == '/sketch':
                proj = project_dir(q['video']); ext = 'png' if q.get('ext') == 'png' else 'svg'
                name = re.sub(r'[^A-Za-z0-9-]', '', q.get('name', ''))
                f = proj / 'sketches' / ('%s.%s' % (name, ext))
                if not f.exists(): return self.send(404, dict(error='No sketch'))
                return self.send(200, f.read_bytes(), 'image/png' if ext == 'png' else 'image/svg+xml')
            self.send(404, dict(error='Unknown path'))
        except Exception as ex:
            self.send(500, dict(error=str(ex)))

    def do_POST(self):
        path = self.path.split('?')[0]
        try:
            if path == '/run':
                req = self.body(); stage = req.get('stage')
                if stage not in RUNNERS: return self.send(400, dict(error='Unknown pass'))
                if not req.get('video'): return self.send(400, dict(error='Choose the video first'))
                if stage in ('flubs', 'shotlist', 'redo', 'build') and not api_key():
                    return self.send(400, dict(error='Save your Claude API key in the panel settings first'))
                if BUSY.locked(): return self.send(409, dict(error='Another pass is still running'))
                job = Job(stage, req); JOBS[job.id] = job
                threading.Thread(target=execute, args=(job,), daemon=True).start()
                return self.send(200, dict(job=job.id))
            if path.startswith('/cancel/'):
                job = JOBS.get(path[8:])
                if not job: return self.send(404, dict(error='No such job'))
                if job.dir: (Path(job.dir) / 'CANCEL').write_text('cancel', encoding='utf-8')
                job.say('Cancelling...'); return self.send(200, dict(ok=True))
            if path == '/settings':
                body = self.body(); key = (body.get('api_key') or '').strip()
                if not key.startswith('sk-'): return self.send(400, dict(error='That does not look like a Claude API key'))
                write_json(SECRETS, dict(api_key=key)); return self.send(200, dict(ok=True))
            if path == '/probe':
                write_json(PROJECTS / 'premiere-probe.json', self.body()); return self.send(200, dict(ok=True))
            if path == '/prefs':
                body = self.body(); p = prefs()
                p.update({k: bool(v) for k, v in body.items() if k in PREF_DEFAULTS})
                write_json(PREFS_PATH, p); return self.send(200, p)
            if path == '/bridge/result':
                bridge_result(self.body()); return self.send(200, dict(ok=True))
            if path == '/bridge/progress':
                # the panel says which step it's on, for the app window's progress screen
                body = self.body(); BRIDGE['progress'] = dict(BRIDGE.get('progress') or {}, phase=str(body.get('phase', '')), text=str(body.get('text', '')))
                return self.send(200, dict(ok=True))
            if path == '/cut-log':
                # every clip on the sequence after a cut, with any gaps or overlaps, for checking what Premiere did
                body = self.body(); write_json(project_dir(body['video']) / 'last-cut.json', dict(body, when=time.strftime('%Y-%m-%d %H:%M:%S')))
                return self.send(200, dict(ok=True))
            if path == '/bridge/call':
                body = self.body()
                return self.send(200, dict(result=bridge_call(body['cmd'], body.get('args') or {})))
            if path == '/quit':
                threading.Thread(target=lambda: (time.sleep(.3), SERVER.shutdown()), daemon=True).start()
                return self.send(200, dict(ok=True))
            if path == '/session':
                # the app window just opened, so every recording starts fresh again
                FRESH.clear(); _CTX.clear(); return self.send(200, dict(ok=True))
            if path == '/open-app':
                return self.send(200, dict(opened=open_app()))
            if path == '/silence-preview':
                body = self.body(); ctx = quick_ctx(body)
                if not ctx: return self.send(200, dict(ready=False))
                try:
                    plan = plan_cut(ctx, body, [])
                except ValueError as ex:
                    return self.send(200, dict(ready=True, error=str(ex)))
                stats = dict(plan['stats'])
                if body.get('spans'):
                    # count only what's still on the open timeline, so a second pass shows what it adds
                    stats.update(on_timeline(removal(plan['keeps'], 0.0, float(ctx['video']['duration'])), body['spans']))
                return self.send(200, dict(ready=True, stats=stats, auto_db=plan['auto_db'],
                                           keeps=[[round(x, 2), round(y, 2)] for x, y in plan['keeps']]))
            if path == '/pip':
                body = self.body(); proj = project_dir(body['video']); state = project_state(proj)
                c = {k: float(v) for k, v in (body.get('pip') or {}).items() if k in ('zoom', 'shift', 'shift_y')}
                c['zoom'] = max(1.0, min(2.5, c.get('zoom', 1.0)))
                if body.get('drag'):
                    # Josh dragged himself inside the shape: sequence pixels -> how far to slide the framing
                    video = engine()['media'].probe(Path(body['video']).resolve())
                    box = style.pip_box(anim_settings(state))
                    f = pip.framing(dict(pip_settings(dict(state, pip=c)), box=box['outer']), video['width'], video['height'])
                    dx, dy = (float(v) for v in body['drag'])
                    if f['slack_x'] > 0: c['shift'] = c.get('shift', 0.0) - dx / f['slack_x']
                    if f['slack_y'] > 0: c['shift_y'] = c.get('shift_y', 0.0) - dy / f['slack_y']
                c['shift'] = max(-1.0, min(1.0, c.get('shift', 0.0))); c['shift_y'] = max(-1.0, min(1.0, c.get('shift_y', 0.0)))
                state['pip'] = c; save_state(proj, state)
                return self.send(200, dict(ok=True, pip=pip_settings(state)))
            if path == '/styles/save':
                body = self.body(); key, saved = style.save(body.get('style') or {})
                return self.send(200, dict(key=key, style=style.describe(saved)))
            if path == '/style-check':
                return self.send(200, style.describe(self.body().get('style') or {}))
            if path == '/anim':
                body = self.body(); proj = project_dir(body['video']); state = project_state(proj)
                state['anim'] = anim_settings(state, body.get('anim')); save_state(proj, state)
                return self.send(200, dict(anim=state['anim']))
            if path == '/shotlist/edit':
                shotlist_edit(self.body()); return self.send(200, dict(ok=True))
            self.send(404, dict(error='Unknown path'))
        except Exception as ex:
            self.send(500, dict(error=str(ex)))


SERVER = None


def serve():
    PROJECTS.mkdir(parents=True, exist_ok=True)
    global SERVER
    server = SERVER = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print('%s helper %s on http://127.0.0.1:%d' % (APP_NAME, VERSION, PORT), flush=True)
    print('Engine: %s' % ENGINE, flush=True); print('Projects: %s' % PROJECTS, flush=True)
    print('Claude API key: %s' % ('saved' if api_key() else 'not saved yet, add it in Settings'), flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass


def already_running():
    import urllib.request
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/health' % PORT, timeout=2) as r:
            return json.loads(r.read()).get('ok')
    except Exception:
        return False


def main():
    """Started with --serve: run the server. Otherwise: keep a server running in the background and open the window."""
    if '--serve' in sys.argv:
        return serve()
    import subprocess
    if already_running():
        if '--no-window' not in sys.argv:
            import urllib.request
            urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:%d/open-app' % PORT, data=b'{}', method='POST'), timeout=5)
        return
    PROJECTS.mkdir(parents=True, exist_ok=True)
    opened = '--no-window' in sys.argv
    while True:
        with open(PROJECTS / 'helper.log', 'ab') as log:
            log.write(('\n==== %s starting\n' % time.strftime('%Y-%m-%d %H:%M:%S')).encode())
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve'], stdout=log, stderr=log,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            for _ in range(30):
                if already_running() or child.poll() is not None: break
                time.sleep(.5)
            if not opened and child.poll() is None:
                open_app(); opened = True
            child.wait()
        if child.returncode == 0: break
        time.sleep(3)


if __name__ == '__main__':
    main()
