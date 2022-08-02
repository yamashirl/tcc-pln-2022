import mysql.connector


class Conexao:
    def __init__(self):
        self.cursor = None
        self.connection = None
        self.commited = False

    def __enter__(self):
        self.connection = mysql.connector.connect(user='root',
                                                  password='see-cret',
                                                  database='tcc')
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.commited:
            self.connection.rollback()
        if self.cursor is not None:
            self.cursor.close()
        self.connection.close()

    def __call__(self, query, params=None):
        self.cursor.execute(query, params)
        return self.cursor

    def fetchonlyone(self):
        row = self.cursor.fetchone()
        self.cursor.fetchall()
        return row

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def commit(self):
        self.commited = True
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()


def obter_lista_diarios():
    with Conexao() as cursor:
        resultado = cursor('SELECT edicao, ano, mes, dia FROM diario ORDER BY edicao DESC')
        diarios = []
        for edicao, ano, mes, dia in resultado:
            diarios.append({
                'edicao': edicao,
                'ano': ano,
                'mes': mes,
                'dia': dia
            })
    return diarios


def obter_paragrafos_do(edicao):
    with Conexao() as cursor:
        resultado = cursor('SELECT paragrafo_id, conteudo FROM paragrafo WHERE edicao = %s', (edicao,))
        if resultado is None:
            return None

        paragrafos = []
        for paragrafo_id, conteudo in resultado:
            paragrafos.append((paragrafo_id, conteudo))

    return paragrafos


def obter_paragrafos():
    with Conexao() as cursor:
        resultado = cursor('SELECT paragrafo_id, conteudo FROM paragrafo')
        if resultado is None:
            return None

        paragrafos = []
        for paragrafo_id, conteudo in resultado:
            paragrafos.append((paragrafo_id, conteudo))

    return paragrafos


def obter_publicacoes():
    conteudo_publicacoes = []

    with Conexao() as cursor:
        resultado = cursor('SELECT publicacao_id, conteudo FROM publicacao')
        for publicacao_id, conteudo in resultado:
            conteudo_publicacoes.append((publicacao_id, conteudo))

    return conteudo_publicacoes


def obter_conteudo_publicacao(publicacao_id):
    with Conexao() as cursor:
        resultado = cursor('SELECT conteudo FROM publicacao WHERE publicacao_id = %s', (publicacao_id,))
        conteudo, = cursor.fetchonlyone()
    return conteudo


def obter_conteudo_paragrafo(paragrafo_id):
    with Conexao() as cursor:
        resultado = cursor('SELECT conteudo FROM paragrafo WHERE paragrafo_id = %s', (paragrafo_id,))
        conteudo, = cursor.fetchonlyone()
    return conteudo


def get_count(tabela):
    with Conexao() as cursor:
        query = f'SELECT count(*) FROM {tabela}'
        resultado = cursor(query)
        retorno, = cursor.fetchonlyone()
    return retorno


def nova_sacola(descricao, itens):
    with Conexao() as cursor:
        cursor('INSERT INTO sacola(descricao) VALUES (%s)', (descricao,))
        cursor.commit()
        sacola_id = get_id('sacola', descricao)
        for item in itens:
            cursor('INSERT INTO sacola_item(sacola_id, chave, frequencia, idf) ' \
                   'VALUES (%s, %s, %s, %s)',
                   (sacola_id, item['chave'], item['frequencia'], item['idf']))
        cursor.commit()
    return sacola_id


def remover_sacola(sacola_id):
    with Conexao() as cursor:
        cursor('DELETE FROM sacola_item WHERE sacola_id = %s', (sacola_id,))
        cursor('DELETE FROM sacola WHERE sacola_id = %s', (sacola_id,))
        cursor.commit()


def get_id(tabela, descricao):
    with Conexao() as cursor:
        query = f'SELECT {tabela}_id FROM {tabela} WHERE descricao LIKE %s'
        cursor(query, (descricao,))

        resultado = cursor.fetchonlyone()
        if resultado is None:
            return None

        retorno, = resultado
    return retorno


def get_sacola(descricao):
    with Conexao() as cursor:
        resultado = cursor('SELECT sacola_id FROM sacola WHERE descricao LIKE %s', (descricao,))
        sacola_id, = cursor.fetchonlyone()

        sacola = {}
        resultado = cursor('SELECT chave, idf FROM sacola_item WHERE sacola_id = %s', (sacola_id,))
        for chave, valor in resultado:
            sacola[chave] = valor

    return sacola_id, sacola


