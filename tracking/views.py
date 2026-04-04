from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q  # <--- ESTA ES LA LÍNEA QUE FALTABA
from .models import OrdenExamen
from .forms import OrdenExamenForm
from django.shortcuts import render, redirect, get_object_or_404
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
        
    # 2. Si buscaron texto, usamos Python para ignorar mayúsculas y la 'Ñ'
    if query:
        query_limpio = query.lower()
        ordenes_filtradas = []
        
        for orden in ordenes:
            nombre = orden.paciente_nombre.lower()
            cama = orden.cama.lower()
            # Si lo que escribieron está en el nombre o en la cama, lo guardamos
            if query_limpio in nombre or query_limpio in cama:
                ordenes_filtradas.append(orden)
                
        ordenes = ordenes_filtradas # Reemplazamos la lista con los resultados correctos
        
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
    # Solo permitimos que los usuarios del Laboratorio (Staff/Administradores) hagan esto
    if request.user.is_staff:
        orden = get_object_or_404(OrdenExamen, id=orden_id)
        # Validamos que el estado sea correcto antes de guardar
        estados_validos = [est[0] for est in OrdenExamen.ESTADO_CHOICES]
        if nuevo_estado in estados_validos:
            orden.estado = nuevo_estado
            orden.save()
            
    return redirect('dashboard')
@login_required(login_url='login')
def subir_resultado(request, orden_id):
    if not request.user.is_staff:
        return redirect('dashboard') # Solo el laboratorio puede subir resultados
        
    orden = get_object_or_404(OrdenExamen, id=orden_id)
    
    if request.method == 'POST':
        # request.FILES es vital para recibir PDFs o imágenes
        form = SubirResultadoForm(request.POST, request.FILES, instance=orden)
        if form.is_valid():
            orden_actualizada = form.save(commit=False)
            orden_actualizada.estado = 'RESULTADO' # Cambiamos el estado automáticamente a Verde
            orden_actualizada.save()
            return redirect('dashboard')
    else:
        form = SubirResultadoForm(instance=orden)
        
    return render(request, 'tracking/subir_resultado.html', {'form': form, 'orden': orden})

@login_required(login_url='login')
def editar_orden(request, orden_id):
    # Solo el personal de laboratorio (Staff) puede editar
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