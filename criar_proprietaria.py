
from getpass import getpass
from database import conectar_banco
from werkzeug.security import generate_password_hash

nome = input("Nome da proprietária: ").strip()
email = input("E-mail da proprietária: ").strip().lower()
senha = getpass("Crie uma senha: ")
confirmacao = getpass("Confirme a senha: ")

if not nome or not email or not senha:
    print("Preencha todos os campos.")
elif len(senha) < 8:
    print("A senha deve ter pelo menos 8 caracteres.")
elif senha != confirmacao:
    print("As senhas não coincidem.")
else:
    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute(
            "SELECT id FROM usuarios WHERE email = %s",
            (email,)
        )

        if cursor.fetchone():
            print("Este e-mail já está cadastrado.")
        else:
            senha_hash = generate_password_hash(senha)

            cursor.execute(
                """
                INSERT INTO usuarios (nome, email, senha, tipo)
                VALUES (%s, %s, %s, 'proprietario')
                """,
                (nome, email, senha_hash)
            )
            conexao.commit()
            print("Conta da proprietária criada com sucesso!")

    finally:
        cursor.close()
        conexao.close()