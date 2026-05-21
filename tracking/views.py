import os
import secrets
import unicodedata
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.db.models import Count, Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    CrearUsuarioSITMEForm,
    EliminarOrdenForm,
    OrdenExamenForm,
    ResetPasswordUsuarioForm,
    SubirResultadoForm,
)
from .models import AuditoriaUsuario, EventoOrden, IntentoLogin, OrdenExamen
from .permissions import (
    GRUPO_EPIDEMIOLOGIA,
    GRUPO_LABORATORIO,
    GRUPO_MEDICO,
    obtener_contexto_roles,
    puede_administrar_usuarios,
    puede_crear_ordenes,
    puede_gestionar_ordenes,
    puede_ver_reportes,
)


ESTADOS_VALIDOS = {estado for estado, _ in OrdenExamen.ESTADO_CHOICES}
LOGIN_MAX_FAILED_ATTEMPTS = getattr(settings, "SITME_LOGIN_MAX_FAILED_ATTEMPTS", 5)
LOGIN_LOCK_MINUTES = getattr(settings, "SITME_LOGIN_LOCK_MINUTES", 15)


def obtener_ip_cliente(request):
    cf_ip = request.META.get("HTTP_CF_CONNECTING_IP")
    if cf_ip:
        return cf_ip.strip()

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR") or "0.0.0.0"


def construir_identificador_login(request):
    username = (request.POST.get("username") or "").strip().casefold()
    ip_address = obtener_ip_cliente(request)
    return username, ip_address, f"{username or 'anonimo'}|{ip_address}"


class SITMELoginView(LoginView):
    template_name = "tracking/login.html"

    def post(self, request, *args, **kwargs):
        username, ip_address, identificador = construir_identificador_login(request)
        intento = IntentoLogin.objects.filter(identificador=identificador).first()

        if intento and intento.esta_bloqueado():
            form = self.get_form()
            form.add_error(
                None,
                "Demasiados intentos fallidos. Por seguridad, este acceso quedó "
                f"bloqueado hasta las {timezone.localtime(intento.bloqueado_hasta):%H:%M}.",
            )
            return super().form_invalid(form)

        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        username, ip_address, identificador = construir_identificador_login(self.request)
        intento, _ = IntentoLogin.objects.get_or_create(
            identificador=identificador,
            defaults={
                "username": username,
                "ip_address": ip_address,
            },
        )

        intento.username = username
        intento.ip_address = ip_address
        intento.intentos_fallidos += 1

        if intento.intentos_fallidos >= LOGIN_MAX_FAILED_ATTEMPTS:
            intento.bloqueado_hasta = timezone.now() + timedelta(minutes=LOGIN_LOCK_MINUTES)
            form.add_error(
                None,
                "Se detectaron varios intentos fallidos. La cuenta quedó protegida "
                f"durante {LOGIN_LOCK_MINUTES} minutos para frenar ataques por fuerza bruta.",
            )
        else:
            restantes = LOGIN_MAX_FAILED_ATTEMPTS - intento.intentos_fallidos
            form.add_error(
                None,
                f"Usuario o contraseña incorrectos. Intentos restantes antes del bloqueo: {restantes}.",
            )

        intento.save()
        return super().form_invalid(form)

    def form_valid(self, form):
        username, ip_address, identificador = construir_identificador_login(self.request)
        IntentoLogin.objects.filter(identificador=identificador).delete()
        IntentoLogin.objects.filter(username=username, ip_address=ip_address).delete()
        return super().form_valid(form)


def generar_password_temporal(longitud=12):
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789@#$"
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


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

    if nuevo_estado == "TOMADO":
        orden.laboratorista_toma = usuario
        orden.fecha_toma = ahora
    elif nuevo_estado == "ENVIADO":
        orden.laboratorista_envio = usuario
        orden.fecha_envio = ahora
    elif nuevo_estado == "RESULTADO":
        orden.laboratorista_resultado = usuario
        orden.fecha_resultado = ahora

    return estado_anterior


def construir_contexto_base(user):
    return obtener_contexto_roles(user)


def obtener_usuarios_para_panel():
    return User.objects.prefetch_related("groups").order_by("username")


