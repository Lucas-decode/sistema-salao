
from datetime import date, datetime, timedelta
import mysql.connector
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import conectar_banco

auth = Blueprint("auth", __name__)


@auth.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        if not nome or not email or not senha:
            flash("Preencha todos os campos.", "danger")
            return redirect(url_for("auth.cadastro"))

        if len(senha) < 8:
            flash("A senha deve ter pelo menos 8 caracteres.", "danger")
            return redirect(url_for("auth.cadastro"))

        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT id FROM usuarios WHERE email = %s",
                (email,)
            )

            if cursor.fetchone():
                flash("Este e-mail já está cadastrado.", "danger")
                return redirect(url_for("auth.cadastro"))

            senha_hash = generate_password_hash(senha)

            cursor.execute(
                """
                INSERT INTO usuarios (nome, email, senha, tipo)
                VALUES (%s, %s, %s, 'cliente')
                """,
                (nome, email, senha_hash)
            )
            conexao.commit()

            flash("Cadastro realizado! Faça seu login.", "success")
            return redirect(url_for("auth.login"))

        finally:
            cursor.close()
            conexao.close()

    return render_template("cadastro.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")

        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        try:
            cursor.execute(
                "SELECT * FROM usuarios WHERE email = %s",
                (email,)
            )
            usuario = cursor.fetchone()

            if usuario and check_password_hash(usuario["senha"], senha):
                session.clear()
                session["usuario_id"] = usuario["id"]
                session["nome"] = usuario["nome"]
                session["tipo"] = usuario["tipo"]

                if usuario["tipo"] == "proprietario":
                    return redirect(url_for("auth.painel_proprietario"))

                return redirect(url_for("auth.area_cliente"))

            flash("E-mail ou senha incorretos.", "danger")

        finally:
            cursor.close()
            conexao.close()

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for("auth.login"))


@auth.route("/cliente")
def area_cliente():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "cliente":
        return redirect(url_for("auth.painel_proprietario"))

    return render_template("cliente.html")


def _obter_horarios_disponiveis(cursor, servico_id, data_agendamento):
    """Gera horários disponíveis conforme o expediente e os agendamentos."""

    # Verifica se o serviço existe e está ativo.
    cursor.execute(
        """
        SELECT duracao_minutos
        FROM servicos
        WHERE id = %s AND ativo = TRUE
        """,
        (servico_id,)
    )
    servico = cursor.fetchone()

    if not servico:
        return []

    duracao = int(servico["duracao_minutos"])

    # Busca os períodos de funcionamento ativos para o dia escolhido.
    cursor.execute(
        """
        SELECT hora_abertura, hora_fechamento
        FROM periodos_funcionamento
        WHERE dia_semana = %s AND ativo = TRUE
        ORDER BY hora_abertura
        """,
        (data_agendamento.weekday(),)
    )
    periodos = cursor.fetchall()

    if not periodos:
        return []

    # Busca os agendamentos do dia e a duração de cada serviço.
    cursor.execute(
        """
        SELECT
            TIME_FORMAT(a.horario, '%H:%i') AS horario,
            s.duracao_minutos,
            a.status
        FROM agendamentos AS a
        INNER JOIN servicos AS s ON s.id = a.servico_id
        WHERE a.`data` = %s
        """,
        (data_agendamento,)
    )

    ocupados = []

    for agendamento in cursor.fetchall():
        # Agendamentos cancelados não bloqueiam horários.
        if agendamento["status"] == "cancelado":
            continue

        inicio_ocupado = datetime.strptime(
            agendamento["horario"], "%H:%M"
        )

        fim_ocupado = inicio_ocupado + timedelta(
            minutes=int(agendamento["duracao_minutos"])
        )

        ocupados.append((inicio_ocupado, fim_ocupado))

    horarios = []
    agora = datetime.now()

    def converter_para_minutos(horario):
        """Converte o horário retornado pelo MySQL em minutos."""

        if isinstance(horario, timedelta):
            return int(horario.total_seconds() // 60)

        if hasattr(horario, "hour") and hasattr(horario, "minute"):
            return horario.hour * 60 + horario.minute

        partes = str(horario).split(":")
        return int(partes[0]) * 60 + int(partes[1])

    # Gera os horários possíveis em intervalos de 15 minutos.
    for periodo in periodos:
        inicio_periodo = converter_para_minutos(
            periodo["hora_abertura"]
        )
        fim_periodo = converter_para_minutos(
            periodo["hora_fechamento"]
        )

        minuto = inicio_periodo

        while minuto < fim_periodo:
            hora, minutos = divmod(minuto, 60)

            inicio = datetime.strptime(
                f"{hora:02d}:{minutos:02d}",
                "%H:%M"
            )

            fim = inicio + timedelta(minutes=duracao)

            # O serviço precisa terminar dentro do período ativo.
            fim_em_minutos = fim.hour * 60 + fim.minute

            if fim_em_minutos > fim_periodo:
                minuto += 15
                continue

            # Não permite horários que já passaram hoje.
            if (
                data_agendamento == date.today()
                and inicio.time() <= agora.time()
            ):
                minuto += 15
                continue

            # Verifica conflitos com agendamentos não cancelados.
            conflita = any(
                inicio < fim_ocupado
                and fim > inicio_ocupado
                for inicio_ocupado, fim_ocupado in ocupados
            )

            if not conflita:
                horarios.append(inicio.strftime("%H:%M"))

            minuto += 15

    return sorted(set(horarios))



@auth.route("/agendamento/horarios")
def horarios_disponiveis():
    """Endpoint consultado pela página para atualizar a lista de horários."""
    if "usuario_id" not in session or session.get("tipo") != "cliente":
        return jsonify({"horarios": [], "erro": "Faça login como cliente."}), 401

    servico_id = request.args.get("servico_id", "").strip()
    data_texto = request.args.get("data", "").strip()
    if not servico_id.isdigit() or not data_texto:
        return jsonify({"horarios": []})

    try:
        data_agendamento = date.fromisoformat(data_texto)
    except ValueError:
        return jsonify({"horarios": []})

    if data_agendamento < date.today():
        return jsonify({"horarios": []})

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)
    try:
        horarios = _obter_horarios_disponiveis(
            cursor, int(servico_id), data_agendamento
        )
        return jsonify({"horarios": horarios})
    finally:
        cursor.close()
        conexao.close()


