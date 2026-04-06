from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q  
from .models import OrdenExamen
from .forms import OrdenExamenForm, SubirResultadoForm

def dashboard(request):
    # Capturamos lo que el usuario busque
    query = request.GET.get('q')
    estado_filtro = request.GET.get('estado')
    
    # Empezamos trayendo todas las órdenes
    ordenes = OrdenExamen.objects.all()
    
    # 1. Si hicieron clic en un botón de estado, filtramos primero eso
    if estado_filtro and estado_filtro != 'TODAS':
        ordenes = ordenes.filter(estado=estado_filtro)
        
    # 2. Si buscaron texto, usamos Q para buscar en nombre o cama (ignora mayúsculas)
    if query:
        ordenes = ordenes.filter(
            Q(paciente_nombre__icontains=query) | Q(cama__icontains=query)
        )
        
    return render(request, 'tracking/dashboard.html', {
        'ordenes': ordenes,
        'estado_actual': estado_filtro 
    })

@login_required(login_url='login') 
def crear_orden(request):
    if request.method == 'POST':
        form = OrdenExamenForm(request.POST)
        if form.is_valid():
            orden = form.save(commit=False)
            if request.user.is_authenticated:
                orden.medico_solicitante = request.user
            orden.save()
            return redirect('dashboard')
    else:
        form = OrdenExamenForm()
    
    return render(request, 'tracking/nueva_orden.html', {'form': form})

@login_required(login_url='login')
def cambiar_estado(request, orden_id, nuevo_estado):
    if not request.user.is_staff:
        return redirect('dashboard')
    
    orden = get_object_or_404(OrdenExamen, id=orden_id)
    orden.estado = nuevo_estado
    
    # --- LÓGICA DE AUDITORÍA: GUARDAR QUIÉN HIZO QUÉ ---
    if nuevo_estado == 'TOMADO':
        orden.laboratorista_toma = request.user
    elif nuevo_estado == 'ENVIADO':
        orden.laboratorista_envio = request.user
    elif nuevo_estado == 'RESULTADO':
        orden.laboratorista_resultado = request.user
        
    orden.save()
    return redirect('dashboard')

@login_required(login_url='login')
def subir_resultado(request, orden_id):
    if not request.user.is_staff:
        return redirect('dashboard') 
        
    orden = get_object_or_404(OrdenExamen, id=orden_id)
    
    if request.method == 'POST':
        form = SubirResultadoForm(request.POST, request.FILES, instance=orden)
        if form.is_valid():
            orden_actualizada = form.save(commit=False)
            orden_actualizada.estado = 'RESULTADO' 
            # --- AQUÍ FALTABA EL REGISTRO DE AUDITORÍA ---
            orden_actualizada.laboratorista_resultado = request.user
            orden_actualizada.save()
            return redirect('dashboard')
    else:
        form = SubirResultadoForm(instance=orden)
        
    return render(request, 'tracking/subir_resultado.html', {'form': form, 'orden': orden})

@login_required(login_url='login')
def editar_orden(request, orden_id):
    if not request.user.is_staff:
        return redirect('dashboard')
        
    orden = get_object_or_404(OrdenExamen, id=orden_id)
    
    if request.method == 'POST':
        form = OrdenExamenForm(request.POST, instance=orden)
        if form.is_valid():
            form.save()
            return redirect('dashboard')
    else:
        form = OrdenExamenForm(instance=orden)
        
    return render(request, 'tracking/editar_orden.html', {'form': form, 'orden': orden})