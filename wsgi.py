# wsgi.py
import sys
import os

# Adiciona o diretório raiz do projeto ao path do Python para resolver import errors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

# A função create_app() é chamada a partir do __init__.py do pacote 'app'
app = create_app()
