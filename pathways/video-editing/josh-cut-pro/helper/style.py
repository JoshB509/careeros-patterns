"""Styles for the animations: fonts, colours, motion and look, saved as styles/<name>.json.

A style only changes CSS variables and which kit files load. Scenes are written
against the kit's classes and variables, so the same shot list re-renders in
any style with no new work from Claude.

The PiP shape and side, and which side the half-and-half panel comes from, are
also turned into CSS variables here, along with the mask that cuts the
see-through hole in alpha renders.
"""
import base64, json, os, re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / 'templates' / 'kit'
FONTS = ROOT / 'templates' / 'fonts'
STYLES = Path(os.environ.get('DAJOSHI_CUT_STYLES') or ROOT / 'styles')
KIT_VERSION = 1

# heading font, body font, and the woff2 files each needs (house fonts are already in the deck template)
PAIRINGS = {
    'house': dict(label='House', head='Outfit', body='Manrope', files=[]),
    'editorial': dict(label='Editorial', head='Fraunces', body='Inter',
                      files=[('Fraunces', 600, 'Fraunces-SemiBold.woff2'), ('Fraunces', 800, 'Fraunces-ExtraBold.woff2'),
                             ('Inter', 500, 'Inter-Medium.woff2'), ('Inter', 700, 'Inter-Bold.woff2')]),
    'modern': dict(label='Modern', head='Space Grotesk', body='Inter',
                   files=[('Space Grotesk', 600, 'SpaceGrotesk-SemiBold.woff2'), ('Space Grotesk', 700, 'SpaceGrotesk-Bold.woff2'),
                          ('Inter', 500, 'Inter-Medium.woff2'), ('Inter', 700, 'Inter-Bold.woff2')]),
    'bold': dict(label='Bold', head='Anton', body='Work Sans',
                 files=[('Anton', 400, 'Anton-Regular.woff2'), ('Work Sans', 500, 'WorkSans-Medium.woff2'),
                        ('Work Sans', 700, 'WorkSans-Bold.woff2')]),
    'friendly': dict(label='Friendly', head='Poppins', body='Nunito',
                     files=[('Poppins', 600, 'Poppins-SemiBold.woff2'), ('Poppins', 800, 'Poppins-ExtraBold.woff2'),
                            ('Nunito', 600, 'Nunito-SemiBold.woff2'), ('Nunito', 800, 'Nunito-ExtraBold.woff2')]),
}

PRESETS = {
    'ink-gold': dict(label='Ink and Gold', background='#FFFFFF', surface='#FFFFFF', text='#15171C', primary='#F5C21B', accent='#C4453A'),
    'paper': dict(label='Paper', background='#F4EEE2', surface='#FFFCF5', text='#1F1B16', primary='#C8372D', accent='#2F5D8A'),
    'midnight': dict(label='Midnight', background='#101B30', surface='#18263F', text='#F1F3F8', primary='#FF7A5C', accent='#7FB7FF'),
    'mono': dict(label='Mono', background='#FFFFFF', surface='#F6F6F6', text='#111111', primary='#2F6BFF', accent='#111111'),
    'newsprint': dict(label='Newsprint', background='#FFE14D', surface='#FFF4B0', text='#111111', primary='#111111', accent='#E63B2E'),
}

MOTIONS = dict(formal='Formal', floaty='Floaty', bouncy='Bouncy')
LOOKS = dict(editorial='Editorial', modern='Modern', bold='Bold')
COLOR_KEYS = ('background', 'surface', 'text', 'primary', 'accent')

HOUSE = dict(name='Josh house', fonts='house', colors='ink-gold', motion='formal', look='editorial')

