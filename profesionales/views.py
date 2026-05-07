import random
from django.shortcuts import render
# Cambiamos Destinatario por Publico
from .models import Psicologo, Modalidad, Publico 

def buscador(request):
    modalidad_id = request.GET.get('modalidad')
    dirigido_a_id = request.GET.get('dirigido_a')
    ciudad = request.GET.get('ciudad')

    queryset = Psicologo.objects.all()

    if modalidad_id:
        queryset = queryset.filter(modalidades__id=modalidad_id)
    
    if dirigido_a_id:
        # Filtramos por el ID del modelo Publico
        queryset = queryset.filter(destinatarios__id=dirigido_a_id)
    
    if ciudad:
        queryset = queryset.filter(ciudad__icontains=ciudad)

    destacados = list(queryset.filter(destacado=True).distinct())
    comunes = list(queryset.filter(destacado=False).distinct())
    random.shuffle(comunes)
    lista_final = destacados + comunes

    return render(request, 'buscador.html', {
        'psicologos': lista_final,
        'modalidades_list': Modalidad.objects.all(),
        'destinatarios_list': Publico.objects.all(), # Usamos Publico.objects
    })

def detalle_psicologo(request, slug):
    psicologo = get_object_or_404(Psicologo, slug=slug)
    return render(request, 'perfil.html', {'p': psicologo})

    # 4. LA FUNCIÓN QUE TE FALTA AHORA:
def unete(request):
    return render(request, 'unete.html')