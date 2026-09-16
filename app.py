from flask import Flask, render_template, request, Response
import pymysql
import os
import secrets

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'test'),
        cursorclass=pymysql.cursors.DictCursor
    )

def admin_credentials_valid(username, password):
    admin_user = os.getenv('ADMIN_USER')
    admin_password = os.getenv('ADMIN_PASSWORD')

    if not admin_user or not admin_password or username is None or password is None:
        return False

    return (
        secrets.compare_digest(username, admin_user)
        and secrets.compare_digest(password, admin_password)
    )

def admin_auth_required():
    return Response(
        'Autenticación requerida',
        401,
        {'WWW-Authenticate': 'Basic realm="CETI Admin"'}
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
    auth = request.authorization
    if not auth or not admin_credentials_valid(auth.username, auth.password):
        return admin_auth_required()

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, folio, transcript, certificate, document_type,
                       nombre, curso, level, hours, fecha, estatus
                FROM certificados
                ORDER BY id DESC
            """)
            certificados = cursor.fetchall()
    finally:
        connection.close()

    return render_template('admin.html', certificados=certificados)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
