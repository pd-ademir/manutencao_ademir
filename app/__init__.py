import os
import logging
from flask import Flask
from urllib.parse import quote_plus
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

from .models import Usuario
from .extensions import db, migrate, login_manager, csrf
from .utils import format_km
from .checklist import checklist_bp
from .mass_update_routes import mass_update_bp

# Carrega variáveis do .env
load_dotenv()

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

def create_app():
    app = Flask(__name__)

    # Caminho base do projeto
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    # Configurações principais
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'sua-chave-super-secreta')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-chave-secreta-padrao')

    ambiente = os.environ.get('AMBIENTE', 'local')

    # Configuração de banco de dados
    if ambiente == 'local':
        db_path = os.path.join(basedir, 'instance', 'local_test.db')
        os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)
        db_uri = f'sqlite:///{db_path}'
        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        app.config['SQLALCHEMY_BINDS'] = {}
    else:
        user = os.environ.get('CLOUD_DB_USER', 'Ornilio_neto')
        senha = os.environ.get('CLOUD_DB_PASSWORD', 'Senhadobanco2025#')
        host = os.environ.get('CLOUD_DB_HOST', '34.39.255.52')
        senha_encoded = quote_plus(senha)

        db_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/manutencao'
        pneus_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/pneus'
        checklist_uri = f'mysql+pymysql://{user}:{senha_encoded}@{host}/checklist'

        app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
        app.config['SQLALCHEMY_BINDS'] = {
            'pneus': pneus_uri,
            'checklist': checklist_uri
        }

    # Configurações adicionais do SQLAlchemy
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_POOL_SIZE'] = 10
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 30
    app.config['SQLALCHEMY_POOL_RECYCLE'] = 1800
    app.config['SQLALCHEMY_MAX_OVERFLOW'] = 20

    # Inicializa extensões
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    csrf.init_app(app)

    # Filtros e variáveis globais do Jinja
    app.jinja_env.filters['format_km'] = format_km
    from .permissoes import tem_permissao
    app.jinja_env.globals['tem_permissao'] = tem_permissao

    # Registro de blueprints
    from .routes import main
    app.register_blueprint(main)
    app.register_blueprint(checklist_bp, url_prefix='/checklist')
    from .veiculos_routes import veiculos_bp
    app.register_blueprint(veiculos_bp, url_prefix='/gerenciamento')
    from .motorista_routes import motoristas_bp
    app.register_blueprint(motoristas_bp)
    app.register_blueprint(mass_update_bp)
    from .ss_routes import ss_bp
    app.register_blueprint(ss_bp)

    # Configuração de logging
    log_dir = os.path.join(basedir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10240,
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Aplicação Flask iniciada')

    return app