def get_sacolas_inner(sacola_id_a, sacola_id_b):
    with Conexao() as cursor:
        query = 'SELECT chave, sa.idf, sb.idf ' \
                'FROM sacola_item as sa INNER JOIN sacola_item as sb USING (chave) ' \
                'WHERE sa.sacola_id = %s AND sb.sacola_id = %s '
        resultado = cursor(query, (sacola_id_a, sacola_id_b))

        sacola_a = {}
        sacola_b = {}
        for chave, sa_idf, sb_idf in resultado:
            sacola_a[chave] = sa_idf
            sacola_b[chave] = sb_idf
    return sacola_a, sacola_b


def insere_diario(titulo, paragrafos):
    success = True
    with Conexao() as cursor:
        try:
            edicao = titulo['edicao']
            ano = titulo['ano']
            mes = titulo['mes']
            dia = titulo['dia']
            edicao_do = titulo['edicao']

            cursor('INSERT INTO diario (edicao, ano, mes, dia)'
                   + ' VALUES (%s, %s, %s, %s)', (edicao, ano, mes, dia))

            for num, paragrafo in enumerate(paragrafos):
                cursor('INSERT INTO paragrafo (edicao, paragrafo, conteudo)'
                       + ' VALUES (%s, %s, %s)', (edicao_do, num, paragrafo))

            cursor.commit()
        except mysql.connector.Error as e:
            success = False
            print(e)
    return success


def select_or_insert(tabela, descricao):
    with Conexao() as cursor:
        select_qry = f'SELECT {tabela + "_id"} FROM {tabela} WHERE descricao LIKE %s'
        resultado = cursor(select_qry, (descricao,))
        row = cursor.fetchonlyone()

        if row is None:
            insert_qry = f'INSERT INTO {tabela}(descricao) VALUES (%s)'
            cursor(insert_qry, (descricao,))
            cursor.commit()

            resultado = cursor(select_qry, (descricao,))
            ret = cursor.fetchonlyone()[0]
        else:
            ret = row[0]

    return ret


def inserir_licitacao_sql(dict_licitacao):
    existe = False
    with Conexao() as cursor:
        titulo_modalidade = dict_licitacao['titulo']['modalidade']
        interessado = dict_licitacao['interessado']
        tipo = dict_licitacao['tipo']
        identificador = dict_licitacao['identificador']
        numero_modalidade = dict_licitacao['titulo']['numero']
        ano_modalidade = dict_licitacao['titulo']['ano']

        modalidade_id = select_or_insert('modalidade', titulo_modalidade)
        interessado_id = select_or_insert('interessado', interessado)
        tipo_id = select_or_insert('tipo', tipo)

        resultado = cursor('SELECT numero_processo FROM licitacao WHERE identificador = %s', (identificador,))
        linha = cursor.fetchonlyone()

        if linha is not None:
            existe = True
            cursor('DELETE FROM publicacao WHERE identificador = %s', (identificador,))
            cursor('DELETE FROM observacao WHERE identificador = %s', (identificador,))
            cursor('DELETE FROM apensados WHERE identificador = %s', (identificador,))
            cursor('DELETE FROM edital WHERE identificador = %s', (identificador,))
            cursor('DELETE FROM especificacao WHERE identificador = %s', (identificador,))
            cursor('DELETE FROM prazo WHERE identificador = %s', (identificador,))
            cursor('DELETE FROM licitacao WHERE identificador = %s', (identificador,))

        cursor('INSERT INTO '
               + 'licitacao(identificador, modalidade_id, numero_modalidade, ano_modalidade, tipo_id, '
                 'interessado_id) '
               + 'VALUES (%s, %s, %s, %s, %s, %s)',
               (identificador, modalidade_id, numero_modalidade, ano_modalidade, tipo_id, interessado_id))

        if 'processo' in dict_licitacao:
            numero_processo = dict_licitacao['processo']['numero']
            ano_processo = dict_licitacao['processo']['ano']

            cursor('UPDATE licitacao SET numero_processo = %s, ano_processo = %s WHERE identificador = %s',
                   (numero_processo, ano_processo, identificador))

        if 'publicacoes' in dict_licitacao:
            for publicacao in dict_licitacao['publicacoes']:
                publicacao_titulo = publicacao['titulo']
                publicacao_titulo_id = select_or_insert('publicacao_titulo', publicacao_titulo)

                ano = publicacao['ano']
                mes = publicacao['mes']
#                dia = publicacao['dia']
                conteudo = publicacao['conteudo']

                cursor(
                    'INSERT INTO publicacao(identificador, publicacao_titulo_id, ano, mes, conteudo) VALUES (%s, %s, '
                    '%s, %s, %s)',
                    (identificador, publicacao_titulo_id, ano, mes, conteudo)
                )
        cursor.commit()
    return existe
