import re
import math
from os import path
import requests

import bs4 as bs

from tika import parser

from . import db_utils


#
# FUNÇÕES RELATIVAS AO DIÁRIO OFICIAL
#

# Pipeline esperado
# ano, mes    -> obter_links_diarios_oficiais              -> link
# link        -> obter_diario_oficial + insere_diario_sql  -> pdf
# pdf         -> raspa_pdf                                 -> xml
# xml         -> limpa_txt                                 -> paragrafos
# paragrafos  -> insere_paragrafos_sql                     -> DB

def obter_links_diarios_oficiais(ano, mes):
    resposta = requests.get(f'https://www2.bauru.sp.gov.br/juridico/diariooficial.aspx?a={ano}&m={mes}')
    if resposta.status_code != 200:
        print('Página retornou erro', resposta.status_code)
        return

    soup = bs.BeautifulSoup(resposta.text, 'html.parser')

    lista_links = []
    itens = soup.find_all('li')
    for item in itens:
        ancora = item.find('a')
        if ancora is not None:
            link = ancora['href']
            if path.splitext(link)[1].lower() == '.pdf':
                lista_links.append(link)

    return lista_links


def obter_diario_oficial(link):
    nome_arquivo = path.basename(link)

    resposta = requests.get(f'https://www2.bauru.sp.gov.br{link}')
    if resposta.status_code != 200:
        print('Página retornou erro', resposta.status_code)
        return

    return nome_arquivo, resposta.content


def raspa_pdf(buffer):
    """
    Gera um arquivo .txt a partir dos dados de um arquivo .pdf utilizando um servidor Apache Tika.
    """

    conteudo = parser.from_buffer(buffer, xmlContent=True)

    return conteudo['content']


def limpa_txt(conteudo):
    """
    Utiliza informações levantadas durante a busca exploratória para extrair apenas os dados relevantes do Diário Oficial de Bauru.
    Ou seja, remove os dados não relevantes como metadados e cabeçalhos de página e separa por parágrafos em uma lista JSON.
    
    :returns:
    """

    soup = bs.BeautifulSoup(conteudo)

    # Remove cabeçalho do arquivo composto de tags meta
    #   Não faz parte do conteúdo do documento
    soup.head.decompose()

    # Planifica as páginas (em divs) do documento
    for div in soup.find_all('div'):
        div.unwrap()

        # Remove os cabeçalhos das páginas
    re_comp_pagina = re.compile(r'\d+\s?diário oficial de bauru', flags=re.IGNORECASE)
    for paragrafo in soup.find_all('p'):
        re_pagina = re_comp_pagina.match(paragrafo.text)
        if re_pagina is not None:
            paragrafo.decompose()

    # Analisa cada parágrafo do arquivo com o Spacy e cria um único Doc do Diário Oficial de Bauru inteiro
    lista_paragrafos = []
    for paragrafo in soup.find_all('p'):
        lista_paragrafos.append(paragrafo.text)

    return lista_paragrafos


def extrai_dados_titulo_do(filename):
    extrator_titulo_do = re.compile(r'do_(?P<ano>\d{4})(?P<mes>\d{2})(?P<dia>\d{2})_(?P<edicao>\d{4})\.pdf')
    titulo_match = extrator_titulo_do.match(filename)
    if titulo_match is None:
        print('Nome do arquivo %s de DO está irregular' % filename)
        return None
    else:
        return {
            'edicao': titulo_match.group('edicao'),
            'ano': titulo_match.group('ano'),
            'mes': titulo_match.group('mes'),
            'dia': titulo_match.group('dia')
        }


#
# FUNÇÕES RELATIVAS ÀS TABELAS DO SITE
#