@auth.route("/agendamento", methods=["GET", "POST"])
def novo_agendamento():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "cliente":
        return redirect(url_for("auth.painel_proprietario"))

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        if request.method == "POST":
            servico_id = request.form.get("servico_id", "").strip()
            data_texto = request.form.get("data", "").strip()
            horario = request.form.get("horario", "").strip()
            observacao = request.form.get("observacao", "").strip()

            if not servico_id.isdigit() or not data_texto or not horario:
                flash("Preencha o serviço, a data e o horário.", "danger")
                return redirect(url_for("auth.novo_agendamento"))

            try:
                data_agendamento = date.fromisoformat(data_texto)
                datetime.strptime(horario, "%H:%M")
            except ValueError:
                flash("Data ou horário inválido.", "danger")
                return redirect(url_for("auth.novo_agendamento"))

            if data_agendamento < date.today():
                flash("Não é possível agendar em uma data passada.", "danger")
                return redirect(url_for("auth.novo_agendamento"))

            horarios_validos = _obter_horarios_disponiveis(
                cursor, int(servico_id), data_agendamento
            )
            if horario not in horarios_validos:
                flash(
                    "Esse horário não está disponível ou o serviço não cabe no expediente. Escolha outro.",
                    "danger"
                )
                return redirect(url_for("auth.novo_agendamento"))

            try:
                cursor.execute(
                    """
                    INSERT INTO agendamentos
                        (cliente_id, servico_id, `data`, horario, observacao)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        session["usuario_id"], int(servico_id),
                        data_texto, horario, observacao or None
                    )
                )
                conexao.commit()
                flash("Agendamento solicitado com sucesso!", "success")
                return redirect(url_for("auth.meus_agendamentos"))

            except mysql.connector.IntegrityError as erro:
                conexao.rollback()
                if erro.errno == 1062:
                    flash("Esse horário já está ocupado. Escolha outro.", "danger")
                else:
                    flash("Não foi possível salvar o agendamento.", "danger")
                return redirect(url_for("auth.novo_agendamento"))

        cursor.execute(
            """
            SELECT id, nome, descricao, comprimento,
                   preco, duracao_minutos
            FROM servicos
            WHERE ativo = TRUE
            ORDER BY nome,
                FIELD(comprimento, 'Curto', 'Médio', 'Comprido')
            """
        )
        servicos = cursor.fetchall()
        return render_template("agendamento.html", servicos=servicos)

    finally:
        cursor.close()
        conexao.close()

@auth.route("/proprietario")
def painel_proprietario():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "proprietario":
        return redirect(url_for("auth.area_cliente"))

    return render_template("painel_proprietario.html")

@auth.route("/meus-agendamentos")
def meus_agendamentos():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "cliente":
        return redirect(url_for("auth.painel_proprietario"))

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                a.id,
                s.nome AS servico,
                a.data,
                TIME_FORMAT(a.horario, '%H:%i') AS horario,
                a.status,
                a.observacao
            FROM agendamentos a
            INNER JOIN servicos s
                ON a.servico_id = s.id
            WHERE a.cliente_id = %s
            ORDER BY a.data DESC, a.horario DESC
            """,
            (session["usuario_id"],)
        )

        agendamentos = cursor.fetchall()

    finally:
        cursor.close()
        conexao.close()

    return render_template(
        "meus_agendamentos.html",
        agendamentos=agendamentos
    )

