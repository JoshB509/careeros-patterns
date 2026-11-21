// Extends ppro-stub.js for Tariq's native edit commands (tq_*). Load it after ppro-stub.js.
// It adds a GREEN_MASTER sequence like Data Storytelling's: background on V1, a shadow copy of the camera on V2
// (rough Ultra Key plus Drop Shadow), the keyed presenter on V3, no audio. Sequences can be placed in other
// sequences as nests, audio files land on audio tracks, and frame export writes a fingerprint of what the
// frame would show, worked out from the master's key settings. That makes the propagation check meaningful
// for the code path, but it is a MOCK: only real Premiere proves a nest really updates.
(function () {
  const TPS = 254016000000;
  const tick = (s) => ({ seconds: s, ticks: String(Math.round(s * TPS)) });
  const secOf = (t) => Number(BigInt(t.ticks)) / TPS;
  const ppro = window.require('premierepro');
  const proj = null;
  const BG = 'E:\\Videos\\DaJoshiCut\\tests\\office-bg.png';
  const cam = window.CLIPS[0], mic = window.CLIPS[1];
  const bg = { path: BG, name: 'office-bg.png', id: 'bg', _in: tick(0), _out: tick(3600), getMediaFilePath: async () => BG, getId: () => 'bg',
    createSetInOutPointsAction: () => ({ run: () => {} }), createClearInOutPointsAction: () => ({ run: () => {} }) };
  window.CLIPS.push(bg);

  function param(name, value) {
    const p = { displayName: name, value, createKeyframe: (v) => ({ v }),
      createSetValueAction: (kf) => ({ run: () => { p.value = kf.v; window.OPS.push('key ' + name + ' ' + kf.v); } }),
      getValueAtTime: async () => ({ value: p.value }) };
    return p;
  }
  function comp(match, params) { return { match, params, getMatchName: async () => match, getDisplayName: async () => match.replace('AE.ADBE ', ''), getParamCount: () => params.length, getParam: (i) => params[i] }; }
  const presenterKey = comp('AE.ADBE Ultra Key', [['Transparency', 45], ['Highlight', 52.04545], ['Shadow', 50.22727], ['Tolerance', 65.45454], ['Pedestal', 100], ['Choke', 7.72727], ['Soften', 0]].map(([n, v]) => param(n, v)));
  const shadowKey = comp('AE.ADBE Ultra Key', [['Transparency', 45], ['Highlight', 20], ['Choke', 0]].map(([n, v]) => param(n, v)));
  const motion = (x, y, s) => comp('AE.ADBE Motion', [param('Position', [x, y]), param('Scale', s)]);
  const shadowFx = comp('AE.ADBE Drop Shadow', [param('Opacity', 52.7), param('Direction', 135), param('Distance', 5), param('Softness', 121.1111), param('Shadow Only', true)]);
  window.MASTER_KEYS = { presenterKey, shadowKey };

  window.ACTIVE().createCloneAction().run();  // gives us a sequence object to turn into the master
  const master = window.SEQS[window.SEQS.length - 1];
  const end = window.STUB_LENGTH || 280;
  const mk = (clip, track, chain) => { const it = window.__mkItem(clip, 'v', track, 0, end, 0, chain); return it; };
  if (window.STUB_SOURCE_CUT) {
    // Josh's real Exec questions sequence: AutoCut has already cut it into pieces with the gaps closed. Background still
    // on V1, keyed camera on V2, camera sound on A1, and no spare track.
    master.name = 'Keyed edit'; master.pi.name = 'Keyed edit'; master.vTracks = 2; master.aTracks = 1;
    const cuts = [[0, 40], [44, 120], [125, 300], [302, end]];
    let at = 0; master.items = [];
    for (const [a, b] of cuts) {
      master.items.push(window.__mkItem(bg, 'v', 0, at, at + b - a, 0));
      master.items.push(window.__mkItem(cam, 'v', 1, at, at + b - a, a, { comps: [motion(1770, 1141, 115), comp('AE.ADBE Ultra Key', presenterKey.params.map((p) => param(p.displayName, p.value)))] }));
      master.items.push(window.__mkItem(cam, 'a', 0, at, at + b - a, a));
      at += b - a;
    }
  } else if (window.STUB_SOURCE_ONLY) {
    // Josh's own keyed sequence: background, keyed presenter, an empty track above, and his mic on A1
    master.name = 'Keyed edit'; master.pi.name = 'Keyed edit'; master.vTracks = 3; master.aTracks = 2;
    master.items = [mk(bg, 0), mk(cam, 1, { comps: [motion(1770, 1141, 115), presenterKey] }), window.__mkItem(mic, 'a', 0, 0, end, 0)];
  } else {
    const nm = window.STUB_LOOK_NAME || 'GREEN_MASTER';  // a reference project Josh keyed by hand, for Tariq's look
    master.name = nm; master.pi.name = nm; master.vTracks = 3; master.aTracks = 2;
    master.items = [mk(bg, 0), mk(cam, 1, { comps: [motion(826, 1376, 100.89), shadowKey, shadowFx] }), mk(cam, 2, { comps: [motion(1770, 1141, 115), presenterKey] })];
  }
  master.pi._in = tick(0); master.pi._out = tick(end);
  if (!cam._in) { cam._in = tick(0); cam._out = tick(end + 30); }  // placing the whole recording uses its full length
  // a clone of a sequence is a full sequence; give every clone a placeable project item with its length
  const seqEnd = (q) => Math.max(0, ...q.items.map((i) => i._end));
  setInterval(() => { for (const q of window.SEQS) if (q.pi && !q.pi._out) { q.pi._in = tick(0); q.pi._out = tick(seqEnd(q)); } }, 50);
  window.MASTER_OF = () => window.SEQS.find((q) => q.name === 'GREEN_MASTER');

  // sequences and audio clips placed by overwrite go where Premiere would put them
  // Like Premiere, a copied clip keeps its own copy of every effect, independent of the original
  const copyChain = (ch) => ({ comps: ch.comps.map((c) => comp(c.match, c.params.map((p) => param(p.displayName, Array.isArray(p.value) ? [...p.value] : p.value)))) });
  window.__copyChain = copyChain;
  const baseEditor = ppro.SequenceEditor.getEditor;
  ppro.SequenceEditor.getEditor = (s) => {
    const e = baseEditor(s);
    e.createCloneTrackItemAction = (it, off, vOff, aOff) => ({ run: () => {
      const d = secOf(off);
      if (it.kind === 'v' && it.track + vOff >= s.vTracks) throw new Error('Invalid parameter.');  // no track there
      s.items.push(window.__mkItem(it.clip, it.kind, it.track + (it.kind === 'v' ? vOff : aOff), it._start + d, it._end + d, it._in, it._chain ? copyChain(it._chain) : undefined));
    } });
    e.createOverwriteItemAction = (item, t, v, a) => ({ run: () => {
      const audio = /\.(wav|aif|aiff|mp3)$/i.test(item.path || '');
      const kind = audio ? 'a' : 'v', track = audio ? a : v;
      if (!item._in) { item._in = tick(0); item._out = tick(/\.(png|jpe?g)$/i.test(item.path || '') ? 5 : end + 30); }  // a still gets Premiere's default 5s
      const len = secOf(item._out) - secOf(item._in), st = t.seconds;
      s.items = s.items.filter((i) => i.kind !== kind || i.track !== track || i._end <= st + 1e-6 || i._start >= st + len - 1e-6);
      s.items.push(window.__mkItem(item, kind, track, st, st + len, secOf(item._in)));
      window.OPS.push('overwrite ' + kind + (track + 1) + ' ' + (item.name || ''));
    } });
    return e;
  };
  // what a frame shows: for a nest of the master, the master's presenter key settings now
  ppro.Exporter = { exportSequenceFrame: async (seq, time, name, dir) => {
    const t = time.seconds, it = seq.items.find((i) => i.kind === 'v' && i._start <= t && t < i._end);
    const m = window.MASTER_OF();
    const pres = m && m.items.filter((i) => i.kind === 'v').sort((a, b) => b.track - a.track).find((i) => i._chain && i._chain.comps.some((c) => /Ultra/.test(c.match)) && !i._chain.comps.some((c) => /Shadow/.test(c.match)));
    const keyed = it && m && it.clip === m.pi && pres ? JSON.stringify(pres._chain.comps.find((c) => /Ultra/.test(c.match)).params.map((p) => p.value)) : 'not the master';
    (window.FRAMES = window.FRAMES || {})[dir + '/' + name] = { at: t, source: it ? (it.clip.name || it.clip.path) : null, src_time: it ? it._in + (t - it._start) : null, keyed };
    return true;
  } };
  ppro.VideoFilterFactory.createComponent = async (m) => comp(m, /Drop Shadow/.test(m)
    ? [param('Opacity', 50), param('Direction', 135), param('Distance', 10), param('Softness', 20), param('Shadow Only', false)]
    : /Ultra Key/.test(m) ? ['Transparency', 'Highlight', 'Shadow', 'Tolerance', 'Pedestal', 'Choke', 'Soften'].map((n) => param(n, 0))
      : [param('Amount', 0)]);
  ppro.OpenProjectOptions = function () { const o = this; ['setShowWarningDialog', 'setShowLocateFileDialog', 'setShowConvertProjectDialog', 'setAddToMRUList'].forEach((k) => { o[k] = () => o; }); };
  ppro.CloseProjectOptions = function () {};
  for (const c of window.CLIPS) c.isOffline = async () => false;
  ppro.Project.open = async (path) => { const p = await ppro.Project.getActiveProject(); p.path = path; window.OPS.push('open ' + path); return p; };
  ppro.EncoderManager = { getManager: () => ({ isAMEInstalled: true, exportSequence: async (seq, type, out) => { window.OPS.push('export ' + seq.name + ' ' + out); return true; } }) };
  ppro.Constants.ExportType = { IMMEDIATELY: 0, QUEUE_TO_AME: 1 };
  // Tariq's own project, built from the raw files with tq_ops. A new project here keeps the stub's sequences,
  // which real Premiere would not, so tests look sequences up by name.
  ppro.Color = function (r, g, b, a) { this.red = r; this.green = g; this.blue = b; this.alpha = a; };
  ppro.Project.createProject = async (path) => { const p = await ppro.Project.getActiveProject(); p.path = path; window.OPS.push('create project ' + path); return p; };
  ppro.Project.getActiveProject().then((p) => {
    p.createSequenceFromMedia = async (name, clips) => {
      window.ACTIVE().createCloneAction().run();
      const s = window.SEQS[window.SEQS.length - 1];
      const c = clips[0], len = secOf(c._out || tick(end + 30)) - secOf(c._in || tick(0));
      s.name = name; s.pi.name = name; s.vTracks = window.STUB_FROM_MEDIA_TRACKS || 3; s.aTracks = 1;
      s.items = [window.__mkItem(c, 'v', 0, 0, len, 0), window.__mkItem(c, 'a', 0, 0, len, 0)];
      window.OPS.push('sequence from media ' + name);
      return s;
    };
  });
  ppro.Project.getActiveProject().then((p) => { p.path = 'E:\\test\\Tariq test copy.prproj'; p.save = async () => { window.OPS.push('save'); return true; };
    p.close = async () => true; });
})();
