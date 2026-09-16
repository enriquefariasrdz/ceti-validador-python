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
    return secrets.compare_digest(username, admin_user) and secrets.compare_digest(password, admin_password)

def admin_auth_required():
    return Response('Autenticación requerida', 401, {'WWW-Authenticate': 'Basic realm="CETI Admin"'})

def require_admin():
    auth = request.authorization
    if not auth or not admin_credentials_valid(auth.username, auth.password):
        return admin_auth_required()
    return None

def clean_optional(value):
    value = (value or '').strip()
    return value or None

def parse_certificate_form():
    data = {
        'folio': (request.form.get('folio') or '').strip(),
        'transcript': clean_optional(request.form.get('transcript')),
        'certificate': clean_optional(request.form.get('certificate')),
        'document_type': clean_optional(request.form.get('document_type')),
        'nombre': (request.form.get('nombre') or '').strip(),
        'curso': (request.form.get('curso') or '').strip(),
        'level': clean_optional(request.form.get('level')),
        'fecha': (request.form.get('fecha') or '').strip(),
        'estatus': (request.form.get('estatus') or 'Valido').strip()
    }
    hours_raw = (request.form.get('hours') or '').strip()
    if not data['folio'] or not data['nombre'] or not data['curso'] or not data['fecha']:
        return None, 'Folio, nombre, programa y fecha son obligatorios.'
    if data['estatus'] not in ('Valido', 'Revocado', 'Expirado'):
        return None, 'El estado seleccionado no es válido.'
    try:
        data['hours'] = int(hours_raw) if hours_raw else None
        if data['hours'] is not None and data['hours'] < 0:
            raise ValueError
    except ValueError:
        return None, 'Horas debe ser un número entero igual o mayor que cero.'
    return data, None

def find_identifier_duplicate(cursor, data, exclude_id=None):
    identifiers = [value for value in (data['folio'], data['transcript'], data['certificate']) if value]
    placeholders = ', '.join(['%s'] * len(identifiers))
    sql = f"""
        SELECT id, folio, transcript, certificate
        FROM certificados
        WHERE (folio IN ({placeholders})
           OR transcript IN ({placeholders})
           OR certificate IN ({placeholders}))
    """
    params = identifiers * 3
    if exclude_id is not None:
        sql += ' AND id <> %s'
        params.append(exclude_id)
    sql += ' LIMIT 1'
    cursor.execute(sql, tuple(params))
    return cursor.fetchone()

@app.route('/', methods=['GET', 'POST'])
def index():
    resultado = None
    if request.method == 'POST':
        folio = request.form.get('folio')
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM certificados
                WHERE folio = %s OR transcript = %s OR certificate = %s
                LIMIT 1
            """, (folio, folio, folio))
            resultado = cursor.fetchone()
        connection.close()
    return render_template('index.html', resultado=resultado)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    auth_error = require_admin()
    if auth_error:
        return auth_error

    error = None
    if request.method == 'POST':
        data, error = parse_certificate_form()
        if error is None:
            connection = get_db_connection()
            try:
                with connection.cursor() as cursor:
                    if find_identifier_duplicate(cursor, data):
                        error = 'Ya existe un certificado que utiliza uno de esos identificadores.'
                    else:
                        cursor.execute("""
                            INSERT INTO certificados
                            (folio, transcript, certificate, document_type, nombre, curso, level, hours, fecha, estatus)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (data['folio'], data['transcript'], data['certificate'], data['document_type'], data['nombre'], data['curso'], data['level'], data['hours'], data['fecha'], data['estatus']))
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
                SELECT id, folio, transcript, certificate, document_type, nombre, curso, level, hours, fecha, estatus
                FROM certificados ORDER BY id DESC
            """)
            certificados = cursor.fetchall()
    finally:
        connection.close()

    return render_template('admin.html', certificados=certificados, error=error, created=request.args.get('created') == '1', updated=request.args.get('updated') == '1')

@app.route('/admin/edit/<int:certificate_id>', methods=['GET', 'POST'])
def admin_edit(certificate_id):
    auth_error = require_admin()
    if auth_error:
        return auth_error

    connection = get_db_connection()
    error = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, folio, transcript, certificate, document_type, nombre, curso, level, hours, fecha, estatus
                FROM certificados WHERE id = %s LIMIT 1
            """, (certificate_id,))
            certificado = cursor.fetchone()
            if not certificado:
                return 'Certificado no encontrado', 404

            if request.method == 'POST':
                data, error = parse_certificate_form()
                if error is None:
                    if find_identifier_duplicate(cursor, data, exclude_id=certificate_id):
                        error = 'Otro certificado ya utiliza uno de esos identificadores.'
                    else:
                        cursor.execute("""
                            UPDATE certificados
                            SET folio=%s, transcript=%s, certificate=%s, document_type=%s,
                                nombre=%s, curso=%s, level=%s, hours=%s, fecha=%s, estatus=%s
                            WHERE id=%s
                        """, (data['folio'], data['transcript'], data['certificate'], data['document_type'], data['nombre'], data['curso'], data['level'], data['hours'], data['fecha'], data['estatus'], certificate_id))
                        connection.commit()
                        return redirect(url_for('admin', updated='1'))
                certificado = {**certificado, **(data or {})}
    except pymysql.MySQLError:
        connection.rollback()
        error = 'No fue posible actualizar el certificado. Verifica los datos e inténtalo nuevamente.'
    finally:
        connection.close()

    return render_template('admin_edit.html', certificado=certificado, error=error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
