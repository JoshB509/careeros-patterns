// Josh Cut Pro: the Premiere side. A small panel that links the Josh Cut Pro window
// to this timeline. The window asks, this panel reads the timeline and makes the edits.
const ppro = require('premierepro');
const HELPER = (typeof window !== 'undefined' && window.JOSH_HELPER) || 'http://127.0.0.1:47820';
const $ = (id) => document.getElementById(id);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, body) {
  const opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
  const res = await fetch(HELPER + path, opt);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || ('Helper error ' + res.status));
  return data;
}

let busy = false;
let lastSent = 0, lastPhase = '';
async function status(msg, phase) {
  // Shows in the panel, and with a phase it also goes to the app window's progress screen. It sends on a
  // new step or at most once a second, and the caller waits for it, so nothing is in flight during an edit.
  $('activity').textContent = msg || '';
  if (!phase) return;
  const now = Date.now();
  if (phase === lastPhase && now - lastSent < 1000) return;
  lastSent = now; lastPhase = phase;
  try { await api('/bridge/progress', { phase, text: msg || '' }); } catch (e) { /* the progress screen just won't update */ }
}
function setLink(on, text) {
  $('link').className = 'link' + (on ? ' on' : '');
  $('linkText').textContent = text;
}

// Premiere has no documented constant for a bin's type, so a bin is anything that casts to a
// FolderItem and can list its items. Media clips are anything with a file path.
async function asFolder(it) {
  try {
    const f = ppro.FolderItem.cast(it);
    if (f && typeof f.getItems === 'function') { await f.getItems(); return f; }
  } catch (e) { /* not a bin */ }
  return null;
}

async function asMedia(it) {
  try {
    const clip = ppro.ClipProjectItem.cast(it);
    const path = clip ? await clip.getMediaFilePath() : '';
    if (path) return { clip, item: it, path };
  } catch (e) { /* a bin or a sequence */ }
  return null;
}

async function walkProject(proj, visit) {
  const stack = [await proj.getRootItem()];
  while (stack.length) {
    const folder = stack.pop();
    for (const it of (await folder.getItems()) || []) {
      const media = await asMedia(it);
      if (media) { if (visit(media)) return; continue; }
      const sub = await asFolder(it);
      if (sub) stack.push(sub);
    }
  }
}

async function findBin(parent, name) {
  for (const it of (await parent.getItems()) || []) {
    if (it.name !== name) continue;
    const f = await asFolder(it);
    if (f) return f;
  }
  return null;
}

async function findClipByPath(proj, path) {
  let hit = null;
  await walkProject(proj, (m) => { if (m.path === path) { hit = { clip: m.clip, item: m.item }; return true; } return false; });
  return hit;
}

// ------------------------------------------------------------ making the cut in Premiere

function transact(proj, label, build) {
  let ok = false;
  try {
    proj.lockedAccess(() => { ok = proj.executeTransaction((ca) => build(ca), label); });
  } catch (e) {
    throw new Error(label.replace('Josh Cut: ', '') + ' step failed in Premiere (' + (e && e.message ? e.message : e) + ')');
  }
  return ok;
}



function ticks(frame, r, offsetSeconds) {
  // exact ticks for a frame number at the source frame rate (254016000000 ticks per second)
  let t = BigInt(frame) * 254016000000n * BigInt(r.fps_den) / BigInt(r.fps_num);
  if (offsetSeconds) t += BigInt(Math.round(offsetSeconds * 254016000000));
  if (t < 0n) t = 0n;
  return ppro.TickTime.createWithTicks(String(t));
}

async function findSequence(proj, name) {
  for (const s of (await proj.getSequences()) || []) if (s.name === name) return s;
  return null;
}

async function cutBin(proj) {
  const root = await proj.getRootItem();
  let bin = await findBin(root, 'Josh Cut Pro');
  if (!bin) { transact(proj, 'Josh Cut: bin', (ca) => ca.addAction(root.createBinAction('Josh Cut Pro', false))); bin = await findBin(root, 'Josh Cut Pro'); }
  return bin;
}

// ------------------------------------------------------------ reading the open sequence

// Times are kept as exact Premiere ticks (BigInt). 254016000000 ticks make a second.
const TPS = 254016000000n;
const tk = (t) => (t && t.ticks != null ? BigInt(t.ticks) : BigInt(Math.round((t ? t.seconds : 0) * 254016000000)));
const sec = (ticksBig) => Number(ticksBig) / 254016000000;
const tt = (ticksBig) => ppro.TickTime.createWithTicks(String(ticksBig < 0n ? 0n : ticksBig));
const CACHE_DIR = /[\\/]animation-cache[\\/]/i;

async function frameTicks(seq) {
  // the sequence's ticks per frame; every cut point is snapped to it
  try { const tb = BigInt(String(await seq.getTimebase())); if (tb > 0n) return tb; } catch (e) { /* fall back to 30 fps */ }
  return TPS / 30n;
}

const snapTo = (t, f) => ((t + f / 2n) / f) * f;

async function trackList(seq, kind) {
  const n = kind === 'v' ? await seq.getVideoTrackCount() : await seq.getAudioTrackCount();
  const out = [];
  for (let t = 0; t < n; t++) out.push(kind === 'v' ? await seq.getVideoTrack(t) : await seq.getAudioTrack(t));
  return out;
}

const PATHS = new Map();
async function pathOf(trackItem) {
  // the media file behind a track item, cached by project item id
  const pi = await trackItem.getProjectItem();
  let id = null;
  try { id = pi.getId(); } catch (e) { /* older Premiere */ }
  if (id && PATHS.has(id)) return PATHS.get(id);
  const m = await asMedia(pi);
  const p = m ? m.path : '';
  if (id) PATHS.set(id, p);
  return p;
}

async function readItem(it, kind, track) {
  const start = tk(await it.getStartTime()), end = tk(await it.getEndTime()), inp = tk(await it.getInPoint());
  return { item: it, kind, track, start, end, inp, path: await pathOf(it) };
}

async function snapshot(seq, only) {
  // every clip on every track (or only the tracks listed in only, like { v: [0], a: [] })
  const CLIP = ppro.Constants.TrackItemType.CLIP, out = [];
  for (const kind of ['v', 'a']) {
    const tracks = await trackList(seq, kind);
    for (let t = 0; t < tracks.length; t++) {
      if (only && !(only[kind] || []).includes(t)) continue;
      for (const it of (await tracks[t].getTrackItems(CLIP, false)) || []) out.push(await readItem(it, kind, t));
    }
  }
  return out.sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : 0));
}

function mainVideo(items) {
  // the recording is the file with the most time on the video tracks, leaving out our own animation renders
  const total = {};
  for (const i of items) if (i.kind === 'v' && i.path && !CACHE_DIR.test(i.path)) total[i.path] = (total[i.path] || 0n) + (i.end - i.start);
  let best = null;
  for (const p of Object.keys(total)) if (!best || total[p] > total[best]) best = p;
  return best;
}

async function readTimeline() {
  const proj = await ppro.Project.getActiveProject();
  if (!proj) throw new Error('Open a Premiere project first.');
  const seq = await proj.getActiveSequence();
  if (!seq) throw new Error('Open the sequence with your recording on it.');
  const items = await snapshot(seq);
  const video = mainVideo(items);
  if (!video) throw new Error('There is no video clip on this sequence yet. Drop your recording on the timeline first.');
  const main = items.filter((i) => i.kind === 'v' && i.path === video && i.track < 3);
  const spans = main.map((m) => ({ start: sec(m.start), in: sec(m.inp), out: sec(m.inp + m.end - m.start) }));
  const at = (t) => main.find((m) => m.start <= t && t < m.end) || main[0];
  const audio = [];
  for (const kind of ['a']) {
    const n = await seq.getAudioTrackCount();
    for (let t = 0; t < n; t++) {
      const first = items.find((i) => i.kind === kind && i.track === t && i.path);
      if (!first) continue;
      const m = at(first.start);
      audio.push({ index: t, path: first.path, name: first.path.split(/[\\/]/).pop(), same: first.path === video,
                   offset: sec((first.inp - first.start) - (m.inp - m.start)) });
    }
  }
  const mic = audio.find((a) => !a.same) || audio[0] || null;
  let frame = [1920, 1080];
  try {
    // the sequence's frame size, so animations render at it (a 4K sequence gets 4K animations)
    const r = await seq.getFrameSize();
    const w = Math.round(r.width || (r.right - r.left) || 0), h = Math.round(r.height || (r.bottom - r.top) || 0);
    if (w > 0 && h > 0) frame = [w, h];
  } catch (e) { /* older Premiere: 1080p */ }
  return { sequenceName: seq.name, video, clipName: video.split(/[\\/]/).pop(), frame,
           in: Math.min(...spans.map((s) => s.in)), out: Math.max(...spans.map((s) => s.out)),
           duration: spans.reduce((n, s) => n + s.out - s.in, 0), spans, audio_tracks: audio,
           mic_track: mic ? mic.index : null, already_cut: main.length > 1 };
}

// ------------------------------------------------------------ backups

const seqKey = (s) => { try { return String(s.guid.toString()); } catch (e) { return s.name; } };

async function subBin(proj, name) {
  const top = await cutBin(proj);
  if (!top) return null;
  let bin = await findBin(top, name);
  if (!bin) { transact(proj, 'Josh Cut: ' + name + ' bin', (ca) => ca.addAction(top.createBinAction(name, false))); bin = await findBin(top, name); }
  return bin;
}

async function cloneSequence(proj, seq, name, binName) {
  // Premiere's own sequence duplicate, renamed and filed in Josh Cut Pro > binName
  const before = new Set(((await proj.getSequences()) || []).map(seqKey));
  const count = before.size;
  transact(proj, 'Josh Cut: backup', (ca) => ca.addAction(seq.createCloneAction()));
  const after = (await proj.getSequences()) || [];
  let copy = after.find((s) => !before.has(seqKey(s)));
  if (!copy && after.length > count) copy = after[after.length - 1];
  if (!copy) throw new Error('Premiere would not make the backup copy, so nothing was cut');
  try {
    const pi = await copy.getProjectItem();
    transact(proj, 'Josh Cut: name backup', (ca) => ca.addAction(pi.createSetNameAction(name)));
    const bin = await subBin(proj, binName);
    if (bin) transact(proj, 'Josh Cut: file backup', (ca) => ca.addAction(bin.createMoveItemAction(pi, bin)));
  } catch (e) { /* the copy still exists, just with Premiere's own name and place */ }
  return copy;
}

async function removeItems(proj, seq, list, label) {
  if (!list.length) return;
  const editor = ppro.SequenceEditor.getEditor(seq);
  for (const kind of ['v', 'a']) {
    let mine = list.filter((i) => i.kind === kind);
    if (kind === 'a' && mine.length && list.some((i) => i.kind === 'v')) {
      // removing a video clip can take its linked audio with it, so only remove audio that's still there
      const left = await snapshot(seq, { a: [...new Set(mine.map((i) => i.track))] });
      mine = mine.filter((i) => left.some((x) => x.track === i.track && x.start === i.start && x.end === i.end)).map((i) =>
        left.find((x) => x.track === i.track && x.start === i.start && x.end === i.end));
    }
    if (!mine.length) continue;
    proj.lockedAccess(() => {
      ppro.TrackItemSelection.createEmptySelection((sel) => {
        mine.forEach((i) => sel.addItem(i.item, true));
        proj.executeTransaction((ca) => ca.addAction(editor.createRemoveItemsAction(sel, false,
          kind === 'v' ? ppro.Constants.MediaType.VIDEO : ppro.Constants.MediaType.AUDIO)), label);
      });
    });
  }
}

// ------------------------------------------------------------ cutting in place

// Premiere 25.6 rejects trims that reach past the media, so a clip is only ever shrunk with its in and out
// points, then slid into place. The check finds how to slide it and whether the out point needs a nudge.
const dt = (ticksBig) => ppro.TickTime.createWithTicks(String(ticksBig));

async function findAt(seq, kind, track, start, f) {
  // the clip that starts at this time on a track. Premiere hands back a new clip object after every edit,
  // so clips are always looked up fresh by where they sit.
  const tr = kind === 'v' ? await seq.getVideoTrack(track) : await seq.getAudioTrack(track);
  const list = (await tr.getTrackItems(ppro.Constants.TrackItemType.CLIP, false)) || [];
  let lo = 0, hi = list.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1, s0 = tk(await list[mid].getStartTime());
    if (near(s0, start, f)) return readItem(list[mid], kind, track);
    if (s0 < start) lo = mid + 1; else hi = mid - 1;
  }
  for (const it of list) if (near(tk(await it.getStartTime()), start, f)) return readItem(it, kind, track);
  return null;
}

