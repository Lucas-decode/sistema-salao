from datetime import date, timedelta

from app import app
from routes.auth import _obter_horarios_disponiveis


def test_pagina_inicial():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        resposta = cliente.get("/")

    assert resposta.status_code == 200


def test_pagina_cadastro():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        resposta = cliente.get("/cadastro")

    assert resposta.status_code == 200


def test_pagina_login():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        resposta = cliente.get("/login")

    assert resposta.status_code == 200


def test_painel_proprietario_exige_login():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        resposta = cliente.get("/proprietario")

    assert resposta.status_code == 302


def test_agendamento_exige_login():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        resposta = cliente.get("/agendamento")

    assert resposta.status_code == 302


def test_cliente_nao_acessa_painel_proprietario():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 10
            sessao["tipo"] = "cliente"

        resposta = cliente.get("/proprietario")

    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/cliente")


def test_proprietario_nao_acessa_area_cliente():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 20
            sessao["tipo"] = "proprietario"

        resposta = cliente.get("/cliente")

    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/proprietario")


def test_api_horarios_exige_login():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        resposta = cliente.get("/agendamento/horarios")

    assert resposta.status_code == 401
    assert resposta.get_json()["horarios"] == []
    assert "erro" in resposta.get_json()


def test_api_horarios_rejeita_usuario_proprietario():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 20
            sessao["tipo"] = "proprietario"

        resposta = cliente.get(
            "/agendamento/horarios?servico_id=1&data=2099-05-05"
        )

    assert resposta.status_code == 401
    assert resposta.get_json()["horarios"] == []


def test_api_horarios_rejeita_parametros_invalidos():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 10
            sessao["tipo"] = "cliente"

        resposta = cliente.get(
            "/agendamento/horarios?servico_id=abc&data=2099-05-05"
        )

    assert resposta.status_code == 200
    assert resposta.get_json()["horarios"] == []


def test_api_horarios_rejeita_data_invalida():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 10
            sessao["tipo"] = "cliente"

        resposta = cliente.get(
            "/agendamento/horarios?servico_id=1&data=nao-e-data"
        )

    assert resposta.status_code == 200
    assert resposta.get_json()["horarios"] == []


def test_api_horarios_rejeita_data_passada():
    app.config["TESTING"] = True

    data_passada = (date.today() - timedelta(days=1)).isoformat()

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 10
            sessao["tipo"] = "cliente"

        resposta = cliente.get(
            f"/agendamento/horarios?servico_id=1&data={data_passada}"
        )

    assert resposta.status_code == 200
    assert resposta.get_json()["horarios"] == []

def test_api_horarios_retorna_json():
    app.config["TESTING"] = True

    with app.test_client() as cliente:
        with cliente.session_transaction() as sessao:
            sessao["usuario_id"] = 10
            sessao["tipo"] = "cliente"

        resposta = cliente.get(
            "/agendamento/horarios?servico_id=abc&data=2099-05-05"
        )

    assert resposta.status_code == 200
    assert resposta.is_json
    assert resposta.get_json() == {"horarios": []}

class CursorSimulado:
    """Simula as respostas do banco para testar a disponibilidade."""

    def __init__(self, servico, periodos, agendamentos):
        self.servico = servico
        self.periodos = periodos
        self.agendamentos = agendamentos
        self.consulta = 0

    def execute(self, consulta, parametros=None):
        self.consulta += 1

    def fetchone(self):
        return self.servico

    def fetchall(self):
        if self.consulta == 2:
            return self.periodos
        if self.consulta == 3:
            return self.agendamentos
        return []

def test_disponibilidade_servico_inexistente():
    cursor = CursorSimulado(None, [], [])

    horarios = _obter_horarios_disponiveis(
        cursor, 999, date(2099, 5, 5)
    )

    assert horarios == []


def test_disponibilidade_servico_inativo():
    cursor = CursorSimulado(None, [], [])

    horarios = _obter_horarios_disponiveis(
        cursor, 999, date(2099, 5, 5)
    )

    assert horarios == []

def test_disponibilidade_sem_expediente():
    cursor = CursorSimulado(
        {"duracao_minutos": 30},
        [],
        []
    )

    horarios = _obter_horarios_disponiveis(
        cursor, 1, date(2099, 5, 5)
    )

    assert horarios == []


def test_disponibilidade_respeita_duracao_do_servico():
    cursor = CursorSimulado(
        {"duracao_minutos": 60},
        [
            {
                "hora_abertura": timedelta(hours=9),
                "hora_fechamento": timedelta(hours=10)
            }
        ],
        []
    )

    horarios = _obter_horarios_disponiveis(
        cursor, 1, date(2099, 5, 5)
    )

    assert horarios == ["09:00"]


def test_disponibilidade_ignora_agendamento_cancelado():
    cursor = CursorSimulado(
        {"duracao_minutos": 30},
        [
            {
                "hora_abertura": timedelta(hours=9),
                "hora_fechamento": timedelta(hours=10)
            }
        ],
        [
            {
                "horario": "09:00",
                "duracao_minutos": 30,
                "status": "cancelado"
            }
        ]
    )

    horarios = _obter_horarios_disponiveis(
        cursor, 1, date(2099, 5, 5)
    )

    assert "09:00" in horarios


def test_disponibilidade_bloqueia_conflito_de_horario():
    cursor = CursorSimulado(
        {"duracao_minutos": 30},
        [
            {
                "hora_abertura": timedelta(hours=9),
                "hora_fechamento": timedelta(hours=10)
            }
        ],
        [
            {
                "horario": "09:00",
                "duracao_minutos": 30,
                "status": "confirmado"
            }
        ]
    )

    horarios = _obter_horarios_disponiveis(
        cursor, 1, date(2099, 5, 5)
    )

    assert "09:00" not in horarios
    assert "09:30" in horarios