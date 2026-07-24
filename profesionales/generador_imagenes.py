import os, urllib.request
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_HERE, 'fonts')
FONT_CACHE = '/tmp/fonts_apsi'

VERDE      = (125, 168, 123)
ROSA       = (233, 168, 166)
BLANCO     = (255, 255, 255)
NEGRO      = (30,  30,  30)
GRIS_MED   = (100, 100, 100)
VERDE_OSC  = (50,  82,  50)
CREMA      = (240, 235, 224)
GRIS_BLOB  = (190, 198, 188)
VERDE_PILL = (195, 215, 193)
COLOR_MAP  = {'verde': VERDE, 'rosa': ROSA}

FONT_SPECS = {
    'bold':    {'file': 'Montserrat.ttf',
                'cdn':  'https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf'},
    'script':  {'file': 'DancingScript.ttf',
                'cdn':  'https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/DancingScript%5Bwght%5D.ttf'},
    'display': {'file': 'PlayfairDisplay.ttf',
                'cdn':  'https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf'},
}

def _get_font_path(key):
    spec = FONT_SPECS[key]
    for p in [os.path.join(FONTS_DIR, spec['file']), os.path.join(FONT_CACHE, spec['file'])]:
        if os.path.exists(p): return p
    os.makedirs(FONT_CACHE, exist_ok=True)
    tmp = os.path.join(FONT_CACHE, spec['file'])
    try:
        req = urllib.request.Request(spec['cdn'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r: data = r.read()
        open(tmp, 'wb').write(data); return tmp
    except Exception: return None

def _font(key, size):
    path = _get_font_path(key)
    if path:
        try:
            fnt = ImageFont.truetype(path, size)
            for attempt in [lambda f: f.set_variation_by_name('Bold'),
                            lambda f: f.set_variation_by_axes([700])]:
                try: attempt(fnt); break
                except Exception: pass
            return fnt
        except Exception: pass
    return ImageFont.load_default(size=size)

def _bb(text, fnt):
    tmp = Image.new('RGB', (1, 1))
    return ImageDraw.Draw(tmp).textbbox((0, 0), text, font=fnt)

def _tw(text, fnt):
    b = _bb(text, fnt); return b[2] - b[0]

def _th(text, fnt):
    b = _bb(text, fnt); return b[3] - b[1]

def _wrap(text, fnt, max_w):
    words = text.split(); lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if _tw(test, fnt) <= max_w: cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [text]

def _center(draw, text, cx, y, fnt, fill):
    draw.text((cx - _tw(text, fnt) // 2, y), text, font=fnt, fill=fill)

def _m2m_str(field, sep=', '):
    try: return sep.join(obj.nombre for obj in field.all())
    except Exception: return str(field) if field else ''

def _crop_top(img, tw, th):
    sw, sh = img.size; ratio = max(tw / sw, th / sh)
    nw, nh = int(sw * ratio), int(sh * ratio)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2; return img.crop((left, 0, left + tw, th))

def _round_mask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255); return m

def _open_foto(foto_field):
    if not foto_field: return None
    try:
        foto_field.open('rb'); data = BytesIO(foto_field.read()); foto_field.close(); return data
    except Exception: return None

def _paste_foto(canvas, foto_field, x, y, w, h, radius=0):
    data = _open_foto(foto_field); draw = ImageDraw.Draw(canvas)
    if data:
        try:
            foto = Image.open(data).convert('RGB'); foto = _crop_top(foto, w, h)
            if radius:
                mask = _round_mask(w, h, radius); rgba = foto.convert('RGBA'); rgba.putalpha(mask)
                canvas.paste(rgba, (x, y), mask=rgba.split()[3])
            else: canvas.paste(foto, (x, y)); return
        except Exception: pass
    if radius: draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(200, 200, 200))
    else: draw.rectangle([x, y, x + w, y + h], fill=(200, 200, 200))


def generar_imagen_post(psicologo, color_top_key='verde', color_bottom_key='rosa'):
    W, H = 1080, 1080
    STRIPE_H = 130; N_STRIPES = 20; SW = W // N_STRIPES
    c_top = COLOR_MAP.get(color_top_key, VERDE)
    c_bot = COLOR_MAP.get(color_bottom_key, ROSA)

    canvas = Image.new('RGB', (W, H), CREMA)
    draw   = ImageDraw.Draw(canvas)

    for i in range(N_STRIPES):
        fill = c_top if i % 2 == 0 else BLANCO
        draw.rectangle([i * SW, 0, (i + 1) * SW, STRIPE_H], fill=fill)
    for i in range(N_STRIPES):
        fill = c_bot if i % 2 == 0 else BLANCO
        draw.rectangle([i * SW, H - STRIPE_H, (i + 1) * SW, H], fill=fill)

    _paste_foto(canvas, psicologo.foto, 30, 155, 470, 780, radius=40)

    RX = 530; RW = W - RX - 10; RCX = RX + RW // 2
    TEXT_TOP = STRIPE_H + 30; TEXT_BOT = H - STRIPE_H - 70

    f_name   = _font('bold',   42)
    f_script = _font('script', 38)
    f_mod    = _font('bold',   26)
    f_dest   = _font('script', 52)
    f_wp     = _font('bold',   22)

    nombre      = (psicologo.nombre or '').strip()
    orient      = (psicologo.orientacion or '').strip()
    modalidades = _m2m_str(psicologo.modalidades).upper()
    dest_str    = _m2m_str(psicologo.destinatarios)

    wp_raw = ''.join(c for c in (psicologo.whatsapp or '') if c.isdigit())
    if len(wp_raw) >= 10:
        wp_text = wp_raw[-10:-8] + ' - ' + wp_raw[-8:-4] + ' - ' + wp_raw[-4:]
    else:
        wp_text = psicologo.whatsapp or ''

    name_lines   = _wrap('Lic. ' + nombre, f_name,   RW - 20)
    orient_lines = _wrap(orient,            f_script, RW - 20)
    mod_lines    = _wrap(modalidades,       f_mod,    RW - 20)

    LG = 14
    name_h   = sum(_th(l, f_name)   + LG for l in name_lines)
    orient_h = sum(_th(l, f_script) + LG for l in orient_lines)
    mod_h    = sum(_th(l, f_mod)    + LG for l in mod_lines)
    BLOCK_H  = name_h + 24 + 2 + 24 + orient_h + 16 + mod_h + 16 + _th(wp_text, f_wp)

    cy = TEXT_TOP + max(0, (TEXT_BOT - TEXT_TOP - BLOCK_H) // 2)

    for line in name_lines:
        _center(draw, line, RCX, cy, f_name, NEGRO); cy += _th(line, f_name) + LG
    cy += 12
    sep_w = min(260, RW - 60)
    draw.line([(RCX - sep_w // 2, cy), (RCX + sep_w // 2, cy)], fill=GRIS_MED, width=2)
    cy += 14
    for line in orient_lines:
        _center(draw, line, RCX, cy, f_script, GRIS_MED); cy += _th(line, f_script) + LG
    cy += 8
    for line in mod_lines:
        _center(draw, line, RCX, cy, f_mod, NEGRO); cy += _th(line, f_mod) + LG
    cy += 8
    _center(draw, wp_text, RCX, cy, f_wp, VERDE_OSC)

    dest_y = H - STRIPE_H - _th(dest_str, f_dest) - 16
    _center(draw, dest_str, W // 2, dest_y, f_dest, c_bot)
    return canvas


def generar_imagen_story(psicologo):
    W, H = 1080, 1920
    canvas = Image.new('RGB', (W, H), CREMA)
    draw   = ImageDraw.Draw(canvas)

    draw.ellipse([600, -250, 1250, 480],  fill=GRIS_BLOB)
    draw.ellipse([-180, 1450, 480, 2100], fill=GRIS_BLOB)

    f_agenda = _font('display', 88)
    f_nombre = _font('display', 42)
    f_script = _font('script',  52)
    f_pill   = _font('bold',    30)

    nombre      = (psicologo.nombre or '').strip().upper()
    orient      = (psicologo.orientacion or '').strip()
    modalidades = _m2m_str(psicologo.modalidades)
    dest_str    = _m2m_str(psicologo.destinatarios)

    wp_raw = ''.join(c for c in (psicologo.whatsapp or '') if c.isdigit())
    if len(wp_raw) >= 10:
        wp_text = wp_raw[-10:-8] + ' - ' + wp_raw[-8:-4] + ' - ' + wp_raw[-4:]
    else:
        wp_text = psicologo.whatsapp or ''

    draw.text((55, 52), 'AGENDA ABIERTA', font=f_agenda, fill=NEGRO)
    cy = 52 + _th('AGENDA ABIERTA', f_agenda) + 14

    for line in _wrap('LIC. ' + nombre, f_nombre, W - 110):
        draw.text((55, cy), line, font=f_nombre, fill=NEGRO)
        cy += _th(line, f_nombre) + 8

    PW, PH = 630, 500
    PX = (W - PW) // 2; PY = cy + 50
    _paste_foto(canvas, psicologo.foto, PX, PY, PW, PH, radius=0)

    PILL_H = 64; PILL_R = PILL_H // 2; PILL_PAD = 40; PILL_GAP = 22
    cy_pill = PY + PH + 55

    for label in [dest_str, 'Atencion ' + modalidades, wp_text]:
        if not label.strip(): continue
        pw = max(_tw(label, f_pill) + PILL_PAD * 2, 300)
        px = (W - pw) // 2
        draw.rounded_rectangle([px, cy_pill, px + pw, cy_pill + PILL_H], radius=PILL_R, fill=VERDE_PILL)
        _center(draw, label, W // 2, cy_pill + (PILL_H - _th(label, f_pill)) // 2, f_pill, VERDE_OSC)
        cy_pill += PILL_H + PILL_GAP

    _center(draw, orient, W // 2, H - _th(orient, f_script) - 80, f_script, NEGRO)
    return canvas
