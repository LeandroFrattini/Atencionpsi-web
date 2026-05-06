import os  # <--- ESTA LÍNEA ES LA QUE SOLUCIONA EL NAMEERROR
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# SEGURIDAD
SECRET_KEY = 'Carmela%70769177.'
DEBUG = False
ALLOWED_HOSTS = ['atencionpsi.com.ar', 'www.atencionpsi.com.ar', 'atencion-psi-web.onrender.com', 'localhost', '127.0.0.1']

# Aplicaciones instaladas
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'profesionales', # <--- AQUÍ SOLO DEBE ESTAR TU APP, NO 'templates'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'atencionpsi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Buscamos en todas las ubicaciones posibles para que no falle
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            os.path.join(BASE_DIR, 'profesionales', 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'atencionpsi.wsgi.application'

# Base de datos
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Idioma y zona horaria
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# --- CONFIGURACIÓN DE ESTÁTICOS ---
STATIC_URL = 'static/'

# Esta es la carpeta donde vos trabajás (la que ya tenés)
BASE_DIR = Path(__file__).resolve().parent.parent

STATIC_URL = '/static/' # Asegurate de que tenga las dos barras

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Esto es lo que agregamos recién, dejalo así:
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Archivos Multimedia (Fotos)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'