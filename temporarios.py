
import os
from sqlalchemy import text
from app import create_app, db

# Ignora o erro se a app já estiver criada em outro lugar
try:
    app = create_app()
except NameError:
    from app import app

# SQL para criar a tabela. "IF NOT EXISTS" garante que ele não dará erro se a tabela já existir.
create_table_sql = text("""
CREATE TABLE IF NOT EXISTS historico_bloqueio (
    id INTEGER NOT NULL,
    veiculo_id INTEGER NOT NULL,
    tipo_manutencao VARCHAR(100) NOT NULL,
    data_bloqueio DATETIME NOT NULL,
    km_bloqueio INTEGER NOT NULL,
    liberado BOOLEAN,
    data_liberacao DATETIME,
    manutencao_id INTEGER,
    PRIMARY KEY (id),
    FOREIGN KEY(veiculo_id) REFERENCES veiculo (id),
    FOREIGN KEY(manutencao_id) REFERENCES manutencao (id)
);
""")

# Usa o contexto da aplicação para garantir que estamos conectados ao banco de dados correto
with app.app_context():
    try:
        print("Conectando ao banco de dados definido na sua aplicação...")
        # Pega uma conexão do engine do banco de dados
        with db.engine.connect() as connection:
            print("Executando comando para criar a tabela 'historico_bloqueio'...")
            connection.execute(create_table_sql)
            print("\n[SUCESSO] O comando foi executado!")
            print("A tabela 'historico_bloqueio' agora deve existir no seu banco de dados.")
            print("Use a extensão SQLite no VS Code para confirmar.")

    except Exception as e:
        print("\n[ERRO] Ocorreu um erro ao tentar executar o comando:")
        print(e)
