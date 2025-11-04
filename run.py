from app import create_app
from flask_login import LoginManager
from datetime import timedelta
from app.models import Usuario  # ajuste conforme o nome do seu modelo de usuário

# Cria a instância do app Flask
app = create_app()

# Configura o tempo de sessão
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Configura o LoginManager
login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'main.login'



# Define como carregar o usuário logado
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Define a rota padrão (opcional, para teste)
@app.route('/')
def index():
    return redirect(url_for('main.login'))

# Executa localmente com Flask (para testes)
if __name__ == "__main__":
#    app.run(debug=True)
     app.run(host='0.0.0.0', port=5000, debug=True)

