from . import processamento as proc
from os import path


def obter_diarios(ano, mes):
    links = proc.obter_links_diarios_oficiais(f'{ano:02d}', f'{mes:02d}')

    for link in links:
        filename = path.basename(link)

        dados_titulo = proc.extrai_dados_titulo_do(filename)
        if dados_titulo is None:
            continue
#        (edicao_do, ano, mes, dia) = dados_titulo

        _, diario = proc.obter_diario_oficial(link)
        dados_raspados = proc.raspa_pdf(diario)
        lista_paragrafos = proc.limpa_txt(dados_raspados)

        proc.insere_diario(dados_titulo, lista_paragrafos)

    return links


def atualizar_licitacao(identificador):
    dict_licitacao = proc.obter_detalhes_licitacao(identificador)
    proc.inserir_licitacao_sql(dict_licitacao)


def atualizar_tabela_licitacoes(tabela, ano=2022):
    licitacoes = proc.obter_tabela_licitacoes(tabela)
    licitacoes_dl = []
    for licitacao in licitacoes:
        if licitacao['ano'] == ano:
            licitacoes_dl.append(licitacao)
    proc.baixar_licitacoes(licitacoes_dl)