def obtener_auditoria_usuarios_panel():
    return (
        AuditoriaUsuario.objects.select_related(
            "usuario_objetivo",
            "usuario_responsable",
        ).order_by("-fecha_evento", "-id")[:15]
    )


def construir_url_dashboard(estado=None, query="", alcance=None):
    params = {}

    if estado and estado != "TODAS":
        params["estado"] = estado

    if query:
        params["q"] = query

    if alcance == "mis":
        params["alcance"] = "mis"

    base = reverse("dashboard")
    querystring = urlencode(params)
    return f"{base}?{querystring}" if querystring else base


def obtener_rol_auditable_usuario(user):
    nombre_grupo = user.groups.values_list("name", flat=True).first()
    if nombre_grupo:
        return nombre_grupo

    if puede_gestionar_ordenes(user):
        return GRUPO_LABORATORIO

    if user.is_authenticated and not puede_crear_ordenes(user):
        return GRUPO_EPIDEMIOLOGIA

    if user.is_authenticated:
        return GRUPO_MEDICO

    return ""


def normalizar_texto_busqueda(texto):
    texto = str(texto or "").strip().casefold()
    texto_preservando_enie = texto.replace("ñ", "__enie__")
    texto_sin_tildes = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", texto_preservando_enie)
        if not unicodedata.combining(caracter)
    ).replace("__enie__", "ñ")
    texto_ascii = texto_sin_tildes.replace("ñ", "n")
    return texto, texto_sin_tildes, texto_ascii


def construir_texto_busqueda_orden(orden):
    partes = [
        orden.paciente_nombre,
        orden.cama,
        orden.notas,
    ]

    if orden.tipo_examen_id:
        partes.append(orden.tipo_examen.nombre)

    for usuario in (
        orden.medico_solicitante,
        orden.laboratorista_toma,
        orden.laboratorista_envio,
        orden.laboratorista_resultado,
    ):
        if usuario:
            partes.extend(
                [
                    usuario.username,
                    usuario.first_name,
                    usuario.last_name,
                    usuario.get_full_name(),
                ]
            )

    return " ".join(str(parte or "") for parte in partes)


def coincide_busqueda(texto_busqueda, query):
    texto_original, texto_normalizado, texto_ascii = normalizar_texto_busqueda(
        texto_busqueda
    )
    query_original, query_normalizada, query_ascii = normalizar_texto_busqueda(query)

    if query_original in texto_original or query_normalizada in texto_normalizado:
        return True

    if "ñ" in query_original:
        return False

    return query_ascii in texto_ascii


def registrar_auditoria_usuario(
    *,
    tipo_evento,
    descripcion,
    usuario_responsable,
    usuario_objetivo,
    rol_asignado="",
):
    return AuditoriaUsuario.objects.create(
        tipo_evento=tipo_evento,
        descripcion=descripcion,
        username_afectado=usuario_objetivo.username,
        nombre_visible_afectado=usuario_objetivo.first_name,
        rol_asignado=rol_asignado,
        usuario_objetivo=usuario_objetivo,
        usuario_responsable=usuario_responsable,
    )


