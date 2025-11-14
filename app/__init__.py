
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Inicialização dos objetos
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# --------------------------------------------------------------------------
# FUNÇÕES DE FILTRO JINJA2
# --------------------------------------------------------------------------

def format_km(value):
    if isinstance(value, (int, float)):
        return f"{value:,.0f}".replace(',', '.')
    return value

def nl2br(value):
    from markupsafe import Markup
    return Markup(value.replace('\n', '<br>\n'))

# --------------------------------------------------------------------------
# FÁBRICA DE APLICAÇÃO
# --------------------------------------------------------------------------

def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))

    # --- CONFIGURAÇÃO DE AMBIENTE ---
    ambiente = os.environ.get('FLASK_ENV', 'producao')
    print(f"Ambiente: {ambiente}")

    # --- CONFIGURAÇÃO DO BANCO DE DADOS ---
    if ambiente == 'local':
        instance_path = os.path.join(os.path.dirname(basedir), 'instance')
        os.makedirs(instance_path, exist_ok=True)

        main_db_uri = f'sqlite:///{os.path.join(instance_path, "main.db")}'
        pneus_db_uri = f'sqlite:///{os.path.join(instance_path, "pneus.db")}'
        checklist_db_uri = f'sqlite:///{os.path.join(instance_path, "checklist.db")}'

        app.config['SQLALCHEMY_DATABASE_URI'] = main_db_uri
        app.config['SQLALCHEMY_BINDS'] = {
            'pneus': pneus_db_uri,
            'checklist': checklist_db_uri
        }
        
        print(f"-> Ambiente local detectado. Usando bases de dados SQLite.")
        print(f"   - Principal: {main_db_uri}")
        print(f"   - Pneus: {pneus_db_uri}")

    else:
        user = os.environ.get('CLOUD_DB_USER', 'Ornilio_neto')
        senha = os.environ.get('CLOUD_DB_PASSWORD', 'Senhadobanco2025#')
        host = os.environ.get('CLOUD_DB_HOST', '34.39.255.52')
        senha_encoded = quote_plus(senha)

        db_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/manutencao'
        pneus_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/pneus'
        checklist_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/checklist'

        print(f"-> Ambiente de produção detectado. Conectando ao MySQL.")
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        app.config['SQLALCHEMY_BINDS'] = {
            'pneus': pneus_uri,
            'checklist': checklist_uri
        }

    # --- OUTRAS CONFIGURAÇÕES ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-bem-dificil')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_POOL_SIZE'] = 10
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
    
    # Inicialização dos plugins com a app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    csrf.init_app(app)

    # --- CONFIGURAÇÃO DO USER LOADER ---
    # É importante definir o user_loader dentro da fábrica para evitar
    # problemas de importação circular e garantir que ele esteja associado
    # à instância correta da aplicação.
    from .models import Usuario
    @login_manager.user_loader
    def load_user(user_id):
        # A função deve retornar o objeto do usuário, ou None se não for encontrado
        return Usuario.query.get(int(user_id))

    # --- REGISTRO DOS FILTROS E GLOBAIS DO JINJA2 ---
    app.jinja_env.filters['format_km'] = format_km
    app.jinja_env.filters['nl2br'] = nl2br
    from .permissoes import tem_permissao 
    app.jinja_env.globals['tem_permissao'] = tem_permissao

    # --- REGISTRO DOS BLUEPRINTS ---
    from .routes import main as main_blueprint
    from .veiculos_routes import veiculos_bp
    from .motorista_routes import motoristas_bp
    from .mass_update_routes import mass_update_bp
    from .ss_routes import ss_bp
    # from .api_routes import api_bp # Comentado para remover o conflito
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(veiculos_bp, url_prefix='/veiculos')
    app.register_blueprint(motoristas_bp, url_prefix='/motoristas')
    app.register_blueprint(mass_update_bp, url_prefix='/mass-update')
    app.register_blueprint(ss_bp, url_prefix='/ss')
    # app.register_blueprint(api_bp, url_prefix='/api') # Comentado para remover o conflito

    return app
