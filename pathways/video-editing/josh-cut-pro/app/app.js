// Josh Cut Pro app window. Talks to the helper on this PC; anything that touches
// the Premiere timeline goes through the helper's bridge to the Premiere panel.
const $ = (id) => document.getElementById(id);

const S = {
  screen: 'home',
  helper: { up: null, key: false, version: '' },
  premiere: { connected: false, info: {} },
  src: null, srcError: null,
  project: null,
  running: null,
  silence: null,
  preview: null,
  wave: null,
  flubs: null, sel: null,
  pip: null, pipV: 0,
  redoOpen: {},
  notes: '',
};

// ------------------------------------------------------------ utilities

const esc = (t) => String(t == null ? '' : t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
function fmt(sec) {
  if (sec == null || isNaN(sec)) return '–';
  sec = Math.round(sec);
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return (h ? h + ':' + String(m).padStart(2, '0') : m) + ':' + String(s).padStart(2, '0');
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(path, body) {
  const opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
  const res = await fetch(path, opt);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Helper error ' + res.status);
  return data;
}
const bridge = async (cmd, args) => (await api('/bridge/call', { cmd, args: args || {} })).result;

function pickedTrack() {
  // the audio track Josh picked to listen to, or the mic track the panel found
  const list = (S.src && S.src.audio_tracks) || [];
  const want = S.track != null ? S.track : S.src && S.src.mic_track;
  return list.find((a) => a.index === want) || list[0] || null;
}

function req(extra) {
  const s = S.src, t = pickedTrack();
  return Object.assign({ video: s.video, audio: t && !t.same ? t.path : null, audio_offset: t && !t.same ? t.offset : null,
                         range: [s.in, s.out], name: s.sequenceName, spans: s.spans, frame: s.frame }, extra || {});
}

// ------------------------------------------------------------ icons and tile art

const ICON = {
  clean: '<svg viewBox="0 0 24 24"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4L8.1 15.9M14.5 14.5L20 20M8.1 8.1L12 12"/></svg>',
  flubs: '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h9M4 17h12"/><path d="M15 10l5 5M20 10l-5 5"/></svg>',
  anim: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M14 9h4v6h-4z"/><path d="M6 10h5M6 14h4"/></svg>',
  style: '<svg viewBox="0 0 24 24"><circle cx="13.5" cy="6.5" r="1.5"/><circle cx="17.5" cy="10.5" r="1.5"/><circle cx="8.5" cy="7.5" r="1.5"/><circle cx="6.5" cy="12.5" r="1.5"/><path d="M12 2a10 10 0 0 0 0 20c1.1 0 2-.9 2-2 0-.5-.2-1-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1.1.9-2 2-2h2.4A5.6 5.6 0 0 0 22 9.8C22 5.5 17.5 2 12 2z"/></svg>',
};

function art(kind) {
  const g = '#F5C21B', w = '#e9e4d8', r = '#E2584C';
  if (kind === 'clean') {
    let bars = '';
    for (let i = 0; i < 46; i++) {
      const x = 12 + i * 6.2, h = 10 + Math.abs(Math.sin(i * 1.7) * 26 + Math.cos(i * .6) * 12);
      const cut = (i > 13 && i < 18) || (i > 30 && i < 34);
      bars += '<rect x="' + x.toFixed(1) + '" y="' + (48 - h / 2).toFixed(1) + '" width="3.4" height="' + h.toFixed(1) + '" rx="1.7" fill="' + (cut ? r : w) + '" opacity="' + (cut ? .55 : .85) + '"/>';
    }
    return '<svg viewBox="0 0 300 96" preserveAspectRatio="xMidYMid slice"><rect x="96" y="6" width="27" height="84" fill="' + r + '" opacity=".10"/><rect x="198" y="6" width="21" height="84" fill="' + r + '" opacity=".10"/>' + bars +
      '<line x1="0" y1="62" x2="300" y2="62" stroke="' + g + '" stroke-width="1.4" stroke-dasharray="4 4" opacity=".8"/></svg>';
  }
  if (kind === 'flubs') {
    const line = (y, w1, cut) => '<rect x="22" y="' + y + '" width="' + w1 + '" height="7" rx="3.5" fill="' + (cut ? r : w) + '" opacity="' + (cut ? .7 : .35) + '"/>' +
      (cut ? '<line x1="18" y1="' + (y + 3.5) + '" x2="' + (26 + w1) + '" y2="' + (y + 3.5) + '" stroke="' + r + '" stroke-width="2"/>' : '');
    return '<svg viewBox="0 0 300 96" preserveAspectRatio="xMidYMid slice">' + line(18, 210) + line(34, 120, true) + line(50, 236) +
      '<rect x="18" y="62" width="150" height="15" rx="4" fill="' + g + '" opacity=".22"/>' + line(66, 140) + '</svg>';
  }
  if (kind === 'anim') {
    return '<svg viewBox="0 0 300 96" preserveAspectRatio="xMidYMid slice"><rect x="26" y="14" width="150" height="68" rx="8" fill="#fff" opacity=".92"/>' +
      '<rect x="38" y="28" width="90" height="10" rx="3" fill="#FDF1C7"/><rect x="38" y="46" width="70" height="10" rx="3" fill="#F3F2EF"/>' +
      '<circle cx="46" cy="69" r="5" fill="' + g + '"/><rect x="56" y="65" width="60" height="8" rx="3" fill="#ECEAE5"/>' +
      '<rect x="196" y="10" width="78" height="78" rx="4" fill="#3a3c44" stroke="' + g + '" stroke-width="3"/>' +
      '<circle cx="235" cy="40" r="11" fill="#8d8a83"/><path d="M212 88c4-18 14-24 23-24s19 6 23 24z" fill="#8d8a83"/></svg>';
  }
  if (kind === 'broll') {
    let f = '';
    for (let i = 0; i < 4; i++) f += '<rect x="' + (20 + i * 68) + '" y="22" width="58" height="52" rx="4" fill="' + w + '" opacity="' + (.16 + i * .08) + '"/>';
    return '<svg viewBox="0 0 300 96" preserveAspectRatio="xMidYMid slice"><rect x="10" y="14" width="280" height="68" rx="6" fill="none" stroke="' + w + '" stroke-opacity=".2" stroke-dasharray="6 6"/>' + f + '</svg>';
  }
  if (kind === 'zoom') return '<svg viewBox="0 0 120 56"><rect x="20" y="8" width="80" height="40" rx="4" stroke="' + w + '" stroke-opacity=".35" fill="none"/><rect x="34" y="15" width="52" height="26" rx="3" stroke="' + g + '" fill="none" stroke-width="1.6"/></svg>';
  if (kind === 'key') return '<svg viewBox="0 0 120 56"><rect x="40" y="6" width="40" height="44" rx="3" fill="#3a3c44" stroke="' + g + '" stroke-width="2"/><circle cx="60" cy="22" r="7" fill="#8d8a83"/><path d="M46 50c2-10 8-14 14-14s12 4 14 14z" fill="#8d8a83"/></svg>';
  if (kind === 'style') return '<svg viewBox="0 0 120 56"><circle cx="38" cy="28" r="10" fill="' + g + '"/><circle cx="60" cy="28" r="10" fill="' + w + '" opacity=".8"/><circle cx="82" cy="28" r="10" fill="#15171C" stroke="' + w + '" stroke-opacity=".4"/></svg>';
  return '';
}

// ------------------------------------------------------------ connection and source

async function checkHelper() {
  try {
    const h = await api('/health');
    S.helper = { up: h.engine_ok, key: h.has_key, version: h.version, error: h.engine_error };
  } catch (e) { S.helper = { up: false }; }
  try {
    const b = await api('/bridge/status');
    const before = S.premiere.connected ? (S.premiere.info.project + '/' + S.premiere.info.sequence) : null;
    S.premiere = b;
    const now = b.connected ? (b.info.project + '/' + b.info.sequence) : null;
    paintConn();
    if (now !== before && !S.running) {
      S.flubs = null; S.preview = null; S.wave = null; S.sel = null;
      await refreshSource();
      if (S.screen === 'clean') loadClean();
    }
  } catch (e) { S.premiere = { connected: false, info: {} }; paintConn(); }
}

function paintConn() {
  const c = $('conn'), t = $('connText');
  if (!S.helper.up) { c.className = 'conn'; t.textContent = 'Helper stopped'; return; }
  if (!S.premiere.connected) { c.className = 'conn'; t.textContent = 'Premiere not connected'; return; }
  c.className = 'conn on';
  t.textContent = S.premiere.info.sequence ? S.premiere.info.sequence : 'Premiere connected';
}

async function refreshSource() {
  if (!S.premiere.connected) { S.src = null; S.srcError = null; S.project = null; render(); return; }
  try {
    S.src = await bridge('timeline');
    S.srcError = null;
    S.project = await api('/project?video=' + encodeURIComponent(S.src.video));
    S.silence = Object.assign({}, S.project.silence_settings);
    S.pip = S.project.pip;
    S.anim = S.project.anim;
  } catch (e) { S.src = null; S.project = null; S.srcError = e.message; }
  render();
}

// ------------------------------------------------------------ jobs and progress

let tick = null;
function toast(msg, opts) {
  opts = opts || {};
  $('toast').className = opts.error ? 'err' : '';
  $('toastMsg').textContent = msg + (opts.busy || opts.error ? '' : costNote());
  $('ring').className = opts.busy ? 'ring' : 'hidden';
  $('toastCancel').className = opts.busy ? 'textBtn' : 'hidden';
  $('toastClose').className = opts.busy ? 'hidden' : 'textBtn';
  if (!opts.busy) $('toastTime').textContent = '';
  clearTimeout(toast.fade);
  if (!opts.busy && !opts.error) toast.fade = setTimeout(hideToast, 8000);
}
function costNote() {
  const d = S.lastCost; S.lastCost = null;
  return d == null ? '' : ' Claude cost about ' + money(d) + '.';
}
function hideToast() { $('toast').className = 'hidden'; }

async function job(stage, body) {
  const started = await api('/run', Object.assign({ stage }, body));
  S.running = { job: started.job, stage, t0: Date.now() };
  render();
  toast('Starting\u2026', { busy: true });
  tick = setInterval(() => { $('toastTime').textContent = fmt((Date.now() - S.running.t0) / 1000); }, 500);
  let view;
  try {
    while (true) {
      await wait(1000);
      view = await api('/job/' + started.job);
      $('toastMsg').textContent = view.message;
      if (S.steps) step(S.steps.cur, view.message);
      $('log').textContent = view.log.join('\n');
      if (view.state !== 'running' && view.state !== 'queued') break;
    }
  } finally { clearInterval(tick); }
  S.lastCost = view.cost && view.cost.calls ? view.cost.dollars : null;
  if (view.state !== 'complete') throw new Error((view.error || 'Cancelled') + costNote());
  return view.result;
}

async function guarded(fn) {
  if (S.running) return;
  try { await fn(); }
  catch (e) { S.running = null; toast(e.message, { error: true }); }
  S.running = null;
  render();
}

// ------------------------------------------------------------ rendering

const TITLES = { clean: ['Clean cut', ICON.clean], flubs: ['Flubs and retakes', ICON.flubs], anim: ['Animations', ICON.anim], styles: ['Styles', ICON.style], settings: ['Settings', ''] };

function render() {
  const home = S.screen === 'home';
  $('back').className = home ? 'iconBtn hidden' : 'iconBtn';
  $('brand').className = home ? 'brand' : 'brand hidden';
  const tt = $('toolTitle');
  tt.className = home ? 'toolTitle hidden' : 'toolTitle';
  if (!home) tt.innerHTML = TITLES[S.screen][1] + '<span>' + TITLES[S.screen][0] + '</span>';
  $('foot').className = home ? 'hidden' : '';
  const v = $('view');
  const keep = v.scrollTop;
  let html = '';
  if (home) html = renderHome();
  else if (S.screen === 'settings') html = renderSettings();
  else if (S.screen === 'styles') html = renderStyles();
  else if (!S.src) html = renderNoSource();
  else if (S.screen === 'clean') html = renderClean();
  else if (S.screen === 'flubs') html = renderFlubs();
  else if (S.screen === 'anim') html = renderAnim();
  v.innerHTML = html;
  if (S.keepScroll) v.scrollTop = keep;
  S.keepScroll = false;
  $('main').disabled = !!S.running || (!home && S.screen !== 'settings' && S.screen !== 'styles' && !S.src) || $('main').dataset.off === '1';
  if (S.screen === 'clean') drawWave();
}

function footer(label, info, off) {
  $('main').textContent = label;
  $('main').dataset.off = off ? '1' : '0';
  $('footInfo').innerHTML = info || '';
}

function renderNoSource() {
  footer('Waiting for Premiere', '', true);
  return '<div class="empty"><b>Open your recording in Premiere</b>' + esc(S.srcError || 'Josh Cut Pro works on the sequence you have open in Premiere.') + '</div>';
}

function renderHome() {
  let h = '';
  if (S.helper.up === null) {
    h += '<div class="notice"><span class="ring"></span><div><b>Connecting</b>Looking for Premiere\u2026</div></div>';
  } else if (!S.helper.up) {
    h += notice('The helper isn\'t running', 'Double-click "Start Josh Cut Pro" in E:\\Videos\\DaJoshiCut.');
  } else if (!S.premiere.connected) {
    h += notice('Connect Premiere', 'Open Premiere, then Window > UXP Plugins > Josh Cut Pro. The little panel links this window to your timeline.');
  } else if (!S.src) {
    h += notice('Open your recording', S.srcError || 'Open the sequence with your recording on it.');
  } else {
    const t = S.project && S.project.transcript;
    let tx = '';
    if (t && t.state === 'ready') tx = '<div class="tx"><span>Transcript ready' + (t.made ? ', made ' + esc(t.made) + ' from this same file' : '') + '</span></div>';
    else if (t && t.state === 'running') tx = '<div class="tx"><span class="bar"><i style="width:' + t.progress + '%"></i></span><span>Transcribing ' + t.progress + '%</span></div>';
    else if (t && t.state === 'failed') tx = '<div class="tx"><span>Transcript failed, it will try again when needed</span></div>';
    h += '<div class="timeline"><div class="grow"><div class="seq">' + esc(S.src.sequenceName) + '</div>' +
      '<div class="meta"><b>' + esc(S.src.clipName) + '</b> \u00B7 ' + fmt(S.src.duration) + (pickedTrack() && !pickedTrack().same ? ' \u00B7 mic ' + esc(pickedTrack().name) : '') +
      (S.src.already_cut ? ' \u00B7 already cut' : '') + '</div>' + tx + '</div>' +
      '<button class="iconBtn" data-act="refresh" title="Read the timeline again"><svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/></svg></button></div>';
  }
  const st = (S.project && S.project.stages) || {};
  const tile = (id, name, desc, opts) => '<div class="tile' + (opts.small ? ' small' : '') + (opts.soon ? ' soon' : '') + '"' + (opts.soon ? '' : ' data-go="' + id + '"') + '>' +
    '<span class="art">' + art(opts.art || id) + '</span>' + (opts.badge ? '<span class="badge' + (opts.done ? ' done' : '') + '">' + opts.badge + '</span>' : '') +
    '<div class="body"><div class="name">' + name + '</div>' + (desc ? '<div class="desc">' + desc + '</div>' : '') + '</div></div>';
  h += '<div class="label">Tools</div><div class="grid">' +
    tile('clean', 'Clean cut', 'Silences, breaths and noises gone in seconds.', { badge: st.clean ? 'Done' : '', done: true }) +
    tile('flubs', 'Flubs and retakes', 'Claude marks the stumbles. You check the script.', { badge: S.project && S.project.has_flubs ? 'Reviewed' : '', done: true }) +
    tile('anim', 'Animations', 'Plan, review and build onto the timeline.', { badge: st.build ? 'Built' : '', done: true }) +
    tile('broll', 'B-roll', 'Clips from your library, matched to what you say.', { soon: true, badge: 'Soon' }) +
    '</div><div class="grid small">' +
    tile('zoom', 'Zooms', '', { soon: true, small: true, badge: 'Soon', art: 'zoom' }) +
    tile('key', 'Your look', '', { soon: true, small: true, badge: 'Soon', art: 'key' }) +
    tile('styles', 'Styles', '', { small: true, art: 'style' }) + '</div>';
  return h;
}

function notice(title, text) {
  return '<div class="notice"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg><div><b>' + esc(title) + '</b>' + esc(text) + '</div></div>';
}

function stepper(steps, cur) {
  return '<div class="stepper">' + steps.map((s, i) => (i ? '<span class="line"></span>' : '') +
    '<span class="st ' + (i < cur ? 'done' : i === cur ? 'on' : '') + '"><i>' + (i < cur ? '\u2713' : i + 1) + '</i>' + s + '</span>').join('') + '</div>';
}

// ---------- settings

function renderSettings() {
  footer('Save key', 'Your key is stored on this PC only');
  return '<div class="card"><div class="cardHead"><h3>Claude API key</h3>' + (S.helper.key ? '<span class="pill">Saved</span>' : '') + '</div>' +
    '<p class="hint">' + (S.helper.key ? 'A key is saved. Paste a new one to replace it.' : 'Paste your key from console.anthropic.com.') + '</p>' +
    '<input type="password" id="apiKey" placeholder="sk-ant-\u2026"></div>' + layerCard() + costCard() +
    '<div class="card"><div class="cardHead"><h3>Josh Cut Pro</h3><span class="hint">Helper ' + esc(S.helper.version || '') + '</span></div>' +
    '<p class="hint">Closing this window leaves the helper running in the background so Premiere stays connected. Quit stops it completely.</p>' +
    '<div class="row mt12"><button class="secondary" data-act="probe">Check Premiere</button><button class="secondary" data-act="log">Show the log</button><button class="secondary" data-act="quit">Quit Josh Cut Pro</button></div></div>';
}

function layerCard() {
  const p = S.prefs;
  if (!p) return '';
  return '<div class="card"><div class="cardHead"><h3>Layers</h3></div>' +
    '<div class="ctl"><div class="switch' + (p.keep_layers ? ' on' : '') + '" data-pref="keep_layers"><i></i>Put layers back after a recut</div></div>' +
    '<p class="hint">Clean cut and Flubs rebuild the Josh Cut sequence. With this on, your animations go back on the words they belong to.</p>' +
    '<div class="ctl mt12"><div class="switch' + (p.animations_own_sequence ? ' on' : '') + '" data-pref="animations_own_sequence"><i></i>Animations in their own sequence</div></div>' +
    '<p class="hint">The old way. This builds a separate "Josh Cut Animations" sequence instead of putting them on V5.</p></div>';
}

function money(d) { return '$' + d.toFixed(2); }

function costCard() {
  const c = S.costs;
  if (!c || !c.show) return '';
  return '<div class="card"><div class="cardHead"><h3>Claude spend</h3><span class="hint">From claude-costs.csv in Projects</span></div>' +
    '<div class="stats mt8"><div class="stat hi"><b>' + money(c.month) + '</b><span>this month</span></div>' +
    '<div class="stat"><b>' + money(c.total) + '</b><span>all time</span></div>' +
    '<div class="stat"><b>' + (c.videos ? money(c.total / c.videos) : '\u2013') + '</b><span>per video</span></div></div></div>';
}

// ---------- clean cut

const PACES = ['calm', 'measured', 'paced', 'energetic'];

function renderClean() {
  const p = S.project, s = S.silence || {};
  if (!p.prepared) {
    footer('Read the audio', 'Takes a few seconds the first time');
    return stepper(['Audio', 'Settings'], 0) + '<div class="empty"><b>Reading your audio</b>Josh Cut Pro needs a quick look at the sound before it can show the cuts.</div>';
  }
  const auto = s.threshold_db == null;
  const db = auto ? (S.preview && S.preview.threshold_db != null ? S.preview.threshold_db : -40) : s.threshold_db;
  const pv = S.preview;
  footer('Cut silences',
    pv && !pv.error ? '<b>' + fmt(pv.source_seconds) + '</b> \u2192 <b>' + fmt(pv.output_seconds) + '</b> \u00B7 ' + pv.cuts + ' cuts' : (pv && pv.error ? esc(pv.error) : ''));
  let h = stepper(['Audio', 'Settings'], 1) + trackPicker();
  h += '<div class="card"><div class="wave"><canvas id="wave"></canvas></div>' +
    '<div class="times"><span>' + fmt(S.src.in) + '</span><span>' + fmt(S.src.out) + '</span></div>' +
    '<div class="legend"><span><i style="background:#e9e4d8"></i>Kept</span><span><i style="background:#E2584C"></i>Cut</span><span><i style="background:#F5C21B;height:2px"></i>Silence level</span></div></div>';
  h += '<div class="stats mt8" style="margin-bottom:14px">' +
    '<div class="stat hi"><b id="stRemoved">' + (pv && !pv.error ? fmt(pv.removed_seconds) : '–') + '</b><span>removed</span></div>' +
    '<div class="stat"><b id="stCuts">' + (pv && !pv.error ? pv.cuts : '–') + '</b><span>cuts</span></div>' +
    '<div class="stat"><b id="stSounds">' + (pv && !pv.error ? pv.sounds : '–') + '</b><span>breaths and noises</span></div>' +
    '<div class="stat"><b id="stLen">' + (pv && !pv.error ? fmt(pv.output_seconds) : '–') + '</b><span>new length</span></div></div>';
  h += '<div class="cols"><div class="card">' +
    '<div class="ctl"><div class="ctlHead"><span>Pace</span></div><div class="seg">' +
    PACES.map((k) => '<button data-pace="' + k + '"' + (s.preset === k ? ' class="on"' : '') + '>' + k[0].toUpperCase() + k.slice(1) + '</button>').join('') + '</div></div>' +
    slider('threshold_db', 'Silence level', db, -70, -15, 1, auto, '<button class="chip' + (auto ? ' on' : '') + '" data-act="auto">Auto</button>') +
    '<p class="hint">Anything quieter than this line counts as silence. Auto sets it just above your room noise.</p></div>' +
    '<div class="card">' + slider('max_pause', 'Longest pause kept', s.max_pause, 0.1, 1.5, 0.05) +
    slider('pad_after', 'Margin around words', s.pad_after, 0, 0.3, 0.01) +
    '<div class="ctl"><div class="switch' + (s.cut_sounds !== false ? ' on' : '') + '" data-act="sounds"><i></i>Cut breaths, coughs and noises</div></div></div></div>';
  h += cutHint();
  return h;
}

const UNITS = { threshold_db: (v) => Math.round(v) + ' dB', max_pause: (v) => Number(v).toFixed(2) + ' s', pad_after: (v) => Number(v).toFixed(2) + ' s' };

function slider(key, label, value, min, max, step, disabled, extra) {
  const v = Number(value), pct = ((v - min) / (max - min) * 100).toFixed(1);
  return '<div class="ctl"><div class="ctlHead"><span>' + label + ' ' + (extra || '') + '</span><b id="v-' + key + '">' + UNITS[key](v) + '</b></div>' +
    '<input type="range" data-key="' + key + '" min="' + min + '" max="' + max + '" step="' + step + '" value="' + v + '" style="--p:' + pct + '%"' + (disabled ? ' disabled' : '') + '></div>';
}

async function loadClean() {
  if (!S.src || !S.project) return;
  if (!S.project.prepared) { await guarded(async () => { await job('prepare', req()); hideToast(); await refreshSource(); }); }
  if (!S.project || !S.project.prepared) return;
  try {
    const w = await api('/waveform?req=' + encodeURIComponent(JSON.stringify(req())));
    if (w.peaks) S.wave = w;
  } catch (e) { /* drawn without it */ }
  schedulePreview(0);
}

let pvTimer = null;
function schedulePreview(delay) {
  clearTimeout(pvTimer);
  pvTimer = setTimeout(async () => {
    try {
      const r = await api('/silence-preview', req({ settings: S.silence }));
      if (!r.ready) return;
      S.preview = r.error ? { error: r.error } : Object.assign({ keeps: r.keeps, auto_db: r.auto_db }, r.stats);
      if (S.screen !== 'clean') return;
      paintStats(); drawWave();
    } catch (e) { /* helper will say */ }
  }, delay == null ? 120 : delay);
}

function paintStats() {
  const pv = S.preview; if (!pv) return;
  const set = (id, t) => { const e = $(id); if (e) e.textContent = t; };
  if (pv.error) { $('footInfo').textContent = pv.error; return; }
  set('stRemoved', fmt(pv.removed_seconds)); set('stCuts', pv.cuts); set('stSounds', pv.sounds); set('stLen', fmt(pv.output_seconds));
  $('footInfo').innerHTML = '<b>' + fmt(pv.source_seconds) + '</b> \u2192 <b>' + fmt(pv.output_seconds) + '</b> \u00B7 ' + pv.cuts + ' cuts';
  if (S.silence.threshold_db == null) {
    const el = $('v-threshold_db'), inp = document.querySelector('input[data-key=threshold_db]');
    if (el) el.textContent = UNITS.threshold_db(pv.threshold_db);
    if (inp) { inp.value = pv.threshold_db; inp.style.setProperty('--p', ((pv.threshold_db + 70) / 55 * 100).toFixed(1) + '%'); }
  }
}

function drawWave() {
  const c = $('wave'); if (!c) return;
  const dpr = window.devicePixelRatio || 1, W = c.clientWidth, H = c.clientHeight;
  c.width = W * dpr; c.height = H * dpr;
  const g = c.getContext('2d'); g.scale(dpr, dpr);
  g.clearRect(0, 0, W, H);
  const w = S.wave, pv = S.preview;
  if (!w) { g.fillStyle = '#5d5b55'; g.font = '12px Manrope'; g.textAlign = 'center'; g.fillText('Reading the audio\u2026', W / 2, H / 2); return; }
  const span = w.end - w.start, lo = Math.min(-50, w.floor - 10), hi = Math.max(-6, w.speech + 3);
  const y = (db) => H - 6 - Math.max(0, Math.min(1, (db - lo) / (hi - lo))) * (H - 12);
  const keeps = (pv && pv.keeps) || null;
  const kept = (t) => !keeps || keeps.some(([a, b]) => t >= a && t <= b);
  // shade the cut stretches
  if (keeps) {
    g.fillStyle = 'rgba(226,88,76,.10)';
    let prev = w.start;
    for (const [a, b] of keeps) { if (a > prev) g.fillRect((prev - w.start) / span * W, 0, (a - prev) / span * W, H); prev = Math.max(prev, b); }
    if (prev < w.end) g.fillRect((prev - w.start) / span * W, 0, (w.end - prev) / span * W, H);
  }
  const n = w.peaks.length, bw = W / n;
  for (let i = 0; i < n; i++) {
    const t = w.start + (i + .5) / n * span, top = y(w.peaks[i]);
    g.fillStyle = kept(t) ? 'rgba(233,228,216,.82)' : 'rgba(226,88,76,.85)';
    g.fillRect(i * bw, top, Math.max(1, bw - .6), H - 6 - top);
  }
  const thr = S.silence && S.silence.threshold_db != null ? S.silence.threshold_db : (pv && pv.threshold_db != null ? pv.threshold_db : w.auto_db);
  g.strokeStyle = '#F5C21B'; g.lineWidth = 1.4; g.setLineDash([5, 4]);
  g.beginPath(); g.moveTo(0, y(thr)); g.lineTo(W, y(thr)); g.stroke(); g.setLineDash([]);
}

async function runClean() {
  if (!S.project.prepared) return loadClean();
  showSteps('Clean cut', [['listen', 'Finding the silences'], ['backup', 'Saving a backup copy'], ['check', 'Checking Premiere (first time only)'],
                          ['cut', 'Cutting the timeline'], ['verify', 'Checking the result']]);
  try {
    const r = await job('silences', req({ settings: S.silence }));
    await applyCut(r, 'Clean cut');
  } finally { endSteps(); }
}

// ------------------------------------------------------------ the progress screen

const TICK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';

function showSteps(title, steps) {
  // a full-window list of steps, like AutoCut's, while the timeline is being edited
  S.steps = { title, steps, cur: steps[0][0], detail: '' };
  paintSteps();
}

function step(key, detail) {
  const st = S.steps;
  if (!st) return;
  if (!st.steps.some((s) => s[0] === key)) return;
  if (st.cur !== key) st.detail = '';
  st.cur = key;
  if (detail != null) st.detail = detail;
  paintSteps();
}

function addStep(key, label) {
  if (S.steps && !S.steps.steps.some((s) => s[0] === key)) { S.steps.steps.push([key, label]); paintSteps(); }
}

function endSteps() { S.steps = null; paintSteps(); }

function paintSteps() {
  let el = $('steps');
  if (!S.steps) { if (el) el.remove(); return; }
  if (!el) { el = document.createElement('div'); el.id = 'steps'; document.body.appendChild(el); }
  const st = S.steps, at = st.steps.findIndex((s) => s[0] === st.cur);
  el.innerHTML = '<div class="stepsBox"><div class="stepsTitle">' + esc(st.title) + '</div><ol>' +
    st.steps.map((s, i) => '<li class="' + (i < at ? 'done' : i === at ? 'on' : '') + '"><i>' + (i < at ? TICK : i === at ? '<span class="ring"></span>' : i + 1) + '</i>' +
      '<span>' + esc(s[1]) + (i === at && st.detail ? '<small>' + esc(st.detail) + '</small>' : '') + '</span></li>').join('') + '</ol>' +
    '<p class="hint center">Please leave the Premiere timeline alone until this finishes. Scrolling and zooming are fine.</p></div>';
}

async function bridgeWithSteps(cmd, args) {
  // follow the panel's progress on the progress screen while Premiere works
  const poll = setInterval(async () => {
    try { const p = await api('/bridge/progress'); if (p.phase) step(p.phase, p.text); } catch (e) { /* next time */ }
  }, 400);
  try { return await bridge(cmd, args); } finally { clearInterval(poll); }
}

function trackPicker() {
  // which audio track Josh Cut Pro listens to for the cut
  const list = (S.src && S.src.audio_tracks) || [];
  if (!list.length) return '';
  const pick = pickedTrack();
  return '<div class="card"><div class="ctl"><div class="ctlHead"><span>Listen to</span><span class="hint">The cut applies to every track</span></div><div class="seg">' +
    list.map((a) => '<button data-track="' + a.index + '"' + (pick && pick.index === a.index ? ' class="on"' : '') + ' title="' + esc(a.name) + '">A' + (a.index + 1) +
      ' \u00B7 ' + esc(a.same ? 'camera' : a.name.replace(/\.[^.]+$/, '').slice(0, 18)) + '</button>').join('') + '</div></div></div>';
}

function cutHint() {
  const seq = esc(S.src.sequenceName), t = pickedTrack(), read = S.project && S.project.audio_read;
  const heard = t ? 'Listening to A' + (t.index + 1) + ' (' + esc(t.name) + ').' : '';
  const reuse = read && S.screen === 'clean' ? ' This audio was read on ' + esc(read) + ' and hasn\'t changed, so the cuts show straight away.' : '';
  return '<p class="hint center mt8">' + heard + reuse + ' Nothing changes in Premiere until you press the button below.</p>' +
    '<p class="hint center">This cuts ' + seq + ' itself. A copy from before each cut goes in Josh Cut Pro > Backups.' +
    (S.src.already_cut ? ' It\'s already cut, so this only takes more out.' : '') + '</p>';
}

async function applyCut(r, label) {
  // cut the open sequence in place, then put the animations back on their words
  if (!r.remove.length || !r.cuts) { endSteps(); toast('There was nothing to cut on ' + S.src.sequenceName + '.'); return; }
  if (r.has_layers) addStep('layers', 'Putting the animations back');
  step('backup');
  toast('Cutting ' + S.src.sequenceName + ' in Premiere\u2026', { busy: true });
  const done = await bridgeWithSteps('cut', { remove: r.remove, video: r.video, label, lift: !!r.has_layers });
  let note = '';
  if (r.has_layers && done.timeline) {
    S.src = done.timeline;
    step('layers', 'Working out where they go');
    toast('Putting the animations back\u2026', { busy: true });
    const lr = await job('layers', req());
    const placed = await bridgeWithSteps('layers', { result: lr });
    note = layerNote(lr, placed);
  }
  endSteps();
  const odd = (done.gaps || []).length + (done.overlaps || []).length;
  toast(label + ' took ' + fmt(done.removed_seconds) + ' out of ' + S.src.sequenceName + ' in ' + done.cuts + (done.cuts === 1 ? ' cut' : ' cuts') + '. The version from before is in Josh Cut Pro > Backups.' + note +
    (odd ? ' ' + odd + ' gap' + (odd === 1 ? '' : 's') + ' or overlap' + (odd === 1 ? '' : 's') + ' were left on the timeline. They\'re listed in last-cut.json in the project folder.' : ''));
  await refreshSource();
}

// ---------- flubs

function renderFlubs() {
  const p = S.project;
  if (!p.has_flubs || !S.flubs) {
    const t = p.transcript || {};
    footer(p.has_flubs ? 'Open the review' : 'Find flubs with Claude', t.state === 'running' ? 'The transcript is ' + t.progress + '% done' : '');
    return stepper(['Find', 'Review', 'Apply'], 0) +
      '<div class="empty"><b>Let Claude read the script</b>It marks abandoned takes, stumbles, repeated words and fillers. Nothing is cut until you\'ve checked them.</div>';
  }
  const f = S.flubs;
  const secs = [...f.cut].reduce((a, i) => a + (f.words[i + 1] ? Math.min(3, f.words[i + 1].t - f.words[i].t) : .3), 0);
  footer('Remove flubs', 'Cutting <b>' + f.cut.size + '</b> words \u00B7 about <b>' + fmt(secs) + '</b>');
  let h = stepper(['Find', 'Review', 'Apply'], 1) + trackPicker();
  h += '<div class="toolbar"><span class="key"><i></i>Red is cut</span><span class="grow">Highlight any words, then Cut or Keep</span><button class="textBtn" data-act="resetFlubs">Reset to Claude\'s picks</button></div>';
  h += '<div class="script" id="script"><p>';
  f.words.forEach((w, i) => {
    if (w.p && i) h += '</p><p>';
    if (w.p) h += '<span class="t">' + fmt(w.t) + '</span>';
    const cls = 'w' + (f.cut.has(i) ? ' cut' : '') + (S.sel && i >= S.sel[0] && i <= S.sel[1] ? ' sel' : '');
    h += '<span class="' + cls + '" data-w="' + i + '">' + esc(w.w) + '</span> ';
  });
  h += '</p></div>' + cutHint();
  if (S.sel) {
    const n = S.sel[1] - S.sel[0] + 1;
    h += '<div class="selbar"><span class="txt">' + n + ' word' + (n > 1 ? 's' : '') + ' selected</span>' +
      '<button class="secondary cutBtn" data-act="cutSel">Cut</button><button class="secondary keepBtn" data-act="keepSel">Keep</button><button class="textBtn" data-act="clearSel">Clear</button></div>';
  }
  return h;
}

async function loadFlubs(fresh) {
  const d = await api('/flubs?video=' + encodeURIComponent(S.src.video));
  S.flubs = { words: d.words, cut: new Set(fresh || !d.applied ? d.proposed : d.applied), proposed: new Set(d.proposed) };
  S.sel = null;
}

function selectionFromHighlight() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed) return false;
  const spans = [...document.querySelectorAll('#script .w')].filter((s) => sel.containsNode(s, true));
  if (!spans.length) return false;
  const idx = spans.map((s) => Number(s.dataset.w));
  S.sel = [Math.min(...idx), Math.max(...idx)];
  sel.removeAllRanges();
  if (!S.running) hideToast();
  return true;
}