def obter_tabela_licitacoes(t=1):
    """
    Obtém os dados resumidos da página de licitações abertas.

    :keyword t int: id interno da tabela.
        * 'Licitações Abertas' se t = 1;
        * 'Licitações Suspensas' se t = 2;
        * 'Licitações Encerradas' se t = 3.

    :returns: DataFrame com os dados da tabela
    """

    # Obter a página de:

    resposta = requests.get(f'https://www2.bauru.sp.gov.br/administracao/licitacoes/licitacoes.aspx?t={t}')
    if resposta.status_code != 200:
        print('Página retornou erro', resposta.status_code)
        return

    soup = bs.BeautifulSoup(resposta.text, 'html.parser')

    # Buscar a tabela das licitações e obter o corpo
    licitacao_table = soup.find('table')
    # Não há dados relevantes no cabeçalho da tabela.
    # cabecalho_tabela = licitacao_table.thead
    conteudo_tabela = licitacao_table.tbody

    # Para cada linha (child em conteudo_tabela, ou <tr />) da tabela,
    #   extrair as três colunas (contents[0..2], <td />)
    licitacoes = []
    extrator_numero_ano = re.compile(r'(?P<numero>\d+)/(?P<ano>\d{2,4})')
    extrator_link = re.compile(r'licitacoes_detalhes\.aspx\?l=(?P<numero_link>\d+)')

    for child in conteudo_tabela:
        objeto = child.contents[0].a.text
        modalidade = child.contents[1].a.contents[0]

        numero_re = extrator_numero_ano.search(child.contents[1].a.contents[2])
        modalidade_numero = numero_re.group('numero')
        ano = numero_re.group('ano')

        interessados = child.contents[2].a.text

        link_re = extrator_link.search(child.contents[0].a['href'])
        numero_link = link_re.group('numero_link')

        licitacoes.append({'modalidade': modalidade,
                           'modalidade_numero': modalidade_numero,
                           'ano': ano,
                           'interessado': interessados,
                           'objeto': objeto,
                           'link': numero_link})

    return licitacoes