@login_required(login_url="login")
def dashboard(request):
    query = (request.GET.get("q") or "").strip()
    estado_filtro = request.GET.get("estado")
    alcance_filtro = "mis" if request.GET.get("alcance") == "mis" and puede_crear_ordenes(request.user) else "todas"

    eventos_queryset = EventoOrden.objects.select_related("usuario")
    ordenes = (
        OrdenExamen.objects.select_related(
            "tipo_examen",
            "medico_solicitante",
            "laboratorista_toma",
            "laboratorista_envio",
            "laboratorista_resultado",
        )
        .prefetch_related(Prefetch("eventos", queryset=eventos_queryset))
        .filter(eliminado=False)
        .order_by("-fecha_solicitud", "-id")
    )

    if alcance_filtro == "mis":
        ordenes = ordenes.filter(medico_solicitante=request.user)

    if estado_filtro and estado_filtro != "TODAS":
        ordenes = ordenes.filter(estado=estado_filtro)

    if query:
        ordenes = [
            orden
            for orden in ordenes
            if coincide_busqueda(construir_texto_busqueda_orden(orden), query)
        ]

    context = {
        "ordenes": ordenes,
        "estado_actual": estado_filtro,
        "alcance_actual": alcance_filtro,
        "mostrar_filtro_mis_solicitudes": puede_crear_ordenes(request.user),
        "filtro_urls": {
            "todas": construir_url_dashboard(
                query=query,
                alcance=alcance_filtro if alcance_filtro == "mis" else None,
            ),
            "solicitado": construir_url_dashboard(
                estado="SOLICITADO",
                query=query,
                alcance=alcance_filtro if alcance_filtro == "mis" else None,
            ),
            "tomado": construir_url_dashboard(
                estado="TOMADO",
                query=query,
                alcance=alcance_filtro if alcance_filtro == "mis" else None,
            ),
            "enviado": construir_url_dashboard(
                estado="ENVIADO",
                query=query,
                alcance=alcance_filtro if alcance_filtro == "mis" else None,
            ),
            "resultado": construir_url_dashboard(
                estado="RESULTADO",
                query=query,
                alcance=alcance_filtro if alcance_filtro == "mis" else None,
            ),
            "alcance_todas": construir_url_dashboard(
                estado=estado_filtro,
                query=query,
            ),
            "alcance_mis": construir_url_dashboard(
                estado=estado_filtro,
                query=query,
                alcance="mis",
            ),
            "limpiar_busqueda": construir_url_dashboard(
                estado=estado_filtro,
                alcance=alcance_filtro if alcance_filtro == "mis" else None,
            ),
        },
    }
    context.update(construir_contexto_base(request.user))
    return render(request, "tracking/dashboard.html", context)


