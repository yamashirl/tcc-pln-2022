import re
import math


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


def calcula_dissimilaridade_strings(string_a, string_b, n=2):
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
