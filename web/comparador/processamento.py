import re
from os import path
import requests
import time

import bs4 as bs

from tika import parser

import mysql.connector

sql_config = {
    'user': 'root',
    'password': 'see-cret',
    'database': 'tcc'
}


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


def insere_diario(titulo, paragrafos):
    success = True
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()
        try:
            insere_diario_sql(cursor,
                              titulo['edicao'],
                              titulo['ano'],
                              titulo['mes'],
                              titulo['dia'])
            insere_paragrafos_sql(cursor, paragrafos, titulo['edicao'])
            cursor.close()
            connection.commit()
        except mysql.connector.Error as e:
            success = False
            cursor.close()
            connection.rollback()
            print(e)
    return success


def insere_diario_sql(cursor, edicao, ano, mes, dia):
    cursor.execute('INSERT INTO diario (edicao, ano, mes, dia)'
                   + ' VALUES (%s, %s, %s, %s)', (edicao, ano, mes, dia))


def insere_paragrafos_sql(cursor, lista_paragrafos, edicao_do):
    for num, paragrafo in enumerate(lista_paragrafos):
        cursor.execute('INSERT INTO paragrafo (edicao, paragrafo, conteudo)'
                       + ' VALUES (%s, %s, %s)', (edicao_do, num, paragrafo))


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


def inserir_licitacao_sql(dict_licitacao):
    existe = False
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        titulo_modalidade = dict_licitacao['titulo']['modalidade']
        cursor.execute('SELECT modalidade_id FROM modalidade WHERE descricao LIKE %s', (titulo_modalidade,))
        modalidade_id = cursor.fetchone()[0]
        cursor.fetchall()

        interessado = dict_licitacao['interessado']
        cursor.execute('SELECT interessado_id FROM interessado WHERE descricao LIKE %s', (interessado,))
        interessado_id = cursor.fetchone()[0]
        cursor.fetchall()

        tipo = dict_licitacao['tipo']
        cursor.execute('SELECT tipo_id FROM tipo WHERE descricao LIKE %s', (tipo,))
        tipo_id = cursor.fetchone()[0]
        cursor.fetchall()

        identificador = dict_licitacao['identificador']
        numero_modalidade = dict_licitacao['titulo']['numero']
        ano_modalidade = dict_licitacao['titulo']['ano']

        if 'processo' in dict_licitacao:
            numero_processo = dict_licitacao['processo']['numero']
            ano_processo = dict_licitacao['processo']['ano']

        cursor.execute('SELECT numero_processo FROM licitacao WHERE identificador = %s', (identificador,))
        linha = cursor.fetchone()
        cursor.fetchall()
        if linha is not None:
            existe = True
            cursor.execute('DELETE FROM publicacao WHERE identificador = %s', (identificador,))
            cursor.execute('DELETE FROM observacao WHERE identificador = %s', (identificador,))
            cursor.execute('DELETE FROM apensados WHERE identificador = %s', (identificador,))
            cursor.execute('DELETE FROM edital WHERE identificador = %s', (identificador,))
            cursor.execute('DELETE FROM especificacao WHERE identificador = %s', (identificador,))
            cursor.execute('DELETE FROM prazo WHERE identificador = %s', (identificador,))
            cursor.execute('DELETE FROM licitacao WHERE identificador = %s', (identificador,))

        cursor.execute('INSERT INTO'
                       + ' licitacao(identificador, modalidade_id, numero_modalidade, ano_modalidade, tipo_id, interessado_id)'
                       + ' VALUES (%s, %s, %s, %s, %s, %s)',
                       (identificador, modalidade_id, numero_modalidade, ano_modalidade, tipo_id, interessado_id))
        if 'processo' in dict_licitacao:
            cursor.execute('UPDATE licitacao SET numero_processo = %s, ano_processo = %s WHERE identificador = %s',
                           (numero_processo, ano_processo, identificador))

        if 'publicacoes' in dict_licitacao:
            for publicacao in dict_licitacao['publicacoes']:
                publicacao_titulo = publicacao['titulo']
                cursor.execute('SELECT publicacao_titulo_id FROM publicacao_titulo'
                               + ' WHERE descricao LIKE %s', (publicacao_titulo,))
                publicacao_titulo_id = cursor.fetchone()[0]
                cursor.fetchall()

                ano = publicacao['ano']
                mes = publicacao['mes']
                dia = publicacao['dia']
                conteudo = publicacao['conteudo']

                cursor.execute(
                    #'INSERT INTO publicacao(identificador, publicacao_titulo_id, ano, mes, dia, conteudo) VALUES (%s, %s, %s, %s, %s, %s)',
                    #(identificador, publicacao_titulo_id, ano, mes, dia, conteudo)
                    'INSERT INTO publicacao(identificador, publicacao_titulo_id, ano, mes, conteudo) VALUES (%s, %s, %s, %s, %s)',
                    (identificador, publicacao_titulo_id, ano, mes, conteudo)
                    )
        cursor.close()
        connection.commit()
    return existe


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
        status = inserir_licitacao_sql(dict_licitacao)
        statuses.append({
            'identificador': dict_licitacao['identificador'],
            'modalidade': dict_licitacao['titulo']['modalidade'],
            'numero': dict_licitacao['titulo']['numero'],
            'ano': dict_licitacao['titulo']['ano'],
            'status': status
        })

    return statuses

