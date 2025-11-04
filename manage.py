import sys
import os
import click

# Adiciona o diretório raiz do projeto ao path do Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Usuario

# Define o ambiente como 'local' para operações de CLI
os.environ['AMBIENTE'] = 'local'

# Cria a instância do app
app = create_app()

# --- DEFINIÇÃO DOS COMANDOS ---

@app.cli.command("create-user")
@click.argument("usuario")
@click.argument("nome")
@click.argument("senha")
@click.argument("tipo")
@click.option("--unidade", default="Matriz", help="Unidade do usuário.")
@click.option("--filial", default="Matriz", help="Filial do usuário.")
def create_user(usuario, nome, senha, tipo, unidade, filial):
    """Cria um novo usuário no banco de dados com senha criptografada."""
    with app.app_context():
        if Usuario.query.filter_by(usuario=usuario).first():
            print(f"Erro: O nome de usuário '{usuario}' já existe.")
            return

        novo_usuario = Usuario(
            usuario=usuario,
            nome=nome,
            tipo=tipo.lower(), # Garante que o tipo seja salvo em minúsculas
            unidade=unidade,
            filial=filial
        )
        novo_usuario.set_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        print(f"Sucesso! Usuário '{usuario}' (tipo: {tipo.lower()}) criado com sucesso!")

# --- PONTO DE ENTRADA PARA EXECUTAR OS COMANDOS ---
if __name__ == '__main__':
    app.cli()
