# #verificar as tabelas dos bancos
# import sqlite3
# import os

# # Caminho para a pasta onde estão os bancos
# pasta_bancos = os.path.join(os.getcwd(), "instance")

# # Extensões de arquivos de banco
# extensoes = ['.db', '.sqlite3']

# # Encontra todos os arquivos de banco na pasta
# arquivos_db = [f for f in os.listdir(pasta_bancos) if os.path.splitext(f)[1] in extensoes]

# if not arquivos_db:
#     print("❌ Nenhum arquivo de banco encontrado na pasta 'instance'.")
# else:
#     for arquivo in arquivos_db:
#         caminho = os.path.abspath(os.path.join(pasta_bancos, arquivo))
#         print(f"\n📦 Banco: {arquivo}")
#         print(f"📍 Caminho: {caminho}")

#         try:
#             conn = sqlite3.connect(caminho)
#             cursor = conn.cursor()
#             cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
#             tabelas = cursor.fetchall()

#             if tabelas:
#                 print("📂 Tabelas encontradas:")
#                 for tabela in tabelas:
#                     print(f" - {tabela[0]}")
#             else:
#                 print("⚠️ Nenhuma tabela encontrada.")
#             conn.close()
#         except Exception as e:
#             print(f"❌ Erro ao acessar {arquivo}: {e}")
# import sqlite3
# import os

# db_path = os.path.abspath("instance/db.sqlite3")
# print("📍 Atualizando banco:", db_path)

# conn = sqlite3.connect(db_path)
# cursor = conn.cursor()

# try:
#     cursor.execute("ALTER TABLE veiculo ADD COLUMN data_proxima_revisao_carreta DATE")
#     conn.commit()
#     print("✅ Campo 'data_proxima_revisao_carreta' adicionado com sucesso à tabela 'veiculo'.")
# except Exception as e:
#     print("❌ Erro ao adicionar campo:", e)

# conn.close()



# #roda banco na web
# # app.py
# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy

# app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
# db = SQLAlchemy(app)

# class Veiculo(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     placa = db.Column(db.String(10), unique=True, nullable=False)
#     data_proxima_revisao_carreta = db.Column(db.String(20))

# @app.route('/veiculo/<placa>')
# def mostrar_revisao(placa):
#     veiculo = Veiculo.query.filter_by(placa=placa.upper()).first()
#     if veiculo:
#         return f"Próxima revisão da carreta ({veiculo.placa}): {veiculo.data_proxima_revisao_carreta}"
#     return "Veículo não encontrado."

# if __name__ == '__main__':
#     app.run(debug=True)


# #cadastra usuario master:
# from app import create_app, db
# from app.models import Usuario
# from werkzeug.security import generate_password_hash

# app = create_app()

# def cadastrar_usuario(nome, usuario, senha, tipo='master'):
#     with app.app_context():
#         # Verifica se o nome de usuário já existe
#         if Usuario.query.filter_by(usuario=usuario).first():
#             print(f"❌ Usuário '{usuario}' já existe.")
#             return

#         # Cria o novo usuário
#         novo_usuario = Usuario(
#             nome=nome,
#             usuario=usuario,
#             senha_hash=generate_password_hash(senha),
#             tipo=tipo
#         )

#         db.session.add(novo_usuario)
#         db.session.commit()
#         print(f"✅ Usuário '{usuario}' cadastrado com sucesso!")

# # Exemplo de uso
# if __name__ == '__main__':
#     cadastrar_usuario('Admin', 'admin', '123456')


from app import db, create_app
from sqlalchemy import text

app = create_app()

def adicionar_campo_tipo():
    with app.app_context():
        try:
            db.session.execute(text("""
                ALTER TABLE manutencao
                ADD COLUMN tipo TEXT NOT NULL DEFAULT 'GERAL';
            """))
            db.session.commit()
            print("✅ Campo 'tipo' adicionado com sucesso à tabela 'manutencao'.")
        except Exception as e:
            print("❌ Erro ao adicionar o campo:", e)

if __name__ == "__main__":
    adicionar_campo_tipo()
