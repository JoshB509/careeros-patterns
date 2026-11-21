"""Assemble Claude's scenes into the house deck template and number the beats.

The style kit (templates/kit) loads after the template's own CSS, and the
template's fixed fonts and colours are pointed at the style's variables, so
one set of scenes renders in any style.
"""
import hashlib, html, re
from pathlib import Path

import style as styles

TEMPLATES = Path(__file__).resolve().parent.parent / 'templates'

# shot type -> the scene class it renders with
SCENE_CLASS = dict(full='scene fs', pip='scene pip', half='scene half', end='scene end', kw='scene kw',
                   title='scene title', lt='scene lt')
TYPE_LABEL = dict(full='Full screen', pip='Picture in picture', half='Half and half', end='Watch next end screen',
                  kw='Key word pop', title='Title card', lt='Lower third')
# shot types that render with a transparent background, so the camera on the track below shows through
ALPHA = {'pip', 'half', 'kw', 'lt'}
# shot types whose layout depends on the PiP shape or the half-and-half side
LAYOUT = {'pip', 'half'}


def template():
    return (TEMPLATES / 'deck-template.html').read_text(encoding='utf-8')


def prompt_css():
    t = template()
    css = t[t.find('<style>') + 7: t.find('</style>')]
    css = styles.theme_template_css(re.sub(r'@font-face\s*\{[^}]*\}\s*', '', css).strip())
    return css + '\n\n/* style kit */\n' + (styles.KIT / 'kit.css').read_text(encoding='utf-8')


def examples():
    return (TEMPLATES / 'example-scenes.html').read_text(encoding='utf-8')


def check_section(section, presses, kind):
    """Basic sanity checks on a generated scene. Returns a cleaned section."""
    section = section.strip()
    m = re.match(r'<section\b([^>]*)>', section)
    if not m:
        raise ValueError('Not a section element')
    want = SCENE_CLASS.get(kind, 'scene fs')
    attrs = re.sub(r'\s*data-(?:from|to)="[^"]*"', '', m.group(1))
    attrs = re.sub(r'class="[^"]*"', 'class="%s"' % want, attrs) if 'class=' in attrs else ' class="%s"%s' % (want, attrs)
    section = '<section%s>' % attrs + section[m.end():]
    if re.search(r'<script|<link|<style|https?://', section, re.I):
        raise ValueError('Scene contains scripts, styles or external links')
    used = [int(x) for x in re.findall(r'data-(?:b|off)="(\d+)"', section)]
    used += [int(p.split(':')[0]) for v in re.findall(r'data-cls="([^"]*)"', section) for p in v.split(',') if ':' in p]
    if used and (max(used) > presses or min(used) < 1):
        raise ValueError('Scene uses press %d but the animation has %d presses' % (max(used), presses))
    return section


def renumber(section, base):
    """Press numbers 1..N become absolute deck beats base+1..base+N."""
    section = re.sub(r'(data-(?:b|off))="(\d+)"', lambda m: '%s="%d"' % (m.group(1), int(m.group(2)) + base), section)
    section = re.sub(r'data-cls="([^"]*)"', lambda m: 'data-cls="%s"' % ','.join(
        '%d:%s' % (int(p.split(':', 1)[0]) + base, p.split(':', 1)[1]) for p in m.group(1).split(',') if ':' in p), section)
    return section


def furnish(section, kind):
    """Parts the kit always adds, so every shot of a type looks the same."""
    first = section.index('>') + 1
    if kind == 'half' and 'k-panel' not in section:
        section = section[:first] + '<div class="k-panel"></div>' + section[first:]
    if kind == 'end':
        add = ''.join('<div class="%s"></div>' % c for c in ('k-endvideo', 'k-endsub') if c not in section)
        section = section[:first] + add + section[first:]
    return styles.theme_scene(section)


def page_css(style, opts):
    """The style's CSS and the per-video layout CSS, kept apart so a PiP change only touches PiP renders."""
    s = styles.clean(style)
    base = '\n'.join([styles.font_faces(s), styles.tokens(s), styles.kit_css(s)])
    return base, styles.layout_css(opts)


def assemble(title, animations, style=None, opts=None):
    """animations: list of dict(number, type, name, presses, section).

    Returns (html, beats, keys). keys holds a render key per animation that
    changes only when that animation's scene, the style, or (for PiP and half
    and half) the layout changes."""
    s = styles.clean(style or styles.HOUSE)
    base_css, layout = page_css(s, opts)
    base_hash = hashlib.sha1((template() + base_css + (styles.KIT / 'kit.js').read_text(encoding='utf-8')).encode()).hexdigest()
    # PiP renders depend on the shape and side, half and half on the panel side, and nothing else on either
    layout_hash = dict(pip=str(styles.pip_box(opts)), half=str((opts or {}).get('half_side', 'left')))
    beat, scenes, beats, keys = 0, [], {}, {}
    for a in animations:
        n = len(a['presses'])
        kind = a['type'] if a['type'] in SCENE_CLASS else 'full'
        scenes.append('<!-- %d marker -->\n<section class="scene mark" data-from="%d" data-to="%d">\n'
                      '  <div class="mk"><div class="mn">%d</div><div class="ml">%s</div><div class="mt">%s</div></div>\n</section>'
                      % (a['number'], beat, beat, a['number'], TYPE_LABEL[kind], html.escape(a['name'])))
        section = furnish(a['section'], kind)
        keys[a['number']] = hashlib.sha1(json_key([section, base_hash, layout_hash.get(kind, ''), kind])).hexdigest()[:12]
        body = renumber(section, beat)
        body = body.replace('<section', '<section data-from="%d" data-to="%d"' % (beat + 1, beat + n), 1)
        scenes.append('<!-- %d scene -->\n%s' % (a['number'], body))
        beats[a['number']] = [beat + p for p in range(1, n + 1)]
        beat += n + 1
    total = beat - 1
    page = template()
    head, rest = page.split('<style>', 1)
    css, tail = rest.split('</style>', 1)
    css = styles.theme_template_css(css)
    page = head + '<style>' + css + '\n/* style: %s */\n' % html.escape(s['name']) + base_css + '\n' + layout + '\n</style>' + tail
    page = page.replace('<div id="stage">', '<div id="stage">\n<div id="camfill" class="camera">CAMERA</div>', 1)
    kit_js = (styles.KIT / 'kit.js').read_text(encoding='utf-8')
    page = page.replace('</body>', '<script>\n' + kit_js + '</script>\n</body>', 1)
    page = page.replace('<!--SCENES-->', '\n'.join(scenes)).replace('__TOTAL__', str(total))
    page = page.replace('__TITLE__', html.escape(title))
    return page, beats, keys


def json_key(parts):
    return '\x1f'.join(str(p) for p in parts).encode()
