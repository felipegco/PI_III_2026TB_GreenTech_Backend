from lotePlantio.models import LotePlantio

from .models import Alerta

# Faixa usada quando a mesa não tem lote com cultura vinculada
FAIXA_PADRAO = {'temp_min': 16.0, 'temp_max': 30.0, 'umidade_ideal': 70.0}

# Mesmos limites da tela de alertas do front-end
TEMP_CRITICO_ALEM_DE = 4.0
UMIDADE_TOLERANCIA = 15.0
UMIDADE_CRITICO_ALEM_DE = 25.0

# Alinhados ao simulador de irrigação, que abre a válvula abaixo de 40 %
SOLO_MINIMO = 40.0
SOLO_CRITICO_ABAIXO_DE = 25.0
SOLO_MAXIMO = 90.0

STATUS_LOTE_EM_CULTIVO = [LotePlantio.StatusPlantio.ATIVO, LotePlantio.StatusPlantio.DISPONIVEL]


def faixa_da_mesa(mesa):
    """Limites da cultura do lote mais recente em cultivo na mesa. Devolve (faixa, usou_padrao)."""
    lote = (
        LotePlantio.objects.filter(mesa_id=mesa, status__in=STATUS_LOTE_EM_CULTIVO)
        .select_related('cultura_id')
        .order_by('-data_plantio', '-id')
        .first()
    )
    if not lote:
        return FAIXA_PADRAO, True
    cultura = lote.cultura_id
    return {
        'temp_min': float(cultura.temperatura_minima),
        'temp_max': float(cultura.temperatura_maxima),
        'umidade_ideal': float(cultura.umidade_ideal),
    }, False


def _formatar(numero):
    return f'{numero:g}'


def avaliar_leitura(leitura, faixa):
    """Lista as anomalias de uma leitura. Cada item tem os campos usados para criar o Alerta."""
    anomalias = []

    temperatura = float(leitura.temperatura)
    temp_min, temp_max = faixa['temp_min'], faixa['temp_max']
    if temperatura < temp_min or temperatura > temp_max:
        acima = temperatura > temp_max
        diferenca = temperatura - temp_max if acima else temp_min - temperatura
        anomalias.append({
            'parametro': Alerta.Parametro.TEMPERATURA,
            'gravidade': Alerta.Gravidade.CRITICO if diferenca > TEMP_CRITICO_ALEM_DE else Alerta.Gravidade.ATENCAO,
            'valor_lido': temperatura,
            'faixa_esperada': f'{_formatar(temp_min)}°C a {_formatar(temp_max)}°C',
            'mensagem': 'Temperatura registrada está '
                        f'{"acima do máximo" if acima else "abaixo do mínimo"} configurado para o cultivo.',
            'acao_sugerida': 'Aumentar a ventilação e acionar o sombreamento da estufa.' if acima
                             else 'Fechar as cortinas laterais e avaliar o aquecimento da estufa.',
        })

    umidade = float(leitura.umidade)
    umidade_ideal = faixa['umidade_ideal']
    desvio = abs(umidade - umidade_ideal)
    if desvio > UMIDADE_TOLERANCIA:
        acima = umidade > umidade_ideal
        anomalias.append({
            'parametro': Alerta.Parametro.UMIDADE,
            'gravidade': Alerta.Gravidade.CRITICO if desvio > UMIDADE_CRITICO_ALEM_DE else Alerta.Gravidade.ATENCAO,
            'valor_lido': umidade,
            'faixa_esperada': f'{_formatar(umidade_ideal)}% (±{_formatar(UMIDADE_TOLERANCIA)}%)',
            'mensagem': f'Umidade relativa está {"acima" if acima else "abaixo"} da ideal para este lote.',
            'acao_sugerida': 'Aumentar a exaustão para reduzir a umidade e o risco de fungos.' if acima
                             else 'Acionar a nebulização para elevar a umidade do ar.',
        })

    if leitura.umidade_solo is not None:
        solo = float(leitura.umidade_solo)
        if solo < SOLO_MINIMO or solo > SOLO_MAXIMO:
            seco = solo < SOLO_MINIMO
            anomalias.append({
                'parametro': Alerta.Parametro.UMIDADE_SOLO,
                'gravidade': Alerta.Gravidade.CRITICO if solo < SOLO_CRITICO_ABAIXO_DE else Alerta.Gravidade.ATENCAO,
                'valor_lido': solo,
                'faixa_esperada': f'{_formatar(SOLO_MINIMO)}% a {_formatar(SOLO_MAXIMO)}%',
                'mensagem': 'Umidade do solo está '
                            f'{"abaixo do mínimo" if seco else "acima do máximo"} recomendado.',
                'acao_sugerida': 'Acionar a irrigação da mesa.' if seco
                                 else 'Suspender a irrigação e verificar a drenagem da mesa.',
            })

    return anomalias


def gerar_alertas(leitura):
    """
    Avalia a leitura e grava os alertas. Se já existe um alerta ativo do mesmo parâmetro
    na mesma mesa, ele é atualizado com a leitura nova em vez de duplicado.
    """
    faixa, usou_padrao = faixa_da_mesa(leitura.mesa_id)
    alertas = []
    for anomalia in avaliar_leitura(leitura, faixa):
        aberto = Alerta.objects.filter(
            mesa_id=leitura.mesa_id, parametro=anomalia['parametro'], status=Alerta.Status.ATIVO,
        ).first()
        if aberto:
            for campo, valor in anomalia.items():
                setattr(aberto, campo, valor)
            aberto.leitura = leitura
            aberto.limite_padrao = usou_padrao
            aberto.atualizado_em = leitura.data_registro
            aberto.save()
            alertas.append(aberto)
        else:
            alertas.append(Alerta.objects.create(
                mesa_id=leitura.mesa_id, leitura=leitura, limite_padrao=usou_padrao,
                data_hora=leitura.data_registro, atualizado_em=leitura.data_registro, **anomalia,
            ))
    return alertas
