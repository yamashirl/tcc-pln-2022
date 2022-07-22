from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader

import mysql.connector
import math
import re

from . import utils

sql_config = {
    'user': 'root',
    'password': 'see-cret',
    'database': 'tcc',
}

def load_3gram_scorer(session):
    try:
        pubs_3gram_bag_idf = session['pubs_3gram_bag_idf']
        pars_3gram_bag_idf = session['pars_3gram_bag_idf']
        pubs_3gram_n       = session['pubs_3gram_n']
        pars_3gram_n       = session['pars_3gram_n']
        score_bag_pub      = session['score_bag_pub']
        score_bag_par      = session['score_bag_par']
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
        session['pubs_3gram_n']       = pubs_3gram_n
        session['pars_3gram_n']       = pars_3gram_n
        session['score_bag_pub']      = score_bag_pub
        session['score_bag_par']      = score_bag_par

def score_paragrafo(session, conteudo):
    if ('score_bag_pub' not in session
            or 'score_bag_par' not in session):
        load_3gram_scorer(session)

    score_bag_pub = session['score_bag_pub']
    score_bag_par = session['score_bag_par']
    pubs_3gram_bag_idf = session['pubs_3gram_bag_idf']

    score_pub = 0
    score_par = 0

    saco_par = utils.monta_saco_ngram(conteudo, n = 3)

    for chave in saco_par:
        if chave in pubs_3gram_bag_idf:
            score_pub += saco_par[chave] * score_bag_pub[chave]
            score_par += saco_par[chave] * score_bag_par[chave]
    score = score_pub/(score_par + 1)

    return score

def temp(request):
    scores = []
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT edicao, paragrafo, conteudo FROM paragrafo')
        for edicao, paragrafo, conteudo, in cursor:
            score = score_paragrafo(request.session, conteudo)
            scores.append((edicao, paragrafo, score))
        cursor.close()

    return HttpResponse(scores)

pubs_1gram_bag_idf = {}

def load_1gram(session):
    if ('pubs_1gram_bag_idf' not in session
            or 'pubs_1gram_n' not in session):
        pubs_1gram_bag_idf = {}
        with mysql.connector.connect(**sql_config) as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT saco_id FROM saco_corpus WHERE descricao LIKE %s', ('publicacoes_1gram',))
            saco_id_publicacoes, = cursor.fetchone()
            cursor.fetchall()

            cursor.execute('SELECT chave, idf FROM saco_item WHERE saco_id = %s', (saco_id_publicacoes,))
            for chave, idf in cursor:
                pubs_1gram_bag_idf[chave] = idf

            cursor.execute('SELECT count(*) FROM publicacao')
            pubs_1gram_n, = cursor.fetchone()
            cursor.fetchall()

#            cursor.execute('SELECT count(*) FROM paragrafo')
#            pars_1gram_n, = cursor.fetchone()
#            cursor.fetchall()
            cursor.close()
        session['pubs_1gram_bag_idf'] = pubs_1gram_bag_idf
        session['pubs_1gram_n']       = pubs_1gram_n

def get_best_n_terms(session, conteudo, n = 1):
    if ('pubs_1gram_bag_idf' not in session
            or 'pubs_1gram_n' not in session):
        load_1gram(session)

    pubs_1gram_bag_idf = session['pubs_1gram_bag_idf']
    pubs_1gram_n = session['pubs_1gram_n']

    tokens = utils.monta_saco_ngram(conteudo, n = 1)
    tf = {}
    for token in tokens:
        if token in tf:
            tf[token] += 1
        else:
            tf[token] = 1
    tfidf_pub = {}
    tfidf_par = {}
    for token in tf:
        if token in pubs_1gram_bag_idf:
            tfidf_pub[token] = tf[token] * math.log(pubs_1gram_n / pubs_1gram_bag_idf[token])
    max_n = [{'token': '_', 'tfidf': -1}] * n
    for token in tfidf_pub:
        i = n - 1
        while i >= 0:
            if tfidf_pub[token] > max_n[i]['tfidf']:
                if i < n - 1:
                    max_n[i+1] = max_n[i]
                max_n[i] = {
                        'token': token,
                        'tfidf': tfidf_pub[token]
                }

            i -= 1
    return max_n


def index(request):
    return HttpResponse("Hello, world.")

def informacoes_paragrafo(request, paragrafo_id):
    load_3gram_scorer(request.session)
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        # OBTÉM O PARÁGRAFO A SER PESQUISADO
        cursor.execute('SELECT conteudo FROM paragrafo WHERE paragrafo_id = %s', (paragrafo_id,))
        conteudo, = cursor.fetchone()
        cursor.fetchall()

        cursor.close()

    score = score_paragrafo(request.session, conteudo)
    max_tfidf = get_best_n_terms(request.session, conteudo, n = 10)

    template = loader.get_template('comparador/info_paragrafo.html')
    context = {
            'paragrafo_id': paragrafo_id,
            'conteudo': conteudo,
            'confianca': score,
            'best_n': max_tfidf,
    }

    return HttpResponse(template.render(context, request))

def exibir_diarios(request):
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
    template = loader.get_template('comparador/diarios.html')
    context = {'diarios': diarios}

    return HttpResponse(template.render(context, request))