@auth.route("/servicos", methods=["GET", "POST"])
def gerenciar_servicos():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "proprietario":
        return redirect(url_for("auth.area_cliente"))

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            descricao = request.form.get("descricao", "").strip()
            comprimento = request.form.get("comprimento", "").strip()
            preco_texto = request.form.get("preco", "").strip()
            duracao_texto = request.form.get("duracao", "").strip()

            comprimentos_validos = ("Curto", "Médio", "Comprido")

            if (
                not nome
                or not preco_texto
                or not duracao_texto
                or comprimento not in comprimentos_validos
            ):
                flash("Preencha corretamente todos os campos.", "danger")
                return redirect(url_for("auth.gerenciar_servicos"))

            try:
                preco = float(preco_texto.replace(",", "."))
                duracao = int(duracao_texto)
            except ValueError:
                flash("Preço ou duração inválidos.", "danger")
                return redirect(url_for("auth.gerenciar_servicos"))

            if preco <= 0 or duracao <= 0:
                flash("Preço e duração devem ser maiores que zero.", "danger")
                return redirect(url_for("auth.gerenciar_servicos"))

            cursor.execute(
                """
                SELECT id FROM servicos
                WHERE nome = %s AND comprimento = %s
                """,
                (nome, comprimento)
            )

            if cursor.fetchone():
                flash(
                    "Já existe esse serviço para esse comprimento.",
                    "danger"
                )
                return redirect(url_for("auth.gerenciar_servicos"))

            try:
                cursor.execute(
                    """
                    INSERT INTO servicos
                        (nome, descricao, comprimento, preco,
                         duracao_minutos, ativo)
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    """,
                    (nome, descricao, comprimento, preco, duracao)
                )
                conexao.commit()
                flash("Serviço cadastrado com sucesso!", "success")

            except mysql.connector.IntegrityError:
                conexao.rollback()
                flash(
                    "Já existe esse serviço para esse comprimento.",
                    "danger"
                )

            return redirect(url_for("auth.gerenciar_servicos"))

        cursor.execute(
            """
            SELECT id, nome, descricao, comprimento,
                   preco, duracao_minutos, ativo
            FROM servicos
            ORDER BY nome,
                FIELD(comprimento, 'Curto', 'Médio', 'Comprido')
            """
        )
        servicos = cursor.fetchall()
        return render_template("servicos.html", servicos=servicos)

    finally:
        cursor.close()
        conexao.close()

