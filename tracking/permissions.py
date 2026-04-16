GRUPO_LABORATORIO = 'Laboratorio'
GRUPO_EPIDEMIOLOGIA = 'Epidemiologia'
GRUPO_MEDICO = 'Medico'


def tiene_grupo(user, nombre_grupo):
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=nombre_grupo).exists()


def es_laboratorio(user):
    return user.is_authenticated and (
        user.is_superuser
        or user.is_staff
        or tiene_grupo(user, GRUPO_LABORATORIO)
    )


def es_epidemiologia(user):
    return user.is_authenticated and (
        user.username.lower() == 'epidemiologia'
        or tiene_grupo(user, GRUPO_EPIDEMIOLOGIA)
    )


def puede_gestionar_ordenes(user):
    return es_laboratorio(user)


def puede_ver_reportes(user):
    return es_laboratorio(user) or es_epidemiologia(user)


def puede_crear_ordenes(user):
    return user.is_authenticated and not es_epidemiologia(user)


def puede_administrar_usuarios(user):
    return user.is_authenticated and (user.is_superuser or es_laboratorio(user))


def obtener_contexto_roles(user):
    laboratorio = es_laboratorio(user)
    epidemiologia = es_epidemiologia(user)

    if laboratorio:
        rol_usuario = 'Laboratorio'
    elif epidemiologia:
        rol_usuario = 'Epidemiologia'
    else:
        rol_usuario = 'Medico / Servicio'

    return {
        'es_laboratorio': laboratorio,
        'es_epidemiologia': epidemiologia,
        'puede_gestionar_ordenes': laboratorio,
        'puede_ver_reportes': laboratorio or epidemiologia,
        'puede_crear_ordenes': user.is_authenticated and not epidemiologia,
        'puede_administrar_usuarios': puede_administrar_usuarios(user),
        'rol_usuario': rol_usuario,
    }
