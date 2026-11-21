"""Layers on top of the Josh Cut sequence: animations, angle shots and B-roll.

Every layer is planned against word numbers in the source transcript, never
against sequence seconds. When the cut changes, the words are mapped through
the new cut map, so a recut can put every layer back where it belongs.

The track plan is fixed so each tool knows where it writes:

  V1 main camera, V2 angle shots, V3 B-roll, V4 camera copy for PiP and
  half-and-half, V5 animations, A1 mic (or main camera audio).

PiP and half-and-half animations render with a transparent hole, so the
camera copy on V4 shows through from underneath.
"""
import json, time
from pathlib import Path

PLAN_VERSION = 1
TRACKS = dict(main=0, angle=1, broll=2, camera=3, animation=4)

# Highest first. A lower layer is trimmed out of any time a higher one covers.
PRIORITY = ['full', 'half', 'pip', 'overlay', 'demo', 'broll', 'alt']
MIN_SECONDS = dict(alt=1.5, demo=2.0, broll=1.0)

PLANS = dict(angles='angles.json', broll='broll.json')
NAMES = dict(full='animation', half='animation', pip='animation', overlay='animation', demo='angle shot', alt='angle shot', broll='B-roll clip')


def load_plan(proj, kind):
    """angles.json and broll.json hold {version, items}. Each item has start_word and end_word."""
    p = Path(proj) / PLANS[kind]
    if not p.exists(): return dict(version=PLAN_VERSION, items=[])
    data = json.loads(p.read_text(encoding='utf-8-sig'))
    data.setdefault('version', PLAN_VERSION); data.setdefault('items', [])
    return data


def save_plan(proj, kind, data):
    data = dict(data, version=PLAN_VERSION, saved=time.strftime('%Y-%m-%d %H:%M:%S'))
    p = Path(proj) / PLANS[kind]; tmp = p.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8'); tmp.replace(p)


class Cut:
    """The current cut, as seen from the source words."""

    def __init__(self, timing, mapping, words, offset, removed=()):
        self.timing = timing; self.mapping = mapping; self.words = words; self.offset = float(offset)
        self.removed = set(removed); self.fps = float(timing.rate(mapping['fps']))

    def source(self, i, edge='start'):
        """Source video seconds for a word edge."""
        return float(self.words[i][edge]) - self.offset

    def kept(self, i):
        return i not in self.removed and self.timing.map_source(self.mapping, self.source(i)) is not None

    def locate(self, start_word, end_word, start_offset=0.0, end_offset=0.0):
        """Sequence frames (lo, hi) for a stretch of words, or None if it was all cut.

        A cut start word snaps to the next kept word. The stretch can cross cut
        boundaries, so the pieces in between are returned too."""
        n = len(self.words)
        a, b = max(0, int(start_word)), min(n - 1, int(end_word))
        if b < a: return None
        first = next((i for i in range(a, b + 1) if self.kept(i)), None)
        if first is None: return None
        last = next(i for i in range(b, first - 1, -1) if self.kept(i))
        lo = self.source(first) + (float(start_offset) if first == a else 0.0)
        hi = self.source(last, 'end') + float(end_offset)
        pieces = self.timing.map_interval(self.mapping, lo, max(hi, lo + 1.0 / self.fps))
        if not pieces: return None
        return dict(lo=pieces[0][0], hi=pieces[-1][1], pieces=[list(p) for p in pieces], snapped=first != a)

    def source_pieces(self, lo, hi):
        """Split sequence frames lo..hi into the source spans that fill them."""
        out = []
        for sp in self.mapping['spans']:
            a, b = max(lo, sp['out_in_frame']), min(hi, sp['out_out_frame'])
            if b > a: out.append(dict(start_f=a, end_f=b, src_f=sp['source_in_frame'] + a - sp['out_in_frame']))
        return out


def resolve(items, fps):
    """Trim lower layers out of the time higher layers cover.

    Each item has kind (one of PRIORITY), lo and hi in frames. Returns the kept
    items, each with its free pieces, and the ones dropped because nothing long
    enough was left."""
    taken, kept, dropped = [], [], []
    for it in sorted(items, key=lambda x: (PRIORITY.index(x['kind']), x['lo'])):
        free = [[it['lo'], it['hi']]]
        for a, b in taken:
            nxt = []
            for x, y in free:
                if b <= x or a >= y: nxt.append([x, y]); continue
                if a > x: nxt.append([x, a])
                if b < y: nxt.append([b, y])
            free = nxt
        need = MIN_SECONDS.get(it['kind'], 0) * fps
        free = [p for p in free if p[1] - p[0] >= max(1, need)]
        if not free:
            dropped.append(dict(it, why='covered')); continue
        it = dict(it, free=free, trimmed=sum(y - x for x, y in free) < it['hi'] - it['lo'])
        kept.append(it); taken.extend(free)
    return kept, dropped


def angle_layers(cut, plan, cameras):
    """V2 clips for planned angle shots. cameras maps a camera id to {path, offset}."""
    out = []
    for it in plan.get('items', []):
        cam = cameras.get(it.get('camera'))
        if not cam: continue
        where = cut.locate(it['start_word'], it['end_word'], it.get('start_offset', 0), it.get('end_offset', 0))
        out.append(dict(it, kind='demo' if it.get('role') == 'demo' else 'alt', where=where, camera=cam))
    return out


def broll_layers(cut, plan):
    out = []
    for it in plan.get('items', []):
        where = cut.locate(it['start_word'], it['end_word'], it.get('start_offset', 0), it.get('end_offset', 0))
        out.append(dict(it, kind='broll', where=where))
    return out


def clips_for(cut, item, piece):
    """Panel clips (track, path, start_f, in_f, out_f) for one free piece of a V2 or V3 item."""
    lo, hi = piece
    if item['kind'] == 'broll':
        src = int(round(float(item.get('src_in', 1.0)) * cut.fps)) + (lo - item['lo'])
        return [dict(track=TRACKS['broll'], path=item['file'], start_f=lo, in_f=src, out_f=src + hi - lo,
                     audio_db=-20 if item.get('keep_audio') else None, kind='broll')]
    off = int(round(float(item['camera'].get('offset', 0)) * cut.fps))
    return [dict(track=TRACKS['angle'], path=item['camera']['path'], start_f=p['start_f'], in_f=p['src_f'] + off,
                 out_f=p['src_f'] + off + p['end_f'] - p['start_f'], kind=item['kind'])
            for p in cut.source_pieces(lo, hi)]


def summary(counts, dropped):
    """Toast text, e.g. "Put back 6 animations and 9 B-roll clips."."""
    def n(k, v): return '%d %s%s' % (v, NAMES[k] if k in NAMES else k, '' if v == 1 else 's')
    parts = [n(k, v) for k, v in counts.items() if v]
    text = ''
    if parts:
        text = 'Put back ' + (', '.join(parts[:-1]) + ' and ' + parts[-1] if len(parts) > 1 else parts[0]) + '.'
    for why, tail in [('cut', 'on words you\'ve since cut'), ('covered', 'left out where something higher up covers them')]:
        lost = {}
        for d in dropped:
            if d.get('why') == why: lost[NAMES[d['kind']]] = lost.get(NAMES[d['kind']], 0) + 1
        for name, v in lost.items():
            text += ' %d %s%s %s %s.' % (v, name, '' if v == 1 else 's', 'was' if v == 1 else 'were', tail)
    return text.strip()
