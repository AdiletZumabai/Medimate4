from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os
import pickle
import pandas as pd
from openai import OpenAI
import time
import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
from threading import Timer
from datetime import datetime, timedelta
# Twilio Credentials
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")

# Gmail Credentials
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
# Load environment variables

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")


client = OpenAI(api_key=api_key)


disease_data = pd.read_csv("symptom_Description.csv")

# Load trained model and vectorizer
with open("disease_model_fixed.pkl", "rb") as model_file:
    model = pickle.load(model_file)

with open("vectorizer_fixed.pkl", "rb") as vectorizer_file:
    vectorizer = pickle.load(vectorizer_file)

# Load environment variables



app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'e469871d8467813135515905637bce5a')
app.config["MONGO_URI"] = "mongodb://localhost:27017/medimate"
mongo = PyMongo(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class and other application setup continue here...


class User(UserMixin):
    def __init__(self, user_id, username):
        self.id = user_id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return None
    return User(str(user['_id']), user['username'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = mongo.db.users.find_one({'username': username})

    if user and check_password_hash(user['password'], password):
        user_obj = User(str(user['_id']), user['username'])
        login_user(user_obj)
        return jsonify({'success': True, 'redirect_url': url_for('dashboard')})
    else:
        return jsonify({'success': False, 'error': 'Invalid username or password'}), 401


@app.route("/check-login", methods=["GET"])
def check_login():
    if current_user.is_authenticated:
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False})


@app.route('/signup', methods=['POST'])
def signup():
    # Получаем данные из формы регистрации
    username = request.form['username']
    password = request.form['password']
    full_name = request.form['full_name']
    dob = request.form['dob']
    gender = request.form['gender']
    email = request.form['email']
    phone = request.form['phone']
    weight = request.form['weight']
    height = request.form['height']
    conditions = request.form['conditions']

    user_exists = mongo.db.users.find_one({'username': username})

    if user_exists:
        return jsonify({'success': False, 'error': 'Username already exists'}), 400
    else:
        hashed_password = generate_password_hash(password)
        new_user = {
            'username': username,
            'password': hashed_password,
            'full_name': full_name,
            'dob': dob,
            'gender': gender,
            'email': email,
            'phone': phone,
            'weight': weight,
            'height': height,
            'conditions': conditions
        }

        result = mongo.db.users.insert_one(new_user)
        user_obj = User(str(result.inserted_id), username)
        login_user(user_obj)

        return jsonify({'success': True, 'redirect_url': url_for('settings')})


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = current_user.id
    doctors = mongo.db.doctors.find()  # Assuming you have a collection of doctors
    return render_template('dashboard.html', username=current_user.username, doctors=doctors)


    

@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():
    if request.method == "GET":
        return render_template("chatbot.html")

    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "Message is required"}), 400

    try:
        # Отправляем запрос в OpenAI API
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a medical chatbot that helps diagnose diseases based on symptoms."},
                {"role": "user", "content": user_input}
            ]
        )

        # Получаем ответ чат-бота
        bot_reply = completion.choices[0].message.content.strip()
        return jsonify({"response": bot_reply})

    except Exception as e:
        return jsonify({"error": f"Chatbot error: {str(e)}"}), 500










@app.route('/book-appointment', methods=['GET', 'POST'])
@login_required
def book_appointment():
    if request.method == 'POST':
        doctor_id = request.form['doctor_id']
        appointment_time = request.form['available_times']
        # Ensure the user is logged in by using Flask-Login's current_user
        mongo.db.appointments.insert_one({
            'user_id': ObjectId(current_user.id),
            'doctor_id': doctor_id,
            'datetime': appointment_time
        })
        flash('Appointment booked successfully!')
        return redirect(url_for('dashboard'))
    return render_template('book_appointment.html')