def obter_detalhes_licitacao(identificador):
    """
    Obtém os dados detalhados de uma licitação a partir do código interno do site
    
    :param identificador int: código indentificador interno do site
    :returns: dict com os dados extraídos
    """

    extrator_numero_ano = re.compile(r'((?P<numero>\d{1,3}(\.\d{3})?)/(?P<ano>\d{2,4}))')
    extrator_nome_numero_ano = re.compile(r'((?P<nome>\D+)\s+(?P<numero>\d{1,3}(\.\d{3})?)/(?P<ano>\d{2,4}))')
    extrator_anexo = re.compile(r'Anexo (?P<numero>\d+) - (?P<descricao>.*)')
    extrator_publicacao = re.compile(
        r'(?P<dia>\d{1,2})/(?P<mes>\d{1,2})/(?P<ano>\d{2,4})\s*:\s*(?P<titulo>(\s?\w)+)\s*:')
    extrator_data = re.compile(
        r'(?P<hora>\d{1,2}):(?P<minuto>\d{1,2}) horas do dia (?P<dia>\d{1,2}) de (?P<mes>\w+) de (?P<ano>\d{2,4}) \((\w+-feira|sábado|domingo)\)')

    def extrair_data(s):
        resultado = extrator_data.search(s)
        if type(resultado) is not None:
            return {
                'ano': resultado.group('ano'),
                'mes': resultado.group('mes'),
                'dia': resultado.group('dia'),
                'hora': resultado.group('hora'),
                'minuto': resultado.group('minuto')
            }
        else:
            return s

    # Adquirir a página de uma licitação
    response = requests.get(
        f'https://www2.bauru.sp.gov.br/administracao/licitacoes/licitacoes_detalhes.aspx?l={identificador}')
    if response.status_code != 200:
        print('Página retornou erro', response.status_code)
        return
    soup = bs.BeautifulSoup(response.text, 'html.parser')

    conteudo = soup.find('main').find('div', class_='col-10')

    detalhes_dict = {
        'identificador': identificador
    }

    for linha in conteudo.find_all('div', class_='row'):
        if len(linha.contents) == 1:
            resultado = extrator_nome_numero_ano.search(linha.text)
            detalhes_dict['titulo'] = {
                'modalidade': resultado.group('nome'),
                'numero': resultado.group('numero'),
                'ano': resultado.group('ano')
            }

        elif len(linha.contents) == 2:
            indice = linha.find('div', class_='col-md-2').text
            valores = linha.find('div', class_='col-md-10')

            if indice == 'Tipo:':
                indice = 'tipo'
                detalhes_dict[indice] = valores.text

            elif indice == 'Interessado:':
                indice = 'interessado'
                detalhes_dict[indice] = valores.text

            elif indice == 'Processo:':
                indice = 'processo'
                resultado = extrator_numero_ano.search(valores.text)
                detalhes_dict[indice] = {
                    'numero': resultado.group('numero'),
                    'ano': resultado.group('ano')
                }

            elif indice == 'Especificação:':
                indice = 'especificacao'
                detalhes_dict[indice] = valores.text

            elif indice == 'Prazo para Recebimento Propostas:':
                indice = 'prazo_recebimento_propostas'
                detalhes_dict[indice] = extrair_data(valores.text)

            elif indice == 'Prazo para Apresentação de Propostas:':
                indice = 'prazo_apresentacao_propostas'
                detalhes_dict[indice] = extrair_data(valores.text)

            elif indice == 'Prazo para Entrega dos Envelopes:':
                indice = 'prazo_entrega_envelopes'
                detalhes_dict[indice] = extrair_data(valores.text)

            elif indice == 'Processo Tribunal de Contas:':
                indice = 'processo_tribunal_de_contas'
                detalhes_dict[indice] = valores.text

            elif indice == 'Data de vencimento:':
                indice = 'data_vencimento'
                detalhes_dict[indice] = extrair_data(valores.text)

            elif indice == 'Data:':
                indice = 'data'
                detalhes_dict[indice] = extrair_data(valores.text)

            elif indice == 'Observação:':
                indice = 'observacao'
                detalhes_dict[indice] = valores.text

            elif indice == 'Processo Apensado' or indice == 'Processos Apensados':
                if 'processos_apensados' not in detalhes_dict:
                    detalhes_dict['processos_apensados'] = []

                matches = extrator_numero_ano.finditer(valores.text)
                for p in matches:
                    detalhes_dict['processos_apensados'].append({
                        'numero': p.group('numero'),
                        'ano': p.group('ano')
                    })

            elif indice == 'Documentos:':
                if 'documentos' not in detalhes_dict:
                    detalhes_dict['documentos'] = []

                for d in valores.find_all('li'):
                    if d.b.string[0] == 'E':
                        # Assume 'Edital xxx/xxxx'
                        resultado = extrator_nome_numero_ano.search(d.b.string)
                        detalhes_dict['documentos'].append({
                            'nome': resultado.group('nome'),
                            'numero': resultado.group('numero'),
                            'ano': resultado.group('ano'),
                            'link': d.a['href']
                        })
                    elif d.b.string[0] == 'A':
                        # Assume 'Anexo x - [...]'
                        resultado = extrator_anexo.search(d.b.string)
                        detalhes_dict['documentos'].append({
                            'nome': 'Anexo',
                            'numero': resultado.group('numero'),
                            'descricao': resultado.group('descricao'),
                            'link': d.a['href']
                        })
                    else:
                        # Situação inesperada??
                        print('Situação Inesperada analisando documentos. "Anexo" ou "Edital" não encontrados.',
                              detalhes_dict['titulo'])
                        detalhes_dict['documentos'].append((d.b.string, d.a['href']))

            elif indice == 'Publicações:':
                if 'publicacoes' not in detalhes_dict:
                    detalhes_dict['publicacoes'] = []

                for i in range(0, len(valores.contents), 3):
                    resultado = extrator_publicacao.search(valores.contents[i].string)
                    publicacao = {
                        'titulo': resultado.group('titulo'),
                        'dia': resultado.group('dia'),
                        'mes': resultado.group('mes'),
                        'ano': resultado.group('ano'),
                        'conteudo': valores.contents[i + 1]
                    }
                    detalhes_dict['publicacoes'].append(publicacao)

            else:
                if 'misc' not in detalhes_dict:
                    detalhes_dict['misc'] = []

                detalhes_dict['misc'].append((indice, str(valores)))

        else:
            print('quantidade de valores inesperado:')
            print(linha)

    return detalhes_dict


