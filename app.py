from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import pickle
import imaplib
import email
from email.policy import default
import pdfplumber
import docx
import re
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a strong secret key


# Temporary storage for OTPs (use a database in production)
otp_storage = {}

# Gmail credentials (Replace with real credentials or use environment variables)
EMAIL_USER = "k12392945@gmail.com"
EMAIL_PASS = "xcya gowp wxrd cjav"


# Allowed users
ALLOWED_USERS = {
    "maneeshaupender30@gmail.com": "Chawoo@30",
    "saicharan.rajampeta@iitlabs.us": "Db2@Admin",                         
    "rakeshthallapalli7@gmail.com": "7799590053"
}

# Load the trained model from pickle file
pkl_file_path = r"C:\Users\andre\Desktop\VSCode\gmail_project\Resume_Shortlisting.pkl"
with open(pkl_file_path, 'rb') as file:
    model = pickle.load(file)

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/', methods=['POST'])
def login_post():
    email = request.form['email']
    password = request.form['password']
    
    # Check if user is in allowed users
    if email in ALLOWED_USERS and ALLOWED_USERS[email] == password:
        session['user'] = email  # Set session for the logged-in user
        return redirect(url_for('index'))  # Redirect to resume shortlisting page
    else:
        flash("Invalid credentials. Please try again.", "danger")
        return redirect(url_for('login'))

# ===== DASHBOARD (Resume Shortlisting) =====
@app.route('/index', methods=['GET', 'POST'])
def index():
    if 'user' not in session:
        return redirect(url_for('login'))

    job_id, extracted_details = None, None

    if request.method == 'POST':
        job_id = request.form.get('job_id')  # Getting Job ID from the form
        if not job_id:
            flash("Job ID is required", "warning")
            return redirect(url_for('index'))

        print(f"🔍 Processing emails for Job ID: {job_id}")
        
        # ✅ Calling process_resumes_and_attachments
        extracted_details = process_resumes_and_attachments(job_id)

        # ✅ Ensuring output is correctly handled
        if extracted_details is not None and not extracted_details.empty:
            flash(f"✅ Found {len(extracted_details)} resumes for Job ID: {job_id}", "success")
        else:
            flash(f"❌ No matching resumes found for Job ID: {job_id}", "warning")
            extracted_details = pd.DataFrame(columns=[
                "name", "email", "phone", "experience", "skills", "certifications", 
                "location", "visa_status", "government", "resume score", "Rank"
            ])

    return render_template('index.html', job_id=job_id, extracted_details=extracted_details)

def get_matching_emails(mail, job_id):
    """Search Gmail for emails related to the given Job ID."""
    mail.select("inbox")

    print(f"🔍 Searching Gmail for Job ID: {job_id}...")

    # 🔴 First, search in SUBJECT
    status, messages = mail.search(None, f'(SUBJECT "{job_id}")')
    email_ids = messages[0].split()

    # 🔵 If no emails found, search in BODY
    if not email_ids:
        status, messages = mail.search(None, f'(BODY "{job_id}")')
        email_ids = messages[0].split()

    print(f"📩 DEBUG: Found {len(email_ids)} emails matching Job ID: {job_id}")

    # Print subject of every email to confirm if Job ID is inside
    for e_id in email_ids:
        result, msg_data = mail.fetch(e_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email, policy=email.policy.default)
        email_subject = msg.get("Subject", "")

        print(f"📧 DEBUG: Email from {msg.get('From')} | Subject: {email_subject}")

    return email_ids  # Return just email IDs

def extract_resumes_from_emails(matching_emails):
    """Extract resume details from email attachments."""
    extracted_resumes = []

    for msg in matching_emails:
        job_desc_text = extract_email_body(msg)

        for part in msg.iter_attachments():
            filename = part.get_filename()

            if filename and (filename.lower().endswith('.pdf') or filename.lower().endswith('.docx')):
                print(f"📎 Found resume: {filename}")
                file_data = part.get_payload(decode=True)
                resume_text = extract_text_from_file(filename, file_data)

                extracted_resumes.append(parse_resume_data(resume_text, job_desc_text))

    return extracted_resumes

def process_resumes_and_attachments(job_id):
    """Searches emails, extracts resumes, and ranks candidates."""
    try:
        print(f"🔍 Processing emails for Job ID: {job_id}")

        # ✅ Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_USER, EMAIL_PASS)

        # ✅ Search emails related to Job ID
        email_ids = get_matching_emails(mail, job_id)
        print(f"✅ Found {len(email_ids)} emails for Job ID: {job_id}")

        if not email_ids:
            print("❌ No resumes found for the given Job ID.")
            return pd.DataFrame(columns=["name", "email", "phone", "experience", "skills", 
                                         "certifications", "location", "visa_status", "government", 
                                         "resume score", "Rank"])

        resume_details = []
        for e_id in email_ids:
            result, msg_data = mail.fetch(e_id, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email, policy=email.policy.default)

            for part in msg.iter_attachments():
                filename = part.get_filename()

                if filename and (filename.lower().endswith('.pdf') or filename.lower().endswith('.docx')):
                    print(f"📎 Found resume: {filename}")
                    file_data = part.get_payload(decode=True)
                    resume_text = extract_text_from_file(filename, file_data)

                    resume_details.append(parse_resume_data(resume_text))

        mail.logout()

        df = pd.DataFrame(resume_details)
        if df.empty:
            return pd.DataFrame(columns=["name", "email", "phone", "experience", "skills", 
                                         "certifications", "location", "visa_status", "government", 
                                         "resume score", "Rank"])

        df["Rank"] = df["resume score"].apply(assign_rank)
        df = df.sort_values(by="Rank", ascending=True)

        return df

    except Exception as e:
        print(f"🚨 ERROR: {str(e)}")
        return pd.DataFrame(columns=["name", "email", "phone", "experience", "skills", 
                                     "certifications", "location", "visa_status", "government", 
                                     "resume score", "Rank"])

@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/forgot_password', methods=['POST'])
def send_otp():
    email = request.form['email']
    otp = str(random.randint(100000, 999999))
    otp_storage[email] = otp  # Store OTP temporarily
    
    # Simulate sending OTP via email (Replace with actual SMTP setup)
    print(f"OTP for {email}: {otp}")
    flash("OTP sent to your email.", "success")
    return redirect(url_for('confirm_otp'))

@app.route('/confirm_otp')
def confirm_otp():
    return render_template('confirm_otp.html')

@app.route('/confirm_otp', methods=['POST'])
def verify_otp():
    email = request.form.get('email')
    otp = request.form['otp']
    
    if email in otp_storage and otp_storage[email] == otp:
        session['reset_email'] = email
        return redirect(url_for('reset_password'))
    else:
        flash("Invalid OTP. Please try again.", "danger")
        return redirect(url_for('confirm_otp'))

@app.route('/reset_password')
def reset_password():
    return render_template('reset_password.html')

@app.route('/reset_password', methods=['POST'])
def reset_password_post():
    if 'reset_email' not in session:
        return redirect(url_for('login'))
    
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if new_password == confirm_password:
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for('login'))
    else:
        flash("Passwords do not match. Try again.", "danger")
        return redirect(url_for('reset_password'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