# PiP shapes as the outer box (border included) on the right of a 1920 by 1080 frame
SHAPES = {
    'small-circle': dict(label='Small circle', box=[1430, 350, 380, 380], round=True),
    'large-circle': dict(label='Large circle', box=[1310, 270, 540, 540], round=True),
    'small-box': dict(label='Small box', box=[1420, 390, 420, 315], round=False),
    'large-box': dict(label='Large box', box=[1290, 315, 560, 450], round=False),
    'tall-box': dict(label='Tall box', box=[1322, 202, 518, 674], round=False),
    'square': dict(label='Square', box=[1340, 300, 480, 480], round=False),
}
BORDER = 6
PIP_SHIFT = 570      # PiP content moves this far right when the camera sits on the left
HALF = 960


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'style'


# ---------------------------------------------------------------- colour maths

def rgb(hexstr):
    h = hexstr.lstrip('#')
    if len(h) == 3: h = ''.join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def hexc(c):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(x))) for x in c)


def mix(a, b, t):
    """t of the way from colour a to colour b."""
    a, b = rgb(a), rgb(b)
    return hexc([a[i] + (b[i] - a[i]) * t for i in range(3)])


def luminance(c):
    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    r, g, b = rgb(c)
    return .2126 * ch(r) + .7152 * ch(g) + .0722 * ch(b)


def contrast(a, b):
    la, lb = sorted([luminance(a), luminance(b)], reverse=True)
    return (la + .05) / (lb + .05)


def readable(color, against, text, target=3.0):
    """The colour, pulled toward the text colour until it reads against the background."""
    for i in range(11):
        c = mix(color, text, i / 10.0)
        if contrast(c, against) >= target: return c
    return text


def triple(c):
    return '%d,%d,%d' % rgb(c)


# ---------------------------------------------------------------- styles on disk

def colors_of(style):
    c = style.get('colors', 'ink-gold')
    if isinstance(c, str): c = PRESETS.get(c, PRESETS['ink-gold'])
    return {k: c.get(k, PRESETS['ink-gold'][k]).upper() for k in COLOR_KEYS}


def clean(style):
    s = dict(HOUSE); s.update({k: v for k, v in (style or {}).items() if k in HOUSE})
    if s['fonts'] not in PAIRINGS: s['fonts'] = 'house'
    if s['motion'] not in MOTIONS: s['motion'] = 'formal'
    if s['look'] not in LOOKS: s['look'] = 'editorial'
    if isinstance(s['colors'], dict):
        s['colors'] = {k: v.upper() for k, v in s['colors'].items() if k in COLOR_KEYS and re.fullmatch(r'#[0-9A-Fa-f]{6}', str(v))}
        if len(s['colors']) != len(COLOR_KEYS): s['colors'] = 'ink-gold'
    elif s['colors'] not in PRESETS:
        s['colors'] = 'ink-gold'
    s['name'] = str(s['name']).strip()[:40] or 'Untitled'
    return s


def list_styles():
    STYLES.mkdir(exist_ok=True)
    out = {slug(HOUSE['name']): dict(HOUSE)}
    for f in sorted(STYLES.glob('*.json')):
        try: out[f.stem] = clean(json.loads(f.read_text(encoding='utf-8-sig')))
        except Exception: pass
    return out


def load(name):
    return list_styles().get(name or slug(HOUSE['name'])) or dict(HOUSE)


def save(style):
    s = clean(style); STYLES.mkdir(exist_ok=True)
    key = slug(s['name'])
    (STYLES / (key + '.json')).write_text(json.dumps(s, indent=2), encoding='utf-8')
    return key, s


def warnings(style):
    c = colors_of(style); out = []
    if contrast(c['text'], c['background']) < 4.5:
        out.append('Text against the background is %.1f to 1, under the 4.5 to 1 that reads well.' % contrast(c['text'], c['background']))
    if contrast(c['text'], c['surface']) < 4.5:
        out.append('Text on cards is %.1f to 1, under the 4.5 to 1 that reads well.' % contrast(c['text'], c['surface']))
    missing = missing_fonts(style)
    if missing: out.append('The %s fonts aren\'t on this PC yet, so this pairing can\'t render.' % PAIRINGS[style['fonts']]['label'])
    return out