def exibir_do(request, edicao):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT paragrafo_id, conteudo FROM paragrafo WHERE edicao = %s', (edicao,))
        if cursor == None:
            return HttpResponse('Sem DO')
        paragrafos = []
        for paragrafo_id, conteudo in cursor:
            confianca = score_paragrafo(request.session, conteudo)
            paragrafos.append((paragrafo_id, conteudo, confianca))
        cursor.close()
    template = loader.get_template('comparador/ler_do.html')
    context = {
            'edicao': edicao,
            'paragrafos': paragrafos,
    }

    return HttpResponse(template.render(context, request))

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
            saco_pub = utils.monta_saco_ngram(conteudo, n = 3)
            saco_publicacoes[str(publicacao_id)] = saco_pub
        session['saco_publicacoes'] = saco_publicacoes
        session['conteudo_publicacoes'] = conteudo_publicacoes

    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT conteudo FROM paragrafo WHERE paragrafo_id = %s', (paragrafo_id,))
        conteudo_paragrafo, = cursor.fetchone()
        cursor.fetchall()
        cursor.close()

    saco_alvo = utils.monta_saco_ngram(conteudo_paragrafo, n = 3)

    publicacoes = []
    for publicacao_id, conteudo in conteudo_publicacoes:
        saco_pub = saco_publicacoes[publicacao_id]

        similaridade_cosseno = utils.calcula_cosseno_sacos(saco_pub, saco_alvo)
        similaridade_jaccard = utils.calcula_jaccard_sacos(saco_pub, saco_alvo)
        dissimilaridade_str  = utils.calcula_dissimilaridade_strings(conteudo_paragrafo, conteudo)
        publicacoes.append({
            'publicacao_id': publicacao_id,
            'conteudo': conteudo,
            'cosseno': similaridade_cosseno,
            'jaccard': similaridade_jaccard,
            'dissim' : dissimilaridade_str,
        })

    return conteudo, publicacoes

def mostrar_candidatos_api(request, paragrafo_id):
    conteudo_paragrafo, publicacoes = obter_melhores_candidatos(request.session, paragrafo_id)

    melhor_cos = None
    melhor_jac = None
    melhor_dis = None
    if len(publicacoes) > 0:
        melhor_cos = publicacoes[0]
        melhor_jac = publicacoes[0]
        melhor_dis = publicacoes[0]
        for publicacao in publicacoes:
            if publicacao['cosseno'] > melhor_cos['cosseno']:
                melhor_cos = publicacao
            if publicacao['jaccard'] > melhor_jac['jaccard']:
                melhor_jac = publicacao
            if publicacao['dissim'] < melhor_dis['dissim']:
                melhor_dis = publicacao

    context = {
            'melhor_cos': melhor_cos,
            'melhor_jac': melhor_jac,
            'melhor_dis': melhor_dis
    }

    template = loader.get_template('comparador/comparacao_api.html')

    return HttpResponse(template.render(context, request))

def mostrar_candidatos(request, paragrafo_id):
    conteudo_paragrafo, publicacoes = obter_melhores_candidatos(paragrafo_id)
    publicacoes_ord = sorted(publicacoes, key = lambda e: e['dissim'], reverse = False)

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

    template = loader.get_template('comparador/comparacao.html')
    context = {
            'paragrafo': {
                'paragrafo_id': paragrafo_id,
                'conteudo': conteudo_paragrafo
            },
            'publicacoes': publicacoes_ord,
            'melhor_cos': melhor_cos,
            'melhor_jac': melhor_jac,
            'melhor_dis': melhor_dis
    }

    return HttpResponse(template.render(context, request))

def comparar(request, paragrafo_id, publicacao_id):
    pass

from django.http import HttpResponseRedirect
from django.urls import reverse

def resultado_busca(request, termo_busca):
    load_1gram(request.session)

    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        buscador_compilado = re.compile(r'\b' + termo_busca.lower() + r'\b')
        tokenizador = re.compile('\w+')
        candidatos = []
        cursor.execute('SELECT publicacao_id, conteudo FROM publicacao')
        for publicacao_id, conteudo in cursor:
            resultado = buscador_compilado.findall(conteudo)
            n_pub = tokenizador.findall(re.sub('\d', ' ', conteudo.lower()))

            lr = len(resultado)
            if lr > 0:
                candidatos.append({'publicacao_id':publicacao_id,
                                    'contagem': lr,
                                    'tfidf': lr/len(n_pub),
                                    'conteudo':conteudo})
        cursor.close()
    template = loader.get_template('comparador/busca.html')
    context = {'candidatos': candidatos}

    return HttpResponse(template.render(context, request))

def buscar(request):

#    template = loader.get_template('comparador/busca.html')
#    context = {'candidatos': candidatos}

#    return HttpResponse(template.render(context, request))
    return HttpResponseRedirect(reverse('resultado', args=(request.POST['termo_busca'],)))

def random(request):
    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()
        cursor.execute('SELECT identificador FROM licitacao')
        identificadores = []
        for identificador, in cursor:
            identificadores.append(identificador)
        cursor.close()

    amontoado = ''
    for identificador in identificadores:
        amontoado += '<p>%d</p>' % identificador

    return HttpResponse(amontoado)