async function place(proj, editor, seq, kind, track, at, want, f, strategy, label) {
  // shrink the clip that starts at `at` to the media it should show, then slide it to where it belongs
  const len = want.end - want.start, where = (kind === 'v' ? 'V' : 'A') + (track + 1);
  const lost = (t) => new Error('Josh Cut Pro lost track of a clip on ' + where + ' at ' + sec(t).toFixed(2) + 's');
  let cur = await findAt(seq, kind, track, at, f);
  if (!cur) throw lost(at);
  if (!near(cur.inp, want.inp, f)) {
    const next = cur.start + (want.inp - cur.inp);   // trimming the in point moves the start by the same amount
    transact(proj, label + ' trim start', (ca) => ca.addAction(cur.item.createSetInPointAction(tt(want.inp))));
    cur = await findAt(seq, kind, track, next, f);
    if (!cur) throw lost(next);
  }
  if (!near(cur.end - cur.start, len, f)) {
    const keep = cur.start;
    transact(proj, label + ' trim end', (ca) => ca.addAction(cur.item.createSetOutPointAction(tt(want.inp + len + BigInt(strategy.out_adjust || '0')))));
    cur = await findAt(seq, kind, track, keep, f);
    if (!cur) throw lost(keep);
  }
  if (!near(cur.inp, want.inp, f) || !near(cur.end - cur.start, len, f)) {
    throw new Error('Premiere trimmed a clip on ' + where + ' differently than planned');
  }
  if (near(cur.start, want.start, f)) return;
  if (strategy.slide === 'move') {
    transact(proj, label + ' move', (ca) => ca.addAction(cur.item.createMoveAction(dt(want.start - cur.start))));
    return;
  }
  // slide by copying to the new spot and removing the original
  const from = cur.start;
  transact(proj, label + ' move', (ca) => ca.addAction(editor.createCloneTrackItemAction(cur.item, dt(want.start - from), 0, 0, kind === 'v', false)));
  const old = await findAt(seq, kind, track, from, f);
  if (old) await removeItems(proj, seq, [old], label + ' tidy');
}

function mergeRanges(list) {
  const out = [];
  for (const r of list.sort((a, b) => (a[0] < b[0] ? -1 : 1))) {
    if (out.length && r[0] <= out[out.length - 1][1]) { if (r[1] > out[out.length - 1][1]) out[out.length - 1][1] = r[1]; }
    else out.push([r[0], r[1]]);
  }
  return out;
}

function removalTicks(main, remove, f, all) {
  // source seconds of the recording to take out -> sequence ticks, wherever those moments sit on the timeline
  const out = [];
  for (const m of main) {
    const dur = m.end - m.start;
    for (const [a, b] of remove) {
      const lo = BigInt(Math.round(a * 254016000000)), hi = BigInt(Math.round(b * 254016000000));
      const x = lo > m.inp ? lo : m.inp, y = hi < m.inp + dur ? hi : m.inp + dur;
      if (y <= x) continue;
      const s = snapTo(m.start + (x - m.inp), f), e = snapTo(m.start + (y - m.inp), f);
      if (e > s) out.push([s, e]);
    }
  }
  // A cut that ends within a frame of an existing join, or of another cut, would leave a sliver of clip
  // shorter than a frame. Premiere can't hold one, so the cut is snapped onto the join and close cuts merge.
  const edges = [];
  for (const m of all || main) edges.push(m.start, m.end);
  const snapEdge = (t) => { for (const e of edges) if ((t > e ? t - e : e - t) < f) return e; return t; };
  const snapped = mergeRanges(out).map(([a, b]) => [snapEdge(a), snapEdge(b)]).filter(([a, b]) => b > a);
  const merged = [];
  for (const r of snapped.sort((p, q) => (p[0] < q[0] ? -1 : 1))) {
    const last = merged[merged.length - 1];
    if (last && r[0] - last[1] < f) { if (r[1] > last[1]) last[1] = r[1]; } else merged.push([r[0], r[1]]);
  }
  return merged;
}

function planItem(i, R, f) {
  // the kept pieces of one clip and where each one ends up once the removed time closes up
  let pieces = [[i.start, i.end]];
  for (const [a, b] of R) {
    const next = [];
    for (const [x, y] of pieces) {
      if (b <= x || a >= y) { next.push([x, y]); continue; }
      if (a > x) next.push([x, a]);
      if (b < y) next.push([b, y]);
    }
    pieces = next;
  }
  const shift = (t) => R.reduce((n, [a, b]) => (a < t ? n + ((b < t ? b : t) - a) : n), 0n);
  // A piece under half a frame is a rounding crumb where a video and a mic join sit a few ticks apart. Premiere
  // can't hold a clip that short, so it's left out. Leaving it out can't show, since nothing is that thin.
  const half = f / 2n;
  return pieces.filter(([x, y]) => y - x >= half).map(([x, y]) => ({ start: x - shift(x), end: y - shift(x), inp: i.inp + (x - i.start) }));
}

const near = (a, b, f) => (a > b ? a - b : b - a) <= f / 2n;
const same = (i, w, f) => near(i.start, w.start, f) && near(i.end, w.end, f) && near(i.inp, w.inp, f);

async function cutInPlace(proj, seq, args, strategy) {
  const f = await frameTicks(seq);
  await status('Saving a backup of ' + seq.name + '…', 'backup');
  const stamp = new Date().toTimeString().slice(0, 5).replace(':', '.');
  const backupName = seq.name + ' before ' + args.label + ' ' + stamp;
  await cloneSequence(proj, seq, backupName, 'Backups');

  let items = await snapshot(seq);
  const video = args.video || mainVideo(items);
  // When the animations are going back on from their words afterwards, they come off first so the cut never trims them.
  const ours = !args.lift ? [] : items.filter((i) => i.kind === 'v' && i.track >= 3 && (CACHE_DIR.test(i.path) || (i.track === 3 && i.path === video)));
  await removeItems(proj, seq, ours, 'Josh Cut: lift layers');
  if (ours.length) items = await snapshot(seq);

  const main = items.filter((i) => i.kind === 'v' && i.path === video && i.track < 3);
  const R = removalTicks(main, args.remove || [], f, items);
  if (!R.length) return { ok: true, removed_seconds: 0, backup: backupName, lifted: ours.length };

  // When Premiere drags linked audio along with its video, the audio half of a linked pair follows on its own.
  const work = items;
  const editor = ppro.SequenceEditor.getEditor(seq);
  const seqEnd = tk(await seq.getEndTime());
  let far = seqEnd + 60n * TPS;
  const expected = [];

  const gone = [], moves = [];
  for (const i of work) {
    const plan = planItem(i, R, f);
    if (!plan.length) gone.push(i);
    else moves.push({ i, plan });
    for (const p of plan) expected.push(Object.assign({ kind: i.kind, track: i.track }, p));
  }
  await status('Cutting ' + R.length + ' gaps…', 'cut');
  await removeItems(proj, seq, gone, 'Josh Cut: remove cut clips');

  let done = 0;
  for (const { i, plan } of moves) {
    if (plan.length === 1 && same(i, plan[0], f)) continue;
    // Every clip that changes is rebuilt from fresh copies made in the empty space past the end of the timeline,
    // trimmed there and slid into place, and then the old clip comes off. Premiere draws new clips correctly,
    // but its timeline stops redrawing properly when lots of existing clips are slid along.
    const where = (i.kind === 'v' ? 'V' : 'A') + (i.track + 1);
    const src = await findAt(seq, i.kind, i.track, i.start, f);
    if (!src) throw new Error('Josh Cut Pro lost track of a clip on ' + where);
    const slots = [];
    for (let k = 0; k < plan.length; k++) { slots.push(far); far += (i.end - i.start) + 10n * TPS; }
    transact(proj, 'Josh Cut: copy clip', (ca) => slots.forEach((slot) => ca.addAction(editor.createCloneTrackItemAction(
      src.item, tt(slot - i.start), 0, 0, i.kind === 'v', false))));
    const old = await findAt(seq, i.kind, i.track, i.start, f);
    if (!old) throw new Error('Josh Cut Pro lost track of a clip on ' + where);
    await removeItems(proj, seq, [old], 'Josh Cut: replace clip');
    for (let k = 0; k < plan.length; k++) await place(proj, editor, seq, i.kind, i.track, slots[k], plan[k], f, strategy, 'Josh Cut:');
    done++;
    await status('Cutting the timeline (' + done + ' of ' + moves.length + ' clips)', 'cut');
  }

  // anything left past the old end is a copy Premiere made that wasn't needed
  const after = await snapshot(seq);
  await removeItems(proj, seq, after.filter((x) => x.start >= seqEnd + 30n * TPS), 'Josh Cut: tidy copies');

  await status('Checking the result…', 'verify');
  const check = await snapshot(seq);
  const report = timelineReport(check, f);
  api('/cut-log', { sequence: seq.name, label: args.label, backup: backupName, video, report,
                    clips: check.map((x) => ({ track: (x.kind === 'v' ? 'V' : 'A') + (x.track + 1), start: sec(x.start), end: sec(x.end), in: sec(x.inp),
                                               file: x.path.split(/[\\/]/).pop() })) }).catch(() => {});
  for (const w of expected) {
    if (!check.some((x) => x.kind === w.kind && x.track === w.track && same(x, w, f))) {
      throw new Error('The cut didn\'t come out as planned on ' + (w.kind === 'v' ? 'V' : 'A') + (w.track + 1) + ' at ' + sec(w.start).toFixed(2) +
        's. Your sequence as it was is saved as "' + backupName + '" in Josh Cut Pro > Backups.');
    }
  }
  // Premiere doesn't always redraw after many quick edits, so open the sequence again to refresh it
  try { await proj.openSequence(seq); } catch (e) { /* the edit is done either way */ }
  const removed = R.reduce((n, [a, b]) => n + (b - a), 0n);
  return { ok: true, removed_seconds: sec(removed), backup: backupName, lifted: ours.length, cuts: R.length, gaps: report.gaps, overlaps: report.overlaps };
}

function timelineReport(items, f) {
  // gaps and overlaps between neighbouring clips on each track, for the cut log
  const gaps = [], overlaps = [], tracks = {};
  for (const x of items) (tracks[x.kind + x.track] = tracks[x.kind + x.track] || []).push(x);
  for (const key of Object.keys(tracks)) {
    const list = tracks[key].sort((a, b) => (a.start < b.start ? -1 : 1));
    const where = (key[0] === 'v' ? 'V' : 'A') + (Number(key.slice(1)) + 1);
    for (let k = 1; k < list.length; k++) {
      const d = list[k].start - list[k - 1].end;
      if (d > f / 2n) gaps.push({ track: where, at: sec(list[k - 1].end), seconds: sec(d) });
      if (d < -f / 2n) overlaps.push({ track: where, at: sec(list[k].start), seconds: sec(-d) });
    }
  }
  return { gaps, overlaps };
}

// ------------------------------------------------------------ the probe