def baixar_licitacoes(lista_download, tempo_espera=0.1):
    """
    Baixa todos as licitações num dataframe
    
    :keyword tempo_espera int: Tempo de espera entre o download de uma licitação e outra. Utilizado para não enviar muitas requisições em um curto período de tempo.
    :keyword diretorio str: Diretorio de destino para os arquivos .json baixados.
    """

    statuses = []
    for licitacao in lista_download:
        link_licitacao = licitacao['link']
        dict_licitacao = obter_detalhes_licitacao(link_licitacao)
        status = db_utils.inserir_licitacao_sql(dict_licitacao)
        statuses.append({
            'identificador': dict_licitacao['identificador'],
            'modalidade': dict_licitacao['titulo']['modalidade'],
            'numero': dict_licitacao['titulo']['numero'],
            'ano': dict_licitacao['titulo']['ano'],
            'status': status
        })

    return statuses


#
# FUNÇÕES RELATIVAS ÀS MÉTRICAS
#

def calcular_tfidf_termo(termo, sacola_documento, sacola_corpus, corpus_n):
    termo_frequencia = 0

    for token in sacola_documento:
        if token == termo:
            termo_frequencia += 1

    inverso_documento_frequencia = math.log(corpus_n / sacola_corpus[termo])

    return inverso_documento_frequencia


def calcular_tfidf_termo_paragrafo(session, termo, paragrafo_id):
    if ('pars_1gram_bag_idf' not in session
            or 'pars_n' not in session):
        load_1gram_paragrafo(session)

    if str(paragrafo_id) + '_1gram_bag' not in session:
        conteudo_paragrafo = db_utils.obter_conteudo_paragrafo(paragrafo_id)
        conteudo_sacola = monta_sacola_ngram(conteudo_paragrafo, n=1)
        session[str(paragrafo_id) + '_1gram_bag'] = conteudo_sacola

    sacola_corpus = session['pars_1gram_bag_idf']
    n_corpus = session['pars_n']
    sacola_paragrafo = session[str(paragrafo_id) + '_1gram_bag']

    tfidf_termo = calcular_tfidf_termo(termo, sacola_paragrafo, sacola_corpus, n_corpus)

    return tfidf_termo


def calcular_tfidf_termo_publicacao(session, termo, publicacao_id):
    if ('pubs_1gram_bag_idf' not in session
            or 'pubs_n' not in session):
        load_1gram_publicacao(session)

    if str(publicacao_id) + '_1gram_bag' not in session:
        conteudo_publicacao = db_utils.obter_conteudo_publicacao(publicacao_id)
        conteudo_sacola = monta_sacola_ngram(conteudo_publicacao, n=1)
        session[str(publicacao_id) + '_1gram_bag'] = conteudo_sacola

    sacola_corpus = session['pubs_1gram_bag_idf']
    n_corpus = session['pubs_n']
    sacola_publicacao = session[str(publicacao_id) + '_1gram_bag']

    tfidf_termo = calcular_tfidf_termo(termo, sacola_publicacao, sacola_corpus, n_corpus)

    return tfidf_termo


