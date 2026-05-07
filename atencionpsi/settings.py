import os
from pathlib import Path
import dj_database_url

# Directorio base
BASE_DIR = Path(__file__).resolve().parent.parent

# SEGURIDAD
SECRET_KEY = 'Carmela%70769177.'
DEBUG = False

ALLOWED_HOSTS = [
    'atencionpsi.com.ar', 
    'www.atencionpsi.com.ar', 
    'atencionpsi-web.onrender.com', 
    '.onrender.com', 
    'localhost', 
    '127.0.0.1'
]

# APLICACIONES
INSTALLED_APPS = [
    'cloudinary_storage',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary',
    'django.contrib.staticfiles',
    'profesionales', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # SERVIDOR DE ESTILOS
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
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

# BASE DE DATOS (Detecta si es Render o PC local)
if 'RENDER' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL', 'postgresql://atencionpsi_user:1NqMJ7fbwN7ujSmN7aqGaEdX5HbBCYBL@dpg-d7tak8jrjlhs73e1jqb0-a/atencionpsi'),
            conn_max_age=600
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ALMACENAMIENTO (STORAGES)
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.StaticFilesStorage",
    },
}

# CLOUDINARY
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dkzniwqq2',
    'API_KEY': '338272543389882',
    'API_SECRET': 'Fratto121030.'
}

# CONFIGURACIÓN DE ESTÁTICOS (Aquí está el truco)
STATIC_URL = '/static/'

# Esto le dice a Django dónde están tus carpetas de CSS/JS originales
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Esto le dice a Render dónde juntar todos los archivos para servirlos
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# PARCHE PARA WHITENOISE
WHITENOISE_MANIFEST_STRICT = False

# MEDIA
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# OTROS
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'