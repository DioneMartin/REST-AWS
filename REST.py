from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import boto3
import uuid
import hashlib
import random
import string
import time
import os
import secrets
from dotenv import load_dotenv

# Cargar configuraciones desde el archivo .env
load_dotenv()

# Configuración de la aplicación
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuración de AWS
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
    region_name=os.getenv('AWS_REGION')
)

sns = boto3.client(
    'sns',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
    region_name=os.getenv('AWS_REGION')
)

dynamodb = boto3.resource(
    'dynamodb',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    aws_session_token=os.getenv('AWS_SESSION_TOKEN'),
    region_name=os.getenv('AWS_REGION')
)

# Variables de AWS
S3_BUCKET = os.getenv('S3_BUCKET')
SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN')
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE')

# Modelo Alumno
class Alumno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    matricula = db.Column(db.String(50), unique=True, nullable=False)
    promedio = db.Column(db.Float, nullable=False)
    foto_perfil_url = db.Column(db.String(255), nullable=True)
    password = db.Column(db.String(255), nullable=False)

# Modelo Profesor
class Profesor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_empleado = db.Column(db.String(50), unique=True, nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    horas_clase = db.Column(db.Integer, nullable=False)

# Inicializar la base de datos
with app.app_context():
    db.create_all()

# Generar un hash de contraseña
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Endpoints de alumnos
@app.route('/alumnos', methods=['GET'])
def get_alumnos():
    try:
        # Consultar todos los alumnos en la base de datos
        alumnos = Alumno.query.all()
        # Retornar un array vacío si no hay registros
        return jsonify([{
            "id": alumno.id,
            "nombres": alumno.nombres,
            "apellidos": alumno.apellidos,
            "matricula": alumno.matricula,
            "promedio": alumno.promedio,
            "fotoPerfilUrl": alumno.foto_perfil_url
        } for alumno in alumnos]), 200
    except Exception as e:
        # Manejo de errores para evitar fallos no controlados
        return jsonify({"error": str(e)}), 500

@app.route('/alumnos/<int:alumno_id>', methods=['GET'])
def get_alumno(alumno_id):
    alumno = Alumno.query.get(alumno_id)
    if alumno:
        return jsonify({
            "id": alumno.id,
            "nombres": alumno.nombres,
            "apellidos": alumno.apellidos,
            "matricula": alumno.matricula,
            "promedio": alumno.promedio,
            "fotoPerfilUrl": alumno.foto_perfil_url
        }), 200
    return jsonify({"error": "Alumno no encontrado"}), 404

@app.route('/alumnos', methods=['POST'])
def create_alumno():
    data = request.get_json()

    # Validaciones de campos
    if not data.get('nombres') or not isinstance(data['nombres'], str):
        return jsonify({"error": "El campo 'nombres' es obligatorio y debe ser una cadena no vacía"}), 400
    if not data.get('apellidos') or not isinstance(data['apellidos'], str):
        return jsonify({"error": "El campo 'apellidos' es obligatorio y debe ser una cadena no vacía"}), 400
    if not data.get('matricula') or not isinstance(data['matricula'], str):
        return jsonify({"error": "El campo 'matricula' es obligatorio y debe ser una cadena"}), 400
    if not isinstance(data.get('promedio'), (int, float)) or not (0 <= data['promedio'] <= 10):
        return jsonify({"error": "El campo 'promedio' debe ser un número entre 0 y 10"}), 400

    # Crear nuevo alumno
    new_alumno = Alumno(
        nombres=data['nombres'],
        apellidos=data['apellidos'],
        matricula=data['matricula'],
        promedio=data['promedio'],
        password=hash_password(data['password'])
    )

    db.session.add(new_alumno)
    db.session.commit()
    return jsonify({"message": "Alumno creado", "id": new_alumno.id}), 201

@app.route('/alumnos/<int:alumno_id>', methods=['PUT'])
def update_alumno(alumno_id):
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    data = request.get_json()

    # Validaciones de los campos
    if 'nombres' in data and (not data['nombres'] or not isinstance(data['nombres'], str)):
        return jsonify({"error": "El campo 'nombres' es inválido"}), 400
    if 'matricula' in data and (not isinstance(data['matricula'], str) or len(data['matricula']) < 1):
        return jsonify({"error": "El campo 'matricula' es inválido"}), 400
    if 'promedio' in data and (not isinstance(data['promedio'], (int, float)) or not (0 <= data['promedio'] <= 10)):
        return jsonify({"error": "El campo 'promedio' debe estar entre 0 y 10"}), 400

    # Actualizar solo los campos válidos
    alumno.nombres = data.get('nombres', alumno.nombres)
    alumno.apellidos = data.get('apellidos', alumno.apellidos)
    alumno.matricula = data.get('matricula', alumno.matricula)
    alumno.promedio = data.get('promedio', alumno.promedio)

    db.session.commit()
    return jsonify({"message": "Alumno actualizado"}), 200


@app.route('/alumnos/<int:alumno_id>', methods=['DELETE'])
def delete_alumno(alumno_id):
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404
    db.session.delete(alumno)
    db.session.commit()
    return jsonify({"message": "Alumno eliminado"}), 200

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": "Recurso no encontrado"}), 404

@app.route('/alumnos/<int:alumno_id>/email', methods=['POST'])
def send_email_to_alumno(alumno_id):
    # Obtener el alumno
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    # Cargar los datos del correo
    data = request.get_json()
    subject = data.get('subject', "Notificación")
    message = data.get('message', f"""
        Hola, este es un mensaje automático.
        Información del alumno:
        Nombre: {alumno.nombres} {alumno.apellidos}
        Matrícula: {alumno.matricula}
        Promedio: {alumno.promedio}
    """)

    try:
        # Publicar en el tópico SNS
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject=subject
        )
        return jsonify({"message": "Correo enviado correctamente"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Upload profile picture
@app.route('/alumnos/<int:alumno_id>/fotoPerfil', methods=['POST'])
def upload_profile_picture(alumno_id):
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    if 'foto' not in request.files:
        return jsonify({"error": "Archivo de imagen no proporcionado"}), 400

    foto = request.files['foto']
    if not foto.filename:
        return jsonify({"error": "Nombre de archivo no válido"}), 400

    # Generar un nombre único para el archivo en S3
    filename = f"{uuid.uuid4().hex}-{foto.filename}"
    try:
        # Subir la imagen a S3
        s3.upload_fileobj(
            foto,
            S3_BUCKET,
            filename,
            ExtraArgs={"ContentType": foto.content_type, "ACL": "public-read"}
        )

        # Generar la URL pública de la imagen
        foto_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"

        # Actualizar el registro del alumno con la URL de la foto
        alumno.foto_perfil_url = foto_url
        db.session.commit()

        return jsonify({"message": "Foto de perfil subida con éxito", "fotoPerfilUrl": foto_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Endpoints de profesores
@app.route('/profesores', methods=['GET'])
def get_profesores():
    profesores = Profesor.query.all()
    return jsonify([{
        "id": profesor.id,
        "numeroEmpleado": profesor.numero_empleado,
        "nombres": profesor.nombres,
        "apellidos": profesor.apellidos,
        "horasClase": profesor.horas_clase
    } for profesor in profesores]), 200

@app.route('/profesores/<int:profesor_id>', methods=['GET'])
def get_profesor(profesor_id):
    profesor = Profesor.query.get(profesor_id)
    if profesor:
        return jsonify({
            "id": profesor.id,
            "numeroEmpleado": profesor.numero_empleado,
            "nombres": profesor.nombres,
            "apellidos": profesor.apellidos,
            "horasClase": profesor.horas_clase
        }), 200
    return jsonify({"error": "Profesor no encontrado"}), 404

@app.route('/profesores', methods=['POST'])
def create_profesor():
    try:
        data = request.get_json()

        # Validaciones de los campos
        if not data or 'numeroEmpleado' not in data or not data['numeroEmpleado']:
            return jsonify({"error": "El campo 'numeroEmpleado' es obligatorio y debe ser una cadena"}), 400
        if not data or 'nombres' not in data or not data['nombres']:
            return jsonify({"error": "El campo 'nombres' es obligatorio y debe ser una cadena no vacía"}), 400
        if not data or 'apellidos' not in data or not data['apellidos']:
            return jsonify({"error": "El campo 'apellidos' es obligatorio y debe ser una cadena no vacía"}), 400
        if not isinstance(data.get('horasClase'), int) or data['horasClase'] <= 0:
            return jsonify({"error": "El campo 'horasClase' debe ser un número entero mayor que 0"}), 400

        # Crear nuevo profesor
        new_profesor = Profesor(
            numero_empleado=data['numeroEmpleado'],
            nombres=data['nombres'],
            apellidos=data['apellidos'],
            horas_clase=data['horasClase']
        )
        db.session.add(new_profesor)
        db.session.commit()

        return jsonify({"message": "Profesor creado", "id": new_profesor.id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


    db.session.add(new_profesor)
    db.session.commit()

    # Retornar el id del nuevo profesor
    return jsonify({"message": "Profesor creado", "id": new_profesor.id}), 201

@app.route('/profesores/<int:profesor_id>', methods=['PUT'])
def update_profesor(profesor_id):
    profesor = Profesor.query.get(profesor_id)
    if not profesor:
        return jsonify({"error": "Profesor no encontrado"}), 404

    data = request.get_json()

    # Validaciones de los campos
    if 'numeroEmpleado' in data and (not isinstance(data['numeroEmpleado'], str) or not data['numeroEmpleado']):
        return jsonify({"error": "El campo 'numeroEmpleado' es inválido"}), 400
    if 'nombres' in data and (not isinstance(data['nombres'], str) or not data['nombres']):
        return jsonify({"error": "El campo 'nombres' es inválido"}), 400
    if 'apellidos' in data and (not isinstance(data['apellidos'], str) or not data['apellidos']):
        return jsonify({"error": "El campo 'apellidos' es inválido"}), 400
    if 'horasClase' in data and (not isinstance(data['horasClase'], int) or data['horasClase'] <= 0):
        return jsonify({"error": "El campo 'horasClase' debe ser un número entero mayor que 0"}), 400

    # Actualizar los campos permitidos
    profesor.numero_empleado = data.get('numeroEmpleado', profesor.numero_empleado)
    profesor.nombres = data.get('nombres', profesor.nombres)
    profesor.apellidos = data.get('apellidos', profesor.apellidos)
    profesor.horas_clase = data.get('horasClase', profesor.horas_clase)

    try:
        db.session.commit()
        return jsonify({
            "message": "Profesor actualizado",
            "id": profesor.id,
            "nombres": profesor.nombres,
            "horasClase": profesor.horas_clase
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/profesores/<int:profesor_id>', methods=['DELETE'])
def delete_profesor(profesor_id):
    try:
        profesor = Profesor.query.get(profesor_id)
        if not profesor:
            return jsonify({"error": "Profesor no encontrado"}), 404

        db.session.delete(profesor)
        db.session.commit()
        return jsonify({"message": "Profesor eliminado"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoints para manejar sesiones de alumnos

# Diccionario para almacenar sesiones activas (solo para propósitos de ejemplo)
active_sessions = {}

@app.route('/alumnos/<int:alumno_id>/session/login', methods=['POST'])
def login_alumno(alumno_id):
    alumno = Alumno.query.get(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    data = request.get_json()
    if not data or 'password' not in data:
        return jsonify({"error": "El campo 'password' es obligatorio"}), 400

    # Validar la contraseña
    if hash_password(data['password']) != alumno.password:
        return jsonify({"error": "Contraseña incorrecta"}), 400

    # Generar una cadena de sesión única
    session_string = secrets.token_hex(64)
    active_sessions[session_string] = alumno_id

    return jsonify({"sessionString": session_string}), 200

@app.route('/alumnos/<int:alumno_id>/session/verify', methods=['POST'])
def verify_session(alumno_id):
    data = request.get_json()
    if not data or 'sessionString' not in data:
        return jsonify({"error": "El campo 'sessionString' es obligatorio"}), 400

    session_string = data['sessionString']

    # Verificar si la sesión es válida y corresponde al alumno
    if session_string not in active_sessions or active_sessions[session_string] != alumno_id:
        return jsonify({"error": "Sesión inválida"}), 400

    return jsonify({"message": "Sesión válida"}), 200

#Cierre de sesión
@app.route('/alumnos/<int:alumno_id>/session/logout', methods=['POST'])
def logout_alumno(alumno_id):
    data = request.get_json()
    if not data or 'sessionString' not in data:
        return jsonify({"error": "El campo 'sessionString' es obligatorio"}), 400

    session_string = data['sessionString']

    # Verificar si la sesión existe y pertenece al alumno
    if session_string in active_sessions and active_sessions[session_string] == alumno_id:
        # Eliminar la sesión del diccionario
        del active_sessions[session_string]
        return jsonify({"message": "Sesión cerrada exitosamente"}), 200

    return jsonify({"error": "Sesión no válida o ya expirada"}), 400


# Migración de tablas
with app.app_context():
    db.create_all()
    print("Tablas creadas o verificadas exitosamente.")

if __name__ == '__main__':
    app.run(debug=True)
