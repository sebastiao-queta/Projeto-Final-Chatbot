import streamlit as st
import os
import torch
import random
import pandas as pd
from sklearn.model_selection import train_test_split
import sys
import sqlite3
from datetime import datetime, timedelta
import re
import time
from dotenv import load_dotenv
import dns.resolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.tipo import nltk_utils
import book_appointment
from modelo.model import CustomRNNModel
from data.Healthguide import health_advice
from app.tipo.responses import greetings, responses, farewell, replies

load_dotenv()


def load_disease_names(file_path):
    ConditionNames = {}
    with open(file_path, 'r') as file:
        for line in file:
            pairs = line.strip().split(',')
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    ConditionNames[int(key)] = value
    return ConditionNames


file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'nome.txt')
names = load_disease_names(file_path)

df = pd.read_csv('data/Symptom2Disease.csv')
df.drop('Unnamed: 0', axis=1, inplace=True)
df.drop_duplicates(inplace=True)
train_data, test_data = train_test_split(df, test_size=0.15, random_state=42)

vectorizer = nltk_utils.cria_tfidf_vector()
vectorizer.fit(train_data['text'])

model = CustomRNNModel()
model.load_state_dict(torch.load(
    'modelo/trem_model.pth', map_location=torch.device('cpu')))

if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'user_input' not in st.session_state:
    st.session_state['user_input'] = ""
if 'booking_appointment' not in st.session_state:
    st.session_state['booking_appointment'] = False
if 'appointment_step' not in st.session_state:
    st.session_state['appointment_step'] = 0
if 'appointment_details' not in st.session_state:
    st.session_state['appointment_details'] = {}
if 'chosen_date' not in st.session_state:
    st.session_state['chosen_date'] = None
if 'selected_time' not in st.session_state:
    st.session_state['selected_time'] = None

CONFIDENCE_THRESHOLD = 0.7


def initialize_db():
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_number INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            doctor TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


initialize_db()


def validate_input(user_input):
    pattern = re.compile(r'[^a-zA-Z\s]')
    return not pattern.search(user_input)


def is_valid_email(email):
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(regex, email):
        domain = email.split('@')[1]
        try:
            records = dns.resolver.resolve(domain, 'MX')
            print(f"MX records for {domain}: {records}")
            return True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.Timeout) as e:
            print(f"Error checking MX records for {domain}: {e}")
            try:
                print("Retrying MX record lookup...")
                time.sleep(2)
                records = dns.resolver.resolve(domain, 'MX')
                print(f"MX records for {domain}: {records}")
                return True
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.Timeout) as e:
                print(f"Second attempt failed for {domain}: {e}")
                return False
    else:
        print("Email format is invalid")
    return False


def is_valid_phone_number(phone):
    return re.match(r'^\d{11}$', phone) is not None


def validate_date(date_str):
    try:
        appointment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        current_date = datetime.now().date()
        return appointment_date >= current_date
    except ValueError:
        return False


def validate_datetime(date_str, time_str=None):
    try:
        appointment_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        current_datetime = datetime.now()
        return appointment_datetime > current_datetime
    except ValueError:
        return False


def is_time_slot_available(date_str, time_str, doctor):
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM appointments WHERE date = ? AND time = ? AND doctor = ?",
                   (date_str, time_str, doctor))
    available = cursor.fetchone() is None
    conn.close()
    return available


def get_occupied_time_slots(date_str, doctor):
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT time FROM appointments WHERE date = ? AND doctor = ?", (date_str, doctor))
    occupied_slots = [row[0] for row in cursor.fetchall()]
    conn.close()
    return occupied_slots


def generate_time_slots(start_time, end_time, interval_minutes, chosen_date=None, occupied_slots=[]):
    times = []
    current_time = datetime.strptime(start_time, "%H:%M")
    end_time = datetime.strptime(end_time, "%H:%M")
    now = datetime.now()

    while current_time <= end_time:
        time_str = current_time.strftime("%H:%M")
        if chosen_date:
            full_datetime = datetime.combine(datetime.strptime(chosen_date, "%Y-%m-%d"), current_time.time())
            if full_datetime > now:
                times.append((time_str, time_str in occupied_slots))
        else:
            times.append((time_str, time_str in occupied_slots))
        current_time += timedelta(minutes=interval_minutes)
    return times


