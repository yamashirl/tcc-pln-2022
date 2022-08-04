from django.http import HttpResponse
from django.template import loader
from django.http import HttpResponseRedirect
from django.urls import reverse

from . import interface as backend


def informacoes_paragrafo(request, paragrafo_id):
    par = backend.informacoes_paragrafo(request.session, paragrafo_id)

    template = loader.get_template('comparador/info_paragrafo.html')
    context = {
        'paragrafo_id': paragrafo_id,
        'conteudo': par['conteudo'],
        'confianca': par['confianca'],
        'best_n': par['max_tfidf'],
    }

    return HttpResponse(template.render(context, request))


def exibir_diarios(request):
    diarios = backend.select_diarios()

    template = loader.get_template('comparador/diarios.html')
    context = {'diarios': diarios}

    return HttpResponse(template.render(context, request))


def exibir_do(request, edicao):
    paragrafos, plot = backend.select_paragrafos_do(request.session, edicao)

    template = loader.get_template('comparador/ler_do.html')
    context = {
        'edicao': edicao,
        'paragrafos': paragrafos,
        'plot': plot
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
    par = backend.informacoes_paragrafo(request.session, paragrafo_id)
    publicacoes_ord, melhor_cos, melhor_jac, melhor_dis, plot = backend.mostrar_candidatos(request.session, paragrafo_id)

    template = loader.get_template('comparador/comparacao.html')
    context = {
        'paragrafo': {
            'paragrafo_id': paragrafo_id,
            'conteudo': par['conteudo']
        },
        'publicacoes': publicacoes_ord,
        'melhor_cos': melhor_cos,
        'melhor_jac': melhor_jac,
        'melhor_dis': melhor_dis,
        'plot': plot
    }

    return HttpResponse(template.render(context, request))


def comparar(request, paragrafo_id, publicacao_id):
    pass


def buscar(request):
    return HttpResponseRedirect(reverse('resultado', args=(request.POST['termo_busca'],)))


def resultado_busca(request, termo_busca):
    candidatos = backend.buscar_termo_publicacao(request.session, termo_busca)

    template = loader.get_template('comparador/busca.html')
    context = {'candidatos': candidatos}

    return HttpResponse(template.render(context, request))


def baixar_do_redirect(request):
    return HttpResponseRedirect(reverse('baixar_do', args=(request.POST['ano_do_busca'], request.POST['mes_do_busca'])))


def baixar_do(request, ano, mes):
    dados = backend.baixar_diarios(ano, mes)

    template = loader.get_template('comparador/diarios_baixados.html')
    context = {
        'dos': dados
    }

    return HttpResponse(template.render(context, request))


def baixar_licitacoes_redirect(request):
    return HttpResponseRedirect(reverse('baixar_licitacoes', args=(request.POST['ano_lic_busca'], request.POST['t'])))


def baixar_licitacoes(request, ano, t):
    statuses = backend.atualizar_licitacoes_por_ano(ano, t=t)

    template = loader.get_template('comparador/licitacoes_baixadas.html')
    context = {
        'licitacoes': statuses
    }

    return HttpResponse(template.render(context, request))


def recriar_ngrams(request):
    # TODO interface
    backend.recriar_ngrams()
    return HttpResponse('Recriado')