async function runFlubs() {
  if (!S.project.has_flubs) {
    await job('flubs', req());
    await refreshSource(); await loadFlubs(true);
    toast('Check the red words, change anything you disagree with, then remove the flubs.');
    return;
  }
  if (!S.flubs) { await loadFlubs(false); return; }
  showSteps('Remove flubs', [['listen', 'Finding the flub words in the audio'], ['backup', 'Saving a backup copy'], ['check', 'Checking Premiere (first time only)'],
                             ['cut', 'Cutting the timeline'], ['verify', 'Checking the result']]);
  try {
    const r = await job('apply', req({ removed: [...S.flubs.cut], settings: S.silence }));
    await applyCut(r, 'Flubs');
  } finally { endSteps(); }
}

// ---------- animations

function renderAnim() {
  const p = S.project;
  const s = p.shotlist;
  let h = stepper(['Plan', 'Review', 'Build'], s ? (p.stages.build && s.approved ? 3 : 1) : 0);
  h += animSettings();
  h += '<div class="card"><div class="cardHead"><h3>Notes for Claude</h3><span class="hint">Optional</span></div>' +
    '<textarea id="notes" placeholder="e.g. Question-mark cards on \'the four things\'. A review card when I mention Sarah.">' + esc(s ? s.instructions : S.notes) + '</textarea>' +
    (s ? '<div class="mt8"><button class="secondary" data-act="plan">Plan again</button></div>' : '') + '</div>';
  if (!s) { footer('Plan the animations', 'Claude plans them from the transcript and your notes, then you review the cards'); return h; }
  h += '<div class="shots">';
  for (const a of s.animations) {
    h += '<div class="shot">' + (a.sketch && a.sketch.indexOf('ext=png') >= 0 ? '<img src="' + a.sketch + '" data-zoom="1">' : '<div class="noimg">No sketch</div>') +
      '<div class="info"><div class="top"><span class="num">' + a.number + '</span><span class="nm">' + esc(a.name) + '</span><span class="pill' + (a.type === 'full' ? ' full' : '') + '">' + esc(SHORT[a.type] || 'Full') + '</span></div>' +
      (a.at ? '<span class="at">' + a.at + '</span>' : '') + '<div class="ds">' + esc(a.description) + '</div>' +
      '<div class="acts"><button class="ghost" data-redo="' + a.number + '">Change</button>' + typeSelect(a) + '<button class="ghost danger" data-remove="' + a.number + '">Remove</button></div>' +
      (S.redoOpen[a.number] ? '<div class="redo"><textarea id="redo-' + a.number + '" placeholder="What should change?"></textarea><button class="secondary" data-send="' + a.number + '">Send to Claude</button></div>' : '') +
      '</div></div>';
  }
  h += '</div>';
  footer(p.stages.build && s.approved ? 'Build again' : 'Approve and build', s.animations.length + ' animations');
  return h;
}