def monta_sacola_ngram(texto, n=2, ignora_digito=True):
    def monta_chave(tokens_anteriores, token_atual):
        chave = ''

        for token in tokens_anteriores:
            chave += token + '_'
        chave += token_atual

        return chave

    def atualiza_tokens(tokens_anteriores, token_atual):
        if n == 1:
            return
        else:
            i = 0
            while i < n - 2:
                tokens_anteriores[i] = tokens_anteriores[i + 1]
                i += 1
            tokens_anteriores[i] = token_atual
            return

    tokenizador = re.compile(r'\w+')

    sacola_ngram = {}

    conteudo = None
    if ignora_digito:
        conteudo = re.sub(r'\d', ' ', texto.lower())
    else:
        conteudo = texto.lower()

    tokens = tokenizador.findall(conteudo)

    tokens_anteriores = []
    for i in range(n - 1):
        tokens_anteriores.append('')

    for token in tokens:
        chave = monta_chave(tokens_anteriores, token)
        if chave not in sacola_ngram:
            sacola_ngram[chave] = 1
        else:
            sacola_ngram[chave] += 1
        atualiza_tokens(tokens_anteriores, token)

    return sacola_ngram


def atualiza_sacola_tf(sacola_corpus, sacola):
    for token in sacola:
        if token not in sacola_corpus:
            sacola_corpus[token] = sacola[token]
        else:
            sacola_corpus[token] += sacola[token]


def atualiza_sacola_idf(sacola_corpus, sacola):
    for token in sacola:
        if token not in sacola_corpus:
            sacola_corpus[token] = 1
        else:
            sacola_corpus[token] += 1


def calcula_cosseno_sacolas(sacola_a, sacola_b):
    produto_escalar = 0.0

    soma_a = 0.0
    soma_b = 0.0

    for k in sacola_a:
        if k in sacola_b:
            produto_escalar += sacola_a[k] * sacola_b[k]
        soma_a += math.pow(sacola_a[k], 2)

    for k in sacola_b:
        soma_b += math.pow(sacola_b[k], 2)

    magnitude = math.sqrt(soma_a) * math.sqrt(soma_b)

    if abs(magnitude) < 1e-3:
        similaridade = 0
    else:
        similaridade = produto_escalar / magnitude

    return similaridade


def calcula_jaccard_sacos(sacola_a, sacola_b):
    intersec = 0

    for key in sacola_a:
        if key in sacola_b:
            intersec += 1
    uniao = len(sacola_a) + len(sacola_b) - intersec
    if uniao == 0:
        return 0
    return intersec / uniao


def calcula_dissimilaridade_sacolas(s_a, s_b, n=1):
    sacola_a = s_a.copy()
    sacola_b = s_b.copy()
    tot_a = 0
    excl_a = 0
    ambos = 0
    excl_b = 0
    tot_b = 0

    for chave in sacola_a:
        tot_a += sacola_a[chave]

        if chave in sacola_b:
            tot_b += sacola_b[chave]
            if sacola_a[chave] < sacola_b[chave]:
                ambos += sacola_a[chave]
                sacola_b[chave] = sacola_b[chave] - sacola_a[chave]
                excl_b += sacola_b[chave]
            else:
                ambos += sacola_b[chave]
                sacola_a[chave] = sacola_a[chave] - sacola_b[chave]
                excl_a += sacola_a[chave]
            sacola_b[chave] = 0
            sacola_a[chave] = 0

        else:
            excl_a += sacola_a[chave]
            sacola_a[chave] = 0

    for chave in sacola_b:
        tot_b += sacola_b[chave]
        excl_b += sacola_b[chave]
        sacola_b[chave] = 0

    if tot_a == 0 or tot_b == 0:
        return 0

    return 1 - (excl_a * excl_b) / (tot_a * tot_b)


def score_paragrafo(session, conteudo):
    if ('score_bag_pub' not in session
            or 'score_bag_par' not in session):
        load_3gram_scorer(session)

    score_bag_pub = session['score_bag_pub']
    score_bag_par = session['score_bag_par']
    pubs_3gram_bag_idf = session['pubs_3gram_bag_idf']

    score_pub = 0
    score_par = 0

    saco_par = monta_sacola_ngram(conteudo, n=3)

    for chave in saco_par:
        if chave in pubs_3gram_bag_idf:
            score_pub += saco_par[chave] * score_bag_pub[chave]
            score_par += saco_par[chave] * score_bag_par[chave]
    score = score_pub / (score_par + 1)

    return score


