
import os
from flask import Flask
from urllib.parse import quote_plus
from dotenv import load_dotenv

from .models import Usuario
from .extensions import db, migrate, login_manager, csrf
from .utils import format_km
from .checklist import checklist_bp
from .mass_update_routes import mass_update_bp

# Carrega variáveis do .env (se existir)
load_dotenv()

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def create_app():
    app = Flask(__name__)
    
    # --- INÍCIO DA ALTERAÇÃO ---
    
    # Caminho base do projeto
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua-chave-super-secreta')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-chave-secreta-padrao')

    # Verifica se está rodando local ou no cloud
    ambiente = os.environ.get('AMBIENTE', 'local')  # Alterado para 'local' como padrão para facilitar testes

    print(f"Ambiente: {ambiente}")

    if ambiente == 'local':
        # --- CONFIGURAÇÃO PARA SQLITE (TESTES LOCAIS) ---
        db_path = os.path.join(basedir, 'instance', 'local_test.db')
        # Garante que o diretório 'instance' exista
        os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
        
        db_uri = f'sqlite:///{db_path}'
        print(f"Database URI usada (SQLite): {db_uri}")
        
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        # Para SQLite, não precisamos de 'binds' complexos para testes simples
        app.config['SQLALCHEMY_BINDS'] = {}

    else:
        # --- CONFIGURAÇÃO PARA MYSQL (PRODUÇÃO/CLOUD) ---
        user = os.environ.get('CLOUD_DB_USER', 'Ornilio_neto')
        senha = os.environ.get('CLOUD_DB_PASSWORD', 'Senhadobanco2025#')
        host = os.environ.get('CLOUD_DB_HOST', '34.39.255.52')
        senha_encoded = quote_plus(senha)

        db_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/manutencao'
        pneus_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/pneus'
        checklist_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/checklist'

        print(f"Database URI usada (MySQL): {db_uri}")
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        app.config['SQLALCHEMY_BINDS'] = {
            'pneus': pneus_uri,
            'checklist': checklist_uri
        }

    # --- FIM DA ALTERAÇÃO ---
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_POOL_SIZE'] = 10
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    csrf.init_app(app)

    app.jinja_env.filters['format_km'] = format_km

    # CORREÇÃO AQUI
    from .permissoes import tem_permissao 
    app.jinja_env.globals['tem_permissao'] = tem_permissao

    # Registra os blueprints existentes
    from .routes import main
    app.register_blueprint(main)
    app.register_blueprint(checklist_bp, url_prefix='/checklist')

    from .veiculos_routes import veiculos_bp
    app.register_blueprint(veiculos_bp, url_prefix='/gerenciamento')

    # --- INÍCIO DA ADIÇÃO ---
    from .motorista_routes import motoristas_bp
    app.register_blueprint(motoristas_bp)
    app.register_blueprint(mass_update_bp)
    # --- FIM DA ADIção ---
    
    from .ss_routes import ss_bp
    app.register_blueprint(ss_bp)

    return app
