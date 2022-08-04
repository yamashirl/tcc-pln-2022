from . import processamento as proc
from . import db_utils

from os import path


def select_diarios():
    return db_utils.obter_lista_diarios()


def select_paragrafos_do(session, edicao):
    diario = db_utils.obter_paragrafos_do(edicao)
    paragrafos = []
    for paragrafo_id, conteudo in diario:
        confianca = proc.score_paragrafo(session, conteudo)
        paragrafos.append((paragrafo_id, confianca, conteudo))

    return paragrafos


def baixar_diarios(ano, mes):
    links = proc.obter_links_diarios_oficiais(f'{ano:02d}', f'{mes:02d}')

    dados = []

    for link in links:
        filename = path.basename(link)

        dados_titulo = proc.extrai_dados_titulo_do(filename)
        if dados_titulo is None:
            continue

        _, diario = proc.obter_diario_oficial(link)
        dados_raspados = proc.raspa_pdf(diario)
        lista_paragrafos = proc.limpa_txt(dados_raspados)

        sucess = db_utils.insere_diario(dados_titulo, lista_paragrafos)
        dados.append({
            'sucess': sucess,
            'edicao': dados_titulo['edicao'],
            'ano': dados_titulo['ano'],
            'mes': dados_titulo['mes'],
            'dia': dados_titulo['dia'],
        })

    return dados


def atualizar_licitacao(identificador):
    dict_licitacao = proc.obter_detalhes_licitacao(identificador)
    proc.inserir_licitacao_sql(dict_licitacao)


def atualizar_licitacoes_por_ano(ano, t=1):
    if type(ano) == int:
        ano_s = str(ano)
    else:
        ano_s = ano

    licitacoes = proc.obter_tabela_licitacoes(t=t)
    licitacoes_dl = []
    for licitacao in licitacoes:
        if licitacao['ano'] == ano_s:
            licitacoes_dl.append(licitacao)
    statuses = proc.baixar_licitacoes(licitacoes_dl)
    return statuses


def informacoes_paragrafo(session, paragrafo_id):
    conteudo = db_utils.obter_conteudo_paragrafo(paragrafo_id)
    score = proc.score_paragrafo(session, conteudo)
    max_tfidf = proc.get_best_n_terms(session, paragrafo_id, n=10)

    return {
        'conteudo': conteudo,
        'confianca': score,
        'max_tfidf': max_tfidf,
    }


def mostrar_candidatos(session, paragrafo_id):
    publicacoes_ord, melhor_cos, melhor_jac, melhor_dis = proc.obter_melhores_candidatos(session, paragrafo_id)

    return publicacoes_ord, melhor_cos, melhor_jac, melhor_dis


def recriar_ngrams():
    # TODO melhorar. deixar bonito
    proc.recriar_sacolas_publicacoes(n=1, ignora_digito=False)
    proc.recriar_sacolas_publicacoes(n=3, ignora_digito=True)
    proc.recriar_sacolas_paragrafos(n=1, ignora_digito=False)
    proc.recriar_sacolas_paragrafos(n=3, ignora_digito=True)
    pass