async function probe() {
  // Tries each edit on a throwaway copy of the open sequence and reports what Premiere did.
  const proj = await ppro.Project.getActiveProject();
  const seq = proj ? await proj.getActiveSequence() : null;
  if (!seq) throw new Error('Open a sequence with your recording on it, then run the check.');
  const report = { when: new Date().toISOString(), premiere: '', tests: {}, notes: [] };
  try { report.premiere = require('uxp').host.version; } catch (e) { /* not in Premiere */ }
  try { report.constants = Object.keys(ppro.Constants); report.project_item_type = ppro.Constants.ProjectItemType || null; } catch (e) { /* none */ }
  await status('Checking how Premiere edits (on a copy)…', 'check');
  const copy = await cloneSequence(proj, seq, 'Josh Cut Pro check', 'Backups');
  report.tests.clone_sequence = { name: copy.name };
  const editor = ppro.SequenceEditor.getEditor(copy);
  const f = await frameTicks(copy);
  report.frame_ticks = String(f);
  const items = await snapshot(copy);
  const video = mainVideo(items);
  const x = items.find((i) => i.kind === 'v' && i.path === video && i.end - i.start >= 6n * TPS);
  if (!x) throw new Error('The check needs a video clip at least 6 seconds long on the open sequence.');
  const end = tk(await copy.getEndTime());
  const slot = (k) => end + 20n * TPS + BigInt(k) * (x.end - x.start + 20n * TPS);
  const key = (i) => i.kind + i.track + ':' + i.start + ':' + i.end;
  const diff = (a, b) => ({ added: b.filter((i) => !a.some((j) => key(j) === key(i))).map(desc), removed: a.filter((i) => !b.some((j) => key(j) === key(i))).map(desc) });
  const desc = (i) => ({ kind: i.kind, track: i.track, start: sec(i.start), end: sec(i.end), in: sec(i.inp) });

  // 1. copying a clip
  let before = await snapshot(copy);
  transact(proj, 'Josh Cut: check copy', (ca) => ca.addAction(editor.createCloneTrackItemAction(x.item, tt(slot(0) - x.start), 0, 0, true, false)));
  let now = await snapshot(copy);
  const d = diff(before, now);
  const c0 = now.find((i) => i.kind === 'v' && i.track === x.track && near(i.start, slot(0), f));
  report.tests.copy_clip = { landed: !!c0, audio_copied_too: d.added.filter((i) => i.kind === 'a').length, changes: d };

  const fresh = async (k) => {
    // a new copy of the clip in its own empty slot past the end
    const s0 = slot(k), xr = await findAt(copy, 'v', x.track, x.start, f);
    transact(proj, 'Josh Cut: check copy', (ca) => ca.addAction(editor.createCloneTrackItemAction(xr.item, tt(s0 - x.start), 0, 0, true, false)));
    const c = (await snapshot(copy)).find((i) => i.kind === 'v' && i.track === x.track && near(i.start, s0, f));
    if (!c) throw new Error('copy not found');
    return c;
  };
  const one = async (name, k, act) => {
    // one action on its own copy, and what it changed
    try {
      const c = await fresh(k);
      before = await snapshot(copy);
      transact(proj, 'Josh Cut: check ' + name, (ca) => ca.addAction(act(c)));
      now = await snapshot(copy);
      report.tests[name] = Object.assign({ was: desc(c) }, diff(before, now));
    } catch (e) { report.tests[name] = { error: e.message }; }
  };
  // 2. each action on its own
  await one('set_in_later', 1, (c) => c.item.createSetInPointAction(tt(c.inp + TPS)));
  await one('set_out_earlier', 2, (c) => c.item.createSetOutPointAction(tt(c.inp + (c.end - c.start) - TPS)));
  await one('set_start_later', 3, (c) => c.item.createSetStartAction(tt(c.start + TPS)));
  await one('set_end_earlier', 4, (c) => c.item.createSetEndAction(tt(c.end - TPS)));
  await one('move_later', 5, (c) => c.item.createMoveAction(dt(TPS)));
  await one('move_earlier', 6, (c) => c.item.createMoveAction(dt(-TPS)));
  await one('copy_earlier', 7, (c) => editor.createCloneTrackItemAction(c.item, dt(-3n * TPS), 0, 0, true, false));

  // how the out point counts: the gap between what was asked for and what came out
  const outTest = report.tests.set_out_earlier;
  let outAdjust = 0n;
  if (outTest && outTest.added && outTest.added.length) {
    const got = outTest.added[0], was = outTest.was;
    const asked = was.in + (was.end - was.start) - 1;
    outAdjust = BigInt(Math.round((asked - (got.in + got.end - got.start)) * 254016000000));
  }
  const moveOk = (t) => t && t.added && t.added.length === 1 && t.removed && t.removed.length === 1 && Math.abs((t.added[0].start - t.removed[0].start) + 1) < 0.02;
  const slide = moveOk(report.tests.move_earlier) ? 'move' : (report.tests.copy_earlier && report.tests.copy_earlier.added && report.tests.copy_earlier.added.length ? 'copy' : null);
  const strategy = { recipe: 'shrink-slide', slide, out_adjust: String(outAdjust) };

  // 3. the whole recipe: shrink a copy to two seconds from two seconds in, then slide it back five seconds
  try {
    const c = await fresh(8);
    const want = { start: snapTo(c.start - 5n * TPS, f), end: snapTo(c.start - 3n * TPS, f), inp: snapTo(c.inp + 2n * TPS, f) };
    if (!slide) throw new Error('no way to slide a clip earlier');
    await place(proj, editor, copy, 'v', x.track, c.start, want, f, strategy, 'Josh Cut: check');
    const got = (await snapshot(copy)).find((i) => i.kind === 'v' && i.track === x.track && near(i.start, want.start, f));
    report.tests.recipe = { exact: !!(got && same(got, want, f)), got: got ? desc(got) : null, want: desc(Object.assign({ kind: 'v', track: x.track }, want)) };
  } catch (e) { report.tests.recipe = { error: e.message }; }

  // 3b. is the recording linked to anything that moves or trims along with it?
  try {
    before = await snapshot(copy);
    const x1 = await findAt(copy, 'v', x.track, x.start, f);
    transact(proj, 'Josh Cut: check link move', (ca) => ca.addAction(x1.item.createMoveAction(dt(TPS))));
    now = await snapshot(copy);
    const moved = diff(before, now).added.filter((i) => i.kind === 'a');
    const x2 = await findAt(copy, 'v', x.track, x.start + TPS, f);
    transact(proj, 'Josh Cut: check link back', (ca) => ca.addAction(x2.item.createMoveAction(dt(-TPS))));
    before = await snapshot(copy);
    const xi = before.find((i) => i.kind === 'v' && i.track === x.track && near(i.start, x.start, f));
    transact(proj, 'Josh Cut: check link trim', (ca) => ca.addAction(xi.item.createSetInPointAction(tt(xi.inp + TPS / 2n))));
    now = await snapshot(copy);
    const trimmed = diff(before, now).added.filter((i) => i.kind === 'a');
    report.tests.links = { audio_moves_with_video: moved.length, audio_trims_with_video: trimmed.length, moved, trimmed };
    // copies of a clip don't bring linked audio with them, so a linked pair can't be split safely
    strategy.linked_follow = moved.length > 0;
    strategy.linked_ok = moved.length === 0;
  } catch (e) { report.tests.links = { error: e.message }; strategy.linked_ok = false; }

  // 4. removing a video clip: does its linked audio go too?
  try {
    before = await snapshot(copy);
    const c = before.find((i) => i.kind === 'v' && i.track === x.track && near(i.start, slot(0), f));
    await removeItems(proj, copy, [c], 'Josh Cut: check remove');
    now = await snapshot(copy);
    report.tests.remove_video = diff(before, now);
  } catch (e) { report.tests.remove_video = { error: e.message }; }

  // 5. what units Position uses
  try {
    const it = (await snapshot(copy)).find((i) => i.kind === 'v' && i.track === x.track);
    const chain = await it.item.getComponentChain();
    for (let i = 0; i < chain.getComponentCount(); i++) {
      const comp = chain.getComponentAtIndex(i);
      if (!/motion/i.test(await comp.getMatchName())) continue;
      const pos = await paramByName(comp, ['position']);
      const read = async () => { const v = await pos.getValueAtTime(tt(it.start)); return v && v.value != null ? v.value : v; };
      const r0 = await read();
      await setParam(proj, 'Josh Cut: check position', pos, new ppro.PointF(0.25, 0.25));
      const r1 = await read();
      report.tests.position = { default: r0, after_setting_quarter: r1 };
    }
  } catch (e) { report.tests.position = { error: e.message }; }

  // tidy up the throwaway copy
  try {
    const pi = await copy.getProjectItem();
    const bin = pi.getParentBin ? pi.getParentBin() : null;
    if (bin) transact(proj, 'Josh Cut: remove check copy', (ca) => ca.addAction(bin.createRemoveItemAction(pi)));
    report.cleaned_up = true;
  } catch (e) { report.cleaned_up = false; report.notes.push('The "Josh Cut Pro check" sequence is left in Josh Cut Pro > Backups. You can delete it.'); }

  report.strategy = strategy;
  report.ok = !!(report.tests.copy_clip.landed && report.tests.recipe && report.tests.recipe.exact && strategy.linked_ok);
  if (!strategy.linked_ok) report.notes.push('Your recording is linked to audio that doesn\'t trim along with it. Unlink the video and the mic, then run the check again.');
  status(report.ok ? 'Premiere check passed' : 'Premiere check found a problem. The app has the details.');
  return report;
}

async function strategyFor() {
  // the probe's result for this Premiere, running the probe the first time
  let ver = '';
  try { ver = require('uxp').host.version; } catch (e) { /* not in Premiere */ }
  const saved = (await api('/probe')).probe;
  if (saved && saved.ok && saved.premiere === ver && saved.strategy && saved.strategy.recipe === 'shrink-slide') return saved.strategy;
  const report = await probe();
  await api('/probe', report);
  if (!report.ok) throw new Error('Josh Cut Pro checked how this Premiere edits clips and something didn\'t work, so nothing was cut. ' +
    (report.notes.length ? report.notes.join(' ') + ' ' : '') + 'The details are in Projects\\premiere-probe.json.');
  return report.strategy;
}

// ------------------------------------------------------------ layers on V2 and up

async function clipIndex(proj) {
  // every media file in the project, by path
  const out = {};
  await walkProject(proj, (m) => { out[m.path.toLowerCase()] = { clip: m.clip, item: m.item }; return false; });
  return out;
}

async function layerBin(proj) {
  let bin = null;
  try { bin = await cutBin(proj); } catch (e) { /* falls back to the project root */ }
  if (!bin) return proj.getRootItem();
  const find = () => findBin(bin, 'Layers');
  let sub = await find();
  if (!sub) { transact(proj, 'Josh Cut: layers bin', (ca) => ca.addAction(bin.createBinAction('Layers', false))); sub = await find(); }
  return sub || bin;
}

async function videoTrackItems(seq, t) {
  if (t >= await seq.getVideoTrackCount()) return [];
  return (await (await seq.getVideoTrack(t)).getTrackItems(ppro.Constants.TrackItemType.CLIP, false)) || [];
}

async function placeLayers(proj, seq, r, strategy) {
  const editor = ppro.SequenceEditor.getEditor(seq);
  let index = await clipIndex(proj);
  const missing = [...new Set(r.layers.map((l) => l.path).filter((p) => !index[p.toLowerCase()]))];
  if (missing.length) {
    await status('Bringing in ' + missing.length + ' layer clip' + (missing.length > 1 ? 's' : '') + '…', 'layers');
    const ok = await proj.importFiles(missing, true, await layerBin(proj), false);
    if (!ok) throw new Error('Premiere would not import the layer clips (' + missing[0] + ')');
    index = await clipIndex(proj);
  }
  await ensureTracks(proj, seq, editor, r, index, Math.max(...r.layers.map((l) => l.track)));
  let n = 0, unframed = 0;
  for (const l of r.layers) {
    if (l.kind === 'camera_copy') {
      try {
        const pieces = await copyCamera(proj, seq, editor, l, r, strategy);
        for (const start of pieces) {
          try { await frameAt(proj, seq, l.track, start, l.framing); }
          catch (e) { unframed++; console.log('PiP framing failed: ' + (e && e.message ? e.message : e)); }
        }
        n++;
        await status('Placing layers (' + n + ' of ' + r.layers.length + ')', 'layers');
        continue;
      } catch (e) {
        // Placing the raw camera file would lose the key and the look, so Tariq's cuts stop here instead.
        if (r.nest) throw new Error('Could not copy the keyed picture from ' + r.nest + ' for a PiP or half and half shot (' + (e && e.message ? e.message : e) + '). Nothing raw was placed instead.');
        console.log('Copying the camera from V1 failed, placing it from the file: ' + (e && e.message ? e.message : e));
      }
    }
    const found = index[l.path.toLowerCase()];
    if (!found) throw new Error('Layer clip ' + l.path + ' is not in the project after the import');
    const label = 'Josh Cut: ' + (l.name || l.kind) + ' on V' + (l.track + 1);
    transact(proj, label + ' in/out', (ca) => ca.addAction(found.clip.createSetInOutPointsAction(ticks(l.in_f, r), ticks(l.out_f, r))));
    // Animations have no sound. Anything else placed from a file (angles, B-roll, a camera copy that couldn't be
    // copied from V1) puts its sound on A4, and it comes off again unless the clip keeps its audio.
    const own = l.kind !== 'animation';
    transact(proj, label, (ca) => ca.addAction(editor.createOverwriteItemAction(found.item, ticks(l.start_f, r), l.track, own ? 3 : 0)));
    if (own && l.audio_db == null) await dropAudioAt(proj, seq, editor, 3, l.start_f * r.fps_den / r.fps_num, r);
    if (l.framing) {
      try { await frameCamera(proj, seq, l, r); }
      catch (e) { unframed++; console.log('PiP framing failed: ' + (e && e.message ? e.message : e)); }
    }
    n++;
    await status('Placing layers (' + n + ' of ' + r.layers.length + ')', 'layers');
  }
  transact(proj, 'Josh Cut: layers tidy', (ca) => {
    const seen = new Set();
    for (const l of r.layers) {
      const f = index[l.path.toLowerCase()];
      if (f && !seen.has(f.clip)) { seen.add(f.clip); ca.addAction(f.clip.createClearInOutPointsAction()); }
    }
  });
  return unframed ? 'Framing didn\'t take on ' + unframed + ' camera clip' + (unframed > 1 ? 's' : '') + ' on V4, so set Scale and Position on those by hand.' : '';
}