@auth.route("/servicos/editar/<int:servico_id>", methods=["GET", "POST"])
def editar_servico(servico_id):
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "proprietario":
        return redirect(url_for("auth.area_cliente"))

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM servicos WHERE id = %s",
            (servico_id,)
        )
        servico = cursor.fetchone()

        if not servico:
            flash("Serviço não encontrado.", "danger")
            return redirect(url_for("auth.gerenciar_servicos"))

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            descricao = request.form.get("descricao", "").strip()
            comprimento = request.form.get("comprimento", "").strip()
            preco_texto = request.form.get("preco", "").strip()
            duracao_texto = request.form.get("duracao", "").strip()

            comprimentos_validos = ("Curto", "Médio", "Comprido")

            if (
                not nome
                or not preco_texto
                or not duracao_texto
                or comprimento not in comprimentos_validos
            ):
                flash("Preencha corretamente todos os campos.", "danger")
                return redirect(
                    url_for("auth.editar_servico", servico_id=servico_id)
                )

            try:
                preco = float(preco_texto.replace(",", "."))
                duracao = int(duracao_texto)
            except ValueError:
                flash("Preço ou duração inválidos.", "danger")
                return redirect(
                    url_for("auth.editar_servico", servico_id=servico_id)
                )

            if preco <= 0 or duracao <= 0:
                flash("Preço e duração devem ser maiores que zero.", "danger")
                return redirect(
                    url_for("auth.editar_servico", servico_id=servico_id)
                )

            cursor.execute(
                """
                SELECT id FROM servicos
                WHERE nome = %s
                  AND comprimento = %s
                  AND id != %s
                """,
                (nome, comprimento, servico_id)
            )

            if cursor.fetchone():
                flash(
                    "Já existe esse serviço para esse comprimento.",
                    "danger"
                )
                return redirect(
                    url_for("auth.editar_servico", servico_id=servico_id)
                )

            try:
                cursor.execute(
                    """
                    UPDATE servicos
                    SET nome = %s,
                        descricao = %s,
                        comprimento = %s,
                        preco = %s,
                        duracao_minutos = %s
                    WHERE id = %s
                    """,
                    (
                        nome, descricao, comprimento,
                        preco, duracao, servico_id
                    )
                )
                conexao.commit()
                flash("Serviço atualizado com sucesso!", "success")
                return redirect(url_for("auth.gerenciar_servicos"))

            except mysql.connector.IntegrityError:
                conexao.rollback()
                flash(
                    "Já existe esse serviço para esse comprimento.",
                    "danger"
                )
                return redirect(
                    url_for("auth.editar_servico", servico_id=servico_id)
                )

        return render_template("editar_servico.html", servico=servico)

    finally:
        cursor.close()
        conexao.close()

@auth.route("/agendamentos", methods=["GET", "POST"])
def gerenciar_agendamentos():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "proprietario":
        return redirect(url_for("auth.area_cliente"))

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        if request.method == "POST":
            agendamento_id = request.form.get(
                "agendamento_id", ""
            ).strip()

            novo_status = request.form.get("status", "").strip()

            valor_texto = request.form.get(
                "valor_final", ""
            ).strip()

            observacao_atendimento = request.form.get(
                "observacao_atendimento", ""
            ).strip()

            status_validos = {
                "pendente",
                "confirmado",
                "cancelado",
                "concluido",
                "faltou",
            }

            if (
                not agendamento_id.isdigit()
                or novo_status not in status_validos
            ):
                flash(
                    "Dados inválidos para atualizar o agendamento.",
                    "danger",
                )
                return redirect(
                    url_for("auth.gerenciar_agendamentos")
                )

            agendamento_id = int(agendamento_id)

            # Confirma que o agendamento existe.
            cursor.execute(
                """
                SELECT id, status
                FROM agendamentos
                WHERE id = %s
                """,
                (agendamento_id,),
            )

            agendamento = cursor.fetchone()

            if not agendamento:
                flash("Agendamento não encontrado.", "danger")
                return redirect(
                    url_for("auth.gerenciar_agendamentos")
                )

            # O valor final é obrigatório para um atendimento concluído.
            valor_final = None

            if novo_status == "concluido":
                try:
                    valor_final = float(
                        valor_texto.replace(",", ".")
                    )
                except ValueError:
                    flash(
                        "Informe um valor final válido para o atendimento.",
                        "danger",
                    )
                    return redirect(
                        url_for("auth.gerenciar_agendamentos")
                    )

                if (
                    not valor_final >= 0
                    or valor_final == float("inf")
                    or valor_final != valor_final
                ):
                    flash(
                        "O valor final deve ser igual ou maior que zero.",
                        "danger",
                    )
                    return redirect(
                        url_for("auth.gerenciar_agendamentos")
                    )

            try:
                # Atualiza o status do agendamento.
                cursor.execute(
                    """
                    UPDATE agendamentos
                    SET status = %s
                    WHERE id = %s
                    """,
                    (novo_status, agendamento_id),
                )

                # Concluído significa que a cliente compareceu.
                # Faltou significa que a cliente não compareceu.
                if novo_status in ("concluido", "faltou"):
                    status_atendimento = (
                        "compareceu"
                        if novo_status == "concluido"
                        else "faltou"
                    )

                    cursor.execute(
                        """
                        INSERT INTO atendimentos
                            (
                                agendamento_id,
                                status,
                                valor_final,
                                observacao
                            )
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            status = VALUES(status),
                            valor_final = VALUES(valor_final),
                            observacao = VALUES(observacao)
                        """,
                        (
                            agendamento_id,
                            status_atendimento,
                            valor_final,
                            observacao_atendimento or None,
                        ),
                    )

                conexao.commit()

                flash(
                    "Agendamento atualizado com sucesso!",
                    "success",
                )

            except mysql.connector.Error:
                conexao.rollback()

                flash(
                    "Não foi possível atualizar o agendamento e "
                    "registrar o atendimento. Verifique os dados "
                    "e tente novamente.",
                    "danger",
                )

            return redirect(
                url_for("auth.gerenciar_agendamentos")
            )

        cursor.execute(
            """
            SELECT
                a.id,
                u.nome AS nome_cliente,
                s.nome AS nome_servico,
                s.comprimento,
                s.preco,
                s.duracao_minutos,
                a.data,
                TIME_FORMAT(a.horario, '%H:%i') AS horario,
                a.observacao,
                a.status,
                a.criado_em,
                at.valor_final,
                at.observacao AS observacao_atendimento,
                at.status AS status_atendimento
            FROM agendamentos AS a
            INNER JOIN usuarios AS u
                ON a.cliente_id = u.id
            INNER JOIN servicos AS s
                ON a.servico_id = s.id
            LEFT JOIN atendimentos AS at
                ON at.agendamento_id = a.id
            ORDER BY a.data DESC, a.horario DESC
            """
        )

        agendamentos = cursor.fetchall()

        return render_template(
            "agendamentos_proprietario.html",
            agendamentos=agendamentos,
        )

    finally:
        cursor.close()
        conexao.close()    
