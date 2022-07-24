import re
import math

import mysql.connector

sql_config = {
    'user': 'root',
    'password': 'see-cret',
    'database': 'tcc',
}


def obter_lista_diarios():
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        cursor.execute('SELECT edicao, ano, mes, dia FROM diario ORDER BY edicao DESC')
        diarios = []
        for edicao, ano, mes, dia in cursor:
            diarios.append({
                'edicao': edicao,
                'ano': ano,
                'mes': mes,
                'dia': dia
            })
        cursor.close()
    return diarios


def obter_paragrafos_do(edicao):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT paragrafo_id, conteudo FROM paragrafo WHERE edicao = %s', (edicao,))
        if cursor is None:
            return None
        paragrafos = []
        for paragrafo_id, conteudo in cursor:
            paragrafos.append((paragrafo_id, conteudo))
        cursor.close()

    return paragrafos


def obter_conteudo_publicacao(publicacao_id):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        # OBTÉM O PARÁGRAFO A SER PESQUISADO
        cursor.execute('SELECT conteudo FROM publicacao WHERE publicacao_id = %s', (publicacao_id,))
        conteudo, = cursor.fetchone()
        cursor.fetchall()

        cursor.close()

    return conteudo


def obter_conteudo_paragrafo(paragrafo_id):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        # OBTÉM O PARÁGRAFO A SER PESQUISADO
        cursor.execute('SELECT conteudo FROM paragrafo WHERE paragrafo_id = %s', (paragrafo_id,))
        conteudo, = cursor.fetchone()
        cursor.fetchall()

        cursor.close()

    return conteudo


def obter_detalhes_paragrafo(paragrafo_id):
    pass


def calcular_tfidf_termo(termo, sacola_documento, sacola_corpus, corpus_n):
    termo_frequencia = 0

    for token in sacola_documento:
        if token == termo:
            termo_frequencia += 1

    inverso_documento_frequencia = math.log(corpus_n / sacola_corpus[termo])

    return inverso_documento_frequencia


def get_sacola(cursor, descricao):
    cursor.execute('SELECT saco_id FROM saco_corpus WHERE descricao LIKE %s', (descricao,))
    sacola_id, = cursor.fetchone()
    cursor.fetchall()

    sacola = {}
    cursor.execute('SELECT chave, idf FROM saco_item WHERE saco_id = %s', (sacola_id,))
    for chave, valor in cursor:
        sacola[chave] = valor

    return sacola


def load_1gram_paragrafo(session):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        sacola = get_sacola(cursor, 'paragrafos_1gram')

        cursor.execute('SELECT count(*) FROM paragrafo')
        n, = cursor.fetchone()
        cursor.fetchall()

        cursor.close()

    session['pars_1gram_bag_idf'] = sacola
    session['pars_n'] = n


def calcular_tfidf_termo_paragrafo(session, termo, paragrafo_id):
    if ('pars_1gram_bag_idf' not in session
            or 'pars_n' not in session):
        load_1gram_paragrafo(session)

    if str(paragrafo_id) + '_1gram_bag' not in session:
        conteudo_paragrafo = obter_conteudo_paragrafo(paragrafo_id)
        conteudo_sacola = monta_saco_ngram(conteudo_paragrafo, n=1)
        session[str(paragrafo_id) + '_1gram_bag'] = conteudo_sacola

    sacola_corpus = session['pars_1gram_bag_idf']
    n_corpus = session['pars_n']
    sacola_paragrafo = session[str(paragrafo_id) + '_1gram_bag']

    tfidf_termo = calcular_tfidf_termo(termo, sacola_paragrafo, sacola_corpus, n_corpus)

    return tfidf_termo


def load_1gram_publicacao(session):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        sacola = get_sacola(cursor, 'publicacoes_1gram')

        cursor.execute('SELECT count(*) FROM paragrafo')
        n, = cursor.fetchone()
        cursor.fetchall()

        cursor.close()

    session['pubs_1gram_bag_idf'] = sacola
    session['pubs_n'] = n


def calcular_tfidf_termo_publicacao(session, termo, publicacao_id):
    if ('pubs_1gram_bag_idf' not in session
            or 'pubs_n' not in session):
        load_1gram_publicacao(session)

    if str(publicacao_id) + '_1gram_bag' not in session:
        conteudo_publicacao = obter_conteudo_publicacao(publicacao_id)
        conteudo_sacola = monta_saco_ngram(conteudo_publicacao, n=1)
        session[str(publicacao_id) + '_1gram_bag'] = conteudo_sacola

    sacola_corpus = session['pubs_1gram_bag_idf']
    n_corpus = session['pubs_n']
    sacola_publicacao = session[str(publicacao_id) + '_1gram_bag']

    tfidf_termo = calcular_tfidf_termo(termo, sacola_publicacao, sacola_corpus, n_corpus)

    return tfidf_termo


