"""Pass 1, the clean cut.

Claude decides which WORDS go (repeats, flubs, fillers, abandoned takes).
This module turns that into exact cut points from the audio itself:
  * cuts land in the quiet just after a kept word and just before the next
  * gaps between words that hold a sound Whisper did not transcribe
    (a cough, a throat clear, a breath, a chair) are cut out
  * long pauses are tightened to a natural beat
"""
import numpy as np

HOP = 100  # energy bins per second


def energy_profile(pcm, sample_rate=16000):
    hop = sample_rate // HOP
    usable = len(pcm) // hop * hop
    e = np.sqrt(np.mean(pcm[:usable].reshape(-1, hop) ** 2, axis=1) + 1e-14)
    threshold = max(.0015, min(.015, float(np.percentile(e, 20)) * 2.5))
    return e, threshold


def _bins(e, a, b):
    lo, hi = max(0, int(a * HOP)), min(len(e), int(b * HOP))
    return e[lo:hi], lo


def gap_noise(e, thr, a, b, guard=.08, min_loud=.08):
    """True if the audio between two words holds an untranscribed sound."""
    if b - a <= 2 * guard + min_loud:
        return False
    seg, _ = _bins(e, a + guard, b - guard)
    if not len(seg):
        return False
    loud = seg > thr
    # longest run of loud bins
    best = run = 0
    for v in loud:
        run = run + 1 if v else 0
        best = max(best, run)
    return best >= int(min_loud * HOP)


def tail_cut(e, thr, word_end, limit, pad):
    """Where to end a clip after a word: first sustained quiet after it, plus a small pad."""
    seg, lo = _bins(e, word_end, min(limit, word_end + .35))
    q = seg < thr
    for k in range(len(q) - 2):
        if q[k] and q[k + 1] and q[k + 2]:
            return min(limit, (lo + k) / HOP + pad)
    return min(limit, word_end + pad + .06)


def head_cut(e, thr, word_start, limit, pad):
    """Where to start a clip before a word: last sustained quiet before it, minus a small pad."""
    seg, lo = _bins(e, max(limit, word_start - .35), word_start)
    q = seg < thr
    for k in range(len(q) - 1, 1, -1):
        if q[k] and q[k - 1] and q[k - 2]:
            return max(limit, (lo + k + 1) / HOP - pad)
    return max(limit, word_start - pad - .04)


def annotate(words, e, thr):
    """Transcript for Claude: '#index word' tokens, with pauses and sounds marked between them."""
    lines, cur = [], []
    for i, w in enumerate(words):
        if i and w.get('segment_start') and cur:
            lines.append(' '.join(cur)); cur = []
        if i:
            gap = float(w['start']) - float(words[i - 1]['end'])
            if gap >= .3:
                noisy = gap_noise(e, thr, float(words[i - 1]['end']), float(w['start']))
                cur.append('<%.1fs%s>' % (gap, ' sound' if noisy else ''))
        cur.append('#%d %s' % (i, w['word'].strip()))
    if cur:
        lines.append(' '.join(cur))
    return '\n'.join(lines)


def plan(words, removed, e, thr, offset, duration, cfg):
    """Return (keeps in video seconds, noise cuts, decisions)."""
    max_pause = float(cfg.get('max_pause', .45))
    pad_after = float(cfg.get('pad_after', .10))
    pad_before = float(cfg.get('pad_before', .08))
    kept = [i for i in range(len(words)) if i not in removed]
    if not kept:
        raise ValueError('Every word was marked for removal, so there is nothing left to keep')
    keeps, noise, decisions = [], [], []
    start = head_cut(e, thr, float(words[kept[0]]['start']), 0, pad_before)
    for a, b in zip(kept, kept[1:]):
        wa, wb = words[a], words[b]
        ea, sb = float(wa['end']), float(wb['start'])
        adjacent = b == a + 1
        noisy = False if cfg.get('ignore_sounds') else gap_noise(e, thr, ea, sb)
        if adjacent and not noisy and sb - ea <= max_pause:
            continue  # natural flow, keep the gap as spoken
        end = tail_cut(e, thr, ea, sb, pad_after)
        nxt = head_cut(e, thr, sb, end, pad_before)
        if adjacent and nxt - end < float(cfg.get('min_cut', .15)):
            continue  # too small to be worth an edit point
        if not adjacent:
            gone = ' '.join(words[k]['word'].strip() for k in range(a + 1, b))
            decisions.append(dict(kind='words', start=end - offset, end=nxt - offset, text=gone))
        elif noisy:
            noise.append(dict(kind='sound', start=end - offset, end=nxt - offset))
        else:
            decisions.append(dict(kind='pause', start=end - offset, end=nxt - offset))
        if nxt - end < .02:
            nxt = end
        keeps.append([start - offset, end - offset]); start = nxt
    end = tail_cut(e, thr, float(words[kept[-1]]['end']), float(words[kept[-1]]['end']) + .6, pad_after)
    keeps.append([start - offset, end - offset])
    keeps = [[max(0.0, a), min(duration, b)] for a, b in keeps if min(duration, b) > max(0.0, a)]
    return keeps, noise, decisions


