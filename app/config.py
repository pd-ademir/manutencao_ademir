import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()  # Carrega variáveis do .env

class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'uma-chave-secreta-padrao')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-chave-secreta-padrao')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Pooling de conexões para desempenho
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_POOL_TIMEOUT = 30
    SQLALCHEMY_POOL_RECYCLE = 1800
    SQLALCHEMY_MAX_OVERFLOW = 20

class DevConfig(BaseConfig):
    """
    Configuração para ambiente de desenvolvimento local
    """
    user = os.environ.get('LOCAL_DB_USER', 'root')
    senha = os.environ.get('LOCAL_DB_PASSWORD', '')
    host = os.environ.get('LOCAL_DB_HOST', 'localhost')
    senha_encoded = quote_plus(senha)

    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{user}:{senha_encoded}@{host}/manutencao'
    SQLALCHEMY_BINDS = {
        'pneus': f'mysql+pymysql://{user}:{senha_encoded}@{host}/pneus',
        'checklist': f'mysql+pymysql://{user}:{senha_encoded}@{host}/checklist'
    }

class ProdConfig(BaseConfig):
    """
    Configuração para ambiente de produção na nuvem
    """
    user = os.environ.get('CLOUD_DB_USER', 'Ornilio_neto')
    senha = os.environ.get('CLOUD_DB_PASSWORD', '@Machado2025')
    host = os.environ.get('CLOUD_DB_HOST', '34.39.255.52')
    senha_encoded = quote_plus(senha)

    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{user}:{senha_encoded}@{host}/manutencao'
    SQLALCHEMY_BINDS = {
        'pneus': f'mysql+pymysql://{user}:{senha_encoded}@{host}/pneus',
        'checklist': f'mysql+pymysql://{user}:{senha_encoded}@{host}/checklist'
    }
