"""
Generador de imágenes para redes sociales (AtencionPsi).

Genera dos formatos por psicólogo:
  • Post  1080×1080  (franjas de color configurables)
  • Story 1080×1920  (fondo crema con blobs)

Fonts: se descargan de Google Fonts la primera vez y se cachean en /tmp/fonts_apsi/.
Si la descarga falla (entorno sin internet), se usa Liberation/Lato como fallback.
"""

import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont

# ── Paleta ───────────────────────────────────────────────────────────────────
VERDE       = (125, 168, 123)
ROSA        = (233, 168, 166)
BLANCO      = (255, 255, 255)
NEGRO       = (30, 30, 30)
GRIS_MEDIO  = (90, 90, 90)
VERDE_OSC   = (50, 82, 50)
CREMA       = (240, 235, 224)
GRIS_BLOB   = (195, 200, 192)
VERDE_PILL  = (195, 215, 195)

COLOR_MAP = {'verde': VERDE, 'rosa': ROSA}

# ── Fonts ─────────────────────────────────────────────────────────────────────
FONT_CACHE = '/tmp/fonts_apsi'
FONT_SPECS = {
    'bold': {
        'url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/static/Montserrat-Bold.ttf',
        'fallback': '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        'file': 'Montserrat-Bold.ttf',
    },
    'script': {
        'url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/dancingscript/static/DancingScript-Bold.ttf',
        'fallback': '/usr/share/fonts/truetype/lato/Lato-BoldItalic.ttf',
        'file': 'DancingScript-Bold.ttf',
    },
    'display': {
        'url': 'https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/static/PlayfairDisplay-Bold.ttf',
        'fallback': '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',
        'file': 'PlayfairDisplay-Bold.ttf',
    },
}


