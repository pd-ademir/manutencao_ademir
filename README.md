# 🛠️ Sistema de Gestão de Almoxarifado

Sistema web desenvolvido em Flask para gerenciamento de veículos, manutenções preventivas e unidades operacionais.

---

## ✨ Funcionalidades

- Cadastro de veículos e suas respectivas unidades
- Painel de manutenção com destaque visual para revisões vencidas
- Gerenciamento de usuários com controle de acesso (Master/Comum)
- Registro de logs de ações (para usuários Master)
- Interface responsiva com menu dinâmico e rodapé fixo
- Autenticação segura com redirecionamento automático para login

# 📦 Plano de manutenção - legenda

- parâmetro principal de busca -> revisão preventiva

1 - Barra amarela

A lógica se baseia principalmente nos quilômetros restantes (km_rest) para cada tipo de manutenção.

A barra de progresso fica amarela (warning) para sinalizar que a manutenção está se aproximando. O gatilho não é uma porcentagem específica, mas sim uma quilometragem limite.

Analisando o código, os limites são:

Preventiva: Fica amarela quando faltam 5.000 km ou menos para a revisão.
Intermediária: Fica amarela quando faltam 3.000 km ou menos.
Diferencial e Câmbio: Ficam amarelas quando faltam 5.000 km ou menos.
Antes disso, a barra fica verde (success), indicando que a manutenção está em dia e não há urgência.

2 - Barra 100% 

A porcentagem (prog) representa o quanto o veículo já rodou dentro de um ciclo de manutenção.

A barra atinge 100% no exato momento em que a quilometragem da revisão é alcançada (ou seja, quando os km_rest chegam a zero).
Nesse ponto, a lógica de "revisão vencida" é ativada.

3 - Revisão vencida
Quando uma revisão está vencida (os quilômetros restantes são zero ou negativos):

A barra de progresso fica Vermelha (danger): Este é o alerta visual mais forte, indicando que uma ação é necessária imediatamente.
A porcentagem é travada em 100%: Isso indica que o ciclo de manutenção foi totalmente consumido e ultrapassado.
O texto de KM restantes fica negativo: Você verá, por exemplo, (-150 km), mostrando exatamente o quanto a quilometragem da revisão foi excedida.

---

## 📦 Tecnologias Utilizadas

- Python + Flask
- SQLAlchemy (ORM)
- SQLite como banco local
- Jinja2 para templates HTML
- Flask-Login para autenticação
- Flask-Migrate para versionamento do banco de dados

---

## 🚀 Executando Localmente

```bash
# Clonar o repositório
git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Rodar aplicação
flask run


---

Você pode colar esse conteúdo num arquivo `README.md`, fazer um `git add README.md`, `git commit -m "Adiciona README"` e depois `git push`.

Se quiser, também posso gerar badges automáticos, um `requirements.txt` baseado no seu `venv` ou até preparar um deploy gratuito com o PythonAnywhere ou Render. Só dizer que o time da retaguarda está a postos 🧰😄


---

