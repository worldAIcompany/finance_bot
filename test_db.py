import psycopg2

try:
    conn = psycopg2.connect(
        database="finance_bot",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5432"
    )
    conn.set_client_encoding('UTF8')
    cur = conn.cursor()
    cur.execute('SHOW client_encoding')
    encoding = cur.fetchone()[0]
    print(f'Текущая кодировка: {encoding}')
    print('Подключение успешно!')
    cur.close()
    conn.close()
except Exception as e:
    print(f'Ошибка подключения: {e}') 