@login_required(login_url="login")
def crear_orden(request):
    if not puede_crear_ordenes(request.user):
        messages.error(
            request,
            "Tu usuario no tiene permisos para registrar solicitudes.",
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = OrdenExamenForm(request.POST)
        if form.is_valid():
            orden = form.save(commit=False)
            orden.medico_solicitante = request.user
            orden.save()
            registrar_evento(
                orden,
                "CREACION",
                "Solicitud registrada en SITME.",
                usuario=request.user,
                estado_nuevo=orden.estado,
            )
            messages.success(request, "La solicitud fue registrada correctamente.")
            return redirect("dashboard")
    else:
        form = OrdenExamenForm()

    context = {"form": form}
    context.update(construir_contexto_base(request.user))
    return render(request, "tracking/nueva_orden.html", context)


@login_required(login_url="login")
@require_POST
def cambiar_estado(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(
            request,
            "Tu usuario no tiene permisos para cambiar estados.",
        )
        return redirect("dashboard")

    nuevo_estado = request.POST.get("nuevo_estado")
    if nuevo_estado not in ESTADOS_VALIDOS:
        messages.error(request, "El estado solicitado no es válido.")
        return redirect("dashboard")

    orden = get_object_or_404(OrdenExamen, id=orden_id, eliminado=False)
    estado_anterior = registrar_cambio_estado(orden, nuevo_estado, request.user)
    orden.save()
    registrar_evento(
        orden,
        "CAMBIO_ESTADO",
        f"Estado actualizado de {estado_anterior} a {nuevo_estado}.",
        usuario=request.user,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
    )
    messages.success(request, "El estado de la muestra fue actualizado.")
    return redirect("dashboard")


@login_required(login_url="login")
def subir_resultado(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(
            request,
            "Tu usuario no tiene permisos para cargar resultados.",
        )
        return redirect("dashboard")

    orden = get_object_or_404(OrdenExamen, id=orden_id, eliminado=False)

    if request.method == "POST":
        ya_tenia_pdf = bool(orden.archivo_resultado)
        form = SubirResultadoForm(request.POST, request.FILES, instance=orden)
        if form.is_valid():
            orden_actualizada = form.save(commit=False)
            estado_anterior = registrar_cambio_estado(
                orden_actualizada, "RESULTADO", request.user
            )
            orden_actualizada.save()
            registrar_evento(
                orden_actualizada,
                "PDF",
                "Resultado PDF actualizado."
                if ya_tenia_pdf
                else "Resultado PDF cargado.",
                usuario=request.user,
                estado_anterior=estado_anterior,
                estado_nuevo="RESULTADO",
            )
            if estado_anterior != "RESULTADO":
                registrar_evento(
                    orden_actualizada,
                    "CAMBIO_ESTADO",
                    f"Estado actualizado de {estado_anterior} a RESULTADO.",
                    usuario=request.user,
                    estado_anterior=estado_anterior,
                    estado_nuevo="RESULTADO",
                )
            messages.success(request, "El resultado PDF fue cargado correctamente.")
            return redirect("dashboard")
    else:
        form = SubirResultadoForm(instance=orden)

    context = {"form": form, "orden": orden}
    context.update(construir_contexto_base(request.user))
    return render(request, "tracking/subir_resultado.html", context)


@login_required(login_url="login")
def descargar_resultado(request, orden_id):
    orden = get_object_or_404(OrdenExamen, id=orden_id, eliminado=False)

    if not orden.archivo_resultado:
        messages.error(request, "La orden seleccionada aún no tiene un PDF cargado.")
        return redirect("dashboard")

    ruta_archivo = orden.archivo_resultado.path
    if not os.path.exists(ruta_archivo):
        raise Http404("El archivo solicitado no existe en el servidor.")

    registrar_evento(
        orden,
        "DESCARGA_PDF",
        "Resultado PDF consultado o descargado.",
        usuario=request.user,
        estado_nuevo=orden.estado,
    )

    nombre_descarga = os.path.basename(orden.archivo_resultado.name)
    response = FileResponse(
        open(ruta_archivo, "rb"),
        as_attachment=False,
        filename=nombre_descarga,
        content_type="application/pdf",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@login_required(login_url="login")
def editar_orden(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(
            request,
            "Tu usuario no tiene permisos para editar solicitudes.",
        )
        return redirect("dashboard")

    orden = get_object_or_404(OrdenExamen, id=orden_id, eliminado=False)

    if request.method == "POST":
        form = OrdenExamenForm(request.POST, instance=orden)
        if form.is_valid():
            cambios = []
            for campo in ("paciente_nombre", "cama", "tipo_examen", "notas"):
                valor_anterior = getattr(orden, campo)
                valor_nuevo = form.cleaned_data[campo]
                if valor_anterior != valor_nuevo:
                    cambios.append(campo)

            form.save()
            descripcion = "Solicitud editada."
            if cambios:
                descripcion = "Solicitud editada: " + ", ".join(cambios) + "."
            registrar_evento(
                orden,
                "EDICION",
                descripcion,
                usuario=request.user,
                estado_nuevo=orden.estado,
            )
            messages.success(request, "La solicitud fue actualizada.")
            return redirect("dashboard")
    else:
        form = OrdenExamenForm(instance=orden)

    context = {"form": form, "orden": orden}
    context.update(construir_contexto_base(request.user))
    return render(request, "tracking/editar_orden.html", context)


@login_required(login_url="login")
@require_POST
def eliminar_orden(request, orden_id):
    if not puede_gestionar_ordenes(request.user):
        messages.error(
            request,
            "Tu usuario no tiene permisos para eliminar solicitudes.",
        )
        return redirect("dashboard")

    orden = get_object_or_404(OrdenExamen, id=orden_id, eliminado=False)
    form = EliminarOrdenForm(request.POST)

    if not form.is_valid():
        messages.error(
            request,
            "No se eliminó la solicitud porque falta registrar un motivo válido.",
        )
        return redirect("dashboard")

    motivo = form.cleaned_data["motivo"]
    ahora = timezone.now()
    orden.eliminado = True
    orden.fecha_eliminacion = ahora
    orden.usuario_eliminacion = request.user
    orden.motivo_eliminacion = motivo
    orden.save(
        update_fields=[
            "eliminado",
            "fecha_eliminacion",
            "usuario_eliminacion",
            "motivo_eliminacion",
        ]
    )

    registrar_evento(
        orden,
        "ELIMINACION",
        f"Solicitud retirada del tablero. Motivo: {motivo}",
        usuario=request.user,
        estado_nuevo=orden.estado,
    )
    messages.success(
        request,
        "La solicitud fue retirada del tablero y quedó registrada en auditoría.",
    )
    return redirect("dashboard")


@login_required(login_url="login")
def estadisticas(request):
    if not puede_ver_reportes(request.user):
        messages.error(request, "Tu usuario no tiene permisos para ver reportes.")
        return redirect("dashboard")

    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)

    fecha_inicio = request.GET.get("inicio", inicio_mes.strftime("%Y-%m-%d"))
    fecha_fin = request.GET.get("fin", hoy.strftime("%Y-%m-%d"))

    ordenes = OrdenExamen.objects.select_related("tipo_examen").filter(
        eliminado=False,
        fecha_solicitud__date__gte=fecha_inicio,
        fecha_solicitud__date__lte=fecha_fin,
    )
    ordenes_eliminadas = (
        OrdenExamen.objects.select_related(
            "tipo_examen",
            "usuario_eliminacion",
            "medico_solicitante",
        )
        .filter(
            eliminado=True,
            fecha_eliminacion__date__gte=fecha_inicio,
            fecha_eliminacion__date__lte=fecha_fin,
        )
        .order_by("-fecha_eliminacion", "-id")
    )

    conteo_examenes = (
        ordenes.values("tipo_examen__nombre").annotate(total=Count("id")).order_by("-total")
    )
    total_general = ordenes.count()

    context = {
        "conteo_examenes": conteo_examenes,
        "total_general": total_general,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "ordenes_eliminadas": ordenes_eliminadas,
    }
    context.update(construir_contexto_base(request.user))
    return render(request, "tracking/estadisticas.html", context)


@login_required(login_url="login")
def gestionar_usuarios(request):
    if not puede_administrar_usuarios(request.user):
        messages.error(
            request,
            "Tu usuario no tiene permisos para administrar usuarios.",
        )
        return redirect("dashboard")

    password_generada = None
    usuario_afectado = None

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "crear_usuario":
            form = CrearUsuarioSITMEForm(request.POST)

            if form.is_valid():
                password_generada = (
                    form.cleaned_data.get("password") or generar_password_temporal()
                )
                usuario = form.save()
                usuario.set_password(password_generada)
                usuario.save(update_fields=["password"])
                usuario_afectado = usuario
                registrar_auditoria_usuario(
                    tipo_evento="CREACION_USUARIO",
                    descripcion="Cuenta creada desde el panel de gestion de usuarios SITME.",
                    usuario_responsable=request.user,
                    usuario_objetivo=usuario,
                    rol_asignado=form.cleaned_data["rol"],
                )
                messages.success(
                    request,
                    f"Usuario {usuario.username} creado correctamente.",
                )
                form = CrearUsuarioSITMEForm()
        elif accion == "reset_password":
            reset_form = ResetPasswordUsuarioForm(request.POST)
            form = CrearUsuarioSITMEForm()

            if reset_form.is_valid():
                usuario = get_object_or_404(
                    User, id=reset_form.cleaned_data["usuario_id"]
                )
                password_generada = generar_password_temporal()
                usuario.set_password(password_generada)
                usuario.save(update_fields=["password"])
                usuario_afectado = usuario
                registrar_auditoria_usuario(
                    tipo_evento="RESET_PASSWORD",
                    descripcion="Se genero una nueva contrasena temporal desde el panel SITME.",
                    usuario_responsable=request.user,
                    usuario_objetivo=usuario,
                    rol_asignado=obtener_rol_auditable_usuario(usuario),
                )
                messages.success(
                    request,
                    f"Se generó una nueva contraseña temporal para {usuario.username}.",
                )
        else:
            form = CrearUsuarioSITMEForm()
    else:
        form = CrearUsuarioSITMEForm()

    context = {
        "form": form,
        "usuarios": obtener_usuarios_para_panel(),
        "auditoria_usuarios": obtener_auditoria_usuarios_panel(),
        "password_generada": password_generada,
        "usuario_afectado": usuario_afectado,
    }
    context.update(construir_contexto_base(request.user))
    return render(request, "tracking/usuarios.html", context)
