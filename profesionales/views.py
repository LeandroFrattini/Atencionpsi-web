from django.shortcuts import render, get_object_or_404
from .models import Psicologo, Modalidad, Publico
import random

def inicio(request):
    return render(request, 'index.html')

def buscador(request):
    modalidad_buscada = request.GET.get('modalidad')
    dirigido_a = request.GET.get('dirigido_a')
    ciudad = request.GET.get('ciudad')

    queryset = Psicologo.objects.all()

    if modalidad_buscada:
        queryset = queryset.filter(modalidades__nombre__icontains=modalidad_buscada)
    
    if dirigido_a:
        queryset = queryset.filter(destinatarios__nombre__icontains=dirigido_a)
    
    if ciudad:
        queryset = queryset.filter(ciudad__icontains=ciudad)

    # Orden: Destacados primero, comunes aleatorios después. 
    # .distinct() es vital aquí para evitar duplicados en ManyToMany
    destacados = list(queryset.filter(destacado=True).distinct())
    comunes = list(queryset.filter(destacado=False).distinct())

    random.shuffle(comunes)
    lista_final = destacados + comunes

    return render(request, 'buscador.html', {'psicologos': lista_final})

def detalle_psicologo(request, slug):
    psicologo = get_object_or_404(Psicologo, slug=slug)
    return render(request, 'perfil.html', {'p': psicologo})

    # 4. LA FUNCIÓN QUE TE FALTA AHORA:
def unete(request):
    return render(request, 'unete.html')