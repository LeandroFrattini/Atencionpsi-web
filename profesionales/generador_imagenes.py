import os, urllib.request
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_HERE, 'fonts')
FONT_CACHE = '/tmp/fonts_apsi'

# ── Brand colours ─────────────────────────────────────────────────────────────
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

# ── Font specs (variable-font files) ─────────────────────────────────────────
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
    for path in [os.path.join(FONTS_DIR, spec['file']),
                 os.path.join(FONT_CACHE, spec['file'])]:
        if os.path.exists(path):
            return path
    os.makedirs(FONT_CACHE, exist_ok=True)
    tmp = os.path.join(FONT_CACHE, spec['file'])
    try:
        req = urllib.request.Request(spec['cdn'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        open(tmp, 'wb').write(data)
        return tmp
    except Exception:
        return None

def _font(key, size):
    path = _get_font_path(key)
    if path:
        try:
            fnt = ImageFont.truetype(path, size)
            # Activate bold weight on variable font
            for attempt in [lambda f: f.set_variation_by_name('Bold'),
                            lambda f: f.set_variation_by_axes([700])]:
                try:
                    attempt(fnt)
                    break
                except Exception:
                    pass
            return fnt
        except Exception:
            pass
    return ImageFont.load_default(size=size)

# ── Text helpers ──────────────────────────────────────────────────────────────
def _bb(text, fnt):
    tmp = Image.new('RGB', (1, 1))
    return ImageDraw.Draw(tmp).textbbox((0, 0), text, font=fnt)

def _tw(text, fnt):
    b = _bb(text, fnt); return b[2] - b[0]

def _th(text, fnt):
    b = _bb(text, fnt); return b[3] - b[1]

def _wrap(text, fnt, max_w):
    words = text.split()
    lines, cur = [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if _tw(test, fnt) <= max_w:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines or [text]

def _center(draw, text, cx, y, fnt, fill):
    draw.text((cx - _tw(text, fnt) // 2, y), text, font=fnt, fill=fill)

def _draw_lines(draw, lines, cx, y, fnt, fill, line_gap=10):
    for line in lines:
        _center(draw, line, cx, y, fnt, fill)
        y += _th(line, fnt) + line_gap
    return y

# ── Photo helpers ─────────────────────────────────────────────────────────────
def _crop_top(img, tw, th):
    sw, sh = img.size
    ratio = max(tw / sw, th / sh)
    nw, nh = int(sw * ratio), int(sh * ratio)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    return img.crop((left, 0, left + tw, th))

def _round_mask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    return m

def _open_foto(foto_field):
    if not foto_field:
        return None
    try:
        foto_field.open('rb')
        data = BytesIO(foto_field.read())
        foto_field.close()
        return data
    except Exception:
        return None

def _paste_foto(canvas, foto_field, x, y, w, h, radius=0):
    data = _open_foto(foto_field)
    draw = ImageDraw.Draw(canvas)
    if data:
        try:
            foto = Image.open(data).convert('RGB')
            foto = _crop_top(foto, w, h)
            if radius:
                mask = _round_mask(w, h, radius)
                rgba = foto.convert('RGBA')
                rgba.putalpha(mask)
                canvas.paste(rgba, (x, y), mask=rgba.split()[3])
            else:
                canvas.paste(foto, (x, y))
            return
        except Exception:
            pass
    # Fallback: grey placeholder
    if radius:
        draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=(200, 200, 200))
    else:
        draw.rectangle([x, y, x + w, y + h], fill=(200, 200, 200))


# ═══════════════════════════════════════════════════════════════════════════════
# POST  1080 × 1080
# ═══════════════════════════════════════════════════════════════════════════════
def generar_imagen_post(psicologo, color_top_key='verde', color_bottom_key='rosa'):
    W, H = 1080, 1080
    STRIPE_H = 130        # height of top/bottom stripe band
    N_STRIPES = 20        # 1080 / 54 = 20 stripes of 54 px
    SW = W // N_STRIPES   # stripe width = 54

    c_top = COLOR_MAP.get(color_top_key, VERDE)
    c_bot = COLOR_MAP.get(color_bottom_key, ROSA)

    canvas = Image.new('RGB', (W, H), CREMA)
    draw   = ImageDraw.Draw(canvas)

    # ── Top stripe band ──
    for i in range(N_STRIPES):
        fill = c_top if i % 2 == 0 else BLANCO
        draw.rectangle([i * SW, 0, (i + 1) * SW, STRIPE_H], fill=fill)

    # ── Bottom stripe band ──
    for i in range(N_STRIPES):
        fill = c_bot if i % 2 == 0 else BLANCO
        draw.rectangle([i * SW, H - STRIPE_H, (i + 1) * SW, H], fill=fill)

    # ── Photo (left half, rounded) ──
    PX, PY, PW, PH = 30, 155, 470, 780
    _paste_foto(canvas, psicologo.foto, PX, PY, PW, PH, radius=40)

    # ── Right panel ──
    RX  = 530          # left edge
    RW  = W - RX - 10  # right panel width  ≈ 540
    RCX = RX + RW // 2 # center x           ≈ 805

    TEXT_TOP = STRIPE_H + 30
    TEXT_BOT = H - STRIPE_H - 70  # leave space for destinatarios line

    # Fonts
    f_name   = _font('bold',    42)
    f_sep    = _font('bold',    16)
    f_script = _font('script',  38)
    f_mod    = _font('bold',    26)
    f_dest   = _font('script',  52)
    f_wp     = _font('bold',    22)

    # --- Nombre ---
    nombre = (psicologo.nombre or '').strip()
    name_label = 'Lic. ' + nombre
    name_lines = _wrap(name_label, f_name, RW - 20)

    # --- Orientación ---
    orient = (psicologo.orientacion or '').strip()
    orient_lines = _wrap(orient, f_script, RW - 20)

    # --- Modalidades ---
    modalidades = (psicologo.modalidades or '').strip().upper()
    mod_lines = _wrap(modalidades, f_mod, RW - 20)

    # --- WhatsApp ---
    wp_raw = ''.join(c for c in (psicologo.whatsapp or '') if c.isdigit())
    # Format: last 8 digits as "XX XX XX XX", first part as area code
    if len(wp_raw) >= 10:
        area = wp_raw[-10:-8]
        num  = wp_raw[-8:]
        wp_text = area + ' - ' + num[:4] + ' - ' + num[4:]
    else:
        wp_text = psicologo.whatsapp or ''

    # --- Measure total text block height ---
    LG = 14  # line gap
    name_block_h  = sum(_th(l, f_name)   + LG for l in name_lines)
    sep_margin    = 24
    sep_h         = 2
    orient_block_h= sum(_th(l, f_script) + LG for l in orient_lines)
    mod_block_h   = sum(_th(l, f_mod)    + LG for l in mod_lines)
    wp_h          = _th(wp_text, f_wp)
    BLOCK_H = name_block_h + sep_margin + sep_h + sep_margin + orient_block_h + 16 + mod_block_h + 16 + wp_h

    panel_h = TEXT_BOT - TEXT_TOP
    cy = TEXT_TOP + max(0, (panel_h - BLOCK_H) // 2)

    # Draw name
    for line in name_lines:
        _center(draw, line, RCX, cy, f_name, NEGRO)
        cy += _th(line, f_name) + LG

    # Separator line
    cy += sep_margin // 2
    sep_w = min(280, RW - 60)
    draw.line([(RCX - sep_w // 2, cy), (RCX + sep_w // 2, cy)], fill=GRIS_MED, width=2)
    cy += sep_h + sep_margin // 2

    # Orientación
    for line in orient_lines:
        _center(draw, line, RCX, cy, f_script, GRIS_MED)
        cy += _th(line, f_script) + LG

    cy += 8
    # Modalidades
    for line in mod_lines:
        _center(draw, line, RCX, cy, f_mod, NEGRO)
        cy += _th(line, f_mod) + LG

    cy += 8
    # WhatsApp
    _center(draw, wp_text, RCX, cy, f_wp, VERDE_OSC)

    # ── Destinatarios centered at bottom ──
    dest = (psicologo.destinatarios or '').strip()
    dest_y = H - STRIPE_H - _th(dest, f_dest) - 16
    _center(draw, dest, W // 2, dest_y, f_dest, c_bot)

    return canvas


# ═══════════════════════════════════════════════════════════════════════════════
# STORY  1080 × 1920
# ═══════════════════════════════════════════════════════════════════════════════
def generar_imagen_story(psicologo):
    W, H = 1080, 1920
    canvas = Image.new('RGB', (W, H), CREMA)
    draw   = ImageDraw.Draw(canvas)

    # ── Decorative blobs (soft ellipses) ──
    # Top-RIGHT blob
    draw.ellipse([600, -250, 1250, 480], fill=GRIS_BLOB)
    # Bottom-LEFT blob
    draw.ellipse([-180, 1450, 480, 2100], fill=GRIS_BLOB)

    # ── Fonts ──
    f_agenda  = _font('display', 88)
    f_nombre  = _font('display', 42)
    f_script  = _font('script',  52)
    f_pill    = _font('bold',    30)

    # ── AGENDA ABIERTA ──
    agenda_text = 'AGENDA ABIERTA'
    draw.text((55, 52), agenda_text, font=f_agenda, fill=NEGRO)

    # ── LIC. NOMBRE ──
    nombre = (psicologo.nombre or '').strip().upper()
    lic_text = 'LIC. ' + nombre
    lic_lines = _wrap(lic_text, f_nombre, W - 110)
    cy = 52 + _th(agenda_text, f_agenda) + 14
    for line in lic_lines:
        draw.text((55, cy), line, font=f_nombre, fill=NEGRO)
        cy += _th(line, f_nombre) + 8

    # ── Photo centered ──
    PW, PH = 630, 500
    PX = (W - PW) // 2
    PY = cy + 50
    _paste_foto(canvas, psicologo.foto, PX, PY, PW, PH, radius=0)

    # ── Pills ──
    PILL_H     = 64
    PILL_R     = PILL_H // 2
    PILL_PAD_X = 40
    PILL_GAP   = 22
    pill_top   = PY + PH + 55

    dest       = (psicologo.destinatarios or '').strip()
    modalidades= (psicologo.modalidades or '').strip()
    wp_raw     = ''.join(c for c in (psicologo.whatsapp or '') if c.isdigit())
    if len(wp_raw) >= 8:
        wp_text = wp_raw[-10:-8] + ' - ' + wp_raw[-8:] if len(wp_raw) >= 10 else wp_raw[:2] + ' - ' + wp_raw[2:]
    else:
        wp_text = psicologo.whatsapp or ''

    pills = [dest, 'Atención ' + modalidades, wp_text]

    cy_pill = pill_top
    for pill_label in pills:
        pill_w = _tw(pill_label, f_pill) + PILL_PAD_X * 2
        pill_w = max(pill_w, 300)
        px = (W - pill_w) // 2
        draw.rounded_rectangle([px, cy_pill, px + pill_w, cy_pill + PILL_H],
                                radius=PILL_R, fill=VERDE_PILL)
        label_y = cy_pill + (PILL_H - _th(pill_label, f_pill)) // 2
        _center(draw, pill_label, W // 2, label_y, f_pill, VERDE_OSC)
        cy_pill += PILL_H + PILL_GAP

    # ── Orientación at bottom ──
    orient = (psicologo.orientacion or '').strip()
    orient_y = H - _th(orient, f_script) - 80
    _center(draw, orient, W // 2, orient_y, f_script, NEGRO)

    return canvas
