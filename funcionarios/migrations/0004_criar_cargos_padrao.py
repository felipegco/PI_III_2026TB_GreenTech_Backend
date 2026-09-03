from django.db import migrations

CARGOS_PADRAO = ['admin', 'gerente', 'operador', 'tecnico']


def criar_cargos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nome in CARGOS_PADRAO:
        Group.objects.get_or_create(name=nome)


def remover_cargos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=CARGOS_PADRAO).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('funcionarios', '0003_remove_funcionario_cargo'),
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(criar_cargos, reverse_code=remover_cargos),
    ]