import re

# Patrones de User-Agent de bots, crawlers, previsualizadores y scripts conocidos.
# Ningún filtro por User-Agent es 100% infalible, pero esto corta la enorme
# mayoría del tráfico no humano que infla las estadísticas (Google, Bing,
# WhatsApp/Facebook generando previews de links, herramientas de SEO, scrapers, etc.)
BOT_PATTERNS = [
    r'bot', r'crawl', r'spider', r'slurp',
    r'facebookexternalhit', r'whatsapp', r'telegrambot', r'discordbot',
    r'twitterbot', r'linkedinbot', r'pinterest',
    r'ahrefs', r'semrush', r'mj12bot', r'dotbot', r'petalbot', r'bytespider',
    r'yandex', r'baiduspider', r'duckduckbot', r'applebot',
    r'python-requests', r'curl/', r'wget/', r'scrapy',
    r'headlesschrome', r'phantomjs', r'go-http-client', r'okhttp',
    r'postmanruntime', r'axios',
]

BOT_REGEX = re.compile('|'.join(BOT_PATTERNS), re.IGNORECASE)


def es_bot(request):
    """
    Heurística simple para detectar bots/crawlers/scripts a partir del User-Agent.

    Se usa en dos lugares:
    - VisitaMiddleware (cuenta de visualizaciones de página)
    - registrar_click_whatsapp (cuenta de clicks reales al botón de WhatsApp)
    """
    ua = request.META.get('HTTP_USER_AGENT', '')

    # Sin User-Agent, o uno sospechosamente corto: casi siempre es un script/bot
    if not ua or len(ua) < 10:
        return True

    if BOT_REGEX.search(ua):
        return True

    return False
