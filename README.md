# MAIL SARTHI: Automated Email Campaign Management System

MAIL SARTHI is a full-stack, secure, and modern SaaS-like email campaign management dashboard built using **Python Flask**, **SQLite**, **Bootstrap 5**, **Chart.js**, and **Quill.js**. It enables users to upload CSV files containing contacts, customize rich HTML templates using personalization variables, and automate message queues with strict rate limits and scheduling.

---

## Core Features

- 🔐 **Secure User Authentication**: Clean sign-up/login flows with secure hashed passwords (`werkzeug.security`) and protection against session hijacking.
- 📊 **Premium Live Dashboard**: Real-time summary metrics (delivered/failed counts, contacts, limit utilization progress bar) and visual delivery breakdown using Chart.js.
- 📁 **CSV Contact Management**: Drag-and-drop CSV importer with client-side parsing, email formatting validation, row counts, duplicate deduplication, and a sample template download.
- ✍️ **Rich Text HTML Composer**: WYSIWYG rich text editor using Quill.js supporting variable buttons (`{name}`, `{email}`) and a side-by-side compiled live preview.
- ⚙️ **Custom SMTP and Queue Constraints**: Configure Gmail TLS credentials, daily delivery limit (default 20), delay throttle seconds between emails, and daily start schedule window.
- 🛠️ **SMTP Connection Tester**: Asynchronous credential validator to test SMTP login credentials before launching campaigns.
- 🔄 **Campaign Queue Actions**: Individual buttons to Start, Pause, Resume, Stop, Delete campaigns, and reset failed contacts for quick retries.
- 📄 **Logging Exporter**: Flat-file logging (`logs/sent.log`, `logs/failed.log`, `logs/error.log`) and direct database logs export to CSV.
- 🌓 **Dynamic Interface**: Dark/Light mode selector synced to browser local storage.

---

## Project Structure

```
email_automation/
├── app.py                  # Main Flask Web App & routing
├── config.py               # Flask environments and directory initialization
├── database.py             # SQLAlchemy models schema
├── mailer.py               # SMTP engine & flat-file log writers
├── scheduler.py            # Background worker thread (rate limits & queue resets)
├── requirements.txt        # Backend dependencies
│
├── database/
│   └── database.db         # Self-initialized SQLite DB file
├── uploads/                # Directory for CSV file uploads
├── logs/
│   ├── sent.log            # Successful delivery logs (timestamped)
│   ├── failed.log          # Delivery failures list (timestamped)
│   └── error.log           # System-level error trace logs
│
├── templates/              # Jinja2 HTML views
│   ├── base.html           # Core layout header/sidebar view
│   ├── login.html          # Authentication - Login
│   ├── register.html       # Authentication - Register
│   ├── dashboard.html      # Overview & Campaign controls
│   ├── upload.html         # CSV Upload and Client Parser Preview
│   ├── composer.html       # Quill WYSIWYG Editor and live renders
│   ├── settings.html       # SMTP & Throttle config
│   └── logs.html           # Historical delivery registries
│
└── static/                 # Static Assets
    ├── css/
    │   └── style.css       # Custom stylesheets & Dark mode properties
    └── js/
        └── main.js         # CSV parser, theme toggles, and status triggers
```

---

## Installation & Setup Guide

### 1. Prerequisites
Make sure you have **Python 3.8+** installed on your system.

### 2. Clone/Copy the Codebase
Navigate to the directory containing the project:
```bash
cd "c:\desktop\email automated"
```

### 3. Create a Virtual Environment
It is highly recommended to isolate dependencies inside a virtual environment:
```powershell
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate on macOS / Linux
source venv/bin/activate
```

### 4. Install Dependencies
Run `pip` to install requirements:
```bash
pip install -r requirements.txt
```

---

## Gmail App Password Configuration Guide

To protect your account, Gmail **does not allow** logging in using your standard email password through third-party smtplib scripts. You must generate an **App Password**:

1. Log in to your [Google Account Dashboard](https://myaccount.google.com/).
2. Navigate to **Security** on the left menu.
3. Under *How you sign in to Google*, make sure **2-Step Verification** is turned **ON**. (This is required by Google to create App Passwords).
4. Click on **2-Step Verification** and scroll down to the bottom where you'll find **App passwords**.
5. Select "App passwords" (you may be asked to authenticate).
6. Enter an application name (e.g., `MAIL SARTHI`) and click **Create**.
7. Google will display a **16-character code** (e.g., `abcd efgh ijkl mnop`). Copy this code.
8. Paste this 16-character code into the **Gmail App Password** field on the settings page of MAIL SARTHI.

---

## Running the Application

Once dependencies are installed, you can launch the application:

```bash
python app.py
```

The system will:
1. Automatically create missing folders (`database/`, `uploads/`, `logs/`).
2. Run database migration mappings to create `database.db`.
3. Spawn a background thread running the queue scheduler.
4. Launch the web application on local port `5000`.

Open your browser and navigate to:
**[http://127.0.5.1:5000](http://127.0.0.1:5000)** (or `http://localhost:5000`)

---

## Security Features

1. **CSRF Protection**: All POST forms and AJAX requests are validated using token hashes (Flask-WTF).
2. **Password Encryption**: Accounts passwords are hashed with PBKDF2 cryptography algorithms.
3. **Parameterized SQL Queries**: All interactions use SQLAlchemy ORM wrappers, which automatically parameterize values, nullifying SQL injection risks.
4. **Local Database Security**: SQLite stores configurations locally. SMTP App Passwords are never sent to third-party endpoints.
