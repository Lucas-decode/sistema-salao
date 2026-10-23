
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
    """Gera inícios de 15 em 15 minutos dentro do expediente."""
    if data_agendamento.weekday() not in (1, 2, 3, 4, 5):
        return []  # Segunda (0) e domingo (6) não há atendimento.

    cursor.execute(
        "SELECT duracao_minutos FROM servicos WHERE id = %s AND ativo = TRUE",
        (servico_id,)
    )
    servico = cursor.fetchone()
    if not servico:
        return []

    duracao = int(servico["duracao_minutos"])
    cursor.execute(
        """
        SELECT TIME_FORMAT(a.horario, '%H:%i') AS horario,
               s.duracao_minutos, a.status
        FROM agendamentos a
        INNER JOIN servicos s ON s.id = a.servico_id
        WHERE a.`data` = %s
        """,
        (data_agendamento,)
    )
    ocupados = []
    for agendamento in cursor.fetchall():
        inicio_ocupado = datetime.strptime(agendamento["horario"], "%H:%M")
        fim_ocupado = inicio_ocupado + timedelta(
            minutes=int(agendamento["duracao_minutos"])
        )
        ocupados.append((inicio_ocupado, fim_ocupado, agendamento["status"]))

    horarios = []
    periodos = ((7 * 60, 11 * 60), (13 * 60, 18 * 60))
    agora = datetime.now()

    for inicio_periodo, fim_periodo in periodos:
        minuto = inicio_periodo
        while minuto < fim_periodo:
            hora, minutos = divmod(minuto, 60)
            inicio = datetime.strptime(f"{hora:02d}:{minutos:02d}", "%H:%M")
            fim = inicio + timedelta(minutes=duracao)

            # O atendimento precisa terminar dentro do mesmo período.
            if fim.hour * 60 + fim.minute > fim_periodo:
                minuto += 15
                continue

            # Não oferecer horários que já passaram no dia atual.
            if data_agendamento == date.today() and inicio.time() <= agora.time():
                minuto += 15
                continue

            conflita = any(
                (
                    inicio == inicio_ocupado
                    if status == "cancelado"
                    # O índice UNIQUE(data, horario) existente no MySQL
                    # ainda impede repetir exatamente o início cancelado.
                    else inicio < fim_ocupado and fim > inicio_ocupado
                )
                for inicio_ocupado, fim_ocupado, status in ocupados
            )
            if not conflita:
                horarios.append(inicio.strftime("%H:%M"))

            minuto += 15

    return horarios


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