async function copyCamera(proj, seq, editor, l, r, strategy) {
  // The camera under a PiP or half-and-half shot is copied from Josh's own clips on V1, so his key, look and
  // edits come with it. Copies don't bring linked audio, so the mic on A1 stays as it is. Each copy is made past
  // the end of the timeline on V4, shrunk to the shot and slid into place, like a cut. Returns where each piece starts.
  const f = await frameTicks(seq);
  const toTicks = (frame) => snapTo(BigInt(Math.round(frame * r.fps_den / r.fps_num * 254016000000)), f);
  const a = toTicks(l.start_f), b = toTicks(l.start_f + l.out_f - l.in_f);
  // In Tariq's cuts the picture on V1 is pieces of the GREEN_MASTER nest, so those are what get copied (key, shadow and all).
  const near3 = (await snapshot(seq, { v: [0, 1, 2] })).filter((i) => i.start < b && i.end > a);
  const src = [];
  for (const i of near3) if (r.nest ? (await itemName(i.item)) === r.nest : i.path.toLowerCase() === l.path.toLowerCase()) src.push(i);
  if (!src.length) throw new Error((r.nest ? 'no piece of ' + r.nest : 'no clip of the recording') + ' on V1 to V3 at ' + sec(a).toFixed(2) + 's');
  let far = tk(await seq.getEndTime()) + 60n * TPS;
  const starts = [];
  for (const i of src) {
    const x = i.start > a ? i.start : a, y = i.end < b ? i.end : b;
    if (y - x < f / 2n) continue;
    const slot = far; far += (i.end - i.start) + 10n * TPS;
    const now = await findAt(seq, 'v', i.track, i.start, f);
    transact(proj, 'Josh Cut: copy camera', (ca) => ca.addAction(editor.createCloneTrackItemAction(now.item, tt(slot - i.start), l.track - i.track, 0, true, false)));
    if (!(await findAt(seq, 'v', l.track, slot, f))) throw new Error('Premiere did not copy the camera onto V' + (l.track + 1));
    await place(proj, editor, seq, 'v', l.track, slot, { start: x, end: y, inp: i.inp + (x - i.start) }, f, strategy, 'Josh Cut: camera');
    starts.push(x);
  }
  return starts;
}

async function frameAt(proj, seq, track, start, framing) {
  // set the PiP framing on the camera copy that starts here
  const f = await frameTicks(seq);
  const it = await findAt(seq, 'v', track, start, f);
  if (!it) throw new Error('could not find the camera copy on V' + (track + 1));
  await frameItem(proj, it.item, start, framing);
}

async function dropAudioAt(proj, seq, editor, track, seconds, r) {
  if (track >= await seq.getAudioTrackCount()) return;
  const half = 0.5 * r.fps_den / r.fps_num, hits = [];
  for (const it of (await (await seq.getAudioTrack(track)).getTrackItems(ppro.Constants.TrackItemType.CLIP, false)) || [])
    if (Math.abs((await it.getStartTime()).seconds - seconds) < half) hits.push(it);
  if (!hits.length) return;
  proj.lockedAccess(() => {
    ppro.TrackItemSelection.createEmptySelection((sel) => {
      hits.forEach((i) => sel.addItem(i, true));
      proj.executeTransaction((ca) => ca.addAction(editor.createRemoveItemsAction(sel, false, ppro.Constants.MediaType.AUDIO)), 'Josh Cut: layer sound off');
    });
  });
}

async function findTrackItem(seq, track, seconds, r) {
  const half = 0.5 * r.fps_den / r.fps_num;
  for (const it of await videoTrackItems(seq, track)) if (Math.abs((await it.getStartTime()).seconds - seconds) < half) return it;
  return null;
}

async function ensureTracks(proj, seq, editor, r, index, need) {
  // Premiere documents that an insert onto a track past the last one adds the track. The insert goes after
  // the end of the cut so nothing shifts, and the placeholder is removed straight after.
  const endF = Math.ceil(sec(tk(await seq.getEndTime())) * r.fps_num / r.fps_den) + 10;
  const pick = r.layers.find((l) => l.kind === 'animation') || r.layers[0];
  const f = index[pick.path.toLowerCase()];
  while ((await seq.getVideoTrackCount()) <= need) {
    const t = await seq.getVideoTrackCount();
    transact(proj, 'Josh Cut: add V' + (t + 1) + ' in/out', (ca) => ca.addAction(f.clip.createSetInOutPointsAction(ticks(pick.in_f, r), ticks(pick.in_f + 1, r))));
    transact(proj, 'Josh Cut: add V' + (t + 1), (ca) => ca.addAction(editor.createInsertProjectItemAction(f.item, ticks(endF, r), t, 0, true)));
    if ((await seq.getVideoTrackCount()) <= t) throw new Error('Premiere would not add track V' + (t + 1));
    const after = endF * r.fps_den / r.fps_num - 0.01, extra = [];
    const CLIP = ppro.Constants.TrackItemType.CLIP;
    for (let i = 0; i < await seq.getVideoTrackCount(); i++) extra.push(...((await (await seq.getVideoTrack(i)).getTrackItems(CLIP, false)) || []));
    for (let i = 0; i < await seq.getAudioTrackCount(); i++) extra.push(...((await (await seq.getAudioTrack(i)).getTrackItems(CLIP, false)) || []));
    const late = [];
    for (const it of extra) if ((await it.getStartTime()).seconds >= after) late.push(it);
    if (late.length) {
      proj.lockedAccess(() => {
        ppro.TrackItemSelection.createEmptySelection((sel) => {
          late.forEach((i) => sel.addItem(i, true));
          proj.executeTransaction((ca) => ca.addAction(editor.createRemoveItemsAction(sel, false, ppro.Constants.MediaType.VIDEO)), 'Josh Cut: tidy V' + (t + 1));
        });
      });
    }
  }
}

async function paramByName(component, names) {
  for (let i = 0; i < component.getParamCount(); i++) {
    const p = component.getParam(i);
    if (names.includes(String(p.displayName).toLowerCase())) return p;
  }
  return null;
}

async function setParam(proj, label, param, value) {
  const kf = param.createKeyframe(value);
  transact(proj, label, (ca) => ca.addAction(param.createSetValueAction(kf, true)));
}

async function frameCamera(proj, seq, l, r) {
  // Scale and position the camera copy on V4 so you fill the hole in the animation above it.
  // The animation covers everything outside the hole, so no crop is needed.
  const start = ticks(l.start_f, r);
  const item = await findTrackItem(seq, l.track, l.start_f * r.fps_den / r.fps_num, r);
  if (!item) throw new Error('could not find the camera copy on V' + (l.track + 1));
  await frameItem(proj, item, tk(start), l.framing);
}

async function frameItem(proj, item, startTicks, f) {
  const start = tt(startTicks);
  const chain = await item.getComponentChain();
  let motion = null;
  for (let i = 0; i < chain.getComponentCount(); i++) {
    const c = chain.getComponentAtIndex(i);
    if (/motion/i.test(await c.getMatchName())) { motion = c; break; }
  }
  if (!motion) throw new Error('no Motion effect on the camera copy');
  const scale = await paramByName(motion, ['scale']);
  const pos = await paramByName(motion, ['position']);
  if (!scale || !pos) throw new Error('Motion has no Scale or Position');
  await setParam(proj, 'Josh Cut: PiP scale', scale, f.scale);
  // Position may be in pixels or as a fraction of the frame. Read the default to tell which.
  const now = await pos.getValueAtTime(start);
  const v = now && now.value != null ? now.value : now;
  const px = Array.isArray(v) ? v[0] > 2 : true;
  await setParam(proj, 'Josh Cut: PiP position', pos, new ppro.PointF(px ? f.x : f.x / 1920, px ? f.y : f.y / 1080));
}

async function importSequence(proj, result) {
  const before = (await proj.getSequences()).length;
  const ok = await proj.importFiles([result.xml], true);
  if (!ok) throw new Error('Premiere refused the import. You can import it yourself with File > Import: ' + result.xml);
  const sequences = await proj.getSequences();
  let target = null;
  for (const s of sequences) if (s.name === result.sequence_name) target = s;
  if (!target && sequences.length > before) target = sequences[sequences.length - 1];
  if (target) { try { await proj.openSequence(target); } catch (e) { /* imported, just not opened */ } }
}


// ------------------------------------------------------------ what the window can ask for

async function liftLayers(proj, seq) {
  // take our animations and camera copies off V4 and V5 before they go back on in their new places
  const items = await snapshot(seq);
  const video = mainVideo(items);
  await removeItems(proj, seq, items.filter((i) => i.kind === 'v' && i.track >= 3 && (CACHE_DIR.test(i.path) || (i.track === 3 && i.path === video))), 'Josh Cut: lift layers');
}

// ------------------------------------------------------------ Tariq's native edit (Josh OS edit workflow)
// GREEN_MASTER is one uncut sequence with the background, the keyed presenter and the shadow copy. Every
// CLEAN_CUT_rNN is a NEW sequence whose pictures are pieces of that one master, so changing the Ultra Key in
// the master shows up in every cut piece. The good mic goes on A1 straight from its own file using the same
// map. Nothing here edits Josh's own sequences or media. No mask or key is invented: the master is a sequence
// Josh keyed in Premiere, and Ultra Key values are only read, or set when he asks.

const KEY_MATCH = /ultra\s*key|ADBE Ultra Key/i;
const SHADOW_MATCH = /drop\s*shadow/i;

async function componentsOf(trackItem) {
  const out = [];
  try {
    const chain = await trackItem.getComponentChain();
    for (let i = 0; i < chain.getComponentCount(); i++) {
      const c = chain.getComponentAtIndex(i);
      let match = '', name = '';
      try { match = await c.getMatchName(); } catch (e) { /* none */ }
      try { name = await c.getDisplayName(); } catch (e) { /* none */ }
      out.push({ c, match: String(match || ''), name: String(name || '') });
    }
  } catch (e) { /* no chain */ }
  return out;
}

async function itemName(trackItem) {
  try { const pi = await trackItem.getProjectItem(); return String(pi.name || ''); } catch (e) { return ''; }
}

async function readParams(component, at) {
  const out = [];
  for (let i = 0; i < component.getParamCount(); i++) {
    const p = component.getParam(i);
    let v = null;
    try { const r = await p.getValueAtTime(at); v = r && r.value != null ? r.value : r; } catch (e) { v = null; }
    if (v && typeof v === 'object' && !Array.isArray(v)) { try { v = JSON.parse(JSON.stringify(v)); } catch (e) { v = String(v); } }
    out.push({ index: i, name: String(p.displayName || ''), value: v });
  }
  return out;
}

async function masterRoles(master) {
  // which video track holds the keyed presenter, which holds the shadow copy, and what the master's audio holds
  const items = await snapshot(master);
  const tracks = {};
  for (const i of items.filter((x) => x.kind === 'v')) {
    const comps = await componentsOf(i.item);
    const t = tracks[i.track] = tracks[i.track] || { track: i.track, clips: 0, key: 0, shadow: 0, paths: new Set() };
    t.clips += 1; t.paths.add(i.path);
    if (comps.some((c) => KEY_MATCH.test(c.match) || KEY_MATCH.test(c.name))) t.key += 1;
    if (comps.some((c) => SHADOW_MATCH.test(c.match) || SHADOW_MATCH.test(c.name))) t.shadow += 1;
  }
  const list = Object.values(tracks).map((t) => Object.assign(t, { paths: [...t.paths] }));
  // the presenter is the highest keyed track without a shadow-only effect; the shadow copy is a keyed track with Drop Shadow
  const keyed = list.filter((t) => t.key > 0);
  const presenter = keyed.filter((t) => !t.shadow).sort((a, b) => b.track - a.track)[0] || null;
  const shadow = keyed.filter((t) => t.shadow).sort((a, b) => b.track - a.track)[0] || null;
  const audio = items.filter((x) => x.kind === 'a');
  return { items, tracks: list, presenter, shadow, audio };
}

