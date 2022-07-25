from django.http import HttpResponse
from django.template import loader
from django.http import HttpResponseRedirect
from django.urls import reverse

import mysql.connector

from . import utils
from . import interface as ido


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
    publicacoes_ord, melhor_cos, melhor_jac, melhor_dis = utils.obter_melhores_candidatos(request.session, paragrafo_id)

    template = loader.get_template('comparador/comparacao_api.html')
    context = {
        'melhor_cos': melhor_cos,
        'melhor_jac': melhor_jac,
        'melhor_dis': melhor_dis
    }

    return HttpResponse(template.render(context, request))


def mostrar_candidatos(request, paragrafo_id):
    conteudo_paragrafo = utils.obter_conteudo_paragrafo(paragrafo_id)
    publicacoes_ord, melhor_cos, melhor_jac, melhor_dis = utils.obter_melhores_candidatos(request.session, paragrafo_id)

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


def buscar(request):
    return HttpResponseRedirect(reverse('resultado', args=(request.POST['termo_busca'],)))


def resultado_busca(request, termo_busca):
    candidatos = utils.buscar_termo_publicacao(request.session, termo_busca)

    template = loader.get_template('comparador/busca.html')
    context = {'candidatos': candidatos}

    return HttpResponse(template.render(context, request))


def baixar_do_redirect(request):
    return HttpResponseRedirect(reverse('baixar_do', args=(request.POST['ano_do_busca'], request.POST['mes_do_busca'])))


def baixar_do(request, ano, mes):
    ido.obter_diarios(ano, mes)
    return HttpResponse(reverse('exibir_diarios'))


def baixar_licitacoes_redirect(request):
    return HttpResponseRedirect(reverse('baixar_licitacoes', args=(request.POST['ano_lic_busca'], request.POST['t'])))


def baixar_licitacoes(request, ano, t):
    lics = ido.atualizar_licitacoes_por_ano(ano, t=t)

    return HttpResponse(str(lics))