// What each shot type is called on a card, and which ones are only suggestions.
const SHORT = { full: 'Full', half: 'Half', pip: 'PiP', end: 'End screen', kw: 'Key word', title: 'Title', lt: 'Lower third' };
const SUGGESTED = { kw: 1, title: 1, lt: 1 };
const TYPE_ORDER = ['full', 'half', 'pip', 'end', 'kw', 'title', 'lt'];

function typeSelect(a) {
  const on = (S.anim && S.anim.types) || ['full', 'pip'];
  const opts = TYPE_ORDER.filter((t) => on.includes(t) || t === a.type);
  return '<select data-type-of="' + a.number + '" title="Shot type">' + opts.map((t) => '<option value="' + t + '"' + (t === a.type ? ' selected' : '') + '>' + SHORT[t] + '</option>').join('') + '</select>';
}

function animSettings() {
  const a = S.anim, cat = S.project.anim_catalogue;
  if (!a || !cat) return '';
  let h = '<div class="card"><div class="cardHead"><h3>Shot types</h3><span class="hint">Claude only plans the ones that are on</span></div><div class="chips">';
  for (const t of TYPE_ORDER) {
    h += '<button class="tchip' + (a.types.includes(t) ? ' on' : '') + '" data-type-chip="' + t + '">' + esc(cat.types[t]) + (SUGGESTED[t] ? ' <span class="hint">suggested</span>' : '') + '</button>';
  }
  h += '</div>';
  if (a.types.length > 4 || (a.often === 'heavy' && a.rich === 'explainer')) h += '<div class="warn">This many could feel busy. Claude will still keep it to what you picked.</div>';
  h += '<div class="ctlRow mt16"><div class="ctl"><div class="ctlHead"><span>How often</span></div><div class="seg">' +
    Object.keys(cat.often).map((k) => '<button data-often="' + k + '"' + (a.often === k ? ' class="on"' : '') + '>' + esc(cat.often[k]) + '</button>').join('') + '</div></div>' +
    '<div class="ctl"><div class="ctlHead"><span>How rich</span></div><div class="seg">' +
    Object.keys(cat.rich).map((k) => '<button data-rich="' + k + '"' + (a.rich === k ? ' class="on"' : '') + '>' + esc(cat.rich[k]) + '</button>').join('') + '</div></div></div>' +
    '<div class="ctl"><div class="ctlHead"><span>Style</span><button class="textBtn" data-go="styles">Edit styles</button></div><select data-anim-style="1">' +
    Object.keys(cat.styles).map((k) => '<option value="' + k + '"' + (a.style === k ? ' selected' : '') + '>' + esc(cat.styles[k]) + '</option>').join('') + '</select></div>';
  if (a.types.includes('half')) {
    h += '<div class="ctl"><div class="ctlHead"><span>Half and half panel comes from</span></div><div class="seg">' +
      ['left', 'right'].map((k) => '<button data-half-side="' + k + '"' + (a.half_side === k ? ' class="on"' : '') + '>' + (k === 'left' ? 'Left' : 'Right') + '</button>').join('') + '</div></div>';
  }
  h += '</div>';
  if (a.types.includes('pip')) h += pipCard();
  return h;
}

