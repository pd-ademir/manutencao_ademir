
# app/models.py
import re
from .extensions import db
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request
from zoneinfo import ZoneInfo
from sqlalchemy import text

# ============================================================================
# FUNÇÃO AUXILIAR PARA CPF
# ============================================================================

def clean_cpf(cpf):
    """Remove a pontuação de uma string de CPF."""
    return re.sub(r'[\.\-]', '', cpf)

# ============================================================================
# 1. TABELAS DE ATIVOS FÍSICOS E PESSOAS (O CORAÇÃO DOS DADOS)
# ============================================================================

class Placa(db.Model):
    __tablename__ = 'placas'
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), nullable=False, unique=True)
    tipo = db.Column(db.String(20))  # BITRUCK, CAVALO, CARRETA
    unidade = db.Column(db.String(50), nullable=False)
    filial = db.Column(db.String(50))
    modelo = db.Column(db.String(50), nullable=True)
    fabricante = db.Column(db.String(50), nullable=True)
    ano = db.Column(db.String(4), nullable=True)
    km_atual = db.Column(db.Integer, default=0)
    data_ultima_atualizacao_km = db.Column(db.DateTime)
    data_calibragem = db.Column(db.Date)
    data_proxima_calibragem = db.Column(db.Date, nullable=True)
    data_proxima_revisao_carreta = db.Column(db.Date)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    em_manutencao = db.Column(db.Boolean, default=False)
    km_troca_preventiva = db.Column(db.Integer, nullable=True)
    km_ultima_revisao_preventiva = db.Column(db.Integer)
    data_ultima_revisao_preventiva = db.Column(db.Date)
    km_troca_intermediaria = db.Column(db.Integer, nullable=True)
    km_ultima_revisao_intermediaria = db.Column(db.Integer)
    data_ultima_revisao_intermediaria = db.Column(db.Date)
    intervalo_oleo_diferencial = db.Column(db.Integer)
    troca_oleo_diferencial = db.Column(db.Integer)
    data_troca_oleo_diferencial = db.Column(db.Date)
    intervalo_oleo_cambio = db.Column(db.Integer)
    troca_oleo_cambio = db.Column(db.Integer)
    data_troca_oleo_cambio = db.Column(db.Date)
    manutencoes = db.relationship('Manutencao', backref='placa_ref', lazy='dynamic')
    historico_bloqueios = db.relationship('HistoricoBloqueio', backref='placa_ref', lazy='dynamic')
    
    @property
    def km_para_preventiva(self):
        if self.km_ultima_revisao_preventiva is not None and self.km_troca_preventiva is not None and self.km_atual is not None:
            return (self.km_ultima_revisao_preventiva + self.km_troca_preventiva) - self.km_atual
        return None

    @property
    def km_para_intermediaria(self):
        if self.km_ultima_revisao_intermediaria is not None and self.km_troca_intermediaria is not None and self.km_atual is not None:
            return (self.km_ultima_revisao_intermediaria + self.km_troca_intermediaria) - self.km_atual
        return None

    @property
    def km_para_diferencial(self):
        if self.troca_oleo_diferencial is not None and self.intervalo_oleo_diferencial is not None and self.km_atual is not None:
            return (self.troca_oleo_diferencial + self.intervalo_oleo_diferencial) - self.km_atual
        return None

    @property
    def km_para_cambio(self):
        if self.troca_oleo_cambio is not None and self.intervalo_oleo_cambio is not None and self.km_atual is not None:
            return (self.troca_oleo_cambio + self.intervalo_oleo_cambio) - self.km_atual
        return None

    def __repr__(self):
        return f'<Placa {self.placa}>'

class Motorista(db.Model):
    __tablename__ = 'motoristas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    _cpf = db.Column("cpf", db.String(14), unique=True, nullable=False)
    cnh = db.Column(db.String(20))
    rg = db.Column(db.String(20))
    ativo = db.Column(db.Boolean, nullable=False, server_default=text('1'))
    unidade = db.Column(db.String(50))
    filial = db.Column(db.String(50))
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculos.id'))
    veiculo = db.relationship('Veiculo', back_populates='motorista')

    @property
    def cpf(self):
        return self._cpf

    @cpf.setter
    def cpf(self, value):
        self._cpf = clean_cpf(value)

    def __repr__(self):
        return f'<Motorista {self.nome}>'

# ============================================================================
# 2. TABELA DE AGRUPAMENTO LÓGICO (O CONJUNTO)
# ============================================================================