def check_email_exists(email):
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM appointments WHERE email = ?", (email,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def check_phone_exists(phone):
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM appointments WHERE phone = ?", (phone,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def responde(message):
    bot_message = ""
    if message.lower() in greetings:
        bot_message = random.choice(responses)
    elif message.lower() in farewell:
        bot_message = random.choice(replies)
    elif "appointment" in message.lower() or "book" in message.lower() or "schedule" in message.lower():
        st.session_state['booking_appointment'] = True
        st.session_state['appointment_step'] = 1
        bot_message = "Sure, I can help you with booking an appointment. What is your first name?"
    else:
        try:
            transform_text = vectorizer.transform([message])
            transform_text = torch.tensor(transform_text.toarray()).float()
            model.eval()
            with torch.no_grad():
                y_logits = model(transform_text)
                pred_prob = torch.softmax(y_logits, dim=1)
                max_prob, pred_class = torch.max(pred_prob, dim=1)

                if max_prob.item() < CONFIDENCE_THRESHOLD:
                    bot_message = "Could you please provide more details about your symptoms? I need more information to understand them fully."
                else:
                    test_pred = names.get(pred_class.item(), "Not Found")
                    st.session_state['predicted_disease'] = test_pred
                    if test_pred == "Not Found":
                        bot_message = "No diagnose available"
                    else:
                        advice_list = health_advice.get(test_pred, ["No advice available"])
                        if advice_list == ["No advice available"]:
                            advice = advice_list[0]
                        else:
                            advice = random.choice(advice_list)  # Select a random piece of advice
                        bot_message = f'Given your symptoms, it seems likely that you might have {test_pred}. {advice}'
        except Exception as e:
            print(f"Error: {e}")  # Print the actual error for debugging
            bot_message = "I encountered an error while processing your request. Please try again."

    return bot_message


def send_verification_email(first_name, last_name, email, phone, date, time, doctor, appointment_number):
    try:
        print(f"Debug: Sending email to {email}")
        print("Debug: Email sent successfully")
    except Exception as e:
        print(f"Debug: Error sending email - {e}")


def handle_booking_conversation(user_input):
    step = st.session_state['appointment_step']
    details = st.session_state['appointment_details']
    print(f"Debug: Entered handle_booking_conversation with step {step} and user_input {user_input}")

    st.session_state['email_error'] = False

    if step == 1:
        if not validate_input(user_input):
            return "Please enter a first name using letters only, avoiding numbers or symbols."
        details['first_name'] = user_input
        st.session_state['appointment_step'] = 2
        return "Could you please provide your last name?"

    elif step == 2:
        if not validate_input(user_input):
            return "Please enter a last name using letters only, avoiding numbers or symbols."
        details['last_name'] = user_input
        st.session_state['appointment_step'] = 3
        return "Could you please provide your email address?"

    elif step == 3:
        if not is_valid_email(user_input):
            st.session_state['email_error'] = True
            print(f"Debug: Invalid email provided: {user_input}")
            return "The email address provided is invalid. Please enter a valid email address."
        if check_email_exists(user_input):
            return "An appointment with this email already exists. Please provide a different email."
        details['email'] = user_input
        st.session_state['appointment_step'] = 4
        return "Could you please provide your phone number?"

    elif step == 4:
        if not is_valid_phone_number(user_input):
            return "The phone number must be exactly 11 digits. Please enter a valid phone number."
        if check_phone_exists(user_input):
            return "An appointment with this phone number already exists. Please provide a different phone number."
        details['phone'] = user_input
        st.session_state['appointment_step'] = 5
        return "Thanks! Please choose a date for the appointment."

    elif step == 5:
        if 'chosen_date' not in st.session_state or st.session_state['chosen_date'] is None:
            return "Please choose a date for the appointment using the calendar."

        date_str = st.session_state['chosen_date'].strftime("%Y-%m-%d")
        if not validate_date(date_str):
            st.session_state['chosen_date'] = None
            return "The chosen date is in the past. Please provide a valid date (YYYY-MM-DD):"

        details['date'] = date_str
        st.session_state['appointment_step'] = 6
        st.session_state['chosen_date'] = None
        return "Please choose a doctor from the options below."

    elif step == 6:
        details['doctor'] = user_input
        st.session_state['appointment_step'] = 7
        return "Please select a time for the appointment from the options below."

    elif step == 7:
        if 'selected_time' in st.session_state and st.session_state['selected_time']:
            time_str = st.session_state['selected_time']
            st.session_state['selected_time'] = None
        else:
            time_str = user_input.strip()

        date_str = details['date']
        doctor = details['doctor']
        print(f"Debug: Date is {date_str}, Time is {time_str}, Doctor is {doctor}")

        if not validate_datetime(date_str, time_str):
            print(f"Debug: Validation failed for datetime {date_str} {time_str}")
            return "The chosen date and time are not available. Please select a valid time (HH:MM):"

        if not is_time_slot_available(date_str, time_str, doctor):
            print(f"Debug: Time slot {date_str} {time_str} not available for doctor {doctor}")
            return "The chosen time slot is already booked for the selected doctor. Please select a different time: "

        details['time'] = time_str
        st.session_state['appointment_step'] = 0
        st.session_state['booking_appointment'] = False

        appointment_number = random.randint(100000, 999999)
        details['appointment_number'] = appointment_number

        try:
            conn = sqlite3.connect('data/appointments.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO appointments (first_name, last_name, email, phone, date, time, doctor, appointment_number) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                details['first_name'], details['last_name'], details['email'], details['phone'], details['date'],
                details['time'], details['doctor'], details['appointment_number']))
            conn.commit()
            conn.close()
            st.session_state['appointment_details'] = {}

            print("Debug: Calling send_verification_email")
            email_sent = book_appointment.send_verification_email(details['first_name'], details['last_name'],
                                                                  details['email'],
                                                                  details['phone'], details['date'], details['time'],
                                                                  details['doctor'], details['appointment_number'])
            print(f"Debug: email_sent returned: {email_sent}")

            if email_sent:
                return "Your appointment has been successfully booked!"
            else:
                return "Your appointment has been booked, but we couldn't send the confirmation email. Please contact support."

        except Exception as e:
            print(f"Debug: Database error occurred: {e}")
            return f"An error occurred while booking the appointment: {e}"


