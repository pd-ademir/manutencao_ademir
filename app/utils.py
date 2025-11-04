from .models import LogSistema, get_ip_real
from .extensions import db

def format_km(value):
    if value is None:
        return "-"
    try:
        return f"{int(value):,}".replace(",", ".") + " km"
    except (ValueError, TypeError):
        return str(value)
    

def detectar_alteracoes(obj, novos_dados, campos_interessantes=None):
    """
    Compara os valores atuais de um objeto com os novos dados.
    Retorna uma lista de strings descrevendo as alterações.
    """
    alteracoes = []

    for campo, novo_valor in novos_dados.items():
        if campos_interessantes and campo not in campos_interessantes:
            continue

        valor_atual = getattr(obj, campo, None)

        # Normaliza strings
        if isinstance(valor_atual, str) and isinstance(novo_valor, str):
            valor_atual = valor_atual.strip().upper()
            novo_valor = novo_valor.strip().upper()

        # Converte strings numéricas para int, se possível
        if isinstance(valor_atual, int) and isinstance(novo_valor, str) and novo_valor.isdigit():
            novo_valor = int(novo_valor)

        if valor_atual != novo_valor:
            alteracoes.append(f"{campo.replace('_', ' ').capitalize()}: '{valor_atual}' → '{novo_valor}'")

    return alteracoes

def registrar_log_sem_alteracoes(usuario, acao):
    """Registra uma ação no log do sistema sem detalhar alterações de campo."""
    log = LogSistema(
        usuario_id=usuario.id,
        usuario_nome=usuario.nome,
        acao=acao,
        ip_usuario=get_ip_real() # Supondo que você tenha essa função
    )
    db.session.add(log)
    # O commit é feito na rota principal após todas as operações