def _font_path(key):
    spec = FONT_SPECS[key]
    os.makedirs(FONT_CACHE, exist_ok=True)
    local = os.path.join(FONT_CACHE, spec['file'])
    if not os.path.exists(local):
        try:
            req = urllib.request.Request(
                spec['url'],
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as r, open(local, 'wb') as f:
                f.write(r.read())
        except Exception:
            return spec['fallback']
    return local


def _font(key, size):
    try:
        return ImageFont.truetype(_font_path(key), size)
    except Exception:
        try:
            return ImageFont.truetype(FONT_SPECS[key]['fallback'], size)
        except Exception:
            return ImageFont.load_default()


# ── Utilidades de texto ───────────────────────────────────────────────────────

def _text_w(text, fnt):
    tmp = Image.new('RGB', (1, 1))
    bb = ImageDraw.Draw(tmp).textbbox((0, 0), text, font=fnt)
    return bb[2] - bb[0]


def _wrap(text, fnt, max_w):
    words = text.split()
    lines, cur = [], ''
    for word in words:
        test = (cur + ' ' + word).strip()
        if _text_w(test, fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines or [text]


def _draw_centered(draw, text, cx, y, fnt, fill):
    draw.text((cx - _text_w(text, fnt) // 2, y), text, font=fnt, fill=fill)


# ── Utilidades de imagen ──────────────────────────────────────────────────────

def _crop_top(img, tw, th):
    sw, sh = img.size
    ratio = max(tw / sw, th / sh)
    nw, nh = int(sw * ratio), int(sh * ratio)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    return img.crop((left, 0, left + tw, th))


def _rounded_mask(size, radius):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255
    )
    return m


def _load_photo(foto_path, target_w, target_h, rounded=False, radius=40):
    if not foto_path or not os.path.exists(str(foto_path)):
        return None
    try:
        img = Image.open(str(foto_path)).convert('RGB')
        img = _crop_top(img, target_w, target_h)
        if rounded:
            mask = _rounded_mask((target_w, target_h), radius)
            rgba = img.convert('RGBA')
            rgba.putalpha(mask)
            return rgba
        return img
    except Exception:
        return None


# ── POST 1080×1080 ────────────────────────────────────────────────────────────

def generar_imagen_post(psicologo, color_top_key='verde', color_bottom_key='rosa', foto_path=None):
    W, H = 1080, 1080
    img = Image.new('RGB', (W, H), BLANCO)
    draw = ImageDraw.Draw(img)

    c_top = COLOR_MAP.get(color_top_key, VERDE)
    c_bot = COLOR_MAP.get(color_bottom_key, ROSA)

    # Franjas verticales top (y=0..140)
    STRIPE_W = 52
    x, alt = 0, True
    while x < W:
        draw.rectangle([x, 0, min(x + STRIPE_W - 1, W - 1), 140], fill=c_top if alt else BLANCO)
        x += STRIPE_W; alt = not alt

    # Franjas verticales bottom (y=940..H)
    x, alt = 0, True
    while x < W:
        draw.rectangle([x, 940, min(x + STRIPE_W - 1, W - 1), H - 1], fill=c_bot if alt else BLANCO)
        x += STRIPE_W; alt = not alt

    # Foto panel izquierdo
    PX, PY, PW, PH, PR = 35, 160, 460, 760, 50
    foto = _load_photo(foto_path, PW, PH, rounded=True, radius=PR)
    if foto:
        img.paste(foto, (PX, PY), mask=foto.split()[3])
    else:
        draw.rounded_rectangle([PX, PY, PX + PW, PY + PH], radius=PR, fill=(210, 210, 210))

    # Panel derecho
    RCX = 780
    RW  = 510

    fn_nombre = _font('bold',   42)
    fn_ori    = _font('script', 38)
    fn_mod    = _font('bold',   30)
    fn_dest   = _font('script', 52)

    y = 220

    # Nombre
    for line in _wrap(psicologo.nombre, fn_nombre, RW - 10):
        _draw_centered(draw, line, RCX, y, fn_nombre, NEGRO)
        y += 55

    # Separador
    y += 12
    draw.rectangle([RCX - 80, y, RCX + 80, y + 3], fill=c_top)
    y += 22

    # Orientación
    if psicologo.orientacion:
        for line in _wrap(psicologo.orientacion, fn_ori, RW - 10):
            _draw_centered(draw, line, RCX, y, fn_ori, GRIS_MEDIO)
            y += 50
        y += 12

    # Modalidades
    mods = [m.nombre for m in psicologo.modalidades.all()]
    if mods:
        for line in _wrap('  ·  '.join(mods), fn_mod, RW - 10):
            _draw_centered(draw, line, RCX, y, fn_mod, GRIS_MEDIO)
            y += 40

    # Destinatarios – centrado, justo arriba de las franjas inferiores
    dests = [d.nombre for d in psicologo.destinatarios.all()]
    if dests:
        dest_lines = _wrap(', '.join(dests), fn_dest, W - 60)
        n_lines    = len(dest_lines)
        dest_y     = max(900 - (n_lines - 1) * 62, 760)
        for line in dest_lines:
            _draw_centered(draw, line, W // 2, dest_y, fn_dest, c_bot)
            dest_y += 62

    return img


# ── STORY 1080×1920 ───────────────────────────────────────────────────────────

def generar_imagen_story(psicologo, foto_path=None):
    W, H = 1080, 1920
    img = Image.new('RGB', (W, H), CREMA)
    draw = ImageDraw.Draw(img)

    # Blobs decorativos
    draw.ellipse([-150, -200,  400,  350], fill=GRIS_BLOB)
    draw.ellipse([ 700, 1600, 1250, 2100], fill=GRIS_BLOB)

    fn_title  = _font('display', 90)
    fn_name   = _font('display', 46)
    fn_pill   = _font('bold',    32)
    fn_script = _font('script',  44)

    MARGIN_L   = 70
    MAX_W      = W - MARGIN_L - 40

    # AGENDA ABIERTA
    TITLE = 'AGENDA ABIERTA'
    if _text_w(TITLE, fn_title) <= MAX_W:
        draw.text((MARGIN_L, 55), TITLE, font=fn_title, fill=VERDE_OSC)
        title_bottom = 165
    else:
        draw.text((MARGIN_L,  40), 'AGENDA',  font=fn_title, fill=VERDE_OSC)
        draw.text((MARGIN_L, 145), 'ABIERTA', font=fn_title, fill=VERDE_OSC)
        title_bottom = 255

    # Nombre
    name_lines = _wrap(f'Lic. {psicologo.nombre}', fn_name, MAX_W)
    ny = title_bottom + 18
    for line in name_lines:
        draw.text((MARGIN_L, ny), line, font=fn_name, fill=VERDE_OSC)
        ny += 58

    # Foto rectangular centrada
    PW, PH = 620, 520
    PX = (W - PW) // 2
    PY = ny + 28

    foto = _load_photo(foto_path, PW, PH, rounded=False)
    if foto:
        img.paste(foto, (PX, PY))
    else:
        draw.rectangle([PX, PY, PX + PW, PY + PH], fill=(210, 210, 210))

    # Pills
    PIL_Y0  = PY + PH + 50
    PIL_W   = W - 140
    PIL_X   = 70
    PIL_H   = 100
    PIL_GAP = 22
    ICON_R  = 27
    ICON_CX = PIL_X + 54
    TEXT_X  = PIL_X + 110

    pills = []
    if psicologo.orientacion:
        pills.append(psicologo.orientacion)
    mods = [m.nombre for m in psicologo.modalidades.all()]
    if mods:
        pills.append('  ·  '.join(mods))
    dests = [d.nombre for d in psicologo.destinatarios.all()]
    if dests:
        pills.append(', '.join(dests))

    for i, text in enumerate(pills):
        py = PIL_Y0 + i * (PIL_H + PIL_GAP)
        draw.rounded_rectangle(
            [PIL_X, py, PIL_X + PIL_W, py + PIL_H],
            radius=PIL_H // 2,
            fill=VERDE_PILL,
        )
        cy = py + PIL_H // 2
        draw.ellipse(
            [ICON_CX - ICON_R, cy - ICON_R, ICON_CX + ICON_R, cy + ICON_R],
            fill=VERDE,
        )
        p_lines = _wrap(text, fn_pill, PIL_W - 160)
        line_h  = 40
        ty = py + (PIL_H - len(p_lines) * line_h) // 2
        for line in p_lines:
            draw.text((TEXT_X, ty), line, font=fn_pill, fill=VERDE_OSC)
            ty += line_h

    # Texto script decorativo al fondo
    if psicologo.orientacion:
        script_y = PIL_Y0 + len(pills) * (PIL_H + PIL_GAP) + 55
        if script_y + 60 < H - 50:
            for line in _wrap(psicologo.orientacion, fn_script, W - 140):
                w_ = _text_w(line, fn_script)
                draw.text(((W - w_) // 2, script_y), line, font=fn_script, fill=(110, 140, 110))
                script_y += 56

    return img