def get_best_n_terms(session, paragrafo_id, n=1):
    conteudo_paragrafo = db_utils.obter_conteudo_paragrafo(paragrafo_id)
    sacola_paragrafo = monta_sacola_ngram(conteudo_paragrafo, n=1)

    tfidf = []
    for token in sacola_paragrafo:
        tfidf.append((token, calcular_tfidf_termo_paragrafo(session, token, paragrafo_id)))

    tfidf.sort(key=lambda k: k[1], reverse=True)

    if len(tfidf) > n:
        return tfidf[:n]
    else:
        return tfidf


def buscar_termo_publicacao(session, termo):
    publicacoes = db_utils.obter_publicacoes()
    candidatos = []

    busca_termo = re.compile(r'\b' + termo + r'\b', flags=re.IGNORECASE)

    for publicacao_id, conteudo in publicacoes:
        match = busca_termo.search(conteudo)

        if match is None:
            continue

        tfidf = calcular_tfidf_termo_publicacao(session, termo, publicacao_id)
        candidatos.append({'publicacao_id': publicacao_id,
                           'tfidf': tfidf,
                           'conteudo': conteudo,
                           })

    return sorted(candidatos, key=lambda k: k['tfidf'], reverse=True)


def obter_melhores_candidatos(session, paragrafo_id):
    try:
        sacolas_publicacoes_geradas = session['sacolas_publicacoes_geradas']
    except KeyError as e:
        conteudo_publicacoes = db_utils.obter_publicacoes()

        sacolas_publicacoes_geradas = []
        for publicacao_id, conteudo in conteudo_publicacoes:
            sacola_pub = monta_sacola_ngram(conteudo, n=3, ignora_digito=False)
            session['sacola_publicacao_' + str(publicacao_id)] = sacola_pub
            session['conteudo_publicacao_' + str(publicacao_id)] = conteudo
            sacolas_publicacoes_geradas.append(publicacao_id)

        session['sacolas_publicacoes_geradas'] = sacolas_publicacoes_geradas

    conteudo_paragrafo = db_utils.obter_conteudo_paragrafo(paragrafo_id)
    sacola_alvo = monta_sacola_ngram(conteudo_paragrafo, n=3, ignora_digito=False)

    publicacoes = []
    for publicacao_id in sacolas_publicacoes_geradas:
        conteudo = session['conteudo_publicacao_' + str(publicacao_id)]
        sacola_pub = monta_sacola_ngram(conteudo, n=3, ignora_digito=False)

        similaridade_cosseno = calcula_cosseno_sacolas(sacola_pub, sacola_alvo)
        similaridade_jaccard = calcula_jaccard_sacos(sacola_pub, sacola_alvo)
        dissimilaridade_str = calcula_dissimilaridade_sacolas(sacola_pub, sacola_alvo)
        publicacoes.append({
            'publicacao_id': publicacao_id,
            'conteudo': conteudo,
            'cosseno': similaridade_cosseno,
            'jaccard': similaridade_jaccard,
            'dissim': dissimilaridade_str,
        })

    publicacoes_ord = sorted(publicacoes, key=lambda e: e['jaccard'], reverse=True)

    melhor_cos = None
    melhor_jac = None
    melhor_dis = None
    if len(publicacoes_ord) > 0:
        melhor_cos = publicacoes_ord[0]
        melhor_jac = publicacoes_ord[0]
        melhor_dis = publicacoes_ord[0]
        for publicacao in publicacoes_ord:
            if publicacao['cosseno'] > melhor_cos['cosseno']:
                melhor_cos = publicacao
            if publicacao['jaccard'] > melhor_jac['jaccard']:
                melhor_jac = publicacao
            if publicacao['dissim'] > melhor_dis['dissim']:
                melhor_dis = publicacao

    return publicacoes_ord, melhor_cos, melhor_jac, melhor_dis


