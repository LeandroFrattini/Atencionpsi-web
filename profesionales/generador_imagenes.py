"""
Generador de historias de Instagram (1080x1920) por psicólogo.

Reemplaza al generador viejo (post + story calcados de un template de Canva
que no terminó de convencer). Este archivo genera SOLO la historia, con un
diseño propio: paleta y tipografías de la marca, medallón de foto, dos
burbujas de datos (teléfono / modalidad+ciudad) y la franja etaria como
tipografía libre abajo.

Para reutilizar este mismo diseño en las webs de otros países (.uy/.py/.cl),
lo único que hay que tocar es el bloque de configuración de abajo.
"""
import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_HERE, 'fonts')

# ── Configuración por país — lo único que cambia entre sitios ─────────────
DOMINIO_SITIO = 'www.atencionpsi.com.ar'
INSTAGRAM_HANDLE = '@atencionpsi.ar'
PREFIJO_TELEFONO = '+54 9 '  # Uruguay: '+598 ', Paraguay: '+595 ', Chile: '+56 '

# ── Paleta (igual a static/style.css / portal.css) ─────────────────────────
CREMA = (253, 251, 249)
BLUSH = (243, 231, 228)
VERDE = (125, 168, 123)
VERDE_OSCURO = (74, 124, 89)
ROSA = (233, 168, 166)
ROSA_OSCURO = (201, 130, 126)
ORO = (220, 174, 107)
TINTA = (43, 42, 40)
TINTA_SUAVE = (107, 101, 96)
BLANCO = (255, 255, 255)

W, H = 1080, 1920


# ── Fuentes (variable fonts locales, sin descargas externas) ───────────────
_FONT_INSTANCES = {
    'playfair': {100: 'Thin', 200: 'ExtraLight', 300: 'Light', 400: 'Regular', 500: 'Medium',
                 600: 'SemiBold', 700: 'Bold', 800: 'ExtraBold', 900: 'Black'},
    'montserrat': {100: 'Thin', 200: 'ExtraLight', 300: 'Light', 400: 'Regular', 500: 'Medium',
                   600: 'SemiBold', 700: 'Bold', 800: 'ExtraBold', 900: 'Black'},
}
_FONT_FILES = {'playfair': 'PlayfairDisplay.ttf', 'montserrat': 'Montserrat.ttf'}
_FONT_CACHE = {}


def _font(familia, peso, tam):
    key = (familia, peso, tam)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = os.path.join(FONTS_DIR, _FONT_FILES[familia])
    fnt = ImageFont.truetype(path, tam)
    nombre_instancia = min(_FONT_INSTANCES[familia].items(), key=lambda kv: abs(kv[0] - peso))[1]
    try:
        fnt.set_variation_by_name(nombre_instancia)
    except Exception:
        pass
    _FONT_CACHE[key] = fnt
    return fnt


def _bb(draw, text, fnt):
    return draw.textbbox((0, 0), text, font=fnt)


def _tw(draw, text, fnt):
    b = _bb(draw, text, fnt)
    return b[2] - b[0]


def _th(draw, text, fnt):
    b = _bb(draw, text, fnt)
    return b[3] - b[1]


def _wrap(draw, text, fnt, max_w):
    palabras = text.split()
    lineas, actual = [], ''
    for palabra in palabras:
        prueba = (actual + ' ' + palabra).strip()
        if _tw(draw, prueba, fnt) <= max_w:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [text]