def missing_fonts(style):
    return [f for _, _, f in PAIRINGS[clean(style)['fonts']]['files'] if not (FONTS / f).exists()]


# ---------------------------------------------------------------- CSS

def tokens(style):
    """:root variables. The deck template's own names (--gold, --ink and so on) are kept so its components follow the style."""
    c = colors_of(style); bg, surf, text, prim, acc = (c[k] for k in COLOR_KEYS)
    dark = luminance(bg) < luminance(text)
    shadow = '0,0,0' if dark else triple(text)
    v = {
        '--white': bg, '--bg': bg, '--canvas': mix(bg, text, .02), '--surface': surf,
        '--grey': mix(surf, text, .05), '--grey-2': mix(surf, text, .09), '--line': mix(surf, text, .13),
        '--ink': text, '--text': mix(text, bg, .1), '--muted': mix(text, bg, .45), '--faint': mix(text, bg, .62),
        '--gold': prim, '--gold-deep': readable(prim, bg, text), '--gold-tint': mix(prim, surf, .8), '--gold-line': mix(prim, surf, .5),
        '--accent': acc, '--accent-deep': readable(acc, bg, text), '--accent-tint': mix(acc, surf, .82),
        '--on-ink': bg, '--on-gold': text if contrast(text, prim) >= contrast(bg, prim) else bg,
        '--primary-rgb': triple(prim), '--text-rgb': triple(text), '--shadow-rgb': shadow, '--deep-rgb': triple(readable(prim, bg, text)),
        '--font-head': "'%s'" % PAIRINGS[style['fonts']]['head'], '--font-body': "'%s'" % PAIRINGS[style['fonts']]['body'],
    }
    return ':root{' + ';'.join('%s:%s' % kv for kv in v.items()) + '}'


def font_faces(style):
    out = []
    for family, weight, f in PAIRINGS[style['fonts']]['files']:
        p = FONTS / f
        if not p.exists(): raise ValueError('The %s font file %s is missing from templates\\fonts' % (family, f))
        out.append("@font-face{font-family:'%s';font-weight:%d;font-style:normal;src:url(data:font/woff2;base64,%s) format('woff2')}"
                   % (family, weight, base64.b64encode(p.read_bytes()).decode()))
    return '\n'.join(out)


def theme_template_css(css):
    """Point the deck template's fixed fonts and colours at the style's variables. @font-face rules are left alone."""
    faces = []
    css = re.sub(r'@font-face\s*\{[^}]*\}', lambda m: faces.append(m.group(0)) or '\x00FACE%d\x00' % (len(faces) - 1), css)
    css = _theme_rules(css)
    return re.sub(r'\x00FACE(\d+)\x00', lambda m: faces[int(m.group(1))], css)


def _theme_rules(css):
    css = re.sub(r"font-family:\s*'Outfit'(?:\s*,\s*'Manrope')?(?:\s*,\s*sans-serif)?", 'font-family:var(--font-head)', css)
    css = re.sub(r"font-family:\s*'Manrope'(?:\s*,\s*system-ui)?(?:\s*,\s*sans-serif)?", 'font-family:var(--font-body)', css)
    css = re.sub(r"(\d+px )(Manrope|Outfit)\b", lambda m: m.group(1) + ('var(--font-head)' if m.group(2) == 'Outfit' else 'var(--font-body)'), css)
    css = css.replace('rgba(245,194,27,', 'rgba(var(--primary-rgb),').replace('rgba(21,23,28,', 'rgba(var(--shadow-rgb),')
    css = css.replace('rgba(168,123,5,', 'rgba(var(--deep-rgb),')
    css = re.sub(r'background:\s*#fff\b', 'background:var(--surface)', css, flags=re.I)
    css = re.sub(r'(?<![-\w])color:\s*#fff\b', 'color:var(--on-ink)', css, flags=re.I)
    css = re.sub(r'background:\s*#D6D2C9', 'background:var(--grey-2)', css, flags=re.I)
    return css


