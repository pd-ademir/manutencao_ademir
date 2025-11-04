from app import create_app
from app.extensions import db
from app.models import Usuario

app = create_app()

with app.app_context():
    # ⚠️ Apaga todos os usuários existentes
    Usuario.query.delete()

    # 🔐 Cria três usuários com senha protegida
    master = Usuario(usuario="admin", nome="Usuário Master", tipo="master")
    master.set_senha("123456")

    comum = Usuario(usuario="comum", nome="Usuário Comum", tipo="comum")
    comum.set_senha("123")

    teste = Usuario(usuario="teste", nome="Usuário de Teste", tipo="teste")
    teste.set_senha("teste")

    db.session.add_all([master, comum, teste])
    db.session.commit()

    print("✅ Usuários criados com sucesso!")