def _center(draw, text, cx, y, fnt, fill):
    draw.text((cx - _tw(draw, text, fnt) // 2, y), text, font=fnt, fill=fill)


def _limpiar_nombre(nombre):
    n = (nombre or '').strip()
    if n.lower().startswith('lic.'):
        n = n[4:].strip()
    return n


def _formatear_telefono(whatsapp_limpio):
    """Agrupa el número (10 dígitos: área + local) para que se lea mejor."""
    n = whatsapp_limpio
    if len(n) == 10:
        return f'{n[:3]} {n[3:7]}-{n[7:]}'
    if len(n) >= 8:
        return f'{n[:-4]}-{n[-4:]}'
    return n


# ── Fondo: gradiente + manchas difuminadas + grano ─────────────────────────
def _gradiente_lineal(w, h, color_a, color_b, angulo=150):
    base = Image.linear_gradient('L').rotate(angulo - 90, expand=True, resample=Image.BICUBIC)
    base = base.resize((w, h))
    capa_a = Image.new('RGB', (w, h), color_a)
    capa_b = Image.new('RGB', (w, h), color_b)
    return Image.composite(capa_b, capa_a, base)


def _mancha(canvas, cx, cy, radio, color, alpha=95):
    d = radio * 2
    capa = Image.new('RGBA', (d, d), (0, 0, 0, 0))
    ImageDraw.Draw(capa).ellipse([0, 0, d, d], fill=color + (alpha,))
    capa = capa.filter(ImageFilter.GaussianBlur(radio * 0.4))
    canvas.paste(capa, (int(cx - radio), int(cy - radio)), capa)


def _grano(canvas, paso=26, alpha=14):
    """canvas debe estar en modo RGB; agrega una textura sutil de puntitos."""
    capa = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    for y in range(0, canvas.size[1], paso):
        for x in range(0, canvas.size[0], paso):
            d.ellipse([x - 1.6, y - 1.6, x + 1.6, y + 1.6], fill=TINTA + (alpha,))
    resultado = Image.alpha_composite(canvas.convert('RGBA'), capa).convert('RGB')
    canvas.paste(resultado, (0, 0))


def _arco_punteado(canvas, cx, cy, radio, color, ancho=2, n_guiones=48, alpha=70):
    capa = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    paso = 360 / n_guiones
    for i in range(n_guiones):
        if i % 2 == 0:
            continue
        ini = i * paso
        fin = ini + paso
        d.arc([cx - radio, cy - radio, cx + radio, cy + radio], ini, fin, fill=color + (alpha,), width=ancho)
    canvas.paste(capa, (0, 0), capa)


# ── Burbujas / pills ─────────────────────────────────────────────────────
def _sombra_para(size, radio_borde, alpha=26, blur=14, offset=(0, 8)):
    w, h = size
    pad = blur * 2
    capa = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle(
        [pad, pad, pad + w, pad + h], radius=radio_borde, fill=TINTA + (alpha,)
    )
    capa = capa.filter(ImageFilter.GaussianBlur(blur))
    return capa, pad, offset


def _pegar_con_sombra(canvas, capa_contenido, x, y, radio_borde):
    w, h = capa_contenido.size
    sombra, pad, offset = _sombra_para((w, h), radio_borde)
    canvas.paste(sombra, (x - pad + offset[0], y - pad + offset[1]), sombra)
    canvas.paste(capa_contenido, (x, y), capa_contenido)


def _icono_telefono(draw, cx, cy, r, color, ancho=5):
    off = r * 0.5
    p1 = (cx - off, cy + off * 0.6)
    p2 = (cx + off * 0.7, cy - off)
    draw.line([p1, p2], fill=color, width=ancho)
    er = r * 0.34
    draw.ellipse([p1[0] - er, p1[1] - er, p1[0] + er, p1[1] + er], outline=color, width=ancho)
    draw.ellipse([p2[0] - er, p2[1] - er, p2[0] + er, p2[1] + er], outline=color, width=ancho)


def _icono_ubicacion(draw, cx, cy, r, color, ancho=5):
    top = cy - r * 0.5
    rc = r * 0.62
    draw.ellipse([cx - rc, top - rc, cx + rc, top + rc], outline=color, width=ancho)
    pr = r * 0.16
    draw.ellipse([cx - pr, top - pr, cx + pr, top + pr], fill=color)
    punta = (cx, cy + r * 0.85)
    draw.line([(cx - rc * 0.72, top + rc * 0.55), punta], fill=color, width=ancho)
    draw.line([(cx + rc * 0.72, top + rc * 0.55), punta], fill=color, width=ancho)


def _dibujar_burbuja_dato(draw_fn, ancho, alto, icono_fn):
    """Arma en una capa aparte una burbuja blanca con ícono + contenido (dibujado por draw_fn)."""
    capa = Image.new('RGBA', (ancho, alto), (0, 0, 0, 0))
    ImageDraw.Draw(capa).rounded_rectangle([0, 0, ancho, alto], radius=alto // 2, fill=BLANCO + (255,))
    d = ImageDraw.Draw(capa)
    icono_cx = 66
    icono_r = 33
    d.ellipse(
        [icono_cx - icono_r, alto // 2 - icono_r, icono_cx + icono_r, alto // 2 + icono_r],
        fill=(*VERDE, 38),
    )
    icono_fn(d, icono_cx, alto // 2, icono_r * 0.55, VERDE_OSCURO)
    draw_fn(d, icono_cx + icono_r + 26)
    return capa


# ── Foto / placeholder circular ─────────────────────────────────────────
def _crop_cuadrado(img, lado):
    sw, sh = img.size
    ratio = max(lado / sw, lado / sh)
    nw, nh = int(sw * ratio), int(sh * ratio)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - lado) // 2
    top = (nh - lado) // 2
    return img.crop((left, top, left + lado, top + lado))


def _abrir_foto(foto_field):
    if not foto_field:
        return None
    try:
        foto_field.open('rb')
        data = BytesIO(foto_field.read())
        foto_field.close()
        return data
    except Exception:
        return None


def _icono_persona_placeholder(draw, cx, cy, r, color):
    draw.ellipse([cx - r * 0.32, cy - r * 0.62, cx + r * 0.32, cy - r * 0.02], outline=color, width=6)
    draw.arc([cx - r * 0.55, cy - r * 0.05, cx + r * 0.55, cy + r * 0.9], 200, 340, fill=color, width=6)


def _medallion(canvas, cx, cy, diametro, foto_field):
    r = diametro // 2
    aro_grosor = 14

    aro = _gradiente_lineal(diametro, diametro, VERDE, ROSA, angulo=145)
    mask = Image.new('L', (diametro, diametro), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([0, 0, diametro, diametro], fill=255)
    md.ellipse([aro_grosor, aro_grosor, diametro - aro_grosor, diametro - aro_grosor], fill=0)
    aro.putalpha(mask)
    canvas.paste(aro, (cx - r, cy - r), aro)

    interior_d = diametro - aro_grosor * 2 - 6
    interior_r = interior_d // 2
    ix, iy = cx - interior_r, cy - interior_r

    interior = _gradiente_lineal(interior_d, interior_d, BLANCO, BLUSH, angulo=160)
    mask_int = Image.new('L', (interior_d, interior_d), 0)
    ImageDraw.Draw(mask_int).ellipse([0, 0, interior_d, interior_d], fill=255)

    data = _abrir_foto(foto_field)
    if data:
        try:
            foto = Image.open(data).convert('RGB')
            foto = _crop_cuadrado(foto, interior_d)
            foto.putalpha(mask_int)
            canvas.paste(foto, (ix, iy), foto)
        except Exception:
            data = None
    if not data:
        interior.putalpha(mask_int)
        canvas.paste(interior, (ix, iy), interior)
        d = ImageDraw.Draw(canvas)
        _icono_persona_placeholder(d, cx, cy, interior_r * 0.62, VERDE_OSCURO)


# ── Generador principal ─────────────────────────────────────────────────
def generar_imagen_story(psicologo):
    canvas = _gradiente_lineal(W, H, CREMA, BLUSH, angulo=150).convert('RGB')

    # Manchas orgánicas en capas (verde, rosa, oro) + arco punteado + grano
    _mancha(canvas, -30, 60, 390, VERDE, alpha=95)
    _mancha(canvas, W + 60, H - 100, 450, ROSA, alpha=100)
    _mancha(canvas, W + 60, 900, 280, ORO, alpha=75)
    _mancha(canvas, -60, 1400, 230, VERDE, alpha=65)
    _arco_punteado(canvas, W // 2, 502, 350, VERDE_OSCURO, ancho=2, alpha=60)
    _grano(canvas)

    draw = ImageDraw.Draw(canvas)

    # ── Marca ──
    f_marca_a = _font('montserrat', 700, 42)
    marca_a, marca_p = 'Atención', 'Psi'
    espacio_w = _tw(draw, ' ', f_marca_a)
    total_w = _tw(draw, marca_a, f_marca_a) + espacio_w + _tw(draw, marca_p, f_marca_a)
    mx = (W - total_w) // 2
    my = 96
    draw.text((mx, my), marca_a, font=f_marca_a, fill=VERDE_OSCURO)
    mx += _tw(draw, marca_a, f_marca_a) + espacio_w
    draw.text((mx, my), marca_p, font=f_marca_a, fill=ROSA_OSCURO)

    # ── Medallón de foto ──
    diam = 588
    medallion_cy = 224 + diam // 2
    _medallion(canvas, W // 2, medallion_cy, diam, getattr(psicologo, 'foto', None))
    cy = 224 + diam + 56

    # ── Nombre ──
    nombre = _limpiar_nombre(psicologo.nombre)
    f_nombre = _font('playfair', 700, 86)
    lineas_nombre = _wrap(draw, nombre, f_nombre, W - 160)
    if len(lineas_nombre) > 2:
        f_nombre = _font('playfair', 700, 66)
        lineas_nombre = _wrap(draw, nombre, f_nombre, W - 160)
    for linea in lineas_nombre:
        _center(draw, linea, W // 2, cy, f_nombre, TINTA)
        cy += _th(draw, linea, f_nombre) + 16
    cy += 36

    # ── Datos: teléfono / modalidad + ciudad ──
    modalidades = list(psicologo.modalidades.values_list('nombre', flat=True))
    ciudades = list(psicologo.ciudades.values_list('nombre', flat=True))
    if len(modalidades) >= 2:
        texto_modalidad = ' y '.join(modalidades)
        texto_ciudad = ', '.join(ciudades)
    else:
        texto_modalidad = modalidades[0] if modalidades else ''
        texto_ciudad = ''

    telefono = _formatear_telefono(psicologo.whatsapp_limpio())
    texto_telefono = f'{PREFIJO_TELEFONO}{telefono}' if telefono else ''

    ancho_burbuja = int(W * 0.68)
    f_dato = _font('montserrat', 800, 36)
    f_dato_sub = _font('montserrat', 500, 23)

    datos_bloques = []
    if texto_telefono:
        alto = 96
        capa = _dibujar_burbuja_dato(
            lambda d, x: d.text((x, alto // 2), texto_telefono, font=f_dato, fill=TINTA, anchor='lm'),
            ancho_burbuja, alto, _icono_telefono,
        )
        datos_bloques.append(capa)
    if texto_modalidad:
        alto = 112 if texto_ciudad else 96
        def _dibujar_modalidad(d, x, alto=alto, texto_ciudad=texto_ciudad, texto_modalidad=texto_modalidad):
            if texto_ciudad:
                d.text((x, alto // 2 - 20), texto_modalidad, font=f_dato, fill=TINTA, anchor='lm')
                d.text((x, alto // 2 + 22), texto_ciudad, font=f_dato_sub, fill=TINTA_SUAVE, anchor='lm')
            else:
                d.text((x, alto // 2), texto_modalidad, font=f_dato, fill=TINTA, anchor='lm')
        capa = _dibujar_burbuja_dato(_dibujar_modalidad, ancho_burbuja, alto, _icono_ubicacion)
        datos_bloques.append(capa)

    bx = (W - ancho_burbuja) // 2
    for capa in datos_bloques:
        _pegar_con_sombra(canvas, capa, bx, cy, capa.size[1] // 2)
        cy += capa.size[1] + 22
    cy += 30

    # ── Burbujas inferiores (ancladas al fondo) ──
    f_burbuja_web = _font('montserrat', 700, 38)
    f_burbuja_ig = _font('montserrat', 600, 26)
    web_texto = DOMINIO_SITIO
    ig_texto = INSTAGRAM_HANDLE

    pad_web_x, pad_web_y = 52, 20
    web_w = _tw(draw, web_texto, f_burbuja_web) + pad_web_x * 2
    web_h = _th(draw, web_texto, f_burbuja_web) + pad_web_y * 2 + 10

    pad_ig_x, pad_ig_y = 32, 11
    ig_w = _tw(draw, ig_texto, f_burbuja_ig) + pad_ig_x * 2
    ig_h = _th(draw, ig_texto, f_burbuja_ig) + pad_ig_y * 2 + 8

    margen_inferior = 90
    gap_burbujas = 18
    ig_y = H - margen_inferior - ig_h
    web_y = ig_y - gap_burbujas - web_h

    draw.rounded_rectangle(
        [(W - web_w) // 2, web_y, (W + web_w) // 2, web_y + web_h],
        radius=web_h // 2, fill=VERDE_OSCURO,
    )
    _center(draw, web_texto, W // 2, web_y + pad_web_y, f_burbuja_web, BLANCO)

    draw.rounded_rectangle(
        [(W - ig_w) // 2, ig_y, (W + ig_w) // 2, ig_y + ig_h],
        radius=ig_h // 2, outline=ROSA_OSCURO, width=3,
    )
    _center(draw, ig_texto, W // 2, ig_y + pad_ig_y, f_burbuja_ig, ROSA_OSCURO)

    # ── Franja etaria: tipografía libre, se achica sola si la lista es larga ──
    destinatarios = ', '.join(psicologo.destinatarios.values_list('nombre', flat=True))
    if destinatarios:
        eyebrow = 'ATIENDE A'
        f_eyebrow = _font('montserrat', 700, 24)
        max_ancho_franja = 900
        limite_superior_y = cy
        limite_inferior_y = web_y - 40
        alto_encabezado = _th(draw, eyebrow, f_eyebrow) + 16 + 20 + 12

        for tam in (58, 50, 44, 38):
            f_franja = _font('playfair', 600, tam)
            lineas = _wrap(draw, destinatarios, f_franja, max_ancho_franja)
            alto_linea = _th(draw, 'Ag', f_franja) + 14
            alto_bloque = alto_linea * len(lineas)
            if limite_superior_y + alto_encabezado + alto_bloque <= limite_inferior_y or tam == 38:
                break

        fy = limite_superior_y
        _center(draw, eyebrow, W // 2, fy, f_eyebrow, VERDE_OSCURO)
        fy += _th(draw, eyebrow, f_eyebrow) + 16
        draw.line([(W // 2 - 32, fy + 8), (W // 2 + 32, fy + 8)], fill=VERDE, width=2)
        fy += 20 + 12
        for linea in lineas:
            capa_linea = _texto_italica(linea, f_franja, TINTA)
            canvas.paste(capa_linea, ((W - capa_linea.size[0]) // 2, fy), capa_linea)
            fy += alto_linea

    return canvas


def _texto_italica(texto, fnt, color, inclinacion=0.22):
    """
    PlayfairDisplay.ttf es una variable font solo de peso (sin eje itálico).
    Para lograr la itálica se dibuja el texto derecho en una capa aparte y se
    aplica una transformación afín (la misma técnica que usan los navegadores
    para la itálica "sintética"), igual a como se ve en el preview HTML.
    """
    tmp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bbox = tmp.textbbox((0, 0), texto, font=fnt)
    w, h = bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20
    capa = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(capa).text((10 - bbox[0], 10 - bbox[1]), texto, font=fnt, fill=color)
    ancho_final = w + int(h * inclinacion)
    capa = capa.transform(
        (ancho_final, h), Image.AFFINE,
        (1, inclinacion, -h * inclinacion, 0, 1, 0),
        resample=Image.BICUBIC,
    )
    return capa
