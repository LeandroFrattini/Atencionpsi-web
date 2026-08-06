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

# Validación de contraseñas (aplica a /admin/ y a /portal/).
# A propósito más simple que en otros proyectos: los profesionales que usan
# esto no son todos usuarios técnicos. Se mantiene lo mínimo indispensable
# (largo razonable, que no sea una clave típica, que no sea igual al usuario)
# y se saca la restricción de "no solo números" para no generar fricción.
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
]

# Login del portal de psicólogos
LOGIN_URL = 'portal_login'
LOGIN_REDIRECT_URL = 'portal_dashboard'
LOGOUT_REDIRECT_URL = 'portal_login'
SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 horas
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Hardening de cookies/SSL solo en Render: en local DEBUG está hardcodeado en False
# así que no sirve para distinguir prod/local (ver convención ya usada más abajo
# para DATABASES y storage de media).
if 'RENDER' in os.environ:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Render termina TLS en su proxy y reenvía HTTP plano a gunicorn: sin esto,
    # SECURE_SSL_REDIRECT provoca un loop infinito de redirects en producción.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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
    'portal',
    'axes',  # Bloqueo por fuerza bruta en el login del portal
    'django.contrib.sitemaps',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'profesionales.auth_backends.EmailCaseInsensitiveBackend',
]

AXES_COOLOFF_TIME = 1  # hora de bloqueo automático tras superar el límite de intentos

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Mantiene tus estilos vivos
    'profesionales.middleware.VisitaMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
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

# Configuración de Media (Fotos de profesionales en Supabase)
if 'RENDER' in os.environ:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    
    SUBDOMAIN = "xaityyqwedfcnizedgkj" 

    if all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME]):
        DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
        AWS_S3_ENDPOINT_URL = f'https://{SUBDOMAIN}.supabase.co/storage/v1/s3'
        
        # Configuración de compatibilidad S3
        AWS_S3_SIGNATURE_VERSION = 's3v4'
        AWS_S3_FILE_OVERWRITE = False
        AWS_DEFAULT_ACL = None
        AWS_QUERYSTRING_AUTH = False
        AWS_S3_VERIFY = True
        AWS_S3_ADDRESSING_STYLE = 'path'
        AWS_S3_REGION_NAME = 'us-east-1'

        # URL pública para que las imágenes se vean (Usar solo para visualización)
        AWS_S3_CUSTOM_DOMAIN = f'{SUBDOMAIN}.supabase.co/storage/v1/object/public/{AWS_STORAGE_BUCKET_NAME}'
    else:
        DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# EXTRAS
WHITENOISE_MANIFEST_STRICT = False
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'