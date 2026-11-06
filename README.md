# Bela Essência — Sistema de Agendamento para Salão de Beleza

Sistema web desenvolvido como Projeto Integrador II da **Universidade Virtual do Estado de São Paulo (UNIVESP)**, com o objetivo de facilitar o gerenciamento de serviços e agendamentos de um salão de beleza.

O **Bela Essência** permite que clientes consultem os serviços disponíveis e realizem agendamentos on-line, enquanto o proprietário administra os serviços, horários de funcionamento e compromissos por meio de uma área administrativa exclusiva.

## Acesso ao sistema

**Versão publicada:** [https://sistema-salao-4h7x.onrender.com/](https://sistema-salao-4h7x.onrender.com/)

## Objetivo do projeto

O projeto surgiu da necessidade de organizar e simplificar o processo de agendamento de horários em um salão de beleza.

A proposta é substituir o controle manual de horários por uma aplicação web que centraliza as informações, facilita o acesso dos clientes aos serviços e auxilia o proprietário na administração da rotina do estabelecimento.

## Funcionalidades

### Área do cliente

- Cadastro de novos usuários e autenticação por login.
- Acesso à relação de serviços disponíveis.
- Consulta de preços e duração dos serviços.
- Seleção do comprimento do cabelo, quando aplicável.
- Consulta de datas e horários disponíveis.
- Realização de agendamentos on-line.
- Inclusão de observações no agendamento.
- Consulta dos próprios agendamentos.
- Acompanhamento do status dos agendamentos.

### Área administrativa do proprietário

- Acesso restrito por autenticação.
- Cadastro, edição e gerenciamento de serviços.
- Ativação e desativação de serviços.
- Configuração dos dias e períodos de funcionamento.
- Gerenciamento dos horários disponíveis para atendimento.
- Visualização dos agendamentos realizados.
- Atualização do status dos agendamentos.

### Validações e regras de negócio

O sistema possui validações para garantir maior consistência no processo de agendamento, incluindo:

- Impedimento de agendamentos em horários indisponíveis.
- Verificação de conflitos com horários já reservados.
- Respeito aos dias e períodos de funcionamento configurados.
- Consideração da duração do serviço na disponibilidade dos horários.
- Validação dos dados enviados pelos formulários.
- Restrições para evitar registros duplicados, conforme as regras definidas no banco de dados.

## Tecnologias utilizadas

| Tecnologia | Aplicação |
|---|---|
| Python | Linguagem de programação principal |
| Flask | Framework para desenvolvimento web |
| MySQL | Sistema de gerenciamento de banco de dados |
| HTML5 | Estrutura das páginas |
| CSS3 | Estilização e responsividade |
| JavaScript | Interatividade e funcionalidades no navegador |
| Jinja2 | Renderização dinâmica de páginas |
| Git e GitHub | Controle de versão e hospedagem do código |
| Render | Hospedagem da aplicação web |
| Aiven | Hospedagem do banco de dados MySQL |
| Pytest | Execução de testes automatizados |

## Estrutura do projeto

```text
sistema-salao/
│
├── app.py
├── database.py
├── criar_proprietaria.py
├── database.sql
├── requirements.txt
├── README.md
│
├── routes/
│   └── auth.py
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── images/
│
├── templates/
│
└── .gitignore
```

### Principais arquivos e diretórios

- `app.py`: inicialização e configuração da aplicação Flask.
- `database.py`: conexão com o banco de dados.
- `criar_proprietaria.py`: criação da conta de acesso administrativo.
- `database.sql`: estrutura do banco de dados.
- `requirements.txt`: dependências necessárias para executar o projeto.
- `routes/`: rotas e regras de funcionamento da aplicação.
- `static/`: arquivos estáticos, como CSS, imagens e JavaScript.
- `templates/`: páginas HTML renderizadas pelo Flask.
- `.gitignore`: arquivos e pastas que não devem ser enviados ao repositório.

## Banco de dados

O sistema utiliza MySQL para armazenar e organizar as informações.

Entre os dados gerenciados estão:

- Usuários e informações de acesso.
- Serviços oferecidos pelo salão.
- Horários e configurações de funcionamento.
- Agendamentos realizados pelos clientes.

O banco de dados utiliza relacionamentos e restrições para manter a integridade das informações e auxiliar na aplicação das regras de negócio.

## Como executar o projeto localmente

### 1. Pré-requisitos

- Python instalado.
- MySQL Server instalado e em execução.
- Git instalado.

### 2. Clonar o repositório

```bash
git clone https://github.com/Lucas-decode/sistema-salao.git
```

Entre na pasta do projeto:

```bash
cd sistema-salao
```

### 3. Criar o ambiente virtual

```bash
python -m venv .venv
```

Ative o ambiente virtual no Windows:

```powershell
.venv\Scripts\activate
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Configurar o banco de dados

- Inicie o MySQL Server ou configure o acesso ao banco MySQL hospedado na Aiven.
- Crie o banco de dados e importe a estrutura disponível no arquivo `database.sql`.
- Crie um arquivo chamado `.env` na raiz do projeto e configure as seguintes variáveis:

```env
DB_HOST=seu_host
DB_PORT=3306
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_NAME=seu_banco
DB_SSL_CA=caminho_do_certificado
```

Preencha os valores de acordo com sua configuração de banco de dados. O certificado SSL deve apontar para o arquivo correspondente quando exigido pela conexão.

**Importante:** nunca compartilhe credenciais ou certificados privados. O arquivo `.env` não deve ser enviado ao GitHub.

### 6. Criar o acesso do proprietário

Execute o script responsável pela criação da conta administrativa:

```bash
python criar_proprietaria.py
```

### 7. Executar a aplicação

```bash
python app.py
```

Após iniciar o servidor, acesse:

[http://127.0.0.1:5000](http://127.0.0.1:5000)

## Testes

O projeto utiliza **Pytest** para a execução de testes automatizados, auxiliando na verificação do funcionamento das funcionalidades e das regras implementadas.

**Última execução de validação: 19 testes aprovados, sem falhas.**

Para executar os testes, utilize:

```bash
python -m pytest
```

## Hospedagem

A aplicação está publicada na plataforma Render, com o banco de dados MySQL hospedado na Aiven.

**Link para acessar o sistema:**

https://sistema-salao-4h7x.onrender.com/

---

**UNIVESP — Universidade Virtual do Estado de São Paulo**

Projeto Integrador II — Engenharia da Computação

**Bela Essência | Sistema de Agendamento para Salão de Beleza**