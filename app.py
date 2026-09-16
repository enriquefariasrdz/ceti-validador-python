from flask import Flask, render_template, request
import pymysql
import os

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'test'),
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None
    if request.method == 'POST':
        folio = request.form.get('folio')
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = """
                SELECT *
                FROM certificados
                WHERE folio = %s
                   OR transcript = %s
                   OR certificate = %s
                LIMIT 1
            """
            cursor.execute(query, (folio, folio, folio))
            resultado = cursor.fetchone()
        connection.close()
    return render_template('index.html', resultado=resultado)

@app.route('/admin', methods=['GET'])
def admin():
    return 'CETI Admin - acceso administrativo en preparación', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
