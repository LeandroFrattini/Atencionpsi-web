import os
import django

# Configuramos el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'atencionpsi.settings')
django.setup()

from django.contrib.auth.models import User

# Datos del superusuario (Cambiá esto por lo que vos quieras)
username = 'barbarapereyra'
email = 'pereyrabn@gmail.com'
password = 'Carmela1410.'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username, email, password)
    print(f"Superusuario '{username}' creado exitosamente.")
else:
    print(f"El usuario '{username}' ya existe.")