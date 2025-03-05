import os
import re
import smtplib
import sqlite3
from datetime import datetime, time as dtime, date as dt_date
from email.mime.text import MIMEText
from random import randint
import streamlit as st
from dotenv import load_dotenv
import dns.resolver


load_dotenv()

disease_to_doctor = {
    'Acne': "Dr. Sophia Miller - Dermatologist",
    'Arthritis': "Dr. David Smith - Orthopedist",
    'Bronchial Asthma': "Dr. Richard Lee - General Physician",
    'Cervical spondylosis': "Dr. James Taylor - Orthopedist",
    'Chicken pox': "Dr. Emma Brown - Dermatologist",
    'Common Cold': "Dr. Mary Johnson - General Physician",
    'Dengue': "Dr. Oliver Garcia - General Physician",
    'Dimorphic Hemorrhoids': "Dr. Ethan Wilson - Gastroenterologist",
    'Fungal infection': "Dr. Ava Martinez - Dermatologist",
    'Hypertension': "Dr. Lucas Thompson - Cardiologist",
    'Impetigo': "Dr. Mia Rodriguez - Dermatologist",
    'Jaundice': "Dr. Amelia Harris - Gastroenterologist",
    'Malaria': "Dr. Mason Clark - General Physician",
    'Migraine': "Dr. Michael Lewis - Neurologist",
    'Pneumonia': "Dr. Jacob Robinson - General Physician",
    'Psoriasis': "Dr. Emily Davis - Dermatologist",
    'Typhoid': "Dr. Benjamin Lopez - Gastroenterologist",
    'Varicose Veins': "Dr. Jack Walker - Orthopedist",
    'allergy': "Dr. Charlotte King - General Physician",
    'diabetes': "Dr. Daniel Wright - General Physician",
    'drug reaction': "Dr. Henry Hall - General Physician",
    'gastroesophageal reflux disease': "Dr. Isabella Young - Gastroenterologist",
    'peptic ulcer disease': "Dr. Alexander Allen - Gastroenterologist",
    'urinary tract infection': "Dr. William Scott - Gastroenterologist"
}


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
            return False
    else:
        print("Email format is invalid")
    return False


def is_valid_phone_number(phone_number):
    return re.match(r'^\d{11}$', phone_number) is not None

def is_valid_appointment_number(appointment_number):
    return re.match(r'^\d+$', appointment_number) is not None

def send_verification_email(first_name, last_name, email, phone, appointment_date, appointment_time, doctor, appointment_number):
    try:
        print(f"Debug: Preparing to send email to {email}")
        cancel_link = f"http://localhost:8501/?cancel=true&appointment_number={appointment_number}&email={email}"
        email_content = f"""
        Dear {first_name} {last_name},

        Your appointment has been booked successfully. Here are your appointment details:

        Appointment Number: {appointment_number}
        Name: {first_name} {last_name}
        Email: {email}
        Phone: {phone}
        Appointment Date: {appointment_date}
        Appointment Time: {appointment_time}
        Doctor: {doctor}

        If you wish to cancel your appointment, please click the link below and enter your appointment number and email to confirm:
        {cancel_link}

        Thank you for booking with us.

        Best regards,
        Medical Chatbot Team
        """

        msg = MIMEText(email_content)
        msg['Subject'] = 'Appointment Confirmation'
        msg['From'] = os.getenv('EMAIL_USER')
        msg['To'] = email

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            print("Debug: Starting TLS")
            server.starttls()
            print("Debug: Logged into SMTP server")
            server.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS'))
            server.send_message(msg)
            print("Debug: Email sent successfully")
        return True
    except smtplib.SMTPException as e:
        print(f"Debug: SMTPException occurred: {e}")
        return False
    except Exception as e:
        print(f"Debug: General exception occurred: {e}")
        return False

def validate_input(user_input):
    pattern = re.compile(r'[^a-zA-Z\s]')
    if pattern.search(user_input):
        return False
    return True

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

def check_appointment_exists(appointment_number, email):
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM appointments WHERE appointment_number = ? AND email = ?", (appointment_number, email))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def is_time_slot_available(appointment_date, appointment_time, doctor):
    conn = sqlite3.connect('data/appointments.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM appointments WHERE date = ? AND time = ? AND doctor = ?",
                   (appointment_date, appointment_time, doctor))
    available = cursor.fetchone() is None
    conn.close()
    return available