async function tqProbe(args) {
  const report = { when: new Date().toISOString(), premiere: '', ok: false, notes: [], master: args.master || 'GREEN_MASTER' };
  try { report.premiere = require('uxp').host.version; } catch (e) { /* not in Premiere */ }
  report.api = { exporter: !!(ppro.Exporter && ppro.Exporter.exportSequenceFrame), filter_factory: !!ppro.VideoFilterFactory,
                 save: true, overwrite: !!(ppro.SequenceEditor) };
  try { report.key_effects = ((await ppro.VideoFilterFactory.getMatchNames()) || []).filter((m) => /key/i.test(m)); } catch (e) { report.key_effects = null; }
  const proj = await ppro.Project.getActiveProject();
  if (!proj) { report.notes.push('Open the test copy of the Premiere project.'); return report; }
  report.project = proj.path || proj.name;
  const master = await findSequence(proj, report.master);
  if (!master) { report.notes.push(`There is no sequence called ${report.master}. Duplicate your keyed, uncut sequence and name it ${report.master}.`); return report; }
  report.frame_ticks = String(await frameTicks(master));
  try { const r = await master.getFrameSize(); report.frame = [Math.round(r.width || (r.right - r.left)), Math.round(r.height || (r.bottom - r.top))]; } catch (e) { report.frame = null; }
  const roles = await masterRoles(master);
  report.tracks = roles.tracks;
  report.presenter_track = roles.presenter ? roles.presenter.track : null;
  report.shadow_track = roles.shadow ? roles.shadow.track : null;
  report.master_audio_clips = roles.audio.length;
  if (!roles.presenter) report.notes.push(`No track in ${report.master} has Ultra Key without Drop Shadow, so the presenter can't be found.`);
  if (roles.presenter && roles.presenter.clips !== 1) report.notes.push('The presenter track in the master should be one uncut clip.');
  if (roles.audio.length) report.notes.push(`${report.master} has audio on it. Remove it there so camera sound can't reach the cut. The good mic is placed separately.`);
  if (!report.api.exporter) report.notes.push('This Premiere has no frame export in its plugin API.');
  report.ok = !report.notes.length;
  return report;
}

async function presenterClip(master, cameraPath) {
  const roles = await masterRoles(master);
  if (!roles.presenter) throw new Error('No keyed presenter track in the master');
  const clips = roles.items.filter((i) => i.kind === 'v' && i.track === roles.presenter.track);
  const cam = clips.filter((i) => !cameraPath || i.path.toLowerCase() === String(cameraPath).toLowerCase());
  if (!cam.length) throw new Error('The master\'s presenter clip is not the chosen camera file');
  return { roles, clip: cam[0] };
}

async function tqMasterRead(args) {
  const proj = await ppro.Project.getActiveProject();
  const master = await findSequence(proj, args.master || 'GREEN_MASTER');
  if (!master) throw new Error('No master sequence');
  const { roles } = await presenterClip(master, args.camera_path);
  const out = [];
  for (const role of ['presenter', 'shadow']) {
    const t = roles[role];
    if (!t) continue;
    for (const i of roles.items.filter((x) => x.kind === 'v' && x.track === t.track)) {
      for (const c of await componentsOf(i.item)) {
        if (!(KEY_MATCH.test(c.match) || KEY_MATCH.test(c.name) || SHADOW_MATCH.test(c.match) || /motion/i.test(c.match))) continue;
        out.push({ role, track: t.track, start: String(i.start), effect: c.match || c.name, params: await readParams(c.c, tt(i.start)) });
      }
    }
  }
  return { master: master.name, effects: out };
}

async function tqMasterSet(args) {
  // set one Ultra Key value on the presenter only. The shadow copy keeps its own rough key.
  if (typeof args.value !== 'number' || !isFinite(args.value)) throw new Error('A key setting must be a number');
  const proj = await ppro.Project.getActiveProject();
  const master = await findSequence(proj, args.master || 'GREEN_MASTER');
  if (!master) throw new Error('No master sequence');
  const { roles } = await presenterClip(master, args.camera_path);
  const changed = [];
  for (const i of roles.items.filter((x) => x.kind === 'v' && x.track === roles.presenter.track)) {
    for (const c of await componentsOf(i.item)) {
      if (!(KEY_MATCH.test(c.match) || KEY_MATCH.test(c.name))) continue;
      const p = await paramByName(c.c, [String(args.param).toLowerCase()]);
      if (!p) throw new Error('Ultra Key has no setting called ' + args.param);
      const before = await p.getValueAtTime(tt(i.start));
      await setParam(proj, 'Josh Cut: master key ' + args.param, p, args.value);
      const after = await p.getValueAtTime(tt(i.start));
      changed.push({ start: String(i.start), before: before && before.value, after: after && after.value });
    }
  }
  if (!changed.length) throw new Error('No Ultra Key on the presenter track');
  return { master: master.name, param: args.param, changed };
}

async function tqExportFrames(args) {
  // real Premiere frames, for checking hair, edges and that a master change reached every cut piece
  const proj = await ppro.Project.getActiveProject();
  const seq = await findSequence(proj, args.sequence);
  if (!seq) throw new Error('No sequence called ' + args.sequence);
  const out = [];
  for (const [i, t] of (args.times || []).entries()) {
    const name = `${args.prefix || 'frame'}-${String(i).padStart(3, '0')}.png`;
    const ok = await ppro.Exporter.exportSequenceFrame(seq, tt(BigInt(t)), name, args.dir, args.width || 1920, args.height || 1080);
    out.push({ time: String(t), file: name, ok: !!ok });
  }
  return { sequence: seq.name, dir: args.dir, frames: out };
}

async function placeFromProject(proj, editor, seq, projectItem, at, videoTrack, audioTrack) {
  transact(proj, 'Josh Cut: place', (ca) => ca.addAction(editor.createOverwriteItemAction(projectItem, tt(at), videoTrack, audioTrack)));
}

async function tqBuildCut(args, boundProject = null, boundMaster = null, boundStrategy = null) {
  const plan = args.plan, map = plan.map;
  const proj = boundProject || await ppro.Project.getActiveProject();
  if (!proj) throw new Error('Open the Premiere project first');
  const master = boundMaster || await findSequence(proj, plan.master);
  if (!master) throw new Error(`There is no ${plan.master} sequence`);
  if (await findSequence(proj, plan.sequence_name)) throw new Error(`${plan.sequence_name} already exists. Nothing was changed. Rename or delete it to build again.`);
  const f = await frameTicks(master);
  if (String(f) !== String(map.frame_ticks)) throw new Error(`The master runs at ${f} ticks a frame, the plan at ${map.frame_ticks}`);
  const { clip: pres, roles } = await presenterClip(master, plan.camera_path);
  if (roles.audio.length) throw new Error('The master has audio on it, which would bring camera sound into the cut');
  const camToMaster = (camTicks) => BigInt(camTicks) - pres.inp + pres.start;
  const masterPI = await master.getProjectItem();
  const mic = await findClipByPath(proj, plan.mic_path);
  if (!mic) throw new Error('Import the good mic file into this project first: ' + plan.mic_path);

  await status('Making ' + plan.sequence_name + '…', 'tq');
  const seq = await cloneSequence(proj, master, plan.sequence_name, 'Tariq cuts');
  const editor = ppro.SequenceEditor.getEditor(seq);
  // empty the copy: it keeps the master's settings, then gets pieces of the master itself
  await removeItems(proj, seq, await snapshot(seq), 'Josh Cut: empty new cut');
  const strategy = boundStrategy || await strategyFor();
  const pieces = map.pieces.filter((p) => p.kind === 'source');
  let far = BigInt(map.duration_ticks) + 120n * TPS;
  for (const [k, p] of pieces.entries()) {
    await status(`Placing piece ${k + 1} of ${pieces.length}`, 'tq');
    const slot = far; far += BigInt(p.out_end - p.out_start) + 10n * TPS;
    // the whole master nest lands past the end, then is shrunk to this piece and slid into place
    await placeFromProject(proj, editor, seq, masterPI, slot, 0, 0);
    const want = { start: BigInt(p.out_start), end: BigInt(p.out_end), inp: camToMaster(p.camera_in) };
    // the nest should carry no audio; anything that came with it is removed before it can be used
    const stray = (await snapshot(seq, { v: [], a: [0, 1, 2, 3] })).filter((i) => near(i.start, slot, f));
    await removeItems(proj, seq, stray, 'Josh Cut: no nest audio');
    await place(proj, editor, seq, 'v', 0, slot, want, f, strategy, 'Josh Cut: piece');
  }
  for (const [k, p] of pieces.entries()) {
    await status(`Placing the mic ${k + 1} of ${pieces.length}`, 'tq');
    transact(proj, 'Josh Cut: mic range', (ca) => ca.addAction(mic.clip.createSetInOutPointsAction(tt(BigInt(p.mic_in)), tt(BigInt(p.mic_out)))));
    await placeFromProject(proj, editor, seq, mic.item, BigInt(p.out_start), 0, 0);
  }
  for (const p of map.pieces.filter((x) => x.kind === 'room_tone')) {
    const rt = await findClipByPath(proj, p.media_path);
    if (!rt) throw new Error('Import the room tone file first: ' + p.media_path);
    transact(proj, 'Josh Cut: room tone range', (ca) => ca.addAction(rt.clip.createSetInOutPointsAction(tt(BigInt(p.media_in)), tt(BigInt(p.media_out)))));
    await placeFromProject(proj, editor, seq, rt.item, BigInt(p.out_start), 0, 1);
  }
  try { transact(proj, 'Josh Cut: clear mic range', (ca) => ca.addAction(mic.clip.createClearInOutPointsAction())); } catch (e) { /* the range stays set in the source monitor */ }
  // read back everything that is on the new sequence
  const all = await snapshot(seq);
  const video = [];
  for (const i of all.filter((x) => x.kind === 'v')) video.push({ track: i.track, start: String(i.start), end: String(i.end), inp: String(i.inp), name: await itemName(i.item) });
  const lc = (s) => String(s || '').toLowerCase();
  const audio = all.filter((x) => x.kind === 'a').map((i) => ({ track: i.track, start: String(i.start), end: String(i.end), inp: String(i.inp),
    role: lc(i.path) === lc(plan.mic_path) ? 'mic' : lc(i.path) === lc(plan.camera_path) ? 'camera' : map.pieces.some((p) => p.kind === 'room_tone' && lc(p.media_path) === lc(i.path)) ? 'room_tone' : 'other' }));
  const rep = timelineReport(all, f);
  try { await proj.openSequence(seq); } catch (e) { /* built, just not opened */ }
  status(plan.sequence_name + ' is built');
  return { sequence: plan.sequence_name, frame_ticks: String(f), video, audio, gaps: rep.gaps, overlaps: rep.overlaps,
           nest: video.every((v) => v.name === master.name), master: master.name, saved: false };
}

async function tqSave() {
  const proj = await ppro.Project.getActiveProject();
  const ok = await proj.save();
  return { saved: !!ok, project: proj.path || proj.name };
}

async function tqAssemble(args) {
  // FINAL_ASSEMBLY_rNN starts as a copy of the approved cut. Josh Cut Pro's Animations tool places the renders on V4 and V5.
  const proj = await ppro.Project.getActiveProject();
  const cut = await findSequence(proj, args.cut);
  if (!cut) throw new Error('No sequence called ' + args.cut);
  if (await findSequence(proj, args.sequence)) return { sequence: args.sequence, existed: true };
  await cloneSequence(proj, cut, args.sequence, 'Tariq cuts');
  return { sequence: args.sequence, existed: false };
}

async function tqExport(args) {
  // a local render through Premiere's own encoder. Josh OS checks the file itself afterwards.
  const proj = await ppro.Project.getActiveProject();
  const seq = await findSequence(proj, args.sequence);
  if (!seq) throw new Error('No sequence called ' + args.sequence);
  const mgr = ppro.EncoderManager.getManager();
  const type = args.queue ? ppro.Constants.ExportType.QUEUE_TO_AME : ppro.Constants.ExportType.IMMEDIATELY;
  const ok = await mgr.exportSequence(seq, type, args.output, args.preset || '', true);
  return { sequence: seq.name, output: args.output, started: !!ok, ame_installed: !!mgr.isAMEInstalled };
}

// Typed Ultra Key values measured from the two reference projects (handover doc 03). Starting points only.
// The key colour is not set here: its serialized form differs between projects and the typed API was not verified.
const KEY_REFERENCES = {
  data: { Transparency: 45, Highlight: 52.04545, Shadow: 50.22727, Tolerance: 65.45454, Pedestal: 100, Choke: 7.72727, Soften: 0, Contrast: 0, 'Mid Point': 50, Desaturate: 25, Range: 50, Spill: 50, Luma: 50, Saturation: 100, Hue: 0, Luminance: 100 },
  exec: { Transparency: 45, Highlight: 5.28302, Shadow: 46.79245, Tolerance: 52.45283, Pedestal: 61.50944, Choke: 0, Soften: 0, Contrast: 0, 'Mid Point': 50, Desaturate: 25, Range: 50, Spill: 50, Luma: 50, Saturation: 100, Hue: 0, Luminance: 100 },
};
// Data Storytelling's shadow copy at 3840 by 2160: Drop Shadow only, offset by the copy's own Motion.
const SHADOW_REFERENCE = { opacity: 52.7, direction: 135, distance: 5, softness: 121.1111, position: [826, 1376], scale: 100.8888855, frame: [3840, 2160] };

async function setNumberParams(proj, component, values, label) {
  const done = [], missing = [];
  for (const [name, v] of Object.entries(values)) {
    const p = await paramByName(component, [name.toLowerCase()]);
    if (!p) { missing.push(name); continue; }
    await setParam(proj, label + ' ' + name, p, v);
    done.push(name);
  }
  return { done, missing };
}

