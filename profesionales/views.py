import random
from django.shortcuts import render, get_object_or_404 # Importación vital agregada
from .models import Psicologo, Modalidad, Publico 

# --- VISTA DE INICIO ---
def inicio(request):
    return render(request, 'index.html')

# --- VISTA DEL BUSCADOR ---
def buscador(request):
    modalidad_id = request.GET.get('modalidad')
    dirigido_a_id = request.GET.get('dirigido_a')
    ciudad = request.GET.get('ciudad')

    queryset = Psicologo.objects.all()

    # Filtros por ID para que coincidan con los Selects del HTML
    if modalidad_id:
        queryset = queryset.filter(modalidades__id=modalidad_id)
    
    if dirigido_a_id:
        queryset = queryset.filter(destinatarios__id=dirigido_a_id)
    
    if ciudad:
        queryset = queryset.filter(ciudad__icontains=ciudad)

    # Lógica de destacados y aleatorios
    destacados = list(queryset.filter(destacado=True).distinct())
    comunes = list(queryset.filter(destacado=False).distinct())
    random.shuffle(comunes)
    lista_final = destacados + comunes

    return render(request, 'buscador.html', {
        'psicologos': lista_final,
        'modalidades_list': Modalidad.objects.all(),
        'destinatarios_list': Publico.objects.all(),
    })

# --- VISTA DE PERFIL ---
def detalle_psicologo(request, slug):
    psicologo = get_object_or_404(Psicologo, slug=slug)
    return render(request, 'perfil.html', {'p': psicologo})

# --- VISTA ÚNETE ---
def unete(request):
    return render(request, 'unete.html')

def sobre_nosotros(request):
    return render(request, 'sobre_nosotros.html')

def faq(request):
    return render(request, 'faq.html')