@app.route('/view-appointments')
@login_required
def view_appointments():
    # Словарь соответствий ID врачей и их имен
    DOCTORS = {
        "1": "Dr. John Smith - Cardiologist",
        "2": "Dr. Jane Doe - Neurologist",
        "3": "Dr. Richard Roe - Pediatrician"
    }

    # Получаем все записи пользователя
    user_appointments = mongo.db.appointments.find({"user_id": ObjectId(current_user.id)})

    # Формируем список с добавлением имен докторов
    appointments = []
    for appointment in user_appointments:
        appointments.append({
            "doctor_name": DOCTORS.get(str(appointment["doctor_id"]), "Unknown Doctor"),  # Преобразуем ID в строку для соответствия ключам
            "datetime": appointment["datetime"]
        })

    return render_template('view_appointments.html', appointments=appointments)

twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_email(to_email, medication_name):
    subject = "MediMate Medication Reminder"
    body = f"Reminder: It's time to take your medication - {medication_name}!"
    
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = to_email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Email sending failed: {e}")

def send_sms(to_phone, medication_name):
    try:
        twilio_client.messages.create(
            body=f"Reminder: It's time to take your medication - {medication_name}!",
            from_=TWILIO_PHONE,
            to=to_phone
        )
        print(f"SMS sent to {to_phone}")
    except Exception as e:
        print(f"SMS sending failed: {e}")

def schedule_reminder(medication_name, reminder_time, frequency, phone=None, email=None):
    now = datetime.now()
    target_time = datetime.strptime(reminder_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)

    if target_time < now:
        target_time += timedelta(days=1)  # Перенос на следующий день

    time_diff = (target_time - now).total_seconds()

    Timer(time_diff, send_notifications, args=(medication_name, phone, email)).start()



def send_notifications(medication_name, phone=None, email=None):
    if phone:
        send_sms(phone, medication_name)
    if email:
        send_email(email, medication_name)


@app.route('/set-reminder', methods=['GET', 'POST'])
@login_required
def set_reminder():
    if request.method == 'POST':
        medication_name = request.form['medication_name']
        reminder_time = request.form['reminder_time']
        frequency = request.form['frequency']
        phone = request.form.get('phone')
        email = request.form.get('email')

        mongo.db.reminders.insert_one({
            'user_id': ObjectId(current_user.id),
            'medication_name': medication_name,
            'reminder_time': reminder_time,
            'frequency': frequency,
            'phone': phone,
            'email': email
        })

        schedule_reminder(medication_name, reminder_time, frequency, phone, email)

        flash('Reminder set successfully!')
        return redirect(url_for('dashboard'))
    
    return render_template('set_reminder.html')

@app.route('/settings', methods=['GET'])
@login_required
def settings():
    user_data = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    return render_template('profile-settings.html', user=user_data)

@app.route('/edit-settings', methods=['GET'])
@login_required
def edit_settings():
    user_data = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    return render_template('edit-settings.html', user=user_data)


@app.route('/save-settings', methods=['POST'])
@login_required
def save_settings():
    full_name = request.form.get('full_name')
    dob = request.form.get('dob')
    gender = request.form.get('gender')
    email = request.form.get('email')
    phone = request.form.get('phone')
    weight = request.form.get('weight')
    height = request.form.get('height')
    conditions = request.form.get('conditions')

    mongo.db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$set': {
            'full_name': full_name,
            'dob': dob,
            'gender': gender,
            'email': email,
            'phone': phone,
            'weight': weight,
            'height': height,
            'conditions': conditions
        }},
        upsert=True
    )

    flash('Profile updated successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/test-results', methods=['GET'])
@login_required
def test_results():
    user_tests = list(mongo.db.test_results.find({'user_id': ObjectId(current_user.id)}))
    
    return render_template('test-results.html', results=user_tests)

@app.route('/contact-specialist')
def contact_specialist():
    return render_template('contact-specialist.html')

if __name__ == '__main__':
    app.debug = True  # Включает подробные ошибки
    app.run(debug=True)

