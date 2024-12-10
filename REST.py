import boto3
import os
import uuid
import random
import string
from flask import Flask, jsonify, request, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pymysql
from datetime import datetime

# Habilitar PyMySQL si usas ese conector
pymysql.install_as_MySQLdb()

app = Flask(__name__)

# Configuración de la base de datos MySQL en RDS
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@RDS_endpoint/database_name'  # Cambia con tu configuración
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Desactivar el seguimiento de modificaciones de objetos
db = SQLAlchemy(app)

# Configuración del bucket S3
S3_BUCKET_NAME = 'tu-bucket-s3'  # Cambia con el nombre de tu bucket S3
S3_ACCESS_KEY = 'tu-access-key'  # Cambia con tu Access Key
S3_SECRET_KEY = 'tu-secret-key'  # Cambia con tu Secret Key
S3_REGION = 'tu-region'  # Cambia con tu región

# Configuración de SNS
SNS_TOPIC_ARN = 'arn:aws:sns:tu-region:tu-id:tu-topic'  # ARN de tu topic SNS
sns_client = boto3.client(
    'sns',
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION
)

# Configuración del cliente S3 de AWS
s3_client = boto3.client(
    's3',
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION
)

# Configuración del cliente DynamoDB
dynamodb_client = boto3.client(
    'dynamodb',
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION
)

# Definición de las entidades
class Alumno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(20), nullable=False, unique=True)
    promedio = db.Column(db.Float, nullable=False)
    fotoPerfilUrl = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<Alumno {self.nombres} {self.apellidos}>"

# Inicializar la base de datos
with app.app_context():
    db.create_all()

# Funciones auxiliares para buscar entidades por ID
def find_alumno(alumno_id):
    return Alumno.query.get(alumno_id)

# Función para generar un sessionString aleatorio
def generate_session_string(length=128):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# Tabla para sesiones de DynamoDB
def create_session_in_dynamodb(alumno_id, session_string):
    table_name = 'sesiones-alumnos'
    item = {
        'id': {'S': str(uuid.uuid4())},
        'fecha': {'N': str(int(datetime.utcnow().timestamp()))},
        'alumnoId': {'N': str(alumno_id)},
        'active': {'BOOL': True},
        'sessionString': {'S': session_string}
    }
    dynamodb_client.put_item(TableName=table_name, Item=item)

def verify_session_in_dynamodb(session_string):
    table_name = 'sesiones-alumnos'
    response = dynamodb_client.query(
        TableName=table_name,
        IndexName='sessionString-index',  # Asumir que hay un índice global en DynamoDB por sessionString
        KeyConditionExpression='sessionString = :sessionString',
        ExpressionAttributeValues={':sessionString': {'S': session_string}}
    )
    if response['Items']:
        item = response['Items'][0]
        return item
    return None

# Endpoint para subir la foto de perfil a S3
@app.route('/alumnos/<int:alumno_id>/fotoPerfil', methods=['POST'])
def upload_foto_perfil(alumno_id):
    alumno = find_alumno(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    # Verificar si se envió un archivo
    if 'foto' not in request.files:
        return jsonify({"error": "No se ha enviado ninguna foto"}), 400
    
    file = request.files['foto']
    
    # Verificar si el archivo tiene un nombre
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ninguna foto"}), 400

    # Guardar el archivo en S3
    try:
        filename = secure_filename(file.filename)
        file_key = f"alumnos/{alumno.id}/perfil/{filename}"  # Estructura del nombre del archivo en S3
        s3_client.upload_fileobj(
            file,
            S3_BUCKET_NAME,
            file_key,
            ExtraArgs={"ACL": "public-read"}
        )
        # Obtener la URL pública de la foto
        foto_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_key}"
        
        # Actualizar el alumno con la URL de la foto
        alumno.fotoPerfilUrl = foto_url
        db.session.commit()

        return jsonify({"message": "Foto subida correctamente", "fotoPerfilUrl": foto_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para obtener los datos del alumno (incluyendo la URL de la foto de perfil)
@app.route('/alumnos/<int:alumno_id>', methods=['GET'])
def get_alumno(alumno_id):
    alumno = find_alumno(alumno_id)
    if alumno:
        return jsonify({
            "id": alumno.id,
            "nombres": alumno.nombres,
            "apellidos": alumno.apellidos,
            "matricula": alumno.matricula,
            "promedio": alumno.promedio,
            "fotoPerfilUrl": alumno.fotoPerfilUrl  # Devuelve la URL de la foto
        }), 200
    return jsonify({"error": "Alumno no encontrado"}), 404

# Endpoint para enviar un correo a través de SNS
@app.route('/alumnos/<int:alumno_id>/email', methods=['POST'])
def send_email_notificacion(alumno_id):
    alumno = find_alumno(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    # Crear el mensaje con la información del alumno
    message = f"Calificaciones del alumno {alumno.nombres} {alumno.apellidos}:\n\n"
    message += f"Promedio: {alumno.promedio}\n"
    message += f"Matricula: {alumno.matricula}"

    try:
        # Publicar el mensaje en el topic SNS
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=f"Notificación de calificaciones: {alumno.nombres} {alumno.apellidos}"
        )
        return jsonify({"message": "Notificación enviada correctamente"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para iniciar sesión (login)
@app.route('/alumnos/<int:alumno_id>/session/login', methods=['POST'])
def login(alumno_id):
    alumno = find_alumno(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    # Comparar la contraseña proporcionada
    password = request.json.get('password')
    if password != alumno.password:
        return jsonify({"error": "Contraseña incorrecta"}), 400

    # Generar sessionString y registrar en DynamoDB
    session_string = generate_session_string()
    create_session_in_dynamodb(alumno.id, session_string)

    return jsonify({"message": "Sesión iniciada correctamente", "sessionString": session_string}), 200

# Endpoint para verificar sesión (verify)
@app.route('/alumnos/<int:alumno_id>/session/verify', methods=['POST'])
def verify_session(alumno_id):
    session_string = request.json.get('sessionString')
    session = verify_session_in_dynamodb(session_string)
    
    if session and session['active']['BOOL']:
        return jsonify({"message": "Sesión válida"}), 200
    return jsonify({"error": "Sesión inválida o inactiva"}), 400

# Endpoint para cerrar sesión (logout)
@app.route('/alumnos/<int:alumno_id>/session/logout', methods=['POST'])
def logout(alumno_id):
    session_string = request.json.get('sessionString')
    session = verify_session_in_dynamodb(session_string)
    
    if session:
        # Desactivar la sesión
        dynamodb_client.update_item(
            TableName='sesiones-alumnos',
            Key={'sessionString': {'S': session_string}},
            UpdateExpression='SET active = :val',
            ExpressionAttributeValues={':val': {'BOOL': False}}
        )
        return jsonify({"message": "Sesión cerrada correctamente"}), 200
    return jsonify({"error": "Sesión no encontrada"}), 400

if __name__ == '__main__':
    app.run(debug=True)