function camLayout(box, p, aspect) {
  // The same framing maths as helper/pip.py: the camera fills the shape's height times zoom, and shift slides
  // it across whatever is left over. Returns the still's size and place as percentages of the shape.
  const b = 6, win = box[2] - 2 * b, hin = box[3] - 2 * b, zoom = p.zoom || 1;
  const dispH = hin * zoom, dispW = dispH * aspect;
  const cutW = Math.max(0, 1 - win / dispW), cutH = Math.max(0, 1 - hin / dispH);
  const left = cutW > 0 ? cutW * (1 + (p.shift || 0)) / 2 * dispW : (dispW - win) / 2;
  const top = cutH > 0 ? cutH * (1 + (p.shift_y || 0)) / 2 * dispH : (dispH - hin) / 2;
  return { w: dispW / win * 100, h: dispH / hin * 100, x: -left / win * 100, y: -top / hin * 100,
           slackX: cutW * dispW / 2, slackY: cutH * dispH / 2 };
}

function camStyle() {
  const a = S.anim, sh = S.project.anim_catalogue.shapes[a.pip_shape] || S.project.anim_catalogue.shapes['tall-box'];
  const L = camLayout(sh.box, S.pip || {}, S.camAspect || 16 / 9);
  return 'width:' + L.w.toFixed(3) + '%;height:' + L.h.toFixed(3) + '%;left:' + L.x.toFixed(3) + '%;top:' + L.y.toFixed(3) + '%';
}

