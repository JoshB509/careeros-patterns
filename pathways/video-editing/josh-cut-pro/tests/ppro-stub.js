// A fake Premiere UXP API so panel/preview.html runs in a normal browser.
// It models Josh's usual setup: the camera clip on V1 with its own sound deleted, and the mic WAV on A1,
// started 2 seconds later so it lines up. The trim actions behave the way the Premiere check found on Josh's
// Premiere 25.6: anything reaching before the media start is refused.
// Set window.STUB_VIDEO / window.STUB_MIC before this loads to use other files, and window.JOSH_HELPER for a test helper port.
(function () {
  const TPS = 254016000000;
  const tick = (s) => ({ seconds: s, ticks: String(Math.round(s * TPS)) });
  const secOf = (t) => Number(BigInt(t.ticks)) / TPS;
  window.OPS = [];
  const VIDEO = window.STUB_VIDEO || 'E:\\Videos\\DaJoshiCut\\tests\\sample-5min.mp4';
  const MIC = window.STUB_MIC || 'E:\\Videos\\DaJoshiCut\\tests\\sample-5min-mic.wav';
  let ids = 0;

  function mkClip(path) {
    const c = { path, type: 1, name: path.split(/[\\/]/).pop(), id: 'clip' + (++ids), _in: null, _out: null,
      getMediaFilePath: async () => path, getId: () => c.id,
      createSetInOutPointsAction: (a, b) => ({ run: () => { c._in = a; c._out = b; } }), createClearInOutPointsAction: () => ({ run: () => {} }) };
    return c;
  }
  const vClip = mkClip(VIDEO), mClip = mkClip(MIC);
  window.CLIPS = [vClip, mClip];

  function PointF(x, y) { this.x = x; this.y = y; }
  function mkParam(name, value) {
    const p = { displayName: name, value,
      createKeyframe: (v) => ({ v }),
      createSetValueAction: (kf) => ({ run: () => { p.value = kf.v instanceof PointF ? [kf.v.x, kf.v.y] : kf.v; window.OPS.push('set ' + name + ' ' + JSON.stringify(p.value)); } }),
      getValueAtTime: async () => ({ value: p.value }) };
    return p;
  }
  function mkComponent(match, params) {
    return { match, params, getMatchName: async () => match, getParamCount: () => params.length, getParam: (i) => params[i] };
  }

  function mkItem(clip, kind, track, start, end, inp, keepChain) {
    const chain = keepChain || { comps: [mkComponent('AE.ADBE Opacity', [mkParam('Opacity', 100)]),
                            mkComponent('AE.ADBE Motion', [mkParam('Position', [0.5, 0.5]), mkParam('Scale', 100)])] };
    chain.getComponentCount = () => chain.comps.length;
    chain.getComponentAtIndex = (i) => chain.comps[i];
    chain.createAppendComponentAction = (c) => ({ run: () => { chain.comps.push(c); window.OPS.push('append ' + c.match); } });
    const it = { clip, kind, track, _start: start, _end: end, _in: inp, _chain: chain,
      getStartTime: async () => tick(it._start), getEndTime: async () => tick(it._end), getInPoint: async () => tick(it._in),
      getOutPoint: async () => tick(it._in + it._end - it._start), getProjectItem: async () => clip, getComponentChain: async () => chain,
      // Like Premiere 25.6: nothing may reach before the start of the media, and setting the in point trims the head
      createSetStartAction: (t) => ({ run: () => { if (secOf(t) < it._start - it._in - 1e-6) throw new Error('Invalid parameter.'); it._in += secOf(t) - it._start; it._start = secOf(t); } }),
      createSetEndAction: (t) => ({ run: () => { it._end = secOf(t); } }),
      createSetInPointAction: (t) => ({ run: () => { if (secOf(t) < -1e-6) throw new Error('Invalid parameter.'); it._start += secOf(t) - it._in; it._in = secOf(t); } }),
      createSetOutPointAction: (t) => ({ run: () => { it._end = it._start + (secOf(t) - it._in); } }),
      createMoveAction: (t) => ({ run: () => { const d = secOf(t); it._start += d; it._end += d; } }) };
    // Like Premiere, a clip object goes stale once any edit has run, and using it again fails
    for (const k of Object.keys(it)) {
      if (typeof it[k] !== 'function') continue;
      const fn = it[k];
      it[k] = (...a) => { if (it.dead) throw new Error('Script action failed to execute.'); return fn(...a); };
    }
    return it;
  }
  window.__mkItem = mkItem;  // used by tq-stub-ext.js
  function refresh() {
    for (const q of window.SEQS) q.items = q.items.map((i) => { i.dead = true; return mkItem(i.clip, i.kind, i.track, i._start, i._end, i._in, i._chain); });
  }

  function mkBin(name) {
    const b = { name, kids: [], getItems: async () => b.kids,
      createBinAction: (n) => ({ run: () => { b.kids.push(mkBin(n)); } }),
      createMoveItemAction: (item, to) => ({ run: () => { for (const f of allBins()) f.kids = f.kids.filter((k) => k !== item); to.kids.push(item); item.parent = to; } }),
      createRemoveItemAction: (item) => ({ run: () => {
        for (const f of allBins()) f.kids = f.kids.filter((k) => k !== item);
        window.SEQS = window.SEQS.filter((q) => q.pi !== item); window.OPS.push('remove ' + item.name); } }) };
    return b;
  }
  const root = mkBin('root');
  function allBins() { const out = [], st = [root]; while (st.length) { const b = st.pop(); out.push(b); b.kids.forEach((k) => k.kids && st.push(k)); } return out; }

  function mkSeq(name, vTracks, aTracks) {
    const s = { name, items: [], vTracks, aTracks, guid: { id: 'seq' + (++ids), toString() { return this.id; } },
      getVideoTrackCount: async () => s.vTracks, getAudioTrackCount: async () => s.aTracks,
      getVideoTrack: async (t) => ({ getTrackItems: () => s.items.filter((i) => i.kind === 'v' && i.track === t).sort((a, b) => a._start - b._start) }),
      getAudioTrack: async (t) => ({ getTrackItems: () => s.items.filter((i) => i.kind === 'a' && i.track === t).sort((a, b) => a._start - b._start) }),
      getFrameSize: async () => ({ width: (window.STUB_FRAME || [1920, 1080])[0], height: (window.STUB_FRAME || [1920, 1080])[1] }),
      getTimebase: async () => String(window.STUB_TIMEBASE || TPS / 30), getEndTime: async () => tick(Math.max(0, ...s.items.map((i) => i._end))),
      createCloneAction: () => ({ run: () => {
        const c = mkSeq(s.name + ' Copy', s.vTracks, s.aTracks);
        c.items = s.items.map((i) => mkItem(i.clip, i.kind, i.track, i._start, i._end, i._in, window.__copyChain && i._chain ? window.__copyChain(i._chain) : undefined));
        window.SEQS.push(c); root.kids.push(c.pi); window.OPS.push('clone sequence ' + s.name);
      } }) };
    s.pi = { name, getId: () => 'pi-' + s.guid.id, createSetNameAction: (n) => ({ run: () => { s.name = n; s.pi.name = n; window.OPS.push('rename ' + n); } }),
             getParentBin: () => s.pi.parent || root };
    s.getProjectItem = async () => s.pi;
    return s;
  }

  const original = mkSeq('Sequence 01', 3, 2);
  if (window.STUB_ITEMS) {
    // a real timeline from a cut log: [{ track: 'V1' or 'A1', start, end, in }]
    for (const c of window.STUB_ITEMS) original.items.push(mkItem(c.track[0] === 'V' ? vClip : mClip, c.track[0] === 'V' ? 'v' : 'a', Number(c.track.slice(1)) - 1, c.start, c.end, c.in));
  } else {
    original.items.push(mkItem(vClip, 'v', 0, 0, 280, 0));
    original.items.push(mkItem(mClip, 'a', 0, 2, 280, 0));
  }
  window.OVERLAPS = [];
  function overlaps(label) {
    // Premiere overwrites whatever a clip lands on, so any overlap mid-cut is a bug
    for (const q of window.SEQS) {
      const groups = {};
      q.items.forEach((i) => (groups[i.kind + i.track] = groups[i.kind + i.track] || []).push(i));
      for (const k of Object.keys(groups)) {
        const l = groups[k].sort((a, b) => a._start - b._start);
        for (let n = 1; n < l.length; n++) if (l[n]._start < l[n - 1]._end - 1e-4) window.OVERLAPS.push({ seq: q.name, label, track: k, at: l[n]._start, by: l[n - 1]._end - l[n]._start, prev: [l[n - 1]._start, l[n - 1]._end, l[n - 1]._in], cur: [l[n]._start, l[n]._end, l[n]._in] });
      }
    }
  }
  root.kids.push(vClip, mClip, original.pi);
  window.SEQS = [original];
  let active = original;
  window.ACTIVE = () => active;

  const proj = { name: 'Stub project', getActiveSequence: async () => active, getRootItem: async () => root, getSequences: async () => window.SEQS,
    importFiles: async (paths, ui, bin) => { paths.forEach((p) => { const c = mkClip(p); window.CLIPS.push(c); (bin || root).kids.push(c); }); window.OPS.push('import ' + paths.length); return true; },
    openSequence: async (s) => { active = s; window.OPS.push('open ' + s.name); return true; },
    lockedAccess: (f) => f(), executeTransaction: (cb, label) => { cb({ addAction: (a) => a.run && a.run() }); overlaps(label); refresh(); return true; } };
  const length = (clip) => secOf(clip._out) - secOf(clip._in);
  const ppro = { Project: { getActiveProject: async () => proj },
    ClipProjectItem: { cast: (x) => (x && x.getMediaFilePath ? x : null) }, FolderItem: { cast: (x) => x },
    Constants: { TrackItemType: { CLIP: 1 }, MediaType: { ANY: 0, VIDEO: 1, AUDIO: 2 } },
    TickTime: { createWithTicks: (t) => tick(Number(BigInt(t)) / TPS) },
    PointF,
    VideoFilterFactory: { getMatchNames: async () => ['AE.ADBE Mosaic', 'AE.ADBE Crop'],
      createComponent: async (m) => mkComponent(m, ['Left', 'Top', 'Right', 'Bottom', 'Edge Feather'].map((n) => mkParam(n, 0))) },
    TrackItemSelection: { createEmptySelection: (cb) => { const sel = { items: [], addItem(i) { this.items.push(i); } }; cb(sel); window.LASTSEL = sel; return true; } },
    SequenceEditor: { getEditor: (s) => ({
      createRemoveItemsAction: (sel) => ({ run: () => { s.items = s.items.filter((i) => !sel.items.includes(i)); } }),
      createCloneTrackItemAction: (it, off, vOff, aOff) => ({ run: () => {
        const d = secOf(off); s.items.push(mkItem(it.clip, it.kind, it.track + (it.kind === 'v' ? vOff : aOff), it._start + d, it._end + d, it._in)); } }),
      createInsertProjectItemAction: (clip, t, v) => ({ run: () => { if (v >= s.vTracks) s.vTracks = v + 1; s.items.push(mkItem(clip, 'v', v, t.seconds, t.seconds + length(clip), secOf(clip._in))); window.OPS.push('insert V' + (v + 1)); } }),
      createOverwriteItemAction: (clip, t, v) => ({ run: () => {
        if (v >= s.vTracks) throw new Error('no track V' + (v + 1));
        const a = t.seconds, b = a + length(clip);
        s.items = s.items.filter((i) => i.kind !== 'v' || i.track !== v || i._end <= a + 1e-6 || i._start >= b - 1e-6);
        s.items.push(mkItem(clip, 'v', v, a, b, secOf(clip._in)));
      } }) }) } };
  window.require = (name) => (name === 'uxp' ? { host: { version: '26.0-stub' }, shell: { openPath: async () => {} } } : ppro);
})();
