import pymysql

host = '136.113.79.172'
user = 'ornilio'
password = '@Machado2025'
database = 'manutencao'

try:
    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=3306,
        connect_timeout=5
    )
    print("Conexão com MySQL bem sucedida!")
    connection.close()
except Exception as e:
    print("Erro ao conectar:", e)