function pipCard() {
  const a = S.anim, shapes = S.project.anim_catalogue.shapes;
  const sh = shapes[a.pip_shape] || shapes['tall-box'];
  let [x, y, w, hh] = sh.box;
  if (a.pip_side === 'left') x = 1920 - x - w;
  const pct = (v, of) => (v / of * 100).toFixed(2) + '%';
  const cam = 'left:' + pct(x, 1920) + ';top:' + pct(y, 1080) + ';width:' + pct(w, 1920) + ';height:' + pct(hh, 1080) + ';border-radius:' + (sh.round ? '50%' : '2px');
  const lines = 'left:' + (a.pip_side === 'left' ? pct(110 + 570, 1920) : '5.73%');
  const arrow = (d, path) => '<button data-nudge="' + d + '"><svg viewBox="0 0 24 24"><path d="' + path + '"/></svg></button>';
  const still = '/camera-still?video=' + encodeURIComponent(S.src.video);
  return '<div class="card"><div class="cardHead"><h3>Picture in picture</h3><span class="hint">Drag yourself inside the shape</span></div>' +
    '<div class="pipStage"><div class="lines" style="' + lines + '"><i></i><i></i><i></i></div>' +
    '<div class="cam live" data-camdrag="1" style="' + cam + '"><img class="camimg" draggable="false" alt="" src="' + still + '" style="' + camStyle() + '"></div></div>' +
    '<div class="shapes">' + Object.keys(shapes).map((k) => {
      const s = shapes[k], r = s.box[2] / s.box[3], ww = Math.round(r >= 1 ? 26 : 26 * r), hh2 = Math.round(r >= 1 ? 26 / r : 26);
      return '<button class="shapeBtn' + (a.pip_shape === k ? ' on' : '') + '" data-shape="' + k + '"><i style="width:' + ww + 'px;height:' + hh2 + 'px;border-radius:' + (s.round ? '50%' : '2px') + '"></i>' + esc(s.label) + '</button>';
    }).join('') + '</div>' +
    '<div class="row mt12" style="align-items:flex-end;gap:16px"><div class="ctl grow" style="margin:0"><div class="ctlHead"><span>Side</span></div><div class="seg">' +
    ['left', 'right'].map((k) => '<button data-pip-side="' + k + '"' + (a.pip_side === k ? ' class="on"' : '') + '>' + (k === 'left' ? 'Left' : 'Right') + '</button>').join('') + '</div></div>' +
    '<div class="pad"><span></span>' + arrow('up', 'M12 19V5M5 12l7-7 7 7') + '<span></span>' + arrow('left', 'M19 12H5M12 19l-7-7 7-7') +
    '<button data-nudge="reset" title="Reset"><svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg></button>' + arrow('right', 'M5 12h14M12 5l7 7-7 7') +
    arrow('out', 'M5 12h14') + arrow('down', 'M12 5v14M5 12l7 7 7-7') + arrow('in', 'M12 5v14M5 12h14') + '</div></div></div>';
}