@auth.route("/configurar-horarios", methods=["GET", "POST"])
def configurar_horarios():
    if "usuario_id" not in session:
        return redirect(url_for("auth.login"))

    if session.get("tipo") != "proprietario":
        return redirect(url_for("auth.area_cliente"))

    conexao = conectar_banco()
    cursor = conexao.cursor(dictionary=True)

    try:
        dias_semana = {
            0: "Segunda-feira",
            1: "Terça-feira",
            2: "Quarta-feira",
            3: "Quinta-feira",
            4: "Sexta-feira",
            5: "Sábado",
            6: "Domingo",
        }

        if request.method == "POST":
            periodo_id = request.form.get("periodo_id", "").strip()
            hora_abertura = request.form.get("hora_abertura", "").strip()
            hora_fechamento = request.form.get("hora_fechamento", "").strip()
            ativo = request.form.get("ativo") == "on"

            if not periodo_id.isdigit():
                flash("Período inválido.", "danger")
                return redirect(url_for("auth.configurar_horarios"))

            try:
                abertura = datetime.strptime(
                    hora_abertura, "%H:%M"
                ).time()
                fechamento = datetime.strptime(
                    hora_fechamento, "%H:%M"
                ).time()
            except ValueError:
                flash("Informe horários válidos.", "danger")
                return redirect(url_for("auth.configurar_horarios"))

            if abertura >= fechamento:
                flash(
                    "O fechamento deve ser posterior à abertura.",
                    "danger",
                )
                return redirect(url_for("auth.configurar_horarios"))

            cursor.execute(
                """
                UPDATE periodos_funcionamento
                SET hora_abertura = %s,
                    hora_fechamento = %s,
                    ativo = %s
                WHERE id = %s
                """,
                (
                    abertura,
                    fechamento,
                    ativo,
                    int(periodo_id),
                ),
            )
            conexao.commit()

            flash("Horário atualizado com sucesso!", "success")
            return redirect(url_for("auth.configurar_horarios"))

        cursor.execute(
            """
            SELECT
                id,
                dia_semana,
                TIME_FORMAT(hora_abertura, '%H:%i') AS hora_abertura,
                TIME_FORMAT(hora_fechamento, '%H:%i') AS hora_fechamento,
                ativo
            FROM periodos_funcionamento
            ORDER BY dia_semana, hora_abertura
            """
        )

        periodos = cursor.fetchall()

        for periodo in periodos:
            periodo["nome_dia"] = dias_semana.get(
                periodo["dia_semana"],
                "Dia desconhecido",
            )

        return render_template(
            "configurar_horarios.html",
            periodos=periodos,
        )

    finally:
        cursor.close()
        conexao.close()