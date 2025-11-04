from sqlalchemy import create_engine, text

# Aponta para seu banco real
engine = create_engine("sqlite:///instance/checklist.db")

with engine.connect() as conn:
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
    tabelas = [row[0] for row in result]
    print("📦 Tabelas encontradas:", tabelas)