let animTimer = null;
function setAnim(patch, opts) {
  // update the screen straight away, then save the choice for this recording
  S.anim = Object.assign({}, S.anim, patch);
  S.keepScroll = true;
  if (opts && opts.inPlace) inPlacePip(); else render();
  clearTimeout(animTimer);
  animTimer = setTimeout(async () => {
    try {
      const r = await api('/anim', { video: S.src.video, anim: S.anim });
      S.anim = r.anim;
      if (opts && opts.reframe) { await nudge('same'); }
    } catch (e) { toast(e.message, { error: true }); }
  }, 250);
}

function inPlacePip() {
  // move the sample camera without rebuilding the screen, so the CSS transition plays
  const stage = document.querySelector('.pipStage');
  if (!stage) return render();
  const fresh = document.createElement('div'); fresh.innerHTML = pipCard();
  const next = fresh.querySelector('.pipStage');
  stage.querySelector('.cam').setAttribute('style', next.querySelector('.cam').getAttribute('style'));
  stage.querySelector('.lines').setAttribute('style', next.querySelector('.lines').getAttribute('style'));
  paintCam();
  document.querySelectorAll('[data-shape]').forEach((b) => b.classList.toggle('on', b.dataset.shape === S.anim.pip_shape));
  document.querySelectorAll('[data-pip-side]').forEach((b) => b.classList.toggle('on', b.dataset.pipSide === S.anim.pip_side));
}

function paintCam() {
  const img = document.querySelector('.camimg');
  if (img) img.setAttribute('style', camStyle());
}

// ---------- styles

function renderStyles() {
  const e = S.edit, cat = S.styleCat;
  if (!e || !cat) { footer('Save style', '', true); return '<div class="empty"><b>Loading styles</b></div>'; }
  const list = S.styleList || {};
  const warn = (e.warnings || []).map((w) => '<div class="warn bad">' + esc(w) + '</div>').join('');
  footer(e.key && list[e.key] ? 'Save changes' : 'Save style', e.missing_fonts && e.missing_fonts.length ? 'These fonts need downloading first' : 'Styles live in the styles folder');
  const q = '/style-preview?style=' + encodeURIComponent(JSON.stringify(styleBody(e))) +
    (S.anim ? '&pip_shape=' + S.anim.pip_shape + '&pip_side=' + S.anim.pip_side + '&half_side=' + S.anim.half_side : '');
  let h = '<div class="prevFrame"><iframe src="' + q + '" title="Preview"></iframe></div>';
  h += '<div class="card"><div class="ctlRow"><div class="ctl"><div class="ctlHead"><span>Style</span></div><select data-pick-style="1">' +
    Object.keys(list).map((k) => '<option value="' + k + '"' + (e.key === k ? ' selected' : '') + '>' + esc(list[k].name) + '</option>').join('') +
    '<option value="__new"' + (!list[e.key] ? ' selected' : '') + '>New style</option></select></div>' +
    '<div class="ctl"><div class="ctlHead"><span>Name</span></div><input type="text" id="styleName" value="' + esc(e.name) + '"></div></div>' + warn + '</div>';
  h += '<div class="card"><div class="cardHead"><h3>Fonts</h3><span class="hint">Heading and body</span></div><div class="chips">' +
    Object.keys(cat.pairings).map((k) => {
      const f = cat.pairings[k];
      return '<button class="tchip' + (e.fonts === k ? ' on' : '') + '" data-font="' + k + '" title="' + esc(f.head + ' and ' + f.body) + '">' + esc(f.label) +
        ' <span class="fontName">' + esc(f.head) + (f.ready ? '' : ', not downloaded') + '</span></button>';
    }).join('') + '</div></div>';
  const custom = typeof e.colors === 'object';
  h += '<div class="card"><div class="cardHead"><h3>Colours</h3><span class="hint">Background, cards, text, primary, accent</span></div><div class="chips">' +
    Object.keys(cat.presets).map((k) => {
      const c = cat.presets[k];
      return '<button class="tchip' + (!custom && e.colors === k ? ' on' : '') + '" data-preset="' + k + '"><span class="swatch">' +
        ['background', 'surface', 'text', 'primary', 'accent'].map((n) => '<i style="background:' + c[n] + '"></i>').join('') + '</span>' + esc(c.label) + '</button>';
    }).join('') + '<button class="tchip' + (custom ? ' on' : '') + '" data-preset="__custom">Your own</button></div>';
  if (custom) {
    h += '<div class="colors">' + [['background', 'Background'], ['surface', 'Cards'], ['text', 'Text'], ['primary', 'Primary'], ['accent', 'Accent']]
      .map(([k, l]) => '<label>' + l + '<input type="color" data-color="' + k + '" value="' + e.colors[k] + '"></label>').join('') + '</div>';
  }
  h += '</div><div class="card"><div class="ctlRow"><div class="ctl"><div class="ctlHead"><span>Motion</span></div><div class="seg">' +
    Object.keys(cat.motions).map((k) => '<button data-motion="' + k + '"' + (e.motion === k ? ' class="on"' : '') + '>' + esc(cat.motions[k]) + '</button>').join('') + '</div></div>' +
    '<div class="ctl"><div class="ctlHead"><span>Look</span></div><div class="seg">' +
    Object.keys(cat.looks).map((k) => '<button data-look="' + k + '"' + (e.look === k ? ' class="on"' : '') + '>' + esc(cat.looks[k]) + '</button>').join('') + '</div></div></div>' +
    '<p class="hint">Changing the style re-renders the animations next time you build. Claude doesn\'t need to write them again.</p></div>';
  return h;
}

