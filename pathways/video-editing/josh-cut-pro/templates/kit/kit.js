// Josh Cut Pro style kit. The deck template already marks PiP scenes on <body>.
// This does the same for the other shot types, so the kit CSS can lay them out.
(function () {
  const TYPES = ['half', 'kw', 'lt', 'title', 'end'];
  const base = render;
  render = function () {
    base();
    const cur = scenes.find((s) => s.classList.contains('on'));
    TYPES.forEach((t) => document.body.classList.toggle(t, !!(cur && cur.classList.contains(t))));
  };
  render();
})();
