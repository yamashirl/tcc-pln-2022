from django.http import HttpResponse
from django.template import loader
from django.http import HttpResponseRedirect
from django.urls import reverse

import mysql.connector
import re

from . import utils


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


def index(request):
    return HttpResponse("Hello, world.")


def informacoes_paragrafo(request, paragrafo_id):
    conteudo = utils.obter_conteudo_paragrafo(paragrafo_id)
    score = utils.score_paragrafo(request.session, conteudo)
    max_tfidf = utils.get_best_n_terms(request.session, paragrafo_id, n=10)

    template = loader.get_template('comparador/info_paragrafo.html')
    context = {
        'paragrafo_id': paragrafo_id,
        'conteudo': conteudo,
        'confianca': score,
        'best_n': max_tfidf,
    }

    return HttpResponse(template.render(context, request))


def exibir_diarios(request):
    diarios = utils.obter_lista_diarios()
    
    template = loader.get_template('comparador/diarios.html')
    context = {'diarios': diarios}

    return HttpResponse(template.render(context, request))


def exibir_do(request, edicao):
    diarios = utils.obter_paragrafos_do(edicao)
    paragrafos = []
    for paragrafo_id, conteudo in diarios:
        confianca = utils.score_paragrafo(request.session, conteudo)
        paragrafos.append((paragrafo_id, confianca, conteudo))

    template = loader.get_template('comparador/ler_do.html')
    context = {
        'edicao': edicao,
        'paragrafos': paragrafos,
    }

    return HttpResponse(template.render(context, request))


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


def resultado_busca(request, termo_busca):
    load_1gram(request.session)

    with mysql.connector.connect(**sql_config) as connection:
        cursor = connection.cursor()

        buscador_compilado = re.compile(r'\b' + termo_busca.lower() + r'\b')
        tokenizador = re.compile(r'\w+')
        candidatos = []
        cursor.execute('SELECT publicacao_id, conteudo FROM publicacao')
        for publicacao_id, conteudo in cursor:
            resultado = buscador_compilado.findall(conteudo)
            n_pub = tokenizador.findall(re.sub(r'\d', ' ', conteudo.lower()))

            lr = len(resultado)
            if lr > 0:
                candidatos.append({'publicacao_id': publicacao_id,
                                   'contagem': lr,
                                   'tfidf': lr / len(n_pub),
                                   'conteudo': conteudo})
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