function styleBody(e) {
  return { name: e.name, fonts: e.fonts, colors: e.colors, motion: e.motion, look: e.look };
}

async function loadStyles(pick) {
  const r = await api('/styles');
  S.styleList = r.styles; S.styleCat = r.catalogue;
  const key = pick || (S.edit && S.edit.key) || (S.anim && S.anim.style) || 'josh-house';
  S.edit = Object.assign({}, r.styles[key] || r.styles['josh-house']);
}

let styleTimer = null;
function setStyle(patch) {
  S.edit = Object.assign({}, S.edit, patch);
  S.keepScroll = true; render();
  clearTimeout(styleTimer);
  styleTimer = setTimeout(async () => {
    try {
      const d = await api('/style-check', { style: styleBody(S.edit) });
      S.edit.warnings = d.warnings; S.edit.missing_fonts = d.missing_fonts; S.edit.resolved_colors = d.resolved_colors;
      const box = document.querySelector('.card .warn.bad'); S.keepScroll = true; if (box || d.warnings.length) render();
    } catch (e) { /* the save will say */ }
  }, 300);
}

async function saveStyle() {
  S.edit.name = ($('styleName') || {}).value || S.edit.name;
  const r = await api('/styles/save', { style: styleBody(S.edit) });
  await loadStyles(r.key);
  if (S.project) S.project.anim_catalogue.styles[r.key] = r.style.name;
  toast(r.style.name + ' is saved. Pick it on the Animations screen to use it.');
}

let pipTimer = null;
function savePip() {
  // keep the framing for every PiP shot of this recording
  clearTimeout(pipTimer);
  pipTimer = setTimeout(async () => {
    try { const r = await api('/pip', { video: S.src.video, pip: S.pip }); S.pip = Object.assign({}, S.pip, r.pip); }
    catch (e) { toast(e.message, { error: true }); }
  }, 250);
}

function nudge(dir) {
  // small steps so you can get it right in the middle. Dragging is quicker for big moves.
  const c = Object.assign({ zoom: 1, shift: 0, shift_y: 0 }, S.pip || {}), step = .04;
  if (dir === 'left') c.shift = Math.min(1, c.shift + step);
  if (dir === 'right') c.shift = Math.max(-1, c.shift - step);
  if (dir === 'up') c.shift_y = Math.min(1, c.shift_y + step);
  if (dir === 'down') c.shift_y = Math.max(-1, c.shift_y - step);
  if (dir === 'in') c.zoom = Math.min(2.5, c.zoom + .05);
  if (dir === 'out') c.zoom = Math.max(1, c.zoom - .05);
  if (dir === 'reset') { c.zoom = 1; c.shift = 0; c.shift_y = 0; }
  S.pip = c; paintCam(); savePip();
}

// drag yourself inside the shape: only the camera still moves, the box stays put
let drag = null;
document.addEventListener('pointerdown', (ev) => {
  const box = ev.target.closest && ev.target.closest('[data-camdrag]');
  if (!box || S.running) return;
  const sh = S.project.anim_catalogue.shapes[S.anim.pip_shape] || S.project.anim_catalogue.shapes['tall-box'];
  const p = Object.assign({ zoom: 1, shift: 0, shift_y: 0 }, S.pip || {});
  const L = camLayout(sh.box, p, S.camAspect || 16 / 9);
  const k = box.parentElement.clientWidth / 1920;   // screen pixels per frame pixel
  drag = { box, x: ev.clientX, y: ev.clientY, p, sx: L.slackX * k, sy: L.slackY * k };
  box.setPointerCapture(ev.pointerId); box.classList.add('dragging');
  ev.preventDefault();
});
document.addEventListener('pointermove', (ev) => {
  if (!drag) return;
  const clamp = (v) => Math.max(-1, Math.min(1, v));
  const p = Object.assign({}, drag.p);
  // dragging right shows more of the left of the shot, which is what shift does going down
  if (drag.sx > 0) p.shift = clamp(drag.p.shift - (ev.clientX - drag.x) / drag.sx);
  if (drag.sy > 0) p.shift_y = clamp(drag.p.shift_y - (ev.clientY - drag.y) / drag.sy);
  S.pip = p; paintCam();
});
document.addEventListener('pointerup', () => {
  if (!drag) return;
  drag.box.classList.remove('dragging'); drag = null;
  savePip();
});
document.addEventListener('load', (ev) => {
  // the still's own shape sets how wide the camera is
  if (ev.target.classList && ev.target.classList.contains('camimg') && ev.target.naturalHeight) {
    const aspect = ev.target.naturalWidth / ev.target.naturalHeight;
    if (Math.abs(aspect - (S.camAspect || 0)) > .001) { S.camAspect = aspect; paintCam(); }
  }
}, true);

async function planAnim() {
  S.notes = ($('notes') || {}).value || '';
  await job('shotlist', req({ instructions: S.notes, anim: S.anim }));
  await refreshSource(); toast('Have a look through the animations, change any you don\'t like, then approve and build.');
}

async function runAnim() {
  // with no plan yet, the gold button plans first. Once there's a plan it builds.
  if (!S.project.shotlist) return planAnim();
  const r = await job('build', req({ anim: S.anim }));
  if (r.layers) {
    toast('Putting the animations on V5 of ' + r.sequence_name + '\u2026', { busy: true });
    const done = await bridge('layers', { result: r });
    const n = (r.layer_counts || {}).full || 0;
    toast(r.sequence_name + ' has ' + n + ' animation' + (n === 1 ? '' : 's') + ' on V5.' + layerNote(Object.assign({}, r, { layer_note: '' }), done));
  } else {
    toast('Bringing the animations into Premiere\u2026', { busy: true });
    await bridge('import', { result: r });
    toast(r.sequence_name + ' is open with ' + r.shots + ' animation clips.');
  }
  await refreshSource();
}

function layerNote(r, done) {
  // what the recut put back, and anything the panel couldn't finish
  return (r.layer_note ? ' ' + r.layer_note : '') + (done && done.note ? ' ' + done.note : '');
}

// ------------------------------------------------------------ events

async function go(screen) {
  S.screen = screen; S.sel = null;
  if (screen === 'settings') api('/costs').then((c) => { S.costs = c; if (S.screen === 'settings') render(); }).catch(() => {});
  if (screen === 'settings') api('/prefs').then((p) => { S.prefs = p; if (S.screen === 'settings') render(); }).catch(() => {});
  if (!S.running && $("toast").className !== "err") hideToast();
  $('view').scrollTop = 0;
  render();
  if (screen === 'clean') loadClean();
  if (screen === 'styles') { try { await loadStyles(); } catch (e) { toast(e.message, { error: true }); } render(); }
  if (screen === 'flubs' && S.project && S.project.has_flubs && !S.flubs) { try { await loadFlubs(false); } catch (e) { /* shown later */ } render(); }
}

