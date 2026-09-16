from flask import Flask, render_template, request, Response, redirect, url_for
import pymysql
import os
import secrets

app = Flask(__name__)

def get_db_connection():
    return pymysql.connect(host=os.getenv('DB_HOST','localhost'), user=os.getenv('DB_USER','root'), password=os.getenv('DB_PASSWORD',''), database=os.getenv('DB_NAME','test'), cursorclass=pymysql.cursors.DictCursor)

def admin_credentials_valid(username,password):
    admin_user=os.getenv('ADMIN_USER'); admin_password=os.getenv('ADMIN_PASSWORD')
    if not admin_user or not admin_password or username is None or password is None: return False
    return secrets.compare_digest(username,admin_user) and secrets.compare_digest(password,admin_password)

def admin_auth_required(): return Response('Autenticación requerida',401,{'WWW-Authenticate':'Basic realm="CETI Admin"'})
def require_admin():
    auth=request.authorization
    return None if auth and admin_credentials_valid(auth.username,auth.password) else admin_auth_required()
def current_admin_user():
    auth=request.authorization
    return auth.username if auth else None
def clean_optional(value):
    value=(value or '').strip(); return value or None

def parse_certificate_form():
    data={'folio':(request.form.get('folio') or '').strip(),'transcript':clean_optional(request.form.get('transcript')),'certificate':clean_optional(request.form.get('certificate')),'document_type':clean_optional(request.form.get('document_type')),'nombre':(request.form.get('nombre') or '').strip(),'curso':(request.form.get('curso') or '').strip(),'level':clean_optional(request.form.get('level')),'fecha':(request.form.get('fecha') or '').strip(),'estatus':(request.form.get('estatus') or 'Valido').strip()}
    hours_raw=(request.form.get('hours') or '').strip()
    if not data['folio'] or not data['nombre'] or not data['curso'] or not data['fecha']: return None,'Folio, nombre, programa y fecha son obligatorios.'
    if data['estatus'] not in ('Valido','Revocado','Expirado'): return None,'El estado seleccionado no es válido.'
    try:
        data['hours']=int(hours_raw) if hours_raw else None
        if data['hours'] is not None and data['hours']<0: raise ValueError
    except ValueError: return None,'Horas debe ser un número entero igual o mayor que cero.'
    return data,None

def find_identifier_duplicate(cursor,data,exclude_id=None):
    identifiers=[v for v in (data['folio'],data['transcript'],data['certificate']) if v]
    placeholders=', '.join(['%s']*len(identifiers)); sql=f"SELECT id,folio,transcript,certificate FROM certificados WHERE (folio IN ({placeholders}) OR transcript IN ({placeholders}) OR certificate IN ({placeholders}))"; params=identifiers*3
    if exclude_id is not None: sql+=' AND id <> %s'; params.append(exclude_id)
    sql+=' LIMIT 1'; cursor.execute(sql,tuple(params)); return cursor.fetchone()

def write_audit(cursor,certificate_id,action,admin_user,old_status=None,new_status=None):
    cursor.execute("INSERT INTO certificado_auditoria (certificado_id,accion,usuario,estado_anterior,estado_nuevo) VALUES (%s,%s,%s,%s,%s)",(certificate_id,action,admin_user,old_status,new_status))

