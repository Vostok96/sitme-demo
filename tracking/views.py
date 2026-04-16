import secrets

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CrearUsuarioSITMEForm, OrdenExamenForm, ResetPasswordUsuarioForm, SubirResultadoForm
from .models import EventoOrden, OrdenExamen
from .permissions import (
    obtener_contexto_roles,
    puede_administrar_usuarios,
    puede_crear_ordenes,
    puede_gestionar_ordenes,
    puede_ver_reportes,
)


ESTADOS_VALIDOS = {estado for estado, _ in OrdenExamen.ESTADO_CHOICES}


def generar_password_temporal(longitud=12):
    alfabeto = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#$'
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


def registrar_evento(
    orden,
    tipo_evento,
    descripcion,
    usuario=None,
    estado_anterior=None,
    estado_nuevo=None,
):
    return EventoOrden.objects.create(
        orden=orden,
        tipo_evento=tipo_evento,
        descripcion=descripcion,
        usuario=usuario,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_nuevo,
    )


def registrar_cambio_estado(orden, nuevo_estado, usuario):
    estado_anterior = orden.estado
    ahora = timezone.now()
    orden.estado = nuevo_estado

    if nuevo_estado == 'TOMADO':
        orden.laboratorista_toma = usuario
        orden.fecha_toma = ahora
    elif nuevo_estado == 'ENVIADO':
        orden.laboratorista_envio = usuario
        orden.fecha_envio = ahora
    elif nuevo_estado == 'RESULTADO':
        orden.laboratorista_resultado = usuario
        orden.fecha_resultado = ahora

    return estado_anterior


def construir_contexto_base(user):
    return obtener_contexto_roles(user)


def obtener_usuarios_para_panel():
    return User.objects.prefetch_related('groups').order_by('username')


@login_required(login_url='login')
def dashboard(request):
    query = request.GET.get('q')
    estado_filtro = request.GET.get('estado')

    eventos_queryset = EventoOrden.objects.select_related('usuario')
    ordenes = OrdenExamen.objects.select_related(
        'tipo_examen',
        'medico_solicitante',
        'laboratorista_toma',
        'laboratorista_envio',
        'laboratorista_resultado',
    ).prefetch_related(
        Prefetch('eventos', queryset=eventos_queryset)
    )

    if estado_filtro and estado_filtro != 'TODAS':
        ordenes = ordenes.filter(estado=estado_filtro)

    if query:
        ordenes = ordenes.filter(
            Q(paciente_nombre__icontains=query)
            | Q(cama__icontains=query)
            | Q(tipo_examen__nombre__icontains=query)
            | Q(medico_solicitante__username__icontains=query)
        )

    context = {
        'ordenes': ordenes,
        'estado_actual': estado_filtro,
    }
    context.update(construir_contexto_base(request.user))
    return render(request, 'tracking/dashboard.html', context)