$('back').onclick = () => go('home');
$('gear').onclick = () => go(S.screen === 'settings' ? 'home' : 'settings');
$('toastClose').onclick = hideToast;
$('toastLog').onclick = () => { const l = $('log'); l.className = l.className ? '' : 'hidden'; };
$('toastCancel').onclick = async () => { if (S.running) { try { await api('/cancel/' + S.running.job, {}); } catch (e) { /* ignore */ } } };

$('main').onclick = () => guarded(async () => {
  if (S.screen === 'settings') {
    await api('/settings', { api_key: ($('apiKey').value || '').trim() });
    toast('Key saved.'); await checkHelper(); S.screen = 'home'; return;
  }
  if (S.screen === 'styles') return saveStyle();
  if (!S.src || !S.project) throw new Error(S.srcError || 'Josh Cut Pro can\'t read your sequence yet. Press refresh on the home screen.');
  if (S.screen === 'clean') return runClean();
  if (S.screen === 'flubs') return runFlubs();
  if (S.screen === 'anim') return runAnim();
});

$('view').addEventListener('mouseup', () => {
  if (S.screen === 'flubs' && selectionFromHighlight()) { S.keepScroll = true; render(); }
});

$('view').addEventListener('click', (ev) => {
  const t = ev.target.closest('[data-go],[data-track],[data-pref],[data-act],[data-w],[data-pace],[data-redo],[data-remove],[data-send],[data-nudge],[data-zoom],' +
    '[data-type-chip],[data-often],[data-rich],[data-half-side],[data-shape],[data-pip-side],[data-font],[data-preset],[data-motion],[data-look]');
  if (!t) return;
  const d = t.dataset;
  if (d.go) return go(d.go);
  if (d.track != null) { S.track = Number(d.track); S.preview = null; S.wave = null; S.flubs = null; S.keepScroll = true;
    return guarded(async () => { S.project = await api('/project?video=' + encodeURIComponent(S.src.video)); render(); if (S.screen === 'clean') loadClean(); }); }
  if (d.pref) return guarded(async () => { S.prefs = await api('/prefs', { [d.pref]: !S.prefs[d.pref] }); S.keepScroll = true; });
  if (d.w != null) { if (!window.getSelection().isCollapsed) return; const i = Number(d.w); S.sel = [i, i]; S.keepScroll = true; return render(); }
  if (d.pace) { S.silence = Object.assign({}, S.silence, S.project.presets[d.pace], { preset: d.pace }); S.keepScroll = true; render(); return schedulePreview(0); }
  if (d.nudge) return nudge(d.nudge);   // moves the still in place, so the page doesn't jump
  if (d.zoom) { const lb = document.createElement('div'); lb.className = 'lightbox'; lb.innerHTML = '<img src="' + t.src + '">'; lb.onclick = () => lb.remove(); document.body.appendChild(lb); return; }
  if (d.redo) { S.redoOpen[d.redo] = !S.redoOpen[d.redo]; S.keepScroll = true; return render(); }
  if (d.typeChip) {
    const on = new Set(S.anim.types);
    if (on.has(d.typeChip)) { if (on.size > 1) on.delete(d.typeChip); } else on.add(d.typeChip);
    return setAnim({ types: TYPE_ORDER.filter((x) => on.has(x)) });
  }
  if (d.often) return setAnim({ often: d.often });
  if (d.rich) return setAnim({ rich: d.rich });
  if (d.halfSide) return setAnim({ half_side: d.halfSide });
  if (d.shape) return setAnim({ pip_shape: d.shape }, { inPlace: true, reframe: true });
  if (d.pipSide) return setAnim({ pip_side: d.pipSide }, { inPlace: true, reframe: true });
  if (d.font) return setStyle({ fonts: d.font });
  if (d.preset) return setStyle({ colors: d.preset === '__custom' ? Object.assign({}, S.edit.resolved_colors) : d.preset });
  if (d.motion) return setStyle({ motion: d.motion });
  if (d.look) return setStyle({ look: d.look });
  if (d.remove) return guarded(async () => { await api('/shotlist/edit', { video: S.src.video, delete: Number(d.remove) }); S.keepScroll = true; await refreshSource(); });
  if (d.send) return guarded(async () => {
    const n = Number(d.send), note = ($('redo-' + n) || {}).value || '';
    await job('redo', req({ number: n, note })); S.redoOpen[n] = false; await refreshSource(); toast('Animation ' + n + ' has been reworked.');
  });
  const act = d.act;
  if (act === 'refresh') return refreshSource();
  if (act === 'auto') {
    const thr = S.preview && S.preview.threshold_db != null ? S.preview.threshold_db : -40;
    S.silence = Object.assign({}, S.silence, { threshold_db: S.silence.threshold_db == null ? thr : null });
    S.keepScroll = true; render(); return schedulePreview(0);
  }
  if (act === 'sounds') { S.silence = Object.assign({}, S.silence, { cut_sounds: S.silence.cut_sounds === false }); S.keepScroll = true; render(); return schedulePreview(0); }
  if (act === 'cutSel' || act === 'keepSel') {
    for (let i = S.sel[0]; i <= S.sel[1]; i++) { if (act === 'cutSel') S.flubs.cut.add(i); else S.flubs.cut.delete(i); }
    S.sel = null; S.keepScroll = true; return render();
  }
  if (act === 'clearSel') { S.sel = null; S.keepScroll = true; return render(); }
  if (act === 'resetFlubs') { S.flubs.cut = new Set(S.flubs.proposed); S.keepScroll = true; return render(); }
  if (act === 'plan') return guarded(planAnim);
  if (act === 'probe') return guarded(async () => {
    toast('Checking how Premiere edits, on a copy of your sequence\u2026', { busy: true });
    const r = await bridge('probe');
    const order = r.strategy ? r.strategy.order_name : 'none';
    toast(r.ok ? 'Premiere check passed. Cutting in place will work on this version.' :
      'Premiere check found a problem (trim order ' + order + '). The details are in Projects\\premiere-probe.json.', { error: !r.ok });
  });
  if (act === 'log') { $('toast').className = ''; $('log').className = ''; $('ring').className = 'hidden'; $('toastMsg').textContent = 'Helper log'; return; }
  if (act === 'quit') return guarded(async () => { await api('/quit', {}); window.close(); });
});

$('view').addEventListener('change', (ev) => {
  const d = ev.target.dataset || {};
  if (d.animStyle) return setAnim({ style: ev.target.value });
  if (d.typeOf) return guarded(async () => { await api('/shotlist/edit', { video: S.src.video, number: Number(d.typeOf), type: ev.target.value }); S.keepScroll = true; await refreshSource(); });
  if (d.pickStyle) {
    if (ev.target.value === '__new') { S.edit = Object.assign({}, S.edit, { name: S.edit.name + ' copy', key: null }); S.keepScroll = true; return render(); }
    S.edit = Object.assign({}, S.styleList[ev.target.value]); S.keepScroll = true; return render();
  }
  if (d.color) {
    const c = Object.assign({}, typeof S.edit.colors === 'object' ? S.edit.colors : S.edit.resolved_colors, { [d.color]: ev.target.value.toUpperCase() });
    return setStyle({ colors: c, resolved_colors: c });
  }
});

$('view').addEventListener('input', (ev) => {
  if (ev.target.id === 'styleName' && S.edit) { S.edit.name = ev.target.value; return; }
  const key = ev.target.dataset && ev.target.dataset.key;
  if (!key) return;
  const v = Number(ev.target.value);
  ev.target.style.setProperty('--p', ((v - ev.target.min) / (ev.target.max - ev.target.min) * 100).toFixed(1) + '%');
  S.silence = Object.assign({}, S.silence, { [key]: v, preset: key === 'threshold_db' ? S.silence.preset : null });
  if (key === 'pad_after') S.silence.pad_before = Math.round(v * .8 * 100) / 100;
  $('v-' + key).textContent = UNITS[key](v);
  if (key !== 'threshold_db') document.querySelectorAll('[data-pace]').forEach((b) => b.className = '');
  drawWave();
  schedulePreview();
});

window.addEventListener('resize', () => { if (S.screen === 'clean') drawWave(); });

render();
// every time the window opens, each recording starts fresh
api('/session', {}).catch(() => {}).then(checkHelper).then(() => { if (!S.src) refreshSource(); });
setInterval(() => { if (!S.running) checkHelper(); }, 2000);