def monta_saco_ngram(texto, n=2, ignora_digito=True):
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

    saco_ngram = dict()

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
        if chave not in saco_ngram:
            saco_ngram[chave] = 1
        else:
            saco_ngram[chave] += 1
        atualiza_tokens(tokens_anteriores, token)

    return saco_ngram


def atualiza_saco_corpus(saco_corpus, saco):
    for token in saco:
        if token not in saco_corpus:
            saco_corpus[token] = saco[token]
        else:
            saco_corpus[token] += saco[token]


def atualiza_idf_corpus(saco_corpus, saco):
    for token in saco:
        if token not in saco_corpus:
            saco_corpus[token] = 1
        else:
            saco_corpus[token] += 1


def calcula_cosseno_sacos(saco_a, saco_b):
    produto_escalar = 0.0

    soma_a = 0.0
    soma_b = 0.0

    for k in saco_a:
        if k in saco_b:
            produto_escalar += saco_a[k] * saco_b[k]
        soma_a += math.pow(saco_a[k], 2)

    for k in saco_b:
        soma_b += math.pow(saco_b[k], 2)

    magnitude = math.sqrt(soma_a) * math.sqrt(soma_b)

    if abs(magnitude) < 1e-3:
        similaridade = 0
    else:
        similaridade = produto_escalar / magnitude

    return similaridade


def calcula_jaccard_sacos(saco_a, saco_b):
    intersec = 0

    for key in saco_a:
        if key in saco_b:
            intersec += 1
    uniao = len(saco_a) + len(saco_b) - intersec
    if uniao == 0:
        return 0
    return intersec / uniao


def calcula_dissimilaridade_strings(string_a, string_b, n=1):
    saco_a = monta_saco_ngram(string_a, n=n, ignora_digito=False)
    saco_b = monta_saco_ngram(string_b, n=n, ignora_digito=False)

    tot_a = 0
    excl_a = 0
    ambos = 0
    excl_b = 0
    tot_b = 0

    for chave in saco_a:
        tot_a += saco_a[chave]

        if chave in saco_b:
            tot_b += saco_b[chave]
            if saco_a[chave] < saco_b[chave]:
                ambos += saco_a[chave]
                saco_b[chave] = saco_b[chave] - saco_a[chave]
                excl_b += saco_b[chave]
            else:
                ambos += saco_b[chave]
                saco_a[chave] = saco_a[chave] - saco_b[chave]
                excl_a += saco_a[chave]
            saco_b[chave] = 0
            saco_a[chave] = 0

        else:
            excl_a += saco_a[chave]
            saco_a[chave] = 0

    for chave in saco_b:
        tot_b += saco_b[chave]
        excl_b += saco_b[chave]
        saco_b[chave] = 0

    if tot_a == 0 or tot_b == 0:
        return 1

    return (excl_a * excl_b) / (tot_a * tot_b)


def load_3gram_scorer(session):
    try:
        pubs_3gram_bag_idf = session['pubs_3gram_bag_idf']
        pars_3gram_bag_idf = session['pars_3gram_bag_idf']
        pubs_3gram_n = session['pubs_3gram_n']
        pars_3gram_n = session['pars_3gram_n']
        score_bag_pub = session['score_bag_pub']
        score_bag_par = session['score_bag_par']
    except KeyError as e:
        pubs_3gram_bag_idf = {}
        pars_3gram_bag_idf = {}
        score_bag_pub = {}
        score_bag_par = {}
        with mysql.connector.connect(**sql_config) as connection:
            cursor = connection.cursor()

            cursor.execute('SELECT saco_id FROM saco_corpus WHERE descricao LIKE %s', ('publicacoes_3gram',))
            saco_id_publicacoes, = cursor.fetchone()
            cursor.fetchall()

            cursor.execute('SELECT saco_id FROM saco_corpus WHERE descricao LIKE %s', ('paragrafos_3gram',))
            saco_id_paragrafos, = cursor.fetchone()
            cursor.fetchall()

            cursor.execute('SELECT chave, pu.idf, pa.idf ' +
                           'FROM saco_item as pu INNER JOIN saco_item as pa ' +
                           'USING (chave) ' +
                           'WHERE pu.saco_id = %s AND pa.saco_id = %s', (saco_id_publicacoes, saco_id_paragrafos))

            for chave, pu_idf, pa_idf in cursor:
                pubs_3gram_bag_idf[chave] = pu_idf
                pars_3gram_bag_idf[chave] = pa_idf

            cursor.execute('SELECT count(*) FROM publicacao')
            pubs_3gram_n, = cursor.fetchone()
            cursor.fetchall()

            cursor.execute('SELECT count(*) FROM paragrafo')
            pars_3gram_n, = cursor.fetchone()
            cursor.fetchall()
            cursor.close()

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


