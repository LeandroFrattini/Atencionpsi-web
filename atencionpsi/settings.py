import os
from pathlib import Path
import dj_database_url

# Directorio base del proyecto
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
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'storages',  # Requerido para Supabase/S3
    'profesionales', 
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Mantiene tus estilos vivos
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

# BASE DE DATOS
if 'RENDER' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
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

# --- CONFIGURACIÓN DE ARCHIVOS (ESTABILIDAD TOTAL) ---

# 1. ESTÁTICOS (CSS/JS) - Manejados por WhiteNoise
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = "whitenoise.storage.StaticFilesStorage"

# 2. MEDIA (FOTOS) - Manejados por Supabase/S3
if 'RENDER' in os.environ:
    # Intentamos obtener las credenciales de las variables de entorno de Render
    AWS_ACCESS_KEY_ID = os.environ.get('ad2c6e68d639588055917cb82c5af3f8')
    AWS_SECRET_ACCESS_KEY = os.environ.get('299fbe7144d2a7178a548694a837d9bd41f4e2b8de947cd87fe26c179ab5eb89')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('atencionpsi')
    AWS_S3_ENDPOINT_URL = os.environ.get('https://xaityyqwedfcnizedgkj.supabase.co/storage/v1/s3')

    # Validación de Seguridad: Si falta alguna, el sitio sigue andando pero te avisa
    if all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL]):
        DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
        AWS_S3_FILE_OVERWRITE = False
        AWS_DEFAULT_ACL = None
        AWS_S3_VERIFY = True
        # Esto asegura que las URLs de las fotos sean firmadas y seguras
        AWS_QUERYSTRING_AUTH = False 
    else:
        # Fallback: Si no configuraste Supabase aún, usa el almacenamiento local 
        # para que la web NO se caiga y los estilos sigan funcionando.
        print("⚠️ Advertencia: Credenciales de Supabase incompletas. Usando almacenamiento local temporal.")
        DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
else:
    # Configuración para tu PC (Localhost)
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# EXTRAS
WHITENOISE_MANIFEST_STRICT = False
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'