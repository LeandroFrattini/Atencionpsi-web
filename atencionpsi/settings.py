import os
from pathlib import Path
import dj_database_url

# Directorio base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# SEGURIDAD
SECRET_KEY = 'Carmela%70769177.'
DEBUG = False # Cambialo a True solo si necesitás ver errores detallados en local

ALLOWED_HOSTS = [
    'atencionpsi.com.ar', 
    'www.atencionpsi.com.ar', 
    'atencionpsi-web.onrender.com', 
    '.onrender.com', 
    'localhost', 
    '127.0.0.1'
]

# --- APLICACIONES INSTALADAS ---
INSTALLED_APPS = [
    'cloudinary_storage', # DEBE IR ANTES QUE STATICFILES
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary',         # AGREGADA
    'django.contrib.staticfiles',
    'profesionales', 
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

# --- BASE DE DATOS ---
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

# --- CONFIGURACIÓN DE CLOUDINARY ---
# Corregido: Las claves van directo o se sacan de las variables de Render
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dkzniwqq2', # El nombre que aparece en tu URL de Cloudinary
    'API_KEY': '338272543389882', # Sacalo de tu Dashboard de Cloudinary
    'API_SECRET': 'Fratto121030.' # Sacalo de tu Dashboard de Cloudinary
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Idioma y zona horaria
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# --- ARCHIVOS ESTÁTICOS Y MEDIA ---
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'