async function copyEffects(proj, from, fresh, notes) {
  // every effect on one clip, with the setting it has at that clip's start, onto another clip. Effects the new clip
  // lacks are added first. fresh() looks the target up again, since Premiere hands back a new clip after each edit.
  const at = tt(from.start);
  const src = await componentsOf(from.item);
  const used = new Set();
  let copied = 0, failed = 0, animated = 0;
  // read every value before any edit, since the source clip's objects go stale too
  for (const c of src) {
    c.values = [];
    for (let i = 0; i < c.c.getParamCount(); i++) {
      const sp = c.c.getParam(i);
      let v;
      try { const r = await sp.getValueAtTime(at); v = r && r.value !== undefined ? r.value : r; } catch (e) { v = null; }
      try { if (sp.isTimeVarying && (await sp.isTimeVarying())) animated += 1; } catch (e) { /* unknown */ }
      c.values.push({ name: String(sp.displayName || i), v });
    }
  }
  for (const c of src) {
    let to = await componentsOf((await fresh()).item);
    let idx = to.findIndex((x, i) => !used.has(i) && x.match === c.match);
    if (idx < 0) {
      try {
        const comp = await ppro.VideoFilterFactory.createComponent(c.match);
        const chain = await (await fresh()).item.getComponentChain();
        transact(proj, 'Josh Cut: copy ' + (c.name || c.match), (ca) => ca.addAction(chain.createAppendComponentAction(comp)));
      } catch (e) { notes.push('Could not add ' + (c.name || c.match) + ' to the uncut presenter: ' + (e.message || e)); continue; }
      to = await componentsOf((await fresh()).item);
      idx = to.map((x, i) => (!used.has(i) && x.match === c.match ? i : -1)).filter((i) => i >= 0).pop();
      if (idx == null || idx < 0) { notes.push('Premiere did not add ' + (c.name || c.match) + ' to the uncut presenter.'); continue; }
    }
    used.add(idx);
    const n = Math.min(c.values.length, to[idx].c.getParamCount());
    for (let i = 0; i < n; i++) {
      const { name: pname, v } = c.values[i];
      if (v === null || v === undefined) continue;
      try {
        const comps = await componentsOf((await fresh()).item);  // a fresh param, since the clip changed with the last edit
        await setParam(proj, 'Josh Cut: copy ' + (c.name || c.match) + ' ' + pname, comps[idx].c.getParam(i), v);
        copied += 1;
      } catch (e) { failed += 1; }
    }
  }
  notes.push(`Copied ${copied} effect settings from your first presenter clip onto the uncut presenter.` +
             (failed ? ` ${failed} settings could not be copied, so check the key on GREEN_MASTER.` : '') +
             (animated ? ` ${animated} settings were animated, and only their value at the start was copied.` : ''));
  return { copied, failed, animated };
}

async function uncutMaster(proj, master, roles, f, notes) {
  // Josh's sequence is already cut (AutoCut), but the master must be one uncut take. Place the whole recording past
  // the end, copy the first presenter clip's effects onto it, remove the pieces and slide it to the start. Each other
  // video track (the background still) keeps its first piece, moved to the start and stretched over the whole take.
  const editor = ppro.SequenceEditor.getEditor(master);
  const pt = roles.presenter.track;
  const vids = roles.items.filter((x) => x.kind === 'v');
  const pres = vids.filter((x) => x.track === pt);
  const first = pres[0];
  if (new Set(pres.map((x) => x.path)).size !== 1) throw new Error('The presenter track holds more than one file, so it cannot be made into one uncut take.');
  const cam = await findClipByPath(proj, first.path);
  if (!cam) throw new Error('The recording ' + first.path + ' is not in this project.');
  const end = vids.reduce((m, x) => (x.end > m ? x.end : m), 0n) + 10n * f;
  const needIn = pres.reduce((m, x) => (x.inp < m ? x.inp : m), pres[0].inp);
  const needOut = pres.reduce((m, x) => { const o = x.inp + (x.end - x.start); return o > m ? o : m; }, 0n);
  await placeFromProject(proj, editor, master, cam.item, end, pt, 0);
  const fresh = async () => { const it = await findAt(master, 'v', pt, end, f); if (!it) throw new Error('Josh Cut Pro lost track of the uncut presenter.'); return it; };
  const placed = await fresh();
  if (placed.inp > needIn || placed.inp + (placed.end - placed.start) < needOut) {
    throw new Error('The recording in the project is marked with In and Out points that leave out part of the take, so it cannot be placed whole. Clear them on the clip and try again.');
  }
  const firstNow = await findAt(master, 'v', pt, first.start, f);  // the old object went stale with the placing
  if (!firstNow) throw new Error('Josh Cut Pro lost track of your first presenter clip.');
  await copyEffects(proj, firstNow, fresh, notes);
  // linked camera sound came with it: take every audio clip off again
  const audio = (await snapshot(master)).filter((x) => x.kind === 'a');
  if (audio.length) await removeItems(proj, master, audio, 'Josh Cut: master audio off');
  const presNow = (await snapshot(master, { v: [pt], a: [] })).filter((x) => x.start < end);  // fresh objects
  await removeItems(proj, master, presNow, 'Josh Cut: remove presenter pieces');
  const u = await fresh();
  transact(proj, 'Josh Cut: uncut presenter to start', (ca) => ca.addAction(u.item.createMoveAction(dt(-u.start))));
  const take = await findAt(master, 'v', pt, 0n, f);
  if (!take) throw new Error('Premiere did not move the uncut presenter to the start.');
  for (const t of [...new Set(vids.filter((x) => x.track !== pt).map((x) => x.track))]) {
    const pieces = vids.filter((x) => x.track === t);
    if (new Set(pieces.map((x) => x.path)).size !== 1) { notes.push('V' + (t + 1) + ' holds more than one file, so it was left as it was.'); continue; }
    if (pieces.length > 1) await removeItems(proj, master, (await snapshot(master, { v: [t], a: [] })).slice(1), 'Josh Cut: remove background pieces');
    let b = await findAt(master, 'v', t, pieces[0].start, f);
    if (b.start !== 0n) { transact(proj, 'Josh Cut: background to start', (ca) => ca.addAction(b.item.createMoveAction(dt(-b.start)))); b = await findAt(master, 'v', t, 0n, f); }
    if (b.end < take.end) {
      try {
        transact(proj, 'Josh Cut: background over the whole take', (ca) => ca.addAction(b.item.createSetEndAction(tt(take.end))));
      } catch (e) {
        // a still that won't stretch is repeated instead
        const len = b.end - b.start;
        const copies = Number((take.end - b.end + len - 1n) / len);
        if (copies > 900) throw new Error('V' + (t + 1) + ' could not be stretched over the take and is too short to repeat.');
        for (let k = 1; k <= copies; k++) {
          const b0 = await findAt(master, 'v', t, 0n, f);
          transact(proj, 'Josh Cut: repeat background', (ca) => ca.addAction(editor.createCloneTrackItemAction(b0.item, dt(len * BigInt(k)), 0, 0, true, false)));
        }
      }
    }
  }
  notes.push('Your sequence was already cut, so GREEN_MASTER was rebuilt as one uncut take of the recording, with the effects from your first presenter clip and the background covering it all.');
}

async function tqMakeMaster(args) {
  // GREEN_MASTER from a sequence Josh has already keyed: a copy, with its audio taken off, the presenter found by
  // its Ultra Key, and (when asked) a rough shadow copy added under the presenter. Josh's own sequence is untouched.
  const proj = await ppro.Project.getActiveProject();
  const name = args.master || 'GREEN_MASTER';
  if (await findSequence(proj, name)) throw new Error(name + ' already exists. Nothing was changed.');
  const src = await findSequence(proj, args.source);
  if (!src) throw new Error('There is no sequence called ' + args.source);
  const roles0 = await masterRoles(src);
  if (!roles0.presenter) throw new Error(args.source + ' has no clip with Ultra Key, so there is no keyed presenter to start from.');
  const master = await cloneSequence(proj, src, name, 'Tariq cuts');
  const notes = [];
  let roles = await masterRoles(master);
  if (!roles.presenter) throw new Error('The copy of ' + args.source + ' lost its keyed presenter, so ' + name + ' is not usable. Delete it and check the key on ' + args.source + '.');
  if (roles.audio.length) { await removeItems(proj, master, roles.audio, 'Josh Cut: master audio off'); notes.push('Took the audio off the master copy. Your sequence keeps its audio.'); }
  const f = await frameTicks(master);
  roles = await masterRoles(master);
  if (roles.presenter.clips > 1) {
    await uncutMaster(proj, master, roles, f, notes);
    roles = await masterRoles(master);
    if (!roles.presenter || roles.presenter.clips !== 1) throw new Error('Rebuilding the presenter as one uncut clip did not work, so ' + name + ' is not usable. Delete it and try again.');
  }
  if (args.reference && KEY_REFERENCES[args.reference]) {
    for (const i of (await masterRoles(master)).items.filter((x) => x.kind === 'v' && x.track === roles.presenter.track)) {
      for (const c of await componentsOf(i.item)) {
        if (!(KEY_MATCH.test(c.match) || KEY_MATCH.test(c.name))) continue;
        const r = await setNumberParams(proj, c.c, KEY_REFERENCES[args.reference], 'Josh Cut: reference key');
        if (r.missing.length) notes.push('Ultra Key here has no ' + r.missing.join(', ') + ', so those were left as they were.');
      }
    }
    notes.push('Set the presenter key to the ' + args.reference + ' reference values. The key colour was left as you had it.');
  }
  roles = await masterRoles(master);
  if (!roles.shadow && args.add_shadow) {
    const pres = roles.items.filter((x) => x.kind === 'v' && x.track === roles.presenter.track);
    if (pres.length !== 1) throw new Error('The presenter track should be one uncut clip before a shadow copy is added.');
    const p = pres[0], top = await master.getVideoTrackCount();
    const above = roles.items.some((x) => x.kind === 'v' && x.track === roles.presenter.track + 1);
    if (above) throw new Error('The track above the presenter in ' + args.source + ' is in use. The shadow copy goes under the presenter, so the presenter moves up one.');
    const editor = ppro.SequenceEditor.getEditor(master);
    // presenter up one track, then a copy of it back on its old track as the shadow. With no track above, see whether
    // Premiere makes one; if it won't, the master goes on without a shadow and says so.
    const ptrack = p.track + 1;
    let up = null;
    try {
      transact(proj, 'Josh Cut: presenter up', (ca) => ca.addAction(editor.createCloneTrackItemAction(p.item, tt(0n), 1, 0, true, false)));
      up = ptrack < (await master.getVideoTrackCount()) ? await findAt(master, 'v', ptrack, p.start, f) : null;
    } catch (e) { if (roles.presenter.track + 1 < top) throw e; }
    if (!up) {
      if (roles.presenter.track + 1 < top) throw new Error('Premiere did not copy the presenter up a track.');
      notes.push('There is no empty video track above the presenter and Premiere would not add one, so there is no shadow copy. Add a video track to GREEN_MASTER and a copy of the presenter under it if you want one.');
      roles = await masterRoles(master);
      return { master: name, from: args.source, frame_ticks: String(f), presenter_track: roles.presenter ? roles.presenter.track : null,
               shadow_track: null, audio_clips: roles.audio.length, notes, shadow_skipped: true };
    }
    const shadow = await findAt(master, 'v', p.track, p.start, f);
    const comp = await ppro.VideoFilterFactory.createComponent('AE.ADBE Drop Shadow');
    const chain = await shadow.item.getComponentChain();
    transact(proj, 'Josh Cut: shadow effect', (ca) => ca.addAction(chain.createAppendComponentAction(comp)));
    const s2 = await findAt(master, 'v', p.track, p.start, f);
    for (const c of await componentsOf(s2.item)) {
      if (SHADOW_MATCH.test(c.match) || SHADOW_MATCH.test(c.name)) {
        await setNumberParams(proj, c.c, { Opacity: SHADOW_REFERENCE.opacity, Direction: SHADOW_REFERENCE.direction, Distance: SHADOW_REFERENCE.distance, Softness: SHADOW_REFERENCE.softness }, 'Josh Cut: shadow');
        const only = await paramByName(c.c, ['shadow only']);
        if (only) await setParam(proj, 'Josh Cut: shadow only', only, true); else notes.push('Drop Shadow has no Shadow Only setting here. Turn it on by hand.');
      }
    }
    let frame = [1920, 1080];
    try { const r = await master.getFrameSize(); frame = [Math.round(r.width || (r.right - r.left)), Math.round(r.height || (r.bottom - r.top))]; } catch (e) { /* 1080p */ }
    const k = frame[0] / SHADOW_REFERENCE.frame[0];
    try {
      const s3 = await findAt(master, 'v', p.track, p.start, f);  // a fresh object: the one above went stale with the edits
      await frameItem(proj, s3.item, s3.start, { scale: SHADOW_REFERENCE.scale, x: SHADOW_REFERENCE.position[0] * k * 1920 / frame[0], y: SHADOW_REFERENCE.position[1] * k * 1080 / frame[1] });
    } catch (e) { notes.push('The shadow copy could not be moved into place, so set its Position and Scale by hand.'); }
    notes.push('Added a shadow copy under the presenter with a rough key and a soft Drop Shadow, from the Data Storytelling settings. Adjust it to taste.');
  }
  roles = await masterRoles(master);
  return { master: name, from: args.source, frame_ticks: String(f), presenter_track: roles.presenter ? roles.presenter.track : null,
           shadow_track: roles.shadow ? roles.shadow.track : null, audio_clips: roles.audio.length, notes };
}

