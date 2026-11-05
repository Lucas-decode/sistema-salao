
CREATE DATABASE IF NOT EXISTS sistema_salao
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE sistema_salao;

-- =========================================
-- USUÁRIOS
-- =========================================

CREATE TABLE usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    senha VARCHAR(255) NOT NULL,
    tipo ENUM('cliente', 'proprietario') NOT NULL DEFAULT 'cliente',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    telefone VARCHAR(11) NOT NULL,
    data_nascimento DATE DEFAULT NULL,

    UNIQUE KEY telefone_unico (telefone)
);

-- =========================================
-- SERVIÇOS
-- =========================================

CREATE TABLE servicos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    preco DECIMAL(10,2) NOT NULL,
    duracao_minutos INT NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    comprimento ENUM('Curto', 'Médio', 'Comprido') NOT NULL,

    UNIQUE KEY uq_servico_comprimento (nome, comprimento)
);

-- =========================================
-- CONFIGURAÇÃO DOS PERÍODOS DE FUNCIONAMENTO
-- =========================================

CREATE TABLE periodos_funcionamento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dia_semana TINYINT NOT NULL,
    hora_abertura TIME NOT NULL,
    hora_fechamento TIME NOT NULL,
    intervalo_minutos INT NOT NULL DEFAULT 30,
    ativo BOOLEAN NOT NULL DEFAULT TRUE
);

-- =========================================
-- AGENDAMENTOS
-- =========================================

CREATE TABLE agendamentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    cliente_id INT NOT NULL,
    servico_id INT NOT NULL,
    data DATE NOT NULL,
    horario TIME NOT NULL,
    observacao TEXT,
    status ENUM(
        'pendente',
        'confirmado',
        'cancelado',
        'concluido',
        'faltou'
    ) NOT NULL DEFAULT 'pendente',
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX (cliente_id),
    INDEX (servico_id),

    CONSTRAINT agendamentos_ibfk_1
        FOREIGN KEY (cliente_id)
        REFERENCES usuarios(id),

    CONSTRAINT agendamentos_ibfk_2
        FOREIGN KEY (servico_id)
        REFERENCES servicos(id)
);

-- =========================================
-- ATENDIMENTOS
-- =========================================

CREATE TABLE atendimentos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agendamento_id INT NOT NULL UNIQUE,
    status ENUM('compareceu', 'faltou') NOT NULL,
    valor_final DECIMAL(10,2),
    observacao TEXT,
    registrado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT atendimentos_ibfk_1
        FOREIGN KEY (agendamento_id)
        REFERENCES agendamentos(id)
);
