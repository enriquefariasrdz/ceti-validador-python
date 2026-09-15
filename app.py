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
            query = "SELECT * FROM certificados WHERE folio = %s"
            cursor.execute(query, (folio,))
            resultado = cursor.fetchone()
        connection.close()
    return render_template('index.html', resultado=resultado)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
