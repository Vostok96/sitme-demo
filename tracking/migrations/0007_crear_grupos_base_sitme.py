from django.db import migrations


GRUPO_LABORATORIO = 'Laboratorio'
GRUPO_EPIDEMIOLOGIA = 'Epidemiologia'
GRUPO_MEDICO = 'Medico'


def crear_grupos_base(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')

    grupo_lab, _ = Group.objects.get_or_create(name=GRUPO_LABORATORIO)
    grupo_epi, _ = Group.objects.get_or_create(name=GRUPO_EPIDEMIOLOGIA)
    Group.objects.get_or_create(name=GRUPO_MEDICO)

    for usuario in User.objects.filter(is_staff=True):
        usuario.groups.add(grupo_lab)

    for usuario in User.objects.filter(username__iexact='epidemiologia'):
        usuario.groups.add(grupo_epi)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tracking', '0006_alter_catalogoexamen_options_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_grupos_base, noop_reverse),
    ]
