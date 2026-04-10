from flask import Flask, render_template, request, redirect, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import os
import re
from openpyxl import Workbook

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

app.secret_key = "super_secret_key"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

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
    matricula = db.Column(db.String(50))
    asistencia = db.Column(db.String(100))
    equipo = db.Column(db.String(50))  # 👈 NUEVO

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
    nombre = db.Column(db.String(100), nullable=False)
    hdcp = db.Column(db.String(10), nullable=False)

with app.app_context():
    db.create_all()
    if not Config.query.first():
        db.session.add(Config())
        db.session.commit()

# =========================
# VALIDACIONES
# =========================
def solo_letras(t): return re.match(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$", t)

# =========================
# WEBSOCKET
# =========================
@socketio.on("nuevo_participante")
def nuevo_participante(data):
    config = Config.query.first()

    nombre = data["nombre"].strip()
    apellido = data["apellido"].strip()
    asistencia = data.get("asistencia")
    equipo = data.get("equipo")

    error = None

    if not equipo:
        error = "Seleccioná un equipo"
    elif config.menu_activo and not asistencia:
        error = "Seleccioná un horario"
    elif not solo_letras(nombre):
        error = "Nombre inválido"
    elif not solo_letras(apellido):
        error = "Apellido inválido"
    elif Participante.query.filter_by(nombre=nombre, apellido=apellido).first():
        error = "Ya anotado"
    else:
        db.session.add(Participante(
            nombre=nombre,
            apellido=apellido,
            asistencia=asistencia if asistencia else "",
            equipo=equipo
        ))
        db.session.commit()

    socketio.emit("actualizar_lista")

# =========================
# ADMIN LOGIN
# =========================
@app.route("/admin", methods=["POST"])
def admin_login():
    if request.form.get("password") == "12345":
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
# HOME
# =========================
@app.route("/")
def index():
    config = Config.query.first()

    return render_template("index.html",
        participantes=Participante.query.order_by(Participante.nombre.asc()).all(),
        handicaps=Handicap.query.order_by(Handicap.nombre.asc()).all(),
        menu_opciones=config.opciones_menu.split(","),
        menu_activo=config.menu_activo,
        admin=session.get("admin", False),
        bg_path="/static_bg" if os.path.exists(os.path.join(UPLOAD_FOLDER,"fondo.jpg")) else None,
        config=config
    )

# =========================
# PARTICIPANTES (ADMIN)
# =========================
@app.route("/edit_participante/<int:id>", methods=["POST"])
def edit_participante(id):
    if not session.get("admin"):
        return "No autorizado",403

    p = Participante.query.get(id)
    if p:
        p.nombre = request.form.get("nombre")
        p.apellido = request.form.get("apellido")
        p.equipo = request.form.get("equipo")
        db.session.commit()

    return redirect("/")

@app.route("/delete/<int:id>")
def delete_participante(id):
    if not session.get("admin"):
        return "No autorizado",403

    p = Participante.query.get(id)
    if p:
        db.session.delete(p)
        db.session.commit()

    return redirect("/")

# =========================
# HANDICAP
# =========================
@app.route("/add_hdcp", methods=["POST"])
def add_hdcp():
    if not session.get("admin"):
        return "No autorizado",403

    db.session.add(Handicap(
        nombre=request.form.get("nombre"),
        hdcp=request.form.get("hdcp")
    ))
    db.session.commit()
    return redirect("/")

@app.route("/upload_hdcp", methods=["POST"])
def upload_hdcp():
    if not session.get("admin"):
        return "No autorizado", 403

    file = request.files.get("file")
    if not file:
        return redirect("/")

    from openpyxl import load_workbook
    wb = load_workbook(file)
    ws = wb.active

    Handicap.query.delete()

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue

        nombre, hdcp = row
        if nombre and hdcp:
            db.session.add(Handicap(
                nombre=str(nombre).strip(),
                hdcp=str(hdcp).strip()
            ))

    db.session.commit()
    return redirect("/")

@app.route("/edit_hdcp/<int:id>", methods=["POST"])
def edit_hdcp(id):
    if not session.get("admin"):
        return "No autorizado",403

    h = Handicap.query.get(id)
    if h:
        h.nombre = request.form.get("nombre")
        h.hdcp = request.form.get("hdcp")
        db.session.commit()

    return redirect("/")

@app.route("/delete_hdcp/<int:id>")
def delete_hdcp(id):
    if not session.get("admin"):
        return "No autorizado",403

    h = Handicap.query.get(id)
    if h:
        db.session.delete(h)
        db.session.commit()

    return redirect("/")

# =========================
# CONFIG
# =========================
@app.route("/update_config", methods=["POST"])
def update_config():
    if not session.get("admin"):
        return "No autorizado",403

    config = Config.query.first()

    config.titulo = request.form.get("titulo")
    config.subtitulo = request.form.get("subtitulo")
    config.subtitulo2 = request.form.get("subtitulo2")
    config.subtitulo3 = request.form.get("subtitulo3")
    config.opciones_menu = request.form.get("opciones_menu")

    config.menu_activo = True if request.form.get("menu_activo") == "on" else False
    config.whatsapp_activo = True if request.form.get("whatsapp_activo") == "on" else False

    db.session.commit()
    return redirect("/")

# =========================
# SISTEMA
# =========================
@app.route("/reset")
def reset():
    if not session.get("admin"):
        return "No autorizado",403

    Participante.query.delete()
    db.session.commit()
    return redirect("/")

@app.route("/export")
def export():
    if not session.get("admin"):
        return "No autorizado",403

    wb = Workbook()
    ws = wb.active
    ws.append(["Nombre","Apellido","Equipo","Horario"])

    for p in Participante.query.all():
        ws.append([p.nombre,p.apellido,p.equipo,p.asistencia])

    path=os.path.join(BASE_PATH,"participantes.xlsx")
    wb.save(path)

    return send_file(path, as_attachment=True)

# =========================
# FONDO
# =========================
@app.route("/upload_bg", methods=["POST"])
def upload_bg():
    if not session.get("admin"):
        return "No autorizado",403

    file = request.files.get("imagen")
    if file and file.filename.lower().endswith(('.png','.jpg','.jpeg')):
        file.save(os.path.join(UPLOAD_FOLDER,"fondo.jpg"))

    return redirect("/")

@app.route("/static_bg")
def bg():
    return send_file(os.path.join(UPLOAD_FOLDER,"fondo.jpg"))

# =========================
# RUN
# =========================
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
