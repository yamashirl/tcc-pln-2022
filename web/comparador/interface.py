from . import processamento as proc
from . import db_utils

from plotly.offline import plot
from plotly.graph_objs import Figure
from plotly.graph_objs import Scatter
from plotly.graph_objs import Scatter3d
from plotly.graph_objs import Layout

from os import path


def select_diarios():
    return db_utils.obter_lista_diarios()


def select_paragrafos_do(session, edicao):
    diario = db_utils.obter_paragrafos_do(edicao)
    paragrafos = []
    confiancas = []
    for num, (paragrafo_id, conteudo) in enumerate(diario):
        confianca = proc.score_paragrafo(session, conteudo)
        confiancas.append(confianca)
        paragrafos.append((num, paragrafo_id, confianca, conteudo))

    x_data = [*range(len(diario))]
    y_data = confiancas

    plot_fig = Figure(data=[Scatter(x=x_data, y=y_data,
                        mode='lines', name='Confiança')],
                layout=Layout(autosize=False, width=854, height=480))
    plot_div = plot(plot_fig,
                output_type='div')

    return paragrafos, plot_div


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

    x_data = []
    y_data = []
    z_data = []
    labels = []

    for publicacao in publicacoes_ord:
        labels.append(publicacao['publicacao_id'])
        x_data.append(publicacao['cosseno'])
        y_data.append(publicacao['jaccard'])
        z_data.append(publicacao['dissim'])

    plot_fig = Figure(data=[Scatter3d(x=x_data, y=y_data, z=z_data,
                        mode='markers', name='Confiança',
                        text=labels,
                        marker_size=1
                        )],
                layout=Layout(autosize=False, width=854, height=480))
    plot_div = plot(plot_fig,
                output_type='div')

    return publicacoes_ord, melhor_cos, melhor_jac, melhor_dis, plot_div


def recriar_ngrams():
    # TODO melhorar. deixar bonito
    proc.recriar_sacolas_publicacoes(n=1, ignora_digito=False)
    proc.recriar_sacolas_publicacoes(n=3, ignora_digito=True)
    proc.recriar_sacolas_paragrafos(n=1, ignora_digito=False)
    proc.recriar_sacolas_paragrafos(n=3, ignora_digito=True)
    pass

def buscar_termo_publicacao(session, termo):
    return proc.buscar_termo_publicacao(session, termo)
