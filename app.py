
from flask import Flask, render_template
from database import conectar_banco
from routes.auth import auth
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

# Registra as rotas de autenticação
app.register_blueprint(auth)


@app.route("/")
def inicio():
 return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)