def handle_time_selection(time):
    st.session_state['selected_time'] = time
    reply = handle_booking_conversation(time)
    st.session_state.chat_history.append((f" selected time {time}", reply))


def handle_doctor_selection(doctor):
    reply = handle_booking_conversation(doctor)
    st.session_state.chat_history.append((f" selected doctor {doctor}", reply))


def main():
    query_params = st.query_params
    if 'cancel' in query_params and query_params['cancel'] == 'true':
        book_appointment.display_cancel_form()
    else:
        st.title("Medical Chatbot")

        menu = ["Home", "Chat", "Book Appointment", "About"]
        choice = st.sidebar.selectbox("Menu", menu)

        if choice == "Home":
            st.write("Welcome to the Medical Chatbot")
            st.markdown(
                "<style>img {border-radius: 125px;}</style>", unsafe_allow_html=True
            )
            st.image("imagem/desenho3.webp", use_column_width=True)

        elif choice == "Chat":
            st.subheader("Chat with the Bot")

            def handle_submit():
                user_input = st.session_state.user_input
                if user_input:
                    if st.session_state['booking_appointment']:
                        reply = handle_booking_conversation(user_input)
                    else:
                        reply = responde(user_input)
                    st.session_state.chat_history.append((user_input, reply))
                    st.session_state.user_input = ""

            with st.form(key='chat_form'):
                st.text_input("Type your message to the chatbot:", key="user_input")
                submit_button = st.form_submit_button(label='Send', on_click=handle_submit)

            for user_input, reply in st.session_state.chat_history:
                st.markdown(f"""
                <div style="text-align: right;">
                    <p><strong>User:</strong> {user_input}</p>
                </div>
                <div style="text-align: left;">
                    <p><strong>Bot:</strong> {reply}</p>
                </div>
                """, unsafe_allow_html=True)

            if st.session_state['booking_appointment']:
                step = st.session_state['appointment_step']

                if step == 5:
                    min_date = datetime.now().date()
                    date_input = st.date_input("Choose a date for the appointment", value=None, min_value=min_date)
                    if date_input:
                        st.session_state['chosen_date'] = date_input
                        reply = handle_booking_conversation(date_input.strftime("%Y-%m-%d"))
                        st.session_state.chat_history.append((f"User selected date {date_input}", reply))

                elif step == 6:
                    doctors_list = list(book_appointment.disease_to_doctor.values())
                    selected_doctor = None
                    cols = st.columns(3)
                    for i, doctor in enumerate(doctors_list):
                        if cols[i % 3].button(doctor, key=f"doctor_button_{doctor}",
                                              on_click=lambda d=doctor: handle_doctor_selection(d)):
                            break

                elif step == 7:
                    doctor = st.session_state['appointment_details']['doctor']
                    date = st.session_state['appointment_details']['date']
                    occupied_slots = get_occupied_time_slots(date, doctor)
                    time_slots = generate_time_slots("07:00", "20:30", 30, date, occupied_slots)
                    selected_time = None
                    cols = st.columns(4)
                    for i, (time, occupied) in enumerate(time_slots):
                        if occupied:
                            cols[i % 4].button(time, key=f"time_button_{time}", disabled=True)
                        else:
                            if cols[i % 4].button(time, key=f"time_button_{time}",
                                                  on_click=lambda t=time: handle_time_selection(t)):
                                break

        elif choice == "Book Appointment":
            book_appointment.book_appointment()

        elif choice == "About":
            st.subheader("About")
            st.write(
                "This chatbot helps with preliminary medical advice and can guide you to the appropriate healthcare resources.")


if __name__ == "__main__":
    main()
