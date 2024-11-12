from flask import Flask, jsonify, request, abort

app = Flask(__name__)

# Almacenamiento en memoria
alumnos = []
profesores = []

# Funciones auxiliares para buscar entidades por ID
def find_alumno(alumno_id):
    return next((alumno for alumno in alumnos if alumno["id"] == alumno_id), None)

def find_profesor(profesor_id):
    return next((profesor for profesor in profesores if profesor["id"] == profesor_id), None)

# Validación de datos
def validar_alumno(data):
    required_fields = ["id", "nombres", "apellidos", "matricula", "promedio"]
    for field in required_fields:
        if field not in data or data[field] is None:
            return False, f"El campo '{field}' es obligatorio"
    if not isinstance(data["promedio"], (int, float)):
        return False, "El campo 'promedio' debe ser un número"
    return True, ""

def validar_profesor(data):
    required_fields = ["id", "numeroEmpleado", "nombres", "apellidos", "horasClase"]
    for field in required_fields:
        if field not in data or data[field] is None:
            return False, f"El campo '{field}' es obligatorio"
    if not isinstance(data["horasClase"], int):
        return False, "El campo 'horasClase' debe ser un número entero"
    return True, ""

# Endpoints para Alumnos
@app.route('/alumnos', methods=['GET'])
def get_alumnos():
    return jsonify(alumnos), 200

@app.route('/alumnos/<int:alumno_id>', methods=['GET'])
def get_alumno(alumno_id):
    alumno = find_alumno(alumno_id)
    if alumno:
        return jsonify(alumno), 200
    return jsonify({"error": "Alumno no encontrado"}), 404

@app.route('/alumnos', methods=['POST'])
def create_alumno():
    data = request.get_json()
    is_valid, message = validar_alumno(data)
    if not is_valid:
        return jsonify({"error": message}), 400
    alumnos.append(data)
    return jsonify(data), 201

@app.route('/alumnos/<int:alumno_id>', methods=['PUT'])
def update_alumno(alumno_id):
    alumno = find_alumno(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404
    data = request.get_json()
    is_valid, message = validar_alumno(data)
    if not is_valid:
        return jsonify({"error": message}), 400
    alumno.update(data)
    return jsonify(alumno), 200

@app.route('/alumnos/<int:alumno_id>', methods=['DELETE'])
def delete_alumno(alumno_id):
    alumno = find_alumno(alumno_id)
    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404
    alumnos.remove(alumno)
    return jsonify({"message": "Alumno eliminado"}), 200

# Endpoints para Profesores
@app.route('/profesores', methods=['GET'])
def get_profesores():
    return jsonify(profesores), 200

@app.route('/profesores/<int:profesor_id>', methods=['GET'])
def get_profesor(profesor_id):
    profesor = find_profesor(profesor_id)
    if profesor:
        return jsonify(profesor), 200
    return jsonify({"error": "Profesor no encontrado"}), 404

@app.route('/profesores', methods=['POST'])
def create_profesor():
    data = request.get_json()
    is_valid, message = validar_profesor(data)
    if not is_valid:
        return jsonify({"error": message}), 400
    profesores.append(data)
    return jsonify(data), 201

@app.route('/profesores/<int:profesor_id>', methods=['PUT'])
def update_profesor(profesor_id):
    profesor = find_profesor(profesor_id)
    if not profesor:
        return jsonify({"error": "Profesor no encontrado"}), 404
    data = request.get_json()
    is_valid, message = validar_profesor(data)
    if not is_valid:
        return jsonify({"error": message}), 400
    profesor.update(data)
    return jsonify(profesor), 200

@app.route('/profesores/<int:profesor_id>', methods=['DELETE'])
def delete_profesor(profesor_id):
    profesor = find_profesor(profesor_id)
    if not profesor:
        return jsonify({"error": "Profesor no encontrado"}), 404
    profesores.remove(profesor)
    return jsonify({"message": "Profesor eliminado"}), 200

if __name__ == '__main__':
    app.run(debug=True)
