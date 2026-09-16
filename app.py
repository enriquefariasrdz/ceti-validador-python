from flask import Flask, render_template, request, Response, redirect, url_for
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

def clean_optional(value):
    value = (value or '').strip()
    return value or None

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

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    auth = request.authorization
    if not auth or not admin_credentials_valid(auth.username, auth.password):
        return admin_auth_required()

    error = None

    if request.method == 'POST':
        folio = (request.form.get('folio') or '').strip()
        transcript = clean_optional(request.form.get('transcript'))
        certificate = clean_optional(request.form.get('certificate'))
        document_type = clean_optional(request.form.get('document_type'))
        nombre = (request.form.get('nombre') or '').strip()
        curso = (request.form.get('curso') or '').strip()
        level = clean_optional(request.form.get('level'))
        hours_raw = (request.form.get('hours') or '').strip()
        fecha = (request.form.get('fecha') or '').strip()
        estatus = (request.form.get('estatus') or 'Valido').strip()

        if not folio or not nombre or not curso or not fecha:
            error = 'Folio, nombre, programa y fecha son obligatorios.'
        elif estatus not in ('Valido', 'Revocado', 'Expirado'):
            error = 'El estado seleccionado no es válido.'
        else:
            try:
                hours = int(hours_raw) if hours_raw else None
                if hours is not None and hours < 0:
                    raise ValueError
            except ValueError:
                error = 'Horas debe ser un número entero igual o mayor que cero.'

        if error is None:
            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    identifiers = [value for value in (folio, transcript, certificate) if value]
                    placeholders = ', '.join(['%s'] * len(identifiers))
                    cursor.execute(
                        f"""
                        SELECT id, folio, transcript, certificate
                        FROM certificados
                        WHERE folio IN ({placeholders})
                           OR transcript IN ({placeholders})
                           OR certificate IN ({placeholders})
                        LIMIT 1
                        """,
                        tuple(identifiers * 3)
                    )
                    duplicate = cursor.fetchone()

                    if duplicate:
                        error = 'Ya existe un certificado que utiliza uno de esos identificadores.'
                    else:
                        cursor.execute("""
                            INSERT INTO certificados
                            (folio, transcript, certificate, document_type, nombre,
                             curso, level, hours, fecha, estatus)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            folio, transcript, certificate, document_type, nombre,
                            curso, level, hours, fecha, estatus
                        ))
                        connection.commit()
                        return redirect(url_for('admin', created='1'))
            except pymysql.MySQLError:
                connection.rollback()
                error = 'No fue posible registrar el certificado. Verifica los datos e inténtalo nuevamente.'
            finally:
                connection.close()

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

    created = request.args.get('created') == '1'
    return render_template('admin.html', certificados=certificados, error=error, created=created)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