@login_required(login_url='login')
def crear_orden(request):
    if not puede_crear_ordenes(request.user):
        messages.error(request, 'Tu usuario no tiene permisos para registrar solicitudes.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = OrdenExamenForm(request.POST)
        if form.is_valid():
            orden = form.save(commit=False)
            orden.medico_solicitante = request.user
            orden.save()
            registrar_evento(
                orden,
                'CREACION',
                'Solicitud registrada en SITME.',
                usuario=request.user,
                estado_nuevo=orden.estado,
            )
            messages.success(request, 'La solicitud fue registrada correctamente.')
            return redirect('dashboard')
    else:
        form = OrdenExamenForm()

    context = {'form': form}
    context.update(construir_contexto_base(request.user))
    return render(request, 'tracking/nueva_orden.html', context)


@login_required(login_url='login')
@require_POST
def cambiar_estado(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(request, 'Tu usuario no tiene permisos para cambiar estados.')
        return redirect('dashboard')

    nuevo_estado = request.POST.get('nuevo_estado')
    if nuevo_estado not in ESTADOS_VALIDOS:
        messages.error(request, 'El estado solicitado no es valido.')
        return redirect('dashboard')

    orden = get_object_or_404(OrdenExamen, id=orden_id)
    estado_anterior = registrar_cambio_estado(orden, nuevo_estado, request.user)
    orden.save()
    registrar_evento(
        orden,
        'CAMBIO_ESTADO',
        f'Estado actualizado de {estado_anterior} a {nuevo_estado}.',
        usuario=request.user,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
    )
    messages.success(request, 'El estado de la muestra fue actualizado.')
    return redirect('dashboard')


@login_required(login_url='login')
def subir_resultado(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(request, 'Tu usuario no tiene permisos para cargar resultados.')
        return redirect('dashboard')

    orden = get_object_or_404(OrdenExamen, id=orden_id)

    if request.method == 'POST':
        ya_tenia_pdf = bool(orden.archivo_resultado)
        form = SubirResultadoForm(request.POST, request.FILES, instance=orden)
        if form.is_valid():
            orden_actualizada = form.save(commit=False)
            estado_anterior = registrar_cambio_estado(orden_actualizada, 'RESULTADO', request.user)
            orden_actualizada.save()
            registrar_evento(
                orden_actualizada,
                'PDF',
                'Resultado PDF actualizado.' if ya_tenia_pdf else 'Resultado PDF cargado.',
                usuario=request.user,
                estado_anterior=estado_anterior,
                estado_nuevo='RESULTADO',
            )
            if estado_anterior != 'RESULTADO':
                registrar_evento(
                    orden_actualizada,
                    'CAMBIO_ESTADO',
                    f'Estado actualizado de {estado_anterior} a RESULTADO.',
                    usuario=request.user,
                    estado_anterior=estado_anterior,
                    estado_nuevo='RESULTADO',
                )
            messages.success(request, 'El resultado PDF fue cargado correctamente.')
            return redirect('dashboard')
    else:
        form = SubirResultadoForm(instance=orden)

    context = {'form': form, 'orden': orden}
    context.update(construir_contexto_base(request.user))
    return render(request, 'tracking/subir_resultado.html', context)


@login_required(login_url='login')
def editar_orden(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(request, 'Tu usuario no tiene permisos para editar solicitudes.')
        return redirect('dashboard')

    orden = get_object_or_404(OrdenExamen, id=orden_id)

    if request.method == 'POST':
        form = OrdenExamenForm(request.POST, instance=orden)
        if form.is_valid():
            cambios = []
            for campo in ('paciente_nombre', 'cama', 'tipo_examen', 'notas'):
                valor_anterior = getattr(orden, campo)
                valor_nuevo = form.cleaned_data[campo]
                if valor_anterior != valor_nuevo:
                    cambios.append(campo)

            form.save()
            descripcion = 'Solicitud editada.'
            if cambios:
                descripcion = 'Solicitud editada: ' + ', '.join(cambios) + '.'
            registrar_evento(
                orden,
                'EDICION',
                descripcion,
                usuario=request.user,
                estado_nuevo=orden.estado,
            )
            messages.success(request, 'La solicitud fue actualizada.')
            return redirect('dashboard')
    else:
        form = OrdenExamenForm(instance=orden)

    context = {'form': form, 'orden': orden}
    context.update(construir_contexto_base(request.user))
    return render(request, 'tracking/editar_orden.html', context)


@login_required(login_url='login')
def estadisticas(request):
    if not puede_ver_reportes(request.user):
        messages.error(request, 'Tu usuario no tiene permisos para ver reportes.')
        return redirect('dashboard')

    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)

    fecha_inicio = request.GET.get('inicio', inicio_mes.strftime('%Y-%m-%d'))
    fecha_fin = request.GET.get('fin', hoy.strftime('%Y-%m-%d'))

    ordenes = OrdenExamen.objects.select_related('tipo_examen').filter(
        fecha_solicitud__date__gte=fecha_inicio,
        fecha_solicitud__date__lte=fecha_fin,
    )

    conteo_examenes = ordenes.values('tipo_examen__nombre').annotate(
        total=Count('id')
    ).order_by('-total')
    total_general = ordenes.count()

    context = {
        'conteo_examenes': conteo_examenes,
        'total_general': total_general,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
    }
    context.update(construir_contexto_base(request.user))
    return render(request, 'tracking/estadisticas.html', context)


@login_required(login_url='login')
def gestionar_usuarios(request):
    if not puede_administrar_usuarios(request.user):
        messages.error(request, 'Tu usuario no tiene permisos para administrar usuarios.')
        return redirect('dashboard')

    password_generada = None
    usuario_afectado = None

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'crear_usuario':
            form = CrearUsuarioSITMEForm(request.POST)
            reset_form = ResetPasswordUsuarioForm()

            if form.is_valid():
                password_generada = form.cleaned_data.get('password') or generar_password_temporal()
                usuario = form.save()
                usuario.set_password(password_generada)
                usuario.save(update_fields=['password'])
                usuario_afectado = usuario
                messages.success(request, f'Usuario {usuario.username} creado correctamente.')
                form = CrearUsuarioSITMEForm()
        elif accion == 'reset_password':
            reset_form = ResetPasswordUsuarioForm(request.POST)
            form = CrearUsuarioSITMEForm()

            if reset_form.is_valid():
                usuario = get_object_or_404(User, id=reset_form.cleaned_data['usuario_id'])
                password_generada = generar_password_temporal()
                usuario.set_password(password_generada)
                usuario.save(update_fields=['password'])
                usuario_afectado = usuario
                messages.success(request, f'Se genero una nueva contrasena temporal para {usuario.username}.')
        else:
            form = CrearUsuarioSITMEForm()
            reset_form = ResetPasswordUsuarioForm()
    else:
        form = CrearUsuarioSITMEForm()
        reset_form = ResetPasswordUsuarioForm()

    context = {
        'form': form,
        'reset_form': reset_form,
        'usuarios': obtener_usuarios_para_panel(),
        'password_generada': password_generada,
        'usuario_afectado': usuario_afectado,
    }
    context.update(construir_contexto_base(request.user))
    return render(request, 'tracking/usuarios.html', context)
