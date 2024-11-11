from flask import Flask, render_template, request, redirect, url_for, flash, session
import flask
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField
from wtforms.validators import DataRequired, Length
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_user, LoginManager, login_required, current_user, logout_user
from flask_socketio import SocketIO, emit, join_room, leave_room
import random
import string

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = "my-secrets"  # Replace with a strong secret key
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///huddle.db"

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# Initialize Flask-SocketIO
socketio = SocketIO(app)

# Define the User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def is_active(self):
        return True

    def get_id(self):
        return str(self.id)

    def is_authenticated(self):
        return True

# Registration Form
class RegistrationForm(FlaskForm):
    email = EmailField(label='Email', validators=[DataRequired()])
    first_name = StringField(label="First Name", validators=[DataRequired()])
    last_name = StringField(label="Last Name", validators=[DataRequired()])
    username = StringField(label="Username", validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField(label="Password", validators=[DataRequired(), Length(min=8, max=20)])

# Login Form
class LoginForm(FlaskForm):
    email = EmailField(label='Email', validators=[DataRequired()])
    password = PasswordField(label="Password", validators=[DataRequired()])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["POST", "GET"])
def login():
    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html", form=form)

@app.route("/logout", methods=["GET"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out of Huddle successfully!", "info")
    return redirect(url_for("login"))

@app.route("/register", methods=["POST", "GET"])
def register():
    form = RegistrationForm()
    if request.method == "POST" and form.validate_on_submit():
        existing_user_email = User.query.filter_by(email=form.email.data).first()
        existing_user_username = User.query.filter_by(username=form.username.data).first()

        if existing_user_email:
            flash("Email address is already registered. Please use a different email.", "danger")
        elif existing_user_username:
            flash("Username is already taken. Please choose a different username.", "danger")
        else:
            new_user = User(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                username=form.username.data,
                password=form.password.data
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Welcome to Huddle! You can now log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html", form=form)

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", first_name=current_user.first_name, last_name=current_user.last_name)

def generate_meeting_id(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@app.route("/meeting", methods=["GET", "POST"])
@login_required
def meeting():
    if request.method == "POST":
        meeting_name = request.form.get("meeting_name")
        room_id = generate_meeting_id()
        session['room_id'] = room_id
        flash(f"Meeting '{meeting_name}' created! Your room ID is: {room_id}", "success")
        return redirect(url_for('meeting', room_id=room_id))

    room_id = request.args.get('roomID', None)
    return render_template("meeting.html", username=current_user.username, room_id=room_id)

@app.route("/join", methods=["GET", "POST"])
@login_required
def join():
    if request.method == "POST":
        room_id = request.form.get("roomID")
        if room_id:
            return redirect(f"/meeting?roomID={room_id}")
        else:
            flash("Invalid Room ID. Please try again.", "danger")
    return render_template("join.html")

@socketio.on('send_message')
def handle_send_message(data):
    room_id = data['room_id']
    emit('receive_message', data, to=room_id)

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data['room_id']
    username = data['username']
    join_room(room_id)
    emit('user_joined', {'username': username, 'room_id': room_id}, to=room_id)

@socketio.on('leave_room')
def handle_leave_room(data):
    room_id = data['room_id']
    username = data['username']
    leave_room(room_id)
    emit('user_left', {'username': username, 'room_id': room_id}, to=room_id)

@socketio.on('mute_user')
def handle_mute_user(data):
    room_id = data['room_id']
    username = data['username']
    # Here you would mute the user's audio stream, handling it on the client side
    emit('user_muted', {'username': username, 'room_id': room_id}, to=room_id)

@socketio.on('toggle_video')
def handle_toggle_video(data):
    room_id = data['room_id']
    username = data['username']
    # Here you would toggle the user's video stream, handling it on the client side
    emit('user_video_toggled', {'username': username, 'room_id': room_id}, to=room_id)

@socketio.on('remove_user')
def handle_remove_user(data):
    room_id = data['room_id']
    username = data['username']
    # Handle removing the user from the room
    emit('user_removed', {'username': username, 'room_id': room_id}, to=room_id)

@socketio.on('share_screen')
def handle_share_screen(data):
    room_id = data['room_id']
    emit('start_screen_share', data, to=room_id)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Ensures the tables are created
    socketio.run(app, debug=True)
