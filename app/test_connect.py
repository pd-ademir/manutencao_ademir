import sqlite3
import csv
import os

db_path = 'instance/checklist.sqlite3'
output_folder = 'export_checklist'

os.makedirs(output_folder, exist_ok=True)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Pega o nome de todas as tabelas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

for table_name in tables:
    table = table_name[0]
    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()

    # Pega os nomes das colunas
    column_names = [description[0] for description in cursor.description]

    with open(os.path.join(output_folder, f"{table}.csv"), 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(column_names)
        writer.writerows(rows)

print("Exportação concluída!")
conn.close()
