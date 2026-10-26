from django.db import migrations


def padronizar(apps, schema_editor):
    # O cadastro de lote gravava 'ENTRADA', fora das opções do campo
    Estoque = apps.get_model('estoque', 'Estoque')
    Estoque.objects.filter(tipo_movimentacao='ENTRADA').update(tipo_movimentacao='Entrada')


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0002_alter_estoque_data_movimentacao_and_more'),
    ]

    operations = [
        migrations.RunPython(padronizar, migrations.RunPython.noop),
    ]