async function tqImport(args) {
  const proj = await ppro.Project.getActiveProject();
  const need = [];
  for (const p of args.paths || []) if (!(await findClipByPath(proj, p))) need.push(p);
  if (need.length && !(await proj.importFiles(need, true, await layerBin(proj), false))) throw new Error('Premiere would not import ' + need[0]);
  return { imported: need };
}

// Tariq's own projects: a Josh OS test copy, or the project he builds in a video's Tariq folder. Josh's projects are never opened.
const TARIQ_PROJECT = /[\\/](native-test[\\/][^\\/]+|Tariq)[\\/][^\\/]+\.prproj$/i;
const unprefix = (p) => String(p || '').replace(/^\\\\\?\\/, '');

// Small fixed edit steps Josh OS strings together to build Tariq's timeline (tq_ops). Each one is a single
// documented Premiere action. They only run in one of Tariq's own projects, so Josh's sequences can't be reached.
async function opItem(seq, a) {
  const tr = a.kind === 'a' ? await seq.getAudioTrack(a.track) : await seq.getVideoTrack(a.track);
  const list = (await tr.getTrackItems(ppro.Constants.TrackItemType.CLIP, false)) || [];
  const items = [];
  for (const it of list) items.push(await readItem(it, a.kind || 'v', a.track));
  items.sort((x, y) => (x.start < y.start ? -1 : x.start > y.start ? 1 : 0));
  const it = items[a.index || 0];
  if (!it) throw new Error(`No clip ${a.index || 0} on ${(a.kind === 'a' ? 'A' : 'V') + (a.track + 1)}`);
  return it;
}

async function opValue(p, at) {
  let v = null;
  try { const r = await p.getValueAtTime(at); v = r && r.value !== undefined ? r.value : r; } catch (e) { v = null; }
  if (v === null || typeof v === 'object') {
    try {
      const s = await p.getStartValue();
      if (s && s.red !== undefined) return { color: [s.red, s.green, s.blue, s.alpha] };
      if (s && s.value !== undefined) v = s.value;
    } catch (e) { /* none */ }
  }
  if (v && typeof v === 'object' && !Array.isArray(v)) { try { v = JSON.parse(JSON.stringify(v)); } catch (e) { v = String(v); } }
  return v;
}

async function opInfo(proj, seq) {
  const out = { name: seq.name, frame_ticks: String(await frameTicks(seq)), video_tracks: await seq.getVideoTrackCount(), audio_tracks: await seq.getAudioTrackCount(), items: [] };
  try { const r = await seq.getFrameSize(); out.frame = [Math.round(r.width || (r.right - r.left)), Math.round(r.height || (r.bottom - r.top))]; } catch (e) { out.frame = null; }
  const items = await snapshot(seq);
  const idx = {};
  for (const i of items) {
    const k = i.kind + i.track; idx[k] = (idx[k] || 0);
    const row = { kind: i.kind, track: i.track, index: idx[k]++, start: String(i.start), end: String(i.end), inp: String(i.inp), path: i.path, effects: [] };
    if (i.kind === 'v') {
      for (const c of await componentsOf(i.item)) {
        const params = [];
        for (let n = 0; n < c.c.getParamCount(); n++) { const p = c.c.getParam(n); params.push({ name: String(p.displayName || ''), value: await opValue(p, tt(i.start)) }); }
        row.effects.push({ match: c.match, name: c.name, params });
      }
    }
    out.items.push(row);
  }
  return out;
}

function opKeyframeValue(a) {
  if (a.type === 'color') { const c = a.value; return new ppro.Color(c[0], c[1], c[2], c.length > 3 ? c[3] : 1); }
  if (a.type === 'point') return new ppro.PointF(a.value[0], a.value[1]);
  if (a.type === 'bool') return !!a.value;
  return a.value;
}

async function opParam(item, a) {
  const comps = (await componentsOf(item.item)).filter((c) => c.match === a.effect || c.name === a.effect);
  const c = comps[a.nth || 0];
  if (!c) throw new Error('The clip has no ' + a.effect);
  if (a.param_index != null) return c.c.getParam(a.param_index);
  const p = await paramByName(c.c, [String(a.param).toLowerCase()]);
  if (!p) throw new Error(a.effect + ' has no setting called ' + a.param);
  return p;
}

async function tqOps(args) {
  const done = [];
  let proj = await ppro.Project.getActiveProject();
  const guard = () => { if (!proj || !TARIQ_PROJECT.test(unprefix(proj.path))) throw new Error('Tariq only edits his own projects. Open one of them first.'); };
  const seqOf = async (name) => { const s = await findSequence(proj, name); if (!s) throw new Error('There is no sequence called ' + name); return s; };
  for (const [n, a] of (args.ops || []).entries()) {
    try {
      let r = null;
      if (a.op === 'create_project') {
        if (!TARIQ_PROJECT.test(a.path || '')) throw new Error('Tariq only makes projects in a Tariq folder.');
        proj = await ppro.Project.createProject(a.path);
        if (!proj) throw new Error('Premiere would not make the project');
        r = { project: proj.path };
      } else if (a.op === 'open_project') {
        if (!TARIQ_PROJECT.test(a.path || '')) throw new Error('Tariq only opens his own projects.');
        const o = new ppro.OpenProjectOptions();
        try { o.setShowWarningDialog(false); o.setShowLocateFileDialog(false); o.setShowConvertProjectDialog(false); o.setAddToMRUList(false); } catch (e) { /* defaults */ }
        proj = await ppro.Project.open(a.path, o);
        r = { project: proj && proj.path };
      } else {
        guard();
        if (a.op === 'project') r = { project: proj.path, sequences: ((await proj.getSequences()) || []).map((s) => s.name) };
        else if (a.op === 'import') {
          const need = [];
          for (const p of a.paths || []) if (!(await findClipByPath(proj, p))) need.push(p);
          if (need.length && !(await proj.importFiles(need, true, await proj.getRootItem(), false))) throw new Error('Premiere would not import ' + need[0]);
          r = { imported: need };
        } else if (a.op === 'seq_from_media') {
          if (await findSequence(proj, a.name)) throw new Error(a.name + ' already exists');
          const m = await findClipByPath(proj, a.media);
          if (!m) throw new Error('Import ' + a.media + ' first');
          const s = await proj.createSequenceFromMedia(a.name, [m.clip], await proj.getRootItem());
          if (!s) throw new Error('Premiere would not make the sequence');
          r = await opInfo(proj, s);
        } else if (a.op === 'info') r = await opInfo(proj, await seqOf(a.seq));
        else if (a.op === 'save') r = { saved: !!(await proj.save()) };
        else {
          const seq = await seqOf(a.seq), editor = ppro.SequenceEditor.getEditor(seq);
          if (a.op === 'place') {
            const m = await findClipByPath(proj, a.media);
            if (!m) throw new Error('Import ' + a.media + ' first');
            await placeFromProject(proj, editor, seq, m.item, BigInt(a.at || '0'), a.v || 0, a.a || 0);
          } else if (a.op === 'place_sequence') {
            // a sequence placed in another as a nest, like GREEN_MASTER under a PiP
            const src = await seqOf(a.source);
            await placeFromProject(proj, editor, seq, await src.getProjectItem(), BigInt(a.at || '0'), a.v || 0, a.a || 0);
          } else if (a.op === 'remove') {
            const it = await opItem(seq, a);
            await removeItems(proj, seq, [it], 'Josh Cut: Tariq remove');
          } else if (a.op === 'remove_track') {
            const all = (await snapshot(seq, a.kind === 'a' ? { v: [], a: [a.track] } : { v: [a.track], a: [] }));
            if (all.length) await removeItems(proj, seq, all, 'Josh Cut: Tariq clear track');
          } else {
            const it = await opItem(seq, a);
            if (a.op === 'clone') transact(proj, 'Josh Cut: Tariq copy', (ca) => ca.addAction(editor.createCloneTrackItemAction(it.item, dt(BigInt(a.offset || '0')), a.v_off || 0, a.a_off || 0, true, false)));
            else if (a.op === 'move') transact(proj, 'Josh Cut: Tariq move', (ca) => ca.addAction(it.item.createMoveAction(dt(BigInt(a.delta)))));
            else if (a.op === 'set_end') transact(proj, 'Josh Cut: Tariq end', (ca) => ca.addAction(it.item.createSetEndAction(tt(BigInt(a.end)))));
            else if (a.op === 'set_in') transact(proj, 'Josh Cut: Tariq in point', (ca) => ca.addAction(it.item.createSetInPointAction(tt(BigInt(a.inp)))));
            else if (a.op === 'set_out') transact(proj, 'Josh Cut: Tariq out point', (ca) => ca.addAction(it.item.createSetOutPointAction(tt(BigInt(a.out)))));
            else if (a.op === 'add_effect') {
              const comp = await ppro.VideoFilterFactory.createComponent(a.effect);
              const chain = await it.item.getComponentChain();
              transact(proj, 'Josh Cut: Tariq effect', (ca) => ca.addAction(chain.createAppendComponentAction(comp)));
            } else if (a.op === 'set') {
              const p = await opParam(it, a);
              await setParam(proj, 'Josh Cut: Tariq ' + a.effect + ' ' + (a.param || a.param_index), p, opKeyframeValue(a));
            } else throw new Error('Unknown step ' + a.op);
          }
          r = a.report === false ? true : { video_tracks: await seq.getVideoTrackCount() };
        }
      }
      done.push({ n, op: a.op, ok: true, result: r });
    } catch (e) {
      done.push({ n, op: a.op, ok: false, error: String(e && e.message ? e.message : e) });
      if (!a.may_fail) return { ok: false, failed_at: n, steps: done };
    }
  }
  return { ok: true, steps: done };
}

async function tqOpenProject(args) {
  // only ever the test copy Josh OS made, or Tariq's own project. Josh's own project stays open as it was.
  if (!/[\\/]native-test[\\/]/i.test(args.path || '') && !TARIQ_PROJECT.test(args.path || '')) throw new Error('Only a Josh OS test copy or Tariq\'s own project can be opened from here.');
  const opts = new ppro.OpenProjectOptions();
  try { opts.setShowWarningDialog(false); opts.setShowLocateFileDialog(false); opts.setShowConvertProjectDialog(false); opts.setAddToMRUList(false); } catch (e) { /* defaults */ }
  const proj = await ppro.Project.open(args.path, opts);
  if (!proj) throw new Error('Premiere would not open the test copy');
  return { project: proj.path || proj.name, name: proj.name };
}

