# app/permissoes.py
from functools import wraps
from flask_login import current_user
from flask import flash, redirect, url_for, request

# Decorator para verificar o tipo de usuário (nível de acesso)
def requer_tipo(*tipos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Você precisa estar logado para acessar esta página.", "warning")
                return redirect(url_for('main.login'))

            user_tipo = current_user.tipo.strip().lower()

            # >>> ALTERAÇÃO 2: 'adm' sempre tem permissão (verificação robusta)
            if user_tipo == 'adm':
                return f(*args, **kwargs)
            
            # Lógica original para outros tipos de usuário
            if user_tipo not in tipos:
                flash("Você não tem permissão para acessar esta página.", "danger")
                if request.headers.get('HX-Request'):
                    return '<div class="alert alert-danger">Acesso negado.</div>', 403
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Função para verificar permissão diretamente no template Jinja2
def tem_permissao(tipos):
    """Verifica se o usuário atual tem um dos tipos de permissão. Tipos é uma string com nomes separados por vírgula."""
    if not current_user.is_authenticated:
        return False
        
    user_tipo = current_user.tipo.strip().lower()

    # >>> ALTERAÇÃO 2: 'adm' sempre tem permissão (verificação robusta)
    if user_tipo == 'adm':
        return True
        
    # Lógica original para outros tipos de usuário
    allowed_types = [t.strip().lower() for t in tipos.split(',')]
    return user_tipo in allowed_types


# --- FUNÇÃO CENTRAL DE FILTRAGEM (Já estava correta) ---
def filtrar_query_por_usuario(query, model):
    """
    Aplica filtros a uma query SQLAlchemy com base na filial e unidade do usuário logado.
    """
    if not current_user.is_authenticated:
        # Retorna uma query que não resulta em nada se o usuário não estiver logado
        return query.filter(db.false())

    if current_user.tipo.strip().lower() == 'adm':
        return query

    if hasattr(model, 'filial') and current_user.filial:
        query = query.filter(model.filial == current_user.filial)
    
    if hasattr(model, 'unidade') and current_user.unidade:
        query = query.filter(model.unidade == current_user.unidade)
        
    return query
