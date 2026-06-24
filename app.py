from flask import Flask, render_template, request, redirect, session, send_file, jsonify
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os
import re
from openpyxl import Workbook, load_workbook

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super_secret_key")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")

socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

if os.path.exists("/var/data"):
    BASE_PATH = "/var/data"
else:
    BASE_PATH = "data"

UPLOAD_FOLDER = os.path.join(BASE_PATH, "uploads")
DB_FILE = os.path.join(BASE_PATH, "datos.db")

os.makedirs(BASE_PATH, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_FILE}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Participante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    dni_matricula = db.Column(db.String(50))
    asistencia = db.Column(db.String(100))
    equipo = db.Column(db.String(50))


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), default="🏌️ Torneo Matungo")
    subtitulo = db.Column(db.String(200), default="")
    subtitulo2 = db.Column(db.String(200), default="")
    subtitulo3 = db.Column(db.String(200), default="")
    opciones_menu = db.Column(db.Text, default="8:00 AM,9:00 AM,10:00 AM")
    menu_activo = db.Column(db.Boolean, default=True)
    cierre_inscripcion = db.Column(db.String(30), default="")
    whatsapp_activo = db.Column(db.Boolean, default=True)


class Handicap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    hdcp = db.Column(db.String(10))


def migrar_columna(tabla, columna, definicion):
    with db.engine.connect() as conn:
        columnas = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({tabla})")]
        if columna not in columnas:
            conn.exec_driver_sql(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
            conn.commit()


with app.app_context():
    db.create_all()

    migrar_columna("config", "subtitulo2", "VARCHAR(200) DEFAULT ''")
    migrar_columna("config", "subtitulo3", "VARCHAR(200) DEFAULT ''")
    migrar_columna("config", "opciones_menu", "TEXT DEFAULT '8:00 AM,9:00 AM,10:00 AM'")
    migrar_columna("config", "menu_activo", "BOOLEAN DEFAULT 1")
    migrar_columna("config", "whatsapp_activo", "BOOLEAN DEFAULT 1")
    migrar_columna("config", "cierre_inscripcion", "VARCHAR(30) DEFAULT ''")
    
    migrar_columna("participante", "asistencia", "VARCHAR(100)")
    migrar_columna("participante", "equipo", "VARCHAR(50)")
    migrar_columna("participante", "dni_matricula", "VARCHAR(50)")

    if not Config.query.first():
        db.session.add(Config())
        db.session.commit()


def validar_dni(t):
    return re.match(r"^\d{1,8}$", t or "")


def solo_letras(t):
    return re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$", t or "")


def participantes_ordenados():
    return Participante.query.order_by(
        Participante.apellido.asc(),
        Participante.nombre.asc()
    ).all()

def inscripcion_cerrada(config):
    if not config.cierre_inscripcion:
        return False

    try:
        cierre = datetime.fromisoformat(config.cierre_inscripcion)
        return datetime.now() >= cierre
    except:
        return False

@app.route("/")
def index():
    config = Config.query.first()

    menu_opciones = []
    if config and config.opciones_menu:
        menu_opciones = [x.strip() for x in config.opciones_menu.split(",") if x.strip()]

    bg_path = "/static_bg" if os.path.exists(os.path.join(UPLOAD_FOLDER, "fondo.jpg")) else None

    return render_template(
        "index.html",
        participantes=participantes_ordenados(),
        handicaps=Handicap.query.order_by(Handicap.nombre.asc()).all(),
        menu_opciones=menu_opciones,
        menu_activo=config.menu_activo,
        admin=session.get("admin", False),
        bg_path=bg_path,
        config=config
    )


@app.route("/participantes")
def participantes():
    data = participantes_ordenados()
    return jsonify([
        {
            "id": p.id,
            "nombre": p.nombre,
            "apellido": p.apellido,
            "equipo": p.equipo or ""
        }
        for p in data
    ])


@app.route("/agregar", methods=["POST"])
def agregar():
    config = Config.query.first()

    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    dni_matricula = request.form.get("dni_matricula", "").strip()
    asistencia = request.form.get("asistencia", "").strip()
    equipo = request.form.get("equipo", "").strip()

    if not equipo:
        return jsonify({"ok": False, "msg": "Falta elegir equipo"}), 400

    if config.menu_activo and not asistencia:
        return jsonify({"ok": False, "msg": "Falta elegir menú"}), 400

    if not solo_letras(nombre) or not solo_letras(apellido):
        return jsonify({"ok": False, "msg": "Nombre o apellido inválido"}), 400

    if not dni_matricula:
        return jsonify({"ok": False, "msg": "Debe ingresar DNI o matrícula"}), 400

    if not validar_dni(dni_matricula):
        return jsonify({"ok": False, "msg": "El DNI debe contener solo números y hasta 8 dígitos"}), 400

    if Participante.query.filter_by(nombre=nombre, apellido=apellido).first():
        return jsonify({"ok": False, "msg": "Ya está anotado"}), 400

    nuevo = Participante(
        nombre=nombre,
        apellido=apellido,
        dni_matricula=dni_matricula,
        asistencia=asistencia,
        equipo=equipo
    )

    db.session.add(nuevo)
    db.session.commit()

    socketio.emit("actualizar_lista")

    return jsonify({
        "ok": True,
        "msg": f"{nombre} {apellido} quedó anotado en {equipo}"
    })


@app.route("/admin", methods=["POST"])
def admin_login():
    if request.form.get("password") == ADMIN_PASSWORD:
        session["admin"] = True
    return redirect("/")


@app.route("/admin-secret")
def admin_secret():
    return render_template("admin_login.html")


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


@app.route("/update_config", methods=["POST"])
def update_config():
    if not session.get("admin"):
        return "No autorizado", 403

    config = Config.query.first()

    config.titulo = request.form.get("titulo", "")
    config.subtitulo = request.form.get("subtitulo", "")
    config.subtitulo2 = request.form.get("subtitulo2", "")
    config.subtitulo3 = request.form.get("subtitulo3", "")
    config.opciones_menu = request.form.get("opciones_menu", "")
    config.menu_activo = bool(request.form.get("menu_activo"))
    config.whatsapp_activo = bool(request.form.get("whatsapp_activo"))

    db.session.commit()
    return redirect("/")


@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if not session.get("admin"):
        return jsonify({"ok": False, "msg": "No autorizado"}), 403

    p = Participante.query.get(id)
    if p:
        db.session.delete(p)
        db.session.commit()

    socketio.emit("actualizar_lista")

    return jsonify({"ok": True})


@app.route("/reset")
def reset():
    if not session.get("admin"):
        return "No autorizado", 403

    Participante.query.delete()
    db.session.commit()

    socketio.emit("actualizar_lista")

    return redirect("/")


@app.route("/export")
def export():
    if not session.get("admin"):
        return "No autorizado", 403

    wb = Workbook()
    ws_default = wb.active
    wb.remove(ws_default)

    def crear_hoja(nombre_hoja, participantes):
        ws = wb.create_sheet(title=nombre_hoja)
        ws.append(["Nombre", "Apellido", "DNI/Matrícula", "Equipo", "Menú"])

        for p in participantes:
            ws.append([
                p.nombre,
                p.apellido,
                p.dni_matricula,
                p.equipo,
                p.asistencia
            ])

    todos = participantes_ordenados()
    team22 = [p for p in todos if p.equipo == "Team 22"]
    aguilas = [p for p in todos if p.equipo == "Águilas"]
    invitados = [p for p in todos if p.equipo == "Invitado"]

    crear_hoja("General", todos)
    crear_hoja("Team 22", team22)
    crear_hoja("Aguilas", aguilas)
    crear_hoja("Invitados", invitados)

    path = os.path.join(BASE_PATH, "participantes.xlsx")
    wb.save(path)

    return send_file(path, as_attachment=True)


@app.route("/upload_hdcp", methods=["POST"])
def upload_hdcp():
    if not session.get("admin"):
        return "No autorizado", 403

    file = request.files.get("file")
    if not file:
        return redirect("/")

    wb = load_workbook(file)
    ws = wb.active

    Handicap.query.delete()

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue

        if not row or len(row) < 2:
            continue

        nombre, hdcp = row[0], row[1]

        if nombre and hdcp:
            db.session.add(Handicap(
                nombre=str(nombre).strip(),
                hdcp=str(hdcp).strip()
            ))

    db.session.commit()
    return redirect("/")


@app.route("/upload_bg", methods=["POST"])
def upload_bg():
    if not session.get("admin"):
        return "No autorizado", 403

    file = request.files.get("imagen")

    if file and file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
        file.save(os.path.join(UPLOAD_FOLDER, "fondo.jpg"))

    return redirect("/")


@app.route("/static_bg")
def bg():
    return send_file(os.path.join(UPLOAD_FOLDER, "fondo.jpg"))


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        debug=True,
        allow_unsafe_werkzeug=True
    )