class Veiculo(db.Model):
    __tablename__ = 'veiculos'
    id = db.Column(db.Integer, primary_key=True)
    nome_conjunto = db.Column(db.String(100), unique=True, nullable=False)
    unidade = db.Column(db.String(100))
    filial = db.Column(db.String(100))
    obs = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    placa_cavalo_id = db.Column(db.Integer, db.ForeignKey('placas.id'))
    placa_carreta1_id = db.Column(db.Integer, db.ForeignKey('placas.id'))
    placa_carreta2_id = db.Column(db.Integer, db.ForeignKey('placas.id'))
    placa_cavalo = db.relationship('Placa', foreign_keys=[placa_cavalo_id])
    placa_carreta1 = db.relationship('Placa', foreign_keys=[placa_carreta1_id])
    placa_carreta2 = db.relationship('Placa', foreign_keys=[placa_carreta2_id])
    motorista = db.relationship('Motorista', back_populates='veiculo', uselist=False)
    
    indisponibilidades = db.relationship('VeiculoIndisponibilidade', backref='veiculo', lazy='dynamic', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Veiculo {self.nome_conjunto}>'

# ============================================================================
# 3. TABELAS DE HISTÓRICO E SUPORTE
# ============================================================================

class VeiculoIndisponibilidade(db.Model):
    __tablename__ = 'veiculos_indisponibilidade'
    id = db.Column(db.Integer, primary_key=True)
    veiculo_id = db.Column(db.Integer, db.ForeignKey('veiculos.id'), nullable=False)
    data_indisponibilidade = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    motivo = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    usuario = db.relationship('Usuario')

    def __repr__(self):
        return f'<Indisponibilidade Veiculo ID {self.veiculo_id}>'

class Manutencao(db.Model):
    __tablename__ = 'manutencoes'
    id = db.Column(db.Integer, primary_key=True)
    placa_id = db.Column(db.Integer, db.ForeignKey('placas.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    km_realizado = db.Column(db.Integer)
    data_troca = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    
    def __repr__(self):
        return f'<Manutencao ID {self.id}>'

class HistoricoBloqueio(db.Model):
    __tablename__ = 'historico_bloqueios'
    id = db.Column(db.Integer, primary_key=True)
    placa_id = db.Column(db.Integer, db.ForeignKey('placas.id'), nullable=False)
    tipo_manutencao = db.Column(db.String(100), nullable=False)
    data_bloqueio = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    km_bloqueio = db.Column(db.Integer, nullable=False)
    liberado = db.Column(db.Boolean, default=False)
    data_liberacao = db.Column(db.DateTime, nullable=True)
    manutencao_id = db.Column(db.Integer, db.ForeignKey('manutencoes.id'), nullable=True)

    def __repr__(self):
        status = "Liberado" if self.liberado else "Pendente"
        return f'<Bloqueio ID {self.id} ({status})>'

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(50), nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    unidade = db.Column(db.String(50), nullable=True)
    filial = db.Column(db.String(50), nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class LogSistema(db.Model):
    __tablename__ = 'logs_sistema'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    acao = db.Column(db.String(200), nullable=False)
    ip = db.Column(db.String(50), nullable=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref='logs')


class SolicitacaoServico(db.Model):
    __tablename__ = 'solicitacoes_servico'
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_previsao_parada = db.Column(db.Date)
    status = db.Column(db.String(50), default='Em Análise')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    usuario = db.relationship('Usuario')

    # --- CAMPOS PARA INTEGRAÇÃO ---
    id_externo = db.Column(db.String(100), nullable=True, index=True)
    observacao_externa = db.Column(db.Text, nullable=True)
    data_resposta_externa = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<SolicitacaoServico {self.id} - {self.placa}>'



# ============================================================================
# 4. TABELAS DO BANCO DE DADOS DE PNEUS
# ============================================================================

class PneuAplicado(db.Model):
    __bind_key__ = 'pneus'
    __tablename__ = 'pneus_aplicados'
    id = db.Column(db.Integer, primary_key=True)
    placa = db.Column(db.String(10), nullable=False)
    referencia = db.Column(db.String(50), nullable=False)
    dot = db.Column(db.String(10), nullable=False)
    numero_fogo = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    data_aplicacao = db.Column(db.Date, nullable=False)
    unidade = db.Column(db.String(30), nullable=False)
    observacoes = db.Column(db.Text, nullable=True)
    extra = db.Column(db.Text, nullable=True)

class EstoquePneu(db.Model):
    __bind_key__ = 'pneus'
    __tablename__ = 'estoque_pneus'
    id = db.Column(db.Integer, primary_key=True)
    numero_fogo = db.Column(db.String(20), unique=True, nullable=False)
    vida = db.Column(db.Integer, nullable=False)
    modelo = db.Column(db.String(50), nullable=False)
    desenho = db.Column(db.String(20), nullable=False)
    dot = db.Column(db.String(10), nullable=True)
    data_entrada = db.Column(db.Date, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='DISPONIVEL')

# ============================================================================
# 5. CONFIGURAÇÕES E FUNÇÕES AUXILIARES
# ============================================================================

# Mapeia a unidade a uma lista de números de WhatsApp para receber alertas.
# Preencha com os números corretos. Ex: {'NOME_UNIDADE': ['+5585999999999']}
whatsapp_numeros = {
    'BAGAM': [],
    'BACRO': [],
    'SPOT RN': [],
    'SPOT PE': [],
    'SMART': [],
}

def get_ip_real():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or "IP desconhecido"

def registrar_log(usuario, acao):
    print("Registrando log:", acao)
    ip = get_ip_real()
    data = datetime.now(ZoneInfo("America/Fortaleza"))
    log = LogSistema(
        usuario_id=usuario.id,
        acao=acao,
        ip=ip,
        data=data
    )
    db.session.add(log)
    db.session.commit()
