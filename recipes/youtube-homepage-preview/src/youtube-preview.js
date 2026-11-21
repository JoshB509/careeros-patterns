/* YouTube-style card and homepage preview. A recipe from careeros-patterns.
 *
 * Lets a creator see their thumbnail as a viewer meets it: as a home-feed card (rounded 16:9 thumbnail, duration
 * badge, avatar, bold title, channel, views and age), and inside a full home-feed mock surrounded by other videos.
 *
 * No dependencies and no build step. Load this file and youtube-preview.css, then call:
 *   YouTubePreview.card({...})            -> an HTML string for one card
 *   YouTubePreview.openHomepage({...})    -> opens the full-screen preview, returns the <dialog>
 *
 * It only draws on the page. It never contacts YouTube and saves nothing.
 * Not affiliated with or endorsed by YouTube.
 */
(function (root) {
  'use strict';

  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  // 346951 -> "347K", 1200000 -> "1.2M"
  function views(n) {
    n = Number(n);
    if (!isFinite(n) || n < 0) return '';
    if (n < 1e3) return String(Math.round(n));
    if (n < 1e6) return (n < 1e4 ? (n / 1e3).toFixed(1).replace(/\.0$/, '') : Math.round(n / 1e3)) + 'K';
    return (n < 1e7 ? (n / 1e6).toFixed(1).replace(/\.0$/, '') : Math.round(n / 1e6)) + 'M';
  }

  // "2026-03-17" -> "8 months ago", relative to `now` (a Date, default today)
  function ago(day, now) {
    const d = Math.floor(((now || new Date()) - new Date(day + 'T00:00:00Z')) / 864e5);
    if (!(d >= 0)) return '';
    if (d < 1) return 'today';
    const [n, unit] = d < 7 ? [d, 'day'] : d < 31 ? [Math.floor(d / 7), 'week'] : d < 365 ? [Math.floor(d / 30.4), 'month'] : [Math.floor(d / 365), 'year'];
    return `${n} ${unit}${n === 1 ? '' : 's'} ago`;
  }

  // A small seeded shuffle, so the same seed always gives the same feed.
  function rand(seed) {
    let s = (seed >>> 0) || 1;
    return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296; };
  }
  function shuffle(list, r) {
    return list.map(x => [r(), x]).sort((a, b) => a[0] - b[0]).map(x => x[1]);
  }

  function avatar(name, mine, src) {
    if (src) return `<img class="yc-av" src="${esc(src)}" alt="" aria-hidden="true">`;
    const n = String(name || '').trim();
    return `<span class="yc-av ${mine ? 'mine' : ''}" aria-hidden="true">${n ? esc(n[0].toUpperCase()) : ''}</span>`;
  }

  /* One card.
   *   image     thumbnail URL (16:9 works best)
   *   title     video title (clamped to two lines, like the home feed)
   *   channel   channel name; leave empty to hide the line and show a blank avatar
   *   avatar    optional avatar image URL; otherwise the channel's first letter
   *   stats     optional line under the channel, e.g. "123K views • 3 days ago"
   *   duration  optional badge text, e.g. "12:38"
   *   mine      true for the creator's own card (dark avatar, marked for tests and styling)
   */
  function card(o) {
    o = o || {};
    return `<div class="yc ${o.mine ? 'mine' : ''}">
      <div class="yc-thumb">${o.image ? `<img src="${esc(o.image)}" alt="${esc(o.alt || o.title)}" loading="lazy" decoding="async">` : ''}${o.duration ? `<span class="yc-dur">${esc(o.duration)}</span>` : ''}</div>
      <div class="yc-meta">${avatar(o.channel, o.mine, o.avatar)}<div class="yc-text"><h3 class="yc-title">${esc(o.title)}</h3>${o.channel ? `<p class="yc-line">${esc(o.channel)}</p>` : ''}${o.stats ? `<p class="yc-line">${esc(o.stats)}</p>` : ''}</div></div>
    </div>`;
  }

  // A reference video's stats line from saved data only: views and/or a publish date. Nothing is made up.
  function refStats(r, now) {
    const parts = [];
    if (r.views != null && r.views !== '') parts.push(views(r.views) + ' views');
    if (r.published) parts.push(ago(r.published, now));
    return parts.filter(Boolean).join(' • ');
  }

  const ICON = d => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${d}"/></svg>`;

  /* The full-screen home-feed preview.
   *   candidates   the creator's own cards to try, e.g. thumbnails A, B and C: [{image, title, channel, stats, duration, label}]
   *   references   other videos to fill the feed: [{image, title, channel, views, published}]
   *   rank         which candidate to show first (default 0)
   *   insertAt     position of the creator's card in the feed (default 1, the middle of the first row)
   *   size         how many cards in total (default 12)
   *   seed         number for the shuffle (default 1); the Shuffle button changes it
   *   chips        category chips along the top (just for looks)
   *   viewer       name for the avatar in the top bar
   *   now          a Date used for "x days ago" (default today), handy in tests
   *   onClose      called after the preview closes
   */
  function openHomepage(opts) {
    const o = Object.assign({ rank: 0, insertAt: 1, size: 12, seed: 1, chips: ['All', 'Careers', 'Leadership', 'Communication', 'Presentations', 'Recently uploaded', 'New to you'], viewer: '' }, opts || {});
    const cands = (o.candidates || []).filter(c => c && c.image);
    if (!cands.length) throw new Error('openHomepage needs at least one candidate with an image.');
    const state = { rank: Math.min(o.rank, cands.length - 1), seed: o.seed };
    document.querySelector('dialog.yh')?.remove();
    const d = document.createElement('dialog');
    d.className = 'yh';
    d.setAttribute('aria-label', 'Homepage preview');
    document.body.append(d);
    d.addEventListener('close', () => { d.remove(); if (o.onClose) o.onClose(); });

    function draw() {
      const r = rand(state.seed);
      const others = shuffle((o.references || []).filter(x => x && x.image), r).slice(0, Math.max(0, o.size - 1));
      const cards = others.map(x => `<article class="yh-card">${card({ image: x.image, title: x.title, channel: x.channel, stats: refStats(x, o.now), duration: x.duration })}</article>`);
      const mine = cands[state.rank];
      cards.splice(Math.min(o.insertAt, cards.length), 0, `<article class="yh-card mine">${card(Object.assign({ mine: true }, mine))}</article>`);
      d.innerHTML = `<header class="yh-top"><span class="yh-ico">${ICON('M3 6h18M3 12h18M3 18h18')}</span><span class="yh-logo"><i aria-hidden="true"></i>Home</span>
          <div class="yh-search"><input readonly tabindex="-1" placeholder="Search" aria-label="Search, preview only"><span class="yh-ico">${ICON('M10.5 4a6.5 6.5 0 1 1 0 13 6.5 6.5 0 0 1 0-13zM15.5 15.5 20 20')}</span></div>
          ${avatar(o.viewer || mine.channel, true)}</header>
        <div class="yh-body"><nav class="yh-side" aria-hidden="true">${[['Home', 'M4 11 12 4l8 7v9h-5v-6H9v6H4z'], ['Shorts', 'M9 7l7 5-7 5z'], ['Subscriptions', 'M4 7h16v12H4zM7 4h10'], ['You', 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20c1-4 5-5 8-5s7 1 8 5']].map(([n, p], i) => `<span class="${i ? '' : 'on'}">${ICON(p)}<small>${n}</small></span>`).join('')}</nav>
          <main class="yh-main"><div class="yh-chips" aria-hidden="true">${o.chips.map((c, i) => `<span class="${i ? '' : 'on'}">${esc(c)}</span>`).join('')}</div>
            <div class="yh-grid">${cards.join('')}</div></main></div>
        <div class="yh-bar" role="toolbar" aria-label="Preview controls">
          ${cands.length > 1 ? `<div class="yh-pick" role="group" aria-label="Which thumbnail">${cands.map((c, i) => `<button type="button" data-yh-rank="${i}" aria-pressed="${i === state.rank}" class="${i === state.rank ? 'on' : ''}">${esc(c.label || String.fromCharCode(65 + i))}</button>`).join('')}</div>` : ''}
          <button type="button" data-yh-shuffle>Shuffle</button><button type="button" data-yh-close>Close</button></div>`;
    }
    d.addEventListener('click', e => {
      const b = e.target.closest('[data-yh-rank],[data-yh-shuffle],[data-yh-close]');
      if (!b) return;
      if (b.hasAttribute('data-yh-close')) return d.close();
      if (b.hasAttribute('data-yh-shuffle')) state.seed = (state.seed * 48271) % 2147483647 || 1;
      else state.rank = Number(b.dataset.yhRank);
      draw();
    });
    draw();
    d.showModal();
    return d;
  }

  root.YouTubePreview = { card, openHomepage, views, ago, esc };
})(typeof window !== 'undefined' ? window : globalThis);
