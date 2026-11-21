"""Frame the camera inside the gold PiP box for picture-in-picture shots.

The rendered animation already draws the box (gold border and drop shadow).
Here the camera clip above it is scaled, cropped and positioned so it fills
exactly the inside of that box, the same way on every PiP shot.
"""
import xml.etree.ElementTree as ET

DEFAULT = dict(box=[1322, 202, 518, 674], border=6, zoom=1.0, shift=0.0, shift_y=0.0)


def framing(cfg, src_w, src_h):
    c = dict(DEFAULT); c.update(cfg or {})
    x, y, w, h = c['box']; b = c['border']
    win, hin = w - 2 * b, h - 2 * b
    cx, cy = x + w / 2.0, y + h / 2.0
    s = hin * float(c['zoom']) / src_h            # source px -> sequence px
    disp_w, disp_h = src_w * s, src_h * s
    cut_w = max(0.0, 1 - win / disp_w)
    cut_h = max(0.0, 1 - hin / disp_h)
    shift = max(-1.0, min(1.0, float(c['shift'])))
    shift_y = max(-1.0, min(1.0, float(c.get('shift_y', 0))))
    left, right = cut_w * (1 + shift) / 2, cut_w * (1 - shift) / 2
    top, bottom = cut_h * (1 + shift_y) / 2, cut_h * (1 - shift_y) / 2
    ax = cx - (left - right) / 2 * disp_w        # anchor so the visible part is centred in the box
    ay = cy - (top - bottom) / 2 * disp_h
    # slack: how far (in sequence pixels) Josh moves inside the shape when shift goes from 0 to 1
    return dict(scale=100 * s, horiz=(ax - 960) / src_w, vert=(ay - 540) / src_h, x=ax, y=ay,
                slack_x=cut_w * disp_w / 2, slack_y=cut_h * disp_h / 2,
                left=100 * left, right=100 * right, top=100 * top, bottom=100 * bottom)


def _param(effect, pid, value, lo=0, hi=100):
    p = ET.SubElement(effect, 'parameter')
    for k, v in [('parameterid', pid), ('name', pid), ('valuemin', lo), ('valuemax', hi), ('value', '%.4f' % value)]:
        ET.SubElement(p, k).text = str(v)


def apply(xml_text, mapping, shots, video, cfg):
    """Rewrite camera clips that fall in PiP shots. Returns new XML text."""
    from dajoshi.timing import split_spans
    from dajoshi.export import layout_at
    if not any(s['layout'] == 'pip' for s in shots):
        return xml_text, 0
    f = framing(cfg, video['width'], video['height'])
    head, body = xml_text.split('<xmeml', 1)
    root = ET.fromstring('<xmeml' + body)
    tracks = root.findall('sequence/media/video/track')
    camera = tracks[1]
    spans = split_spans(mapping, [x for s in shots for x in [s['out_start'], s['out_end']]])
    changed = 0
    for i, s in enumerate(spans, 1):
        if layout_at(shots, s['out_in_frame'])['layout'] != 'pip':
            continue
        clip = camera.find("clipitem[@id='video-%d']" % i)
        if clip is None:
            continue
        for p in clip.iter('parameter'):
            pid = p.findtext('parameterid')
            if pid == 'scale':
                p.find('value').text = '%.4f' % f['scale']
            elif pid == 'center':
                v = p.find('value'); v.find('horiz').text = '%.6f' % f['horiz']; v.find('vert').text = '%.6f' % f['vert']
        new = ET.Element('filter'); effect = ET.SubElement(new, 'effect')
        for k, v in [('name', 'Crop'), ('effectid', 'crop'), ('effectcategory', 'motion'), ('effecttype', 'motion'), ('mediatype', 'video')]:
            ET.SubElement(effect, k).text = v
        for side in ['left', 'right', 'top', 'bottom']:
            _param(effect, side, f[side])
        _param(effect, 'edgefeather', 0)
        # Keep the filters together, ahead of the links, so the file still matches the XMEML DTD.
        filters = clip.findall('filter')
        idx = list(clip).index(filters[-1]) + 1 if filters else len(list(clip))
        clip.insert(idx, new)
        changed += 1
    ET.indent(root)
    return head + ET.tostring(root, encoding='unicode'), changed


def preview(cfg, video, ffmpeg, out, at=None):
    """Draw the camera inside the gold box on a plain frame, for the panel's nudge preview."""
    import subprocess
    c = dict(DEFAULT); c.update(cfg or {})
    w, h = video['width'], video['height']
    f = framing(c, w, h)
    W, H = round(w * f['scale'] / 100), round(h * f['scale'] / 100)
    cl, cr = round(W * f['left'] / 100), round(W * f['right'] / 100)
    ct, cb = round(H * f['top'] / 100), round(H * f['bottom'] / 100)
    x = round(960 + f['horiz'] * w - W / 2) + cl
    y = round(540 + f['vert'] * h - H / 2) + ct
    bx, by, bw, bh = c['box']; b = c['border']
    t = at if at is not None else min(30.0, float(video['duration']) / 2)
    left = bx < 960
    cx = 1920 - 110 - 1000 if left else 110
    if c.get('round'):
        # a circle: gold disc for the border, the camera cut to a circle inside it
        disc = "format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='if(lte(hypot(X-W/2,Y-H/2),W/2),255,0)'"
        graph = ('color=c=0xFFFFFF:s=1920x1080[bg];'
                 'color=c=0xF5C21B:s=%dx%d,%s[gold];'
                 '[0:v]scale=%d:%d,crop=%d:%d:%d:%d,%s[cam];'
                 '[bg][gold]overlay=%d:%d[gb];'
                 '[gb][cam]overlay=%d:%d,drawbox=x=%d:y=300:w=1000:h=110:color=0xFDF1C7:t=fill,'
                 'drawbox=x=%d:y=470:w=1000:h=110:color=0xF3F2EF:t=fill,scale=960:540'
                 % (bw, bh, disc, W, H, W - cl - cr, H - ct - cb, cl, ct, disc, bx, by, x, y, cx, cx))
    else:
        graph = ('color=c=0xFFFFFF:s=1920x1080[bg];'
                 '[bg]drawbox=x=%d:y=%d:w=%d:h=%d:color=0x15171C@0.10:t=fill[sh];'
                 '[sh]drawbox=x=%d:y=%d:w=%d:h=%d:color=0xF5C21B:t=fill[gb];'
                 '[0:v]scale=%d:%d,crop=%d:%d:%d:%d[cam];'
                 '[gb][cam]overlay=%d:%d,drawbox=x=%d:y=300:w=1000:h=110:color=0xFDF1C7:t=fill,'
                 'drawbox=x=%d:y=470:w=1000:h=110:color=0xF3F2EF:t=fill,scale=960:540'
                 % (bx + 6, by + 14, bw, bh, bx, by, bw, bh, W, H, W - cl - cr, H - ct - cb, cl, ct, x, y, cx, cx))
    subprocess.run([ffmpeg, '-v', 'error', '-y', '-ss', '%.2f' % t, '-i', video['path'], '-filter_complex', graph,
                    '-frames:v', '1', str(out)], check=True, timeout=60,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return out