def load_1gram_paragrafo(session):
    sacola_id, sacola = db_utils.get_sacola('paragrafos_1gram')
    n = db_utils.get_count('paragrafo')

    session['pars_1gram_bag_idf'] = sacola
    session['pars_n'] = n


def load_1gram_publicacao(session):
    sacola_id, sacola = db_utils.get_sacola('publicacoes_1gram')
    n = db_utils.get_count('publicacao')

    session['pubs_1gram_bag_idf'] = sacola
    session['pubs_n'] = n


def load_3gram_scorer(session):
    if ('pubs_3gram_bag_idf' not in session
            or 'pars_3gram_bag_idf' not in session
            or 'pubs_3gram_n' not in session
            or 'pars_3gram_n' not in session
            or 'score_bag_pub' not in session
            or 'score_bag_par' not in session):
        score_bag_pub = {}
        score_bag_par = {}

        pubs_3gram_id, _ = db_utils.get_sacola('publicacoes_3gram')
        pars_3gram_id, _ = db_utils.get_sacola('paragrafos_3gram')

        pubs_3gram_bag_idf, pars_3gram_bag_idf = db_utils.get_sacolas_inner(pubs_3gram_id, pars_3gram_id)

        pubs_3gram_n = db_utils.get_count('publicacao')
        pars_3gram_n = db_utils.get_count('paragrafo')

        for key in pubs_3gram_bag_idf:
            if key in pars_3gram_bag_idf:
                score_bag_pub[key] = pubs_3gram_bag_idf[key] / pubs_3gram_n

        for key in pubs_3gram_bag_idf:
            if key in pars_3gram_bag_idf:
                score_bag_par[key] = pars_3gram_bag_idf[key] / pars_3gram_n

        session['pubs_3gram_bag_idf'] = pubs_3gram_bag_idf
        session['pars_3gram_bag_idf'] = pars_3gram_bag_idf
        session['pubs_3gram_n'] = pubs_3gram_n
        session['pars_3gram_n'] = pars_3gram_n
        session['score_bag_pub'] = score_bag_pub
        session['score_bag_par'] = score_bag_par


def recriar_sacolas_publicacoes(n=1, ignora_digito=True):
    publicacoes = db_utils.obter_publicacoes()

    sacola_id = db_utils.get_id('sacola', f'publicacoes_{n}gram')
    if sacola_id is not None:
        db_utils.remover_sacola(sacola_id)

    sacola_tf = {}
    sacola_idf = {}

    for publicacao_id, conteudo in publicacoes:
        sacola_publicacao = monta_sacola_ngram(conteudo, n=n, ignora_digito=ignora_digito)
        atualiza_sacola_tf(sacola_tf, sacola_publicacao)
        atualiza_sacola_idf(sacola_idf, sacola_publicacao)

    itens = []
    for chave in sacola_tf:
        itens.append({
            'chave': chave,
            'frequencia': sacola_tf[chave],
            'idf': sacola_idf[chave]
        })

    sacola_id = db_utils.nova_sacola(f'publicacoes_{n}gram', itens)
    return sacola_id


def recriar_sacolas_paragrafos(n=1, ignora_digito=True):
    paragrafos = db_utils.obter_paragrafos()

    sacola_id = db_utils.get_id('sacola', f'paragrafos_{n}gram')
    if sacola_id is not None:
        db_utils.remover_sacola(sacola_id)

    sacola_tf = {}
    sacola_idf = {}

    for paragrafo_id, conteudo in paragrafos:
        sacola_paragrafo = monta_sacola_ngram(conteudo, n=n, ignora_digito=ignora_digito)
        atualiza_sacola_tf(sacola_tf, sacola_paragrafo)
        atualiza_sacola_idf(sacola_idf, sacola_paragrafo)

    itens = []
    for chave in sacola_tf:
        itens.append({
            'chave': chave,
            'frequencia': sacola_tf[chave],
            'idf': sacola_idf[chave]
        })

    sacola_id = db_utils.nova_sacola(f'paragrafos_{n}gram', itens)
    return sacola_id