def score_paragrafo(session, conteudo):
    if ('score_bag_pub' not in session
            or 'score_bag_par' not in session):
        load_3gram_scorer(session)

    score_bag_pub = session['score_bag_pub']
    score_bag_par = session['score_bag_par']
    pubs_3gram_bag_idf = session['pubs_3gram_bag_idf']

    score_pub = 0
    score_par = 0

    saco_par = monta_saco_ngram(conteudo, n=3)

    for chave in saco_par:
        if chave in pubs_3gram_bag_idf:
            score_pub += saco_par[chave] * score_bag_pub[chave]
            score_par += saco_par[chave] * score_bag_par[chave]
    score = score_pub / (score_par + 1)

    return score


def get_best_n_terms(session, paragrafo_id, n=1):
    conteudo_paragrafo = obter_conteudo_paragrafo(paragrafo_id)
    sacola_paragrafo = monta_saco_ngram(conteudo_paragrafo, n=1)

    tfidf = []
    for token in sacola_paragrafo:
        tfidf.append((token, calcular_tfidf_termo_paragrafo(session, token, paragrafo_id)))

    tfidf.sort(key=lambda k: k[1], reverse=True)

    if len(tfidf) > n:
        return tfidf[:n]
    else:
        return tfidf


def obter_melhores_candidatos(session, paragrafo_id):
    try:
        conteudo_publicacoes = session['conteudo_publicacoes']
        saco_publicacoes = session['saco_publicacoes']
    except KeyError as e:
        print('regenerando chaves')
        conteudo_publicacoes = []
        saco_publicacoes = {}
        with mysql.connector.connect(**sql_config) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT publicacao_id, conteudo FROM publicacao')
            for publicacao_id, conteudo in cursor:
                conteudo_publicacoes.append((str(publicacao_id), conteudo))
            cursor.close()

        for publicacao_id, conteudo in conteudo_publicacoes:
            saco_pub = monta_saco_ngram(conteudo, n=3)
            saco_publicacoes[str(publicacao_id)] = saco_pub
        session['saco_publicacoes'] = saco_publicacoes
        session['conteudo_publicacoes'] = conteudo_publicacoes

    conteudo_paragrafo = obter_conteudo_paragrafo(paragrafo_id)
    saco_alvo = monta_saco_ngram(conteudo_paragrafo, n=3)

    publicacoes = []
    for publicacao_id, conteudo in conteudo_publicacoes:
        saco_pub = saco_publicacoes[publicacao_id]

        similaridade_cosseno = calcula_cosseno_sacos(saco_pub, saco_alvo)
        similaridade_jaccard = calcula_jaccard_sacos(saco_pub, saco_alvo)
        dissimilaridade_str = calcula_dissimilaridade_strings(conteudo_paragrafo, conteudo)
        publicacoes.append({
            'publicacao_id': publicacao_id,
            'conteudo': conteudo,
            'cosseno': similaridade_cosseno,
            'jaccard': similaridade_jaccard,
            'dissim': dissimilaridade_str,
        })

    publicacoes_ord = sorted(publicacoes, key=lambda e: e['dissim'], reverse=False)

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
            if publicacao['dissim'] < melhor_dis['dissim']:
                melhor_dis = publicacao

    return publicacoes_ord, melhor_cos, melhor_jac, melhor_dis


def obter_publicacoes():
    publicacoes = []
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        cursor.execute('SELECT publicacao_id, conteudo FROM publicacao')
        for publicacao_id, conteudo in cursor:
            publicacoes.append((publicacao_id, conteudo))
        cursor.close()
    return publicacoes


def buscar_termo_publicacao(session, termo):
    publicacoes = obter_publicacoes()
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
