
CREATE TABLE modalidade (
	modalidade_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	descricao VARCHAR(20)
);

CREATE TABLE interessado (
	interessado_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	descricao VARCHAR(100)
);

CREATE TABLE tipo (
	tipo_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	descricao VARCHAR(20)
);

CREATE TABLE prazo_tipo (
	prazo_tipo_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	descricao VARCHAR(20)
);

CREATE TABLE publicacao_titulo (
	publicacao_titulo_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	descricao VARCHAR(50)
);

-- ============================================================================= --

CREATE TABLE licitacao (
	identificador INTEGER NOT NULL PRIMARY KEY,
	modalidade_id BIGINT NOT NULL,
	numero_modalidade INTEGER,
	ano_modalidade INTEGER,
	tipo_id BIGINT,
	interessado_id BIGINT,
	numero_processo INTEGER NOT NULL,
	ano_processo INTEGER NOT NULL,

	FOREIGN KEY (modalidade_id) REFERENCES modalidade (modalidade_id),
	FOREIGN KEY (tipo_id) REFERENCES tipo (tipo_id),
	FOREIGN KEY (interessado_id) REFERENCES interessado (interessado_id)
);

CREATE TABLE especificacao (
	especificacao_id INTEGER NOT NULL PRIMARY KEY,
	identificador INTEGER NOT NULL,
	conteudo TEXT NOT NULL,

	FOREIGN KEY (identificador) REFERENCES licitacao (identificador)
);

CREATE TABLE publicacao (
	publicacao_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	identificador INTEGER NOT NULL,
	publicacao_titulo_id BIGINT NOT NULL,
	ano INTEGER NOT NULL,
	mes INTEGER NOT NULL,
	conteudo TEXT NOT NULL,

	FOREIGN KEY (identificador) REFERENCES licitacao (identificador),
	FOREIGN KEY (publicacao_titulo_id) REFERENCES publicacao_titulo (publicacao_titulo_id)
);

CREATE TABLE observacao (
	identificador INTEGER NOT NULL,
	conteudo TEXT NOT NULL,

	FOREIGN KEY (identificador) REFERENCES licitacao (identificador)
);

CREATE TABLE edital (
	edital_id INTEGER NOT NULL PRIMARY KEY,
	identificador INTEGER NOT NULL,
	numero INTEGER NOT NULL,
	ano INTEGER NOT NULL,
	endereco VARCHAR(100),

	FOREIGN KEY (identificador) REFERENCES licitacao (identificador)
);

CREATE TABLE apensados (
	identificador INTEGER NOT NULL,
	numero INTEGER NOT NULL,
	ano INTEGER NOT NULL,

	FOREIGN KEY (identificador) REFERENCES licitacao (identificador)
);

CREATE TABLE prazo (
	identificador INTEGER NOT NULL,
	prazo_tipo_id BIGINT NOT NULL,
	ano INTEGER NOT NULL,
	mes INTEGER NOT NULL,
	dia INTEGER NOT NULL,
	hora INTEGER NOT NULL DEFAULT 23,
	minuto INTEGER NOT NULL DEFAULT 59,

	FOREIGN KEY (identificador) REFERENCES licitacao (identificador),
	FOREIGN KEY (prazo_tipo_id) REFERENCES prazo_tipo (prazo_tipo_id)
);

CREATE TABLE diario (
	edicao INTEGER NOT NULL PRIMARY KEY,
	ano INTEGER NOT NULL,
	mes INTEGER NOT NULL,
	dia INTEGER NOT NULL
);

CREATE TABLE paragrafo (
	paragrafo_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	edicao INTEGER NOT NULL,
	paragrafo INTEGER NOT NULL,
	conteudo TEXT NOT NULL,

	FOREIGN KEY (edicao) REFERENCES diario (edicao)
);

CREATE TABLE saco_corpus (
	saco_id BIGINT NOT NULL DEFAULT (UUID_SHORT()) PRIMARY KEY,
	descricao VARCHAR(20) NOT NULL
);

CREATE TABLE saco_item (
	saco_id BIGINT NOT NULL,
	chave VARCHAR(500) NOT NULL,
	frequencia INTEGER NOT NULL,
	idf INTEGER NOT NULL,

	FOREIGN KEY (saco_id) REFERENCES saco_corpus (saco_id)
);

