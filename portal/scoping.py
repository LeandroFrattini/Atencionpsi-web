"""
Único punto de acceso para traer un Paciente o Turno puntual por id dentro
del portal. Toda vista que necesite un objeto individual DEBE pasar por acá
(nunca `get_object_or_404(Paciente, pk=pk)` directo) para garantizar que un
psicólogo jamás pueda ver/editar el registro de otro cambiando el id en la URL.
"""
from django.shortcuts import get_object_or_404
from .models import Paciente, Turno


def get_paciente_or_404(psico, pk):
    return get_object_or_404(Paciente, pk=pk, psicologo=psico)


def get_turno_or_404(psico, pk):
    return get_object_or_404(Turno, pk=pk, psicologo=psico)