# ---------------------------------------------------------------- acoustic clean cut (no transcript needed)

def db_profile(pcm, sample_rate=16000):
    hop = sample_rate // HOP
    usable = len(pcm) // hop * hop
    rms = np.sqrt(np.mean(pcm[:usable].reshape(-1, hop) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(rms)


def levels(db):
    """Noise floor, speech level and the automatic silence threshold, in dBFS."""
    floor = float(np.percentile(db, 10))
    speech = float(np.percentile(db, 95))
    auto = max(-65.0, min(-20.0, floor + 5.0))
    return floor, speech, auto


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def smooth(db, n=5):
    p = 10 ** (db / 10.0)
    return 10 * np.log10(np.convolve(p, np.ones(n) / n, mode='same') + 1e-12)


def acoustic_keeps(db, thr, speech, settings):
    """Kept stretches of AUDIO time in seconds, plus how many breaths and noises were dropped.

    1. anything above the silence threshold is sound (smoothed over 50ms so words don't break up)
    2. bits of sound closer than 150ms are one phrase
    3. a phrase that never gets near speech level is a breath, cough or noise, and is dropped
    4. gaps shorter than the longest pause kept are bridged, then a margin goes either side
    """
    max_pause = float(settings.get('max_pause', .4))
    pad_before = float(settings.get('pad_before', .08))
    pad_after = float(settings.get('pad_after', .10))
    cut_breaths = settings.get('cut_sounds', True)
    s = smooth(db)
    phrases = []
    for a, b in runs(s > thr):
        if phrases and (a - phrases[-1][1]) / HOP < .15:
            phrases[-1][1] = b
        else:
            phrases.append([a, b])
    sound, dropped = [], 0
    for a, b in phrases:
        dur = (b - a) / HOP
        peak = float(np.max(s[a:b]))
        if dur < .08:
            dropped += 1; continue                      # click or knock
        if cut_breaths and dur < 1.2 and peak < speech - 11:
            dropped += 1; continue                      # breath, cough or noise, well below speech level
        sound.append([a / HOP, b / HOP])
    merged = []
    for a, b in sound:
        if merged and a - merged[-1][1] < max_pause:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    out = []
    for a, b in merged:
        a, b = max(0.0, a - pad_before), b + pad_after
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out, dropped


def word_cuts(words, removed, e, thr):
    """Audio-time intervals to remove for struck words, snapped to the quietest point nearby."""
    removed = sorted(set(removed))
    groups, start = [], None
    for k, i in enumerate(removed):
        if start is None: start = i
        if k + 1 == len(removed) or removed[k + 1] != i + 1:
            groups.append((start, i)); start = None
    cuts = []
    for a, b in groups:
        lo = float(words[a]['start'])
        hi = float(words[b]['end'])
        if b + 1 < len(words):
            hi = min(hi + .05, float(words[b + 1]['start']) - .02)
        if a > 0:
            lo = max(lo - .05, float(words[a - 1]['end']) + .02)
        # nudge each edge to the quietest 10ms within 80ms
        def quietest(t, lo_lim, hi_lim):
            s, base = _bins(e, max(lo_lim, t - .08), min(hi_lim, t + .08))
            return (base + int(np.argmin(s))) / HOP if len(s) else t
        lo = quietest(lo, float(words[a - 1]['end']) if a > 0 else 0, float(words[a]['start']))
        hi = quietest(hi, float(words[b]['end']), float(words[b + 1]['start']) if b + 1 < len(words) else hi + .1)
        if hi > lo: cuts.append([lo, hi])
    return cuts