def ensure_audit_table():
    connection=get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS certificado_auditoria (id INT NOT NULL AUTO_INCREMENT PRIMARY KEY, certificado_id INT NOT NULL, accion VARCHAR(30) NOT NULL, usuario VARCHAR(100) NOT NULL, estado_anterior VARCHAR(20) NULL, estado_nuevo VARCHAR(20) NULL, fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, INDEX idx_certificado_id (certificado_id), INDEX idx_fecha_hora (fecha_hora)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            connection.commit()
    finally: connection.close()

@app.route('/',methods=['GET','POST'])
def index():
    resultado=None
    if request.method=='POST':
        folio=request.form.get('folio'); connection=get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM certificados WHERE folio=%s OR transcript=%s OR certificate=%s LIMIT 1",(folio,folio,folio)); resultado=cursor.fetchone()
        connection.close()
    return render_template('index.html',resultado=resultado)

@app.route('/admin',methods=['GET','POST'])
def admin():
    auth_error=require_admin()
    if auth_error: return auth_error
    error=None; admin_user=current_admin_user()
    if request.method=='POST':
        data,error=parse_certificate_form()
        if error is None:
            connection=get_db_connection()
            try:
                with connection.cursor() as cursor:
                    if find_identifier_duplicate(cursor,data): error='Ya existe un certificado que utiliza uno de esos identificadores.'
                    else:
                        cursor.execute("INSERT INTO certificados (folio,transcript,certificate,document_type,nombre,curso,level,hours,fecha,estatus) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(data['folio'],data['transcript'],data['certificate'],data['document_type'],data['nombre'],data['curso'],data['level'],data['hours'],data['fecha'],data['estatus']))
                        certificate_id=cursor.lastrowid; write_audit(cursor,certificate_id,'CREADO',admin_user,None,data['estatus']); connection.commit(); return redirect(url_for('admin',created='1'))
            except pymysql.MySQLError:
                connection.rollback(); error='No fue posible registrar el certificado. Verifica los datos e inténtalo nuevamente.'
            finally: connection.close()
    search=(request.args.get('q') or '').strip(); status_filter=(request.args.get('status') or '').strip()
    if status_filter not in ('','Valido','Revocado','Expirado'): status_filter=''
    connection=get_db_connection()
    try:
        with connection.cursor() as cursor:
            conditions=[]; params=[]
            if search:
                like=f'%{search}%'; conditions.append('(folio LIKE %s OR transcript LIKE %s OR certificate LIKE %s OR nombre LIKE %s OR curso LIKE %s OR document_type LIKE %s OR level LIKE %s)'); params.extend([like]*7)
            if status_filter: conditions.append('estatus=%s'); params.append(status_filter)
            where=(' WHERE '+' AND '.join(conditions)) if conditions else ''
            cursor.execute(f"SELECT id,folio,transcript,certificate,document_type,nombre,curso,level,hours,fecha,estatus FROM certificados{where} ORDER BY id DESC",tuple(params)); certificados=cursor.fetchall()
    finally: connection.close()
    return render_template('admin.html',certificados=certificados,error=error,created=request.args.get('created')=='1',updated=request.args.get('updated')=='1',search=search,status_filter=status_filter)

@app.route('/admin/auditoria')
def admin_auditoria():
    auth_error=require_admin()
    if auth_error: return auth_error
    connection=get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT a.id,a.certificado_id,c.folio,c.nombre,a.accion,a.usuario,a.estado_anterior,a.estado_nuevo,a.fecha_hora FROM certificado_auditoria a LEFT JOIN certificados c ON c.id=a.certificado_id ORDER BY a.id DESC"""); auditoria=cursor.fetchall()
    finally: connection.close()
    return render_template('admin_auditoria.html',auditoria=auditoria)

@app.route('/admin/edit/<int:certificate_id>',methods=['GET','POST'])
def admin_edit(certificate_id):
    auth_error=require_admin()
    if auth_error: return auth_error
    connection=get_db_connection(); error=None; admin_user=current_admin_user()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id,folio,transcript,certificate,document_type,nombre,curso,level,hours,fecha,estatus FROM certificados WHERE id=%s LIMIT 1",(certificate_id,)); certificado=cursor.fetchone()
            if not certificado: return 'Certificado no encontrado',404
            if request.method=='POST':
                old_status=certificado['estatus']; data,error=parse_certificate_form()
                if error is None:
                    if find_identifier_duplicate(cursor,data,exclude_id=certificate_id): error='Otro certificado ya utiliza uno de esos identificadores.'
                    else:
                        cursor.execute("UPDATE certificados SET folio=%s,transcript=%s,certificate=%s,document_type=%s,nombre=%s,curso=%s,level=%s,hours=%s,fecha=%s,estatus=%s WHERE id=%s",(data['folio'],data['transcript'],data['certificate'],data['document_type'],data['nombre'],data['curso'],data['level'],data['hours'],data['fecha'],data['estatus'],certificate_id)); write_audit(cursor,certificate_id,'EDITADO',admin_user,old_status,data['estatus']); connection.commit(); return redirect(url_for('admin',updated='1'))
                certificado={**certificado,**(data or {})}
    except pymysql.MySQLError:
        connection.rollback(); error='No fue posible actualizar el certificado. Verifica los datos e inténtalo nuevamente.'
    finally: connection.close()
    return render_template('admin_edit.html',certificado=certificado,error=error)

ensure_audit_table()
if __name__=='__main__': app.run(host='0.0.0.0',port=5000)