def is_appointment_in_future(appointment_date, appointment_time):
    appointment_datetime = datetime.combine(appointment_date, datetime.strptime(appointment_time, "%H:%M").time())
    return appointment_datetime > datetime.now()


def book_appointment():
    st.title("Book an Appointment")

    initialize_db()

    valid_times = [dtime(hour, minute).strftime("%H:%M") for hour in range(7, 21) for minute in (0, 30)]

    with st.form("appointment_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        date = st.date_input("Appointment Date", min_value=dt_date.today())
        time = st.selectbox("Appointment Time", valid_times)

        predicted_disease = st.session_state.get('predicted_disease', None)
        suggested_doctor = disease_to_doctor.get(predicted_disease, "Select a Doctor")

        doctor = st.selectbox("Choose a Doctor", ["Select a Doctor"] + list(set(disease_to_doctor.values())), index=0)

        submitted = st.form_submit_button("Book Appointment")

        if submitted:
            if not validate_input(first_name) or not validate_input(last_name):
                st.error("The name fields may only contain letters. Please remove any numbers or symbols.")
            elif not first_name.strip() or not last_name.strip():
                st.error("Appointment booking unsuccessful. Please provide both your first and last name.")
            elif not email.strip():
                st.error("Appointment booking unsuccessful. Please provide your email.")
            elif not phone.strip():
                st.error("Appointment booking unsuccessful. Please provide your phone number.")
            elif not is_valid_email(email):
                st.error("Invalid email address. Please enter a valid email address.")
                print(f"Invalid email address: {email}")
            elif not is_valid_phone_number(phone):
                st.error("Invalid phone number. Please enter a correct phone number.")
            elif doctor == "Select a Doctor":
                st.error("Appointment booking unsuccessful. Please choose a doctor.")
            elif check_email_exists(email):
                st.error("Appointment booking unsuccessful. An appointment with this email already exists.")
            elif check_phone_exists(phone):
                st.error("Appointment booking unsuccessful. An appointment with this phone number already exists.")
            elif not is_time_slot_available(date.strftime("%Y-%m-%d"), time, doctor):
                st.error("Appointment booking unsuccessful. This time slot is already booked.")
            elif not is_appointment_in_future(date, time):
                st.error(
                    "The appointment booking could not be completed because the chosen date and time are not available.")
            else:
                try:
                    appointment_number = randint(100000, 999999)
                    if not send_verification_email(first_name, last_name, email, phone, date, time, doctor,
                                                   appointment_number):
                        st.error("Failed to send verification email. Please try again.")
                    else:
                        conn = sqlite3.connect('data/appointments.db')
                        cursor = conn.cursor()
                        cursor.execute('''
                            INSERT INTO appointments (appointment_number, first_name, last_name, email, phone, date, time, doctor) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (appointment_number, first_name.strip(), last_name.strip(), email.strip(), phone.strip(),
                              date.strftime("%Y-%m-%d"), time, doctor))
                        conn.commit()
                        conn.close()
                        st.success(f"Appointment booked successfully!")
                except Exception as e:
                    st.error(f"An error occurred while booking the appointment: {e}")


def display_cancel_form():
    st.title("Cancel an Appointment")
    st.write("Cancellation Form")

    query_params = st.query_params

    email = query_params.get("email", "")
    appointment_number = query_params.get("appointment_number", "")

    with st.form("cancel_form"):
        email_input = st.text_input("Email", value=email)
        appointment_number_input = st.text_input("Appointment Number", value=appointment_number)
        submitted = st.form_submit_button("Cancel Appointment")

        if submitted:
            if not is_valid_email(email_input) or not is_valid_appointment_number(appointment_number_input):
                st.error("Invalid email or appointment number. Please provide correct information.")
            elif not check_appointment_exists(appointment_number_input, email_input):
                st.error(
                    "No appointment found with the provided appointment number and email. Please check your details.")
            else:
                try:
                    conn = sqlite3.connect('data/appointments.db')
                    cursor = conn.cursor()
                    cursor.execute('''DELETE FROM appointments WHERE email=? AND appointment_number=?''',
                                   (email_input, appointment_number_input))
                    conn.commit()
                    conn.close()
                    st.success("Appointment canceled successfully.")
                except Exception as e:
                    st.error(f"An error occurred while canceling the appointment: {e}")


def main():
    query_params = st.query_params
    if 'cancel' in query_params and query_params['cancel'] == 'true':
        display_cancel_form()
    else:
        book_appointment()


if __name__ == "__main__":
    main()