def theme_scene(html):
    """The same fixes for a scene Claude wrote, in case it named a house font or white outright."""
    html = re.sub(r"font-family:\s*'?Outfit'?", 'font-family:var(--font-head)', html)
    html = re.sub(r"font-family:\s*'?Manrope'?", 'font-family:var(--font-body)', html)
    html = re.sub(r'(?<![-\w])color:\s*#fff(?:fff)?\b', 'color:var(--on-ink)', html, flags=re.I)
    html = re.sub(r'background:\s*#fff(?:fff)?\b', 'background:var(--surface)', html, flags=re.I)
    return html


def kit_css(style):
    parts = [(KIT / 'kit.css').read_text(encoding='utf-8'),
             (KIT / ('motion-%s.css' % style['motion'])).read_text(encoding='utf-8'),
             (KIT / ('look-%s.css' % style['look'])).read_text(encoding='utf-8')]
    return '\n'.join(parts)


def shape_of(opts):
    return SHAPES.get((opts or {}).get('pip_shape') or 'tall-box', SHAPES['tall-box'])


def pip_box(opts):
    """Outer box (with border) and inner hole, after the side is applied."""
    shape = shape_of(opts)
    x, y, w, h = shape['box']
    if (opts or {}).get('pip_side') == 'left': x = 1920 - x - w
    b = BORDER
    return dict(outer=[x, y, w, h], hole=[x + b, y + b, w - 2 * b, h - 2 * b], round=shape['round'])


def hole_mask(hole, round_):
    x, y, w, h = hole
    inner = ('M%g,%g a%g,%g 0 1,0 %g,0 a%g,%g 0 1,0 %g,0 Z' % (x, y + h / 2.0, w / 2.0, h / 2.0, w, w / 2.0, h / 2.0, -w)
             if round_ else 'M%g,%g h%g v%g h%g Z' % (x, y, w, h, -w))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"><path fill-rule="evenodd" fill="#000" '
           'd="M0,0 H1920 V1080 H0 Z %s"/></svg>' % inner)
    return 'url("data:image/svg+xml,%s")' % quote(svg)


def layout_css(opts):
    """Where the PiP camera and the half-and-half panel sit for this video."""
    p = pip_box(opts); x, y, w, h = p['outer']
    left = (opts or {}).get('pip_side') == 'left'
    half_right = (opts or {}).get('half_side') == 'right'
    panel = '--panel-from:100%;--panel-edge-l:0;--panel-edge-r:auto' if half_right else '--panel-from:-100%;--panel-edge-l:auto;--panel-edge-r:0'
    return (':root{--pip-x:%dpx;--pip-y:%dpx;--pip-w:%dpx;--pip-h:%dpx;--pip-r:%s;--pip-shift:%dpx;--half-shift:%dpx;%s;--pip-mask:%s}'
            % (x, y, w, h, '50%' if p['round'] else '0px', PIP_SHIFT if left else 0, HALF if half_right else 0, panel,
               hole_mask(p['hole'], p['round'])))


def camera_box(kind, opts):
    """The box the V4 camera copy has to fill, for the framing maths in pip.py."""
    if kind == 'pip':
        return pip_box(opts)['hole']
    return [0 if (opts or {}).get('half_side') == 'right' else HALF, 0, HALF, 1080] if kind == 'half' else None


def describe(style):
    s = clean(style); c = colors_of(s)
    return dict(s, key=slug(s['name']), resolved_colors=c, warnings=warnings(s), missing_fonts=missing_fonts(s))


def catalogue():
    return dict(pairings={k: dict(label=v['label'], head=v['head'], body=v['body'], ready=not [f for _, _, f in v['files'] if not (FONTS / f).exists()])
                          for k, v in PAIRINGS.items()},
                presets=PRESETS, motions=MOTIONS, looks=LOOKS,
                shapes={k: dict(label=v['label'], box=v['box'], round=v['round']) for k, v in SHAPES.items()})