async function tqCloseProject(args) {
  const proj = await ppro.Project.getActiveProject();
  // after a save Premiere reports the path with a \\?\ long-path prefix
  const norm = (p) => String(p || '').replace(/^\\\\\?\\/, '').replace(/\//g, '\\').toLowerCase();
  if (!proj || norm(proj.path) !== norm(args.path)) throw new Error('The open project is not the test copy, so nothing was closed.');
  let opts;
  try { opts = new ppro.CloseProjectOptions(); if (opts.setPromptIfDirty) opts.setPromptIfDirty(false); if (opts.setShowCancelButton) opts.setShowCancelButton(false); } catch (e) { opts = undefined; }
  const ok = await proj.close(opts);
  return { closed: !!ok };
}

async function tqVerifyProject(args) {
  // after reopening: the sequences are there, the cut is still pieces of the master, and every clip's media is online
  const proj = await ppro.Project.getActiveProject();
  const seqs = ((await proj.getSequences()) || []).map((s) => s.name);
  const offline = [], paths = [];
  await walkProject(proj, (m) => { paths.push(m); return false; });
  for (const m of paths) { try { if (await m.clip.isOffline()) offline.push(m.path); } catch (e) { /* not media */ } }
  const out = { project: proj.path || proj.name, sequences: seqs, offline, media: paths.map((m) => m.path) };
  for (const name of args.expect || []) if (!seqs.includes(name)) (out.missing = out.missing || []).push(name);
  if (args.cut) {
    const cut = await findSequence(proj, args.cut);
    if (cut) {
      const v = (await snapshot(cut)).filter((x) => x.kind === 'v' && x.track === 0);
      const names = [];
      for (const i of v) names.push(await itemName(i.item));
      out.cut_pieces = v.length; out.cut_is_master_nests = names.every((n) => n === (args.master || 'GREEN_MASTER'));
    }
  }
  if (args.master) { try { out.keys = (await tqMasterRead({ master: args.master })).effects; } catch (e) { out.keys_error = e.message; } }
  return out;
}

async function tqPlaceLayers(args) {
  // Tariq's rendered animations on V5 and keyed camera copies on V4, on the named assembly sequence only.
  const proj = await ppro.Project.getActiveProject();
  const seq = await findSequence(proj, args.sequence);
  if (!seq) throw new Error('No sequence called ' + args.sequence);
  try { await proj.openSequence(seq); } catch (e) { /* placed anyway */ }
  const r = Object.assign({}, args.result, { nest: args.nest || 'GREEN_MASTER' });
  const strategy = r.layers.some((l) => l.kind === 'camera_copy') ? await strategyFor() : null;
  const note = r.layers.length ? await placeLayers(proj, seq, r, strategy) : '';
  const items = await snapshot(seq);
  const f = await frameTicks(seq);
  return { sequence: seq.name, note, v4: items.filter((i) => i.kind === 'v' && i.track === 3).length, v5: items.filter((i) => i.kind === 'v' && i.track === 4).length,
           report: timelineReport(items.filter((i) => i.kind === 'v' && i.track >= 3), f) };
}

// BEGIN GUARDED NATIVE IDENTITY: source-only, opt-in commands; legacy callers unchanged.
function guardedPath(path) {
  let value = String(path || '').split(String.fromCharCode(92)).join('/').toLowerCase();
  if (value.startsWith('//?/')) value = value.slice(4);
  const parts = value.split('/');
  if (!'abcdefghijklmnopqrstuvwxyz'.includes(value[0]) || value[1] !== ':' || value[2] !== '/' || parts.some(p => p === '.' || p === '..' || !p)) throw new Error('An absolute local project path is required');
  if (!value.endsWith('.prproj') || !(parts[parts.length - 2] === 'tariq' || (parts.length >= 4 && parts[parts.length - 3] === 'native-test'))) throw new Error('Only a Tariq project or isolated native test project is allowed');
  return value;
}
function guardedGuid(sequence) {
  let guid = '';
  try { guid = String(sequence.guid.toString()); } catch (e) { /* fail closed */ }
  if (!guid || guid === 'undefined' || guid === 'null') throw new Error('Stable sequence GUID unavailable');
  return guid;
}
async function guardedProject(expected) {
  const path = guardedPath(expected);
  const project = await ppro.Project.getActiveProject();
  if (!project || guardedPath(project.path) !== path) throw new Error('The active Premiere project differs from the requested project');
  return project;
}
async function guardedSequence(project, name, expectedGuid) {
  if (typeof name !== 'string' || !name || typeof expectedGuid !== 'string' || !expectedGuid) throw new Error('Exact sequence name and GUID are required');
  const matches = ((await project.getSequences()) || []).filter(s => s.name === name);
  if (matches.length !== 1 || guardedGuid(matches[0]) !== expectedGuid) throw new Error('Sequence identity changed or its name is ambiguous');
  return matches[0];
}
async function tqGuardedReadSequence(args) {
  const project = await guardedProject(args.expected_project);
  const sequence = await guardedSequence(project, args.sequence, args.expected_sequence_guid);
  const info = await opInfo(project, sequence);
  if (guardedPath(project.path) !== guardedPath(args.expected_project)) throw new Error('Project path changed during readback');
  return { project: project.path, sequence_guid: guardedGuid(sequence), info };
}
async function tqGuardedBuildCut(args) {
  if (!args.plan || !args.expected_master_state) throw new Error('Exact build plan and reviewed master state are required');
  const project = await guardedProject(args.expected_project);
  const master = await guardedSequence(project, args.plan.master, args.expected_master_guid);
  const state = await opInfo(project, master);
  if (JSON.stringify(state) !== JSON.stringify(args.expected_master_state)) throw new Error('The master changed after review');
  // Never run the automatic native probe from a guarded command: it uses active state.
  const saved = (await api('/probe')).probe;
  let version = ''; try { version = require('uxp').host.version; } catch (e) { /* fail closed */ }
  if (!version || !saved || !saved.ok || saved.premiere !== version || !saved.strategy || saved.strategy.recipe !== 'shrink-slide') throw new Error('A verified native editing strategy is required first');
  if (guardedPath(project.path) !== guardedPath(args.expected_project)) throw new Error('Project path changed before build');
  const result = await tqBuildCut(args, project, master, saved.strategy);
  const copies = ((await project.getSequences()) || []).filter(s => s.name === args.plan.sequence_name);
  if (copies.length !== 1) throw new Error('Built sequence identity is ambiguous; do not retry automatically');
  const sequence = copies[0], sequenceGuid = guardedGuid(sequence);
  const readback = await opInfo(project, sequence);
  if (guardedPath(project.path) !== guardedPath(args.expected_project)) throw new Error('Project path changed before save; do not retry automatically');
  const savedProject = await project.save();
  if (!savedProject) throw new Error('Built sequence was not confirmed saved; do not retry automatically');
  return { ...result, project: project.path, sequence_guid: sequenceGuid, readback, saved: true };
}
// END GUARDED NATIVE IDENTITY

// BEGIN NATIVE SOURCE TRANSCRIPT
// Only source microphone metadata is changed. No sequence, track, mask or cut action is used.
const nativeTranscriptJobs = new Map();
function nativeMediaPath(value) {
  const path = String(value || '').replace(/\\/g, '/').replace(/^\/\/\?\//, '').toLowerCase();
  if (!/^[a-z]:\//.test(path) || path.split('/').some(p => !p || p === '.' || p === '..')) throw new Error('An exact absolute microphone path is required');
  return path;
}
async function tqNativeTranscript(args) {
  if (args.action === 'capabilities') {
    const supported = !!(ppro.Transcript && typeof ppro.Transcript.transcribeClipProjectItem === 'function');
    return { version: 1, supported, reason: supported ? '' : 'This Premiere version does not expose native source transcription to Josh Cut Pro.' };
  }
  const key = String(args.request_id || '');
  if (!/^[a-zA-Z0-9-]{8,80}$/.test(key)) throw new Error('A stable native transcription request ID is required');
  const expected = guardedPath(args.expected_project), mic = nativeMediaPath(args.mic_path);
  const previous = nativeTranscriptJobs.get(key);
  if (previous) {
    if (previous.project !== expected || previous.mic !== mic) throw new Error('Native transcription request identity changed');
    return { ...previous };
  }
  if (args.action === 'status') return { state: 'missing', message: 'The native transcription request is no longer in this panel session. Check its saved outcome before requesting another transcription.' };
  if (args.action !== 'start') throw new Error('Unknown native transcription action');
  const project = await guardedProject(args.expected_project);
  if (!ppro.Transcript || typeof ppro.Transcript.transcribeClipProjectItem !== 'function') throw new Error('Native source transcription API is unavailable');
  const matches = [];
  await walkProject(project, m => { if (nativeMediaPath(m.path) === mic) matches.push(m.clip); return false; });
  if (matches.length !== 1) throw new Error('The selected microphone must match exactly one source clip in the requested project');
  const job = { state: 'running', request_id: key, project: expected, mic, saved: false };
  nativeTranscriptJobs.set(key, job);
  // Return promptly so CareerOS can poll progress, cancel its wait and avoid HTTP timeout retries.
  (async () => {
    try {
      await guardedProject(args.expected_project);
      const existing = typeof ppro.Transcript.hasTranscript === 'function' && await ppro.Transcript.hasTranscript(matches[0]);
      if (!existing && !(await ppro.Transcript.transcribeClipProjectItem(matches[0]))) throw new Error('Premiere did not confirm source microphone transcription');
      await guardedProject(args.expected_project);
      if (!(await project.save())) throw new Error('Premiere did not confirm the microphone transcript was saved');
      job.saved = true; job.state = 'done';
    } catch (error) {
      job.state = 'blocked'; job.message = String(error && error.message || error);
    }
  })();
  return { ...job };
}
// END NATIVE SOURCE TRANSCRIPT

const COMMANDS = {
  async tq_native_transcript(args) { return tqNativeTranscript(args || {}); },
  async tq_guarded_capabilities() { return { version: 1, exact_project: true, sequence_guid: true, commands: ['tq_guarded_read_sequence', 'tq_guarded_build_cut'] }; },
  async tq_guarded_read_sequence(args) { return tqGuardedReadSequence(args || {}); },
  async tq_guarded_build_cut(args) { return tqGuardedBuildCut(args || {}); },
  async tq_probe(args) { return tqProbe(args || {}); },
  async tq_master_read(args) { return tqMasterRead(args || {}); },
  async tq_master_set(args) { return tqMasterSet(args || {}); },
  async tq_export_frames(args) { return tqExportFrames(args || {}); },
  async tq_build_cut(args) { return tqBuildCut(args || {}); },
  async tq_assemble(args) { return tqAssemble(args || {}); },
  async tq_export(args) { return tqExport(args || {}); },
  async tq_save() { return tqSave(); },
  async tq_make_master(args) { return tqMakeMaster(args || {}); },
  async tq_import(args) { return tqImport(args || {}); },
  async tq_open_project(args) { return tqOpenProject(args || {}); },
  async tq_close_project(args) { return tqCloseProject(args || {}); },
  async tq_verify_project(args) { return tqVerifyProject(args || {}); },
  async tq_place_layers(args) { return tqPlaceLayers(args || {}); },
  async tq_ops(args) { return tqOps(args || {}); },
  async timeline() { return readTimeline(); },
  async cut(args) {
    const proj = await ppro.Project.getActiveProject();
    const seq = await proj.getActiveSequence();
    if (!seq) throw new Error('Open the sequence you want to cut.');
    const strategy = await strategyFor();
    const done = await cutInPlace(proj, seq, args, strategy);
    done.timeline = await readTimeline();
    return done;
  },
  async layers(args) {
    const proj = await ppro.Project.getActiveProject();
    const seq = await proj.getActiveSequence();
    if (!seq) throw new Error('Open the sequence for the animations.');
    await liftLayers(proj, seq);
    const layers = args.result.layers || [];
    // copying the camera from V1 uses the same trims as a cut, so it needs the Premiere check's findings
    const strategy = layers.some((l) => l.kind === 'camera_copy') ? await strategyFor() : null;
    const note = layers.length ? await placeLayers(proj, seq, args.result, strategy) : '';
    return { ok: true, note };
  },
  async probe() {
    const report = await probe();
    await api('/probe', report);
    return report;
  },
  async import(args) {
    const proj = await ppro.Project.getActiveProject();
    await importSequence(proj, args.result);
    return { ok: true };
  },
};

async function info() {
  try {
    const proj = await ppro.Project.getActiveProject();
    const seq = proj ? await proj.getActiveSequence() : null;
    return { project: proj ? proj.name : '', sequence: seq ? seq.name : '' };
  } catch (e) { return {}; }
}

async function loop() {
  while (true) {
    let call = null;
    try {
      const i = await info();
      $('seq').textContent = i.sequence || 'No sequence open';
      const r = await api('/bridge/poll?info=' + encodeURIComponent(JSON.stringify(i)));
      setLink(true, 'Linked');
      call = r.call;
    } catch (e) {
      setLink(false, 'Helper not running');
      await wait(2500);
      continue;
    }
    if (!call) continue;
    busy = true;
    status({ cut: 'Cutting the timeline\u2026', layers: 'Placing the animations\u2026', probe: 'Checking Premiere\u2026', import: 'Bringing in the sequence\u2026' }[call.cmd] || 'Reading the timeline\u2026');
    try {
      if (call.expires_at_ms != null && Date.now() >= call.expires_at_ms) throw new Error('Bridge command expired before execution; nothing was run');
      const result = await COMMANDS[call.cmd](call.args || {});
      await api('/bridge/result', { id: call.id, result });
      status(call.cmd === 'cut' ? (result && result.note ? result.note : 'Cut done') : '');
    } catch (e) {
      await api('/bridge/result', { id: call.id, error: e && e.message ? e.message : String(e) });
      status('Last step failed: ' + (e && e.message ? e.message : e));
    }
    busy = false;
  }
}

$('open').addEventListener('click', async () => {
  try {
    await api('/open-app', {});
  } catch (e) {
    try {
      await require('uxp').shell.openPath('E:\\Videos\\DaJoshiCut\\Start Josh Cut Pro.bat');
    } catch (e2) {
      status('Double-click "Start Josh Cut Pro" in E:\\Videos\\DaJoshiCut');
    }
  }
});

loop();
