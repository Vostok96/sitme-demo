from django.db import migrations


def asignar_grupo_medico(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    grupo_medico, _ = Group.objects.get_or_create(name='Medico')

    for usuario in User.objects.filter(groups__isnull=True, is_active=True):
        if usuario.username.lower() == 'epidemiologia':
            continue
        if usuario.is_staff or usuario.is_superuser:
            continue
        usuario.groups.add(grupo_medico)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0007_crear_grupos_base_sitme'),
    ]

    operations = [
        migrations.RunPython(asignar_grupo_medico, noop_reverse),
    ]
