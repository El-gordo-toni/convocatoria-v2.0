from flask import Flask, render_template, request, redirect, session, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import re
from openpyxl import Workbook

app = Flask(__name__)

app.secret_key = "super_secret_key"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "12345")  # fallback seguro

# 📁 RUTAS
BASE_PATH = "/var/data"
UPLOAD_FOLDER = "/var/data/uploads"

os.makedirs(BASE_PATH, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////var/data/datos.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELOS
# =========================
class Participante(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    asistencia = db.Column(db.String(100))
    equipo = db.Column(db.String(50))


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), default="🏌️ Torneo Matungo")
    subtitulo = db.Column(db.String(200), default="Anotate para la próxima fecha")
    subtitulo2 = db.Column(db.String(200), default="")
    subtitulo3 = db.Column(db.String(200), default="")
    opciones_menu = db.Column(db.Text, default="8:00 AM,9:00 AM,10:00 AM")
    menu_activo = db.Column(db.Boolean, default=True)
    whatsapp_activo = db.Column(db.Boolean, default=True)


class Handicap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    hdcp = db.Column(db.String(10))


with app.app_context():
    db.create_all()
    if not Config.query.first():
        db.session.add(Config())
        db.session.commit()

# =========================
# VALIDACIÓN
# =========================
def solo_letras(t):
    return re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$", t)

# =========================
# PARTICIPANTES API
# =========================
@app.route("/participantes")
def participantes():
    jugadores = Participante.query.order_by(Participante.nombre.asc()).all()
    return jsonify([
        {
            "nombre": j.nombre,
            "apellido": j.apellido,
            "equipo": j.equipo
        } for j in jugadores
    ])

# =========================
# AGREGAR PARTICIPANTE
# =========================
@app.route("/agregar", methods=["POST"])
def agregar():
    config = Config.query.first()

    nombre = request.form.get("nombre", "").strip()
    apellido = request.form.get("apellido", "").strip()
    asistencia = request.form.get("asistencia")
    equipo = request.form.get("equipo")

    if not equipo:
        return "Seleccioná equipo", 400

    if config and config.menu_activo and not asistencia:
        return "Seleccioná horario", 400

    if not solo_letras(nombre) or not solo_letras(apellido):
        return "Nombre inválido", 400

    if Participante.query.filter_by(nombre=nombre, apellido=apellido).first():
        return "Ya anotado", 400

    db.session.add(Participante(
        nombre=nombre,
        apellido=apellido,
        asistencia=asistencia or "",
        equipo=equipo
    ))
    db.session.commit()

    return redirect("/")

# =========================
# ADMIN LOGIN
# =========================
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

# =========================
# HOME (FIX MENÚ)
# =========================
@app.route("/")
def index():
    config = Config.query.first()

    menu_opciones = []
    if config and config.opciones_menu:
        menu_opciones = [
            x.strip() for x in config.opciones_menu.split(",") if x.strip()
        ]

    return render_template(
        "index.html",
        participantes=Participante.query.all(),
        handicaps=Handicap.query.all(),
        menu_opciones=menu_opciones,
        menu_activo=config.menu_activo if config else True,
        admin=session.get("admin", False),
        bg_path="/static_bg" if os.path.exists(os.path.join(UPLOAD_FOLDER, "fondo.jpg")) else None,
        config=config
    )

# =========================
# CONFIG UPDATE
# =========================
@app.route("/update_config", methods=["POST"])
def update_config():
    if not session.get("admin"):
        return "No autorizado", 403

    config = Config.query.first()

    config.titulo = request.form.get("titulo") or config.titulo
    config.subtitulo = request.form.get("subtitulo") or config.subtitulo
    config.subtitulo2 = request.form.get("subtitulo2") or config.subtitulo2
    config.subtitulo3 = request.form.get("subtitulo3") or config.subtitulo3

    config.opciones_menu = request.form.get("opciones_menu") or config.opciones_menu

    config.menu_activo = "menu_activo" in request.form
    config.whatsapp_activo = "whatsapp_activo" in request.form

    db.session.commit()
    return redirect("/")

# =========================
# RESET
# =========================
@app.route("/reset")
def reset():
    if not session.get("admin"):
        return "No autorizado", 403

    Participante.query.delete()
    db.session.commit()
    return redirect("/")

# =========================
# EXPORT EXCEL
# =========================
@app.route("/export")
def export():
    if not session.get("admin"):
        return "No autorizado", 403

    wb = Workbook()
    ws = wb.active
    ws.append(["Nombre", "Apellido", "Equipo", "Horario"])

    for p in Participante.query.all():
        ws.append([p.nombre, p.apellido, p.equipo, p.asistencia])

    path = os.path.join(BASE_PATH, "participantes.xlsx")
    wb.save(path)

    return send_file(path, as_attachment=True)

# =========================
# FONDO
# =========================
@app.route("/upload_bg", methods=["POST"])
def upload_bg():
    if not session.get("admin"):
        return "No autorizado", 403

    file = request.files.get("imagen")
    if file:
        file.save(os.path.join(UPLOAD_FOLDER, "fondo.jpg"))

    return redirect("/")

@app.route("/static_bg")
def bg():
    return send_file(os.path.join(UPLOAD_FOLDER, "fondo.jpg"))

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run()
