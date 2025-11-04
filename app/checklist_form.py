from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField
from wtforms.validators import DataRequired, Optional

class ChecklistForm(FlaskForm):
    mes = StringField("Mês", validators=[DataRequired()])
    data_registro = DateField("Data do Registro", validators=[DataRequired()], format="%Y-%m-%d")
    placa = StringField("Placa", validators=[DataRequired()])
    item = StringField("Item", validators=[DataRequired()])
    fonte = SelectField("Fonte", choices=[
        ("Checklist", "Checklist"),
        ("Visual", "Visual"),
        ("Motorista", "Motorista"),
        ("Outro", "Outro")
    ], validators=[DataRequired()])
    tipo_manutencao = SelectField("Tipo de Manutenção", choices=[
        ("Corretiva", "Corretiva"),
        ("Preventiva", "Preventiva")
    ], validators=[DataRequired()])
    status = SelectField("Status", choices=[
        ("Pendente", "Pendente"),
        ("Em andamento", "Em andamento"),
        ("Concluído", "Concluído")
    ], validators=[DataRequired()])
    ordem_servico = StringField("Ordem de Serviço", validators=[Optional()])
    conclusao = TextAreaField("Conclusão", validators=[Optional()])
    data_servico = DateField("Data do Serviço", validators=[Optional()], format="%Y-%m-%d")
