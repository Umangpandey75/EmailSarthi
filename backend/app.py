import os
import csv
from io import StringIO
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_cors import CORS

from config import Config
from database import db, User, Settings, Campaign, Contact, EmailTemplate, EmailLog
from mailer import test_smtp_connection, log_to_file, send_campaign_email
from scheduler import start_scheduler, stop_scheduler

app = Flask(__name__)
app.config.from_object(Config)

# Enable CORS for Frontend (Allow Credentials for session cookies)
allowed_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000').split(',')
CORS(app, supports_credentials=True, origins=allowed_origins)

# Enable CSRF Protection
csrf = CSRFProtect(app)

# Disable CSRF check on specific routes if needed, but we can provide /api/csrf-token and require X-CSRFToken headers.
# Exempt the login/register/status endpoints if we want, or keep it strict and fetch CSRF token first.
# To make it simple for the frontend, we will keep CSRFProtect on all POST routes,
# and the frontend will fetch the CSRF token on startup and attach it to headers.

# Initialize Database
db.init_app(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Return JSON 401 for unauthorized API requests instead of redirecting to login page
@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'message': 'Unauthorized. Please login.', 'authenticated': False}), 401

# Initialize database tables
with app.app_context():
    db.create_all()
    # Check if 'attachments' column exists in 'campaigns' table (self-healing migration)
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('campaigns')]
        if 'attachments' not in columns:
            db.session.execute(db.text("ALTER TABLE campaigns ADD COLUMN attachments TEXT"))
            db.session.commit()
            print("Database migration: Added 'attachments' column to 'campaigns' table.")
    except Exception as e:
        print(f"Migration warning: {e}")

# Start background scheduler
start_scheduler(app)


# --- GENERAL & CSRF ENDPOINTS ---

@app.route('/api/csrf-token', methods=['GET'])
def get_csrf():
    """Generates and returns a CSRF token for cross-origin forms."""
    token = generate_csrf()
    return jsonify({'csrf_token': token})


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Returns current user's login state."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'username': current_user.username,
            'email': current_user.email
        })
    return jsonify({'authenticated': False})


# --- AUTHENTICATION ENDPOINTS ---

@app.route('/api/auth/register', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return jsonify({'message': 'Already logged in', 'authenticated': True})
        
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    
    if not username or not email or not password:
        return jsonify({'message': 'All fields are required.'}), 400
        
    if password != confirm_password:
        return jsonify({'message': 'Passwords do not match.'}), 400
        
    # Check if username or email exists
    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists.'}), 400
        
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email address already registered.'}), 400
        
    try:
        # Create user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.flush() # Fetch user id before commit
        
        # Create default settings
        default_settings = Settings(
            user_id=new_user.id,
            daily_limit=20,
            delay_seconds=2,
            schedule_time="09:00"
        )
        db.session.add(default_settings)
        db.session.commit()
        
        login_user(new_user)
        return jsonify({
            'success': True,
            'message': 'Account created successfully!',
            'username': username
        })
        
    except Exception as e:
        db.session.rollback()
        log_to_file(Config.ERROR_LOG, f"Registration error for {username}: {str(e)}")
        return jsonify({'message': 'A database error occurred.'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return jsonify({
            'success': True,
            'message': 'Already authenticated.',
            'username': current_user.username
        })
        
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        login_user(user)
        return jsonify({
            'success': True,
            'message': 'Logged in successfully.',
            'username': username
        })
    else:
        return jsonify({'message': 'Invalid username or password.'}), 401


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})


# --- DASHBOARD & ANALYTICS ---

@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    # Calculate statistics
    total_contacts = Contact.query.filter_by(user_id=current_user.id).count()
    sent_emails = EmailLog.query.filter_by(user_id=current_user.id, status='Sent').count()
    failed_emails = EmailLog.query.filter_by(user_id=current_user.id, status='Failed').count()
    
    stats = {
        'total_contacts': total_contacts,
        'sent_emails': sent_emails,
        'failed_emails': failed_emails
    }
    
    # Get settings
    settings_obj = Settings.query.filter_by(user_id=current_user.id).first()
    if not settings_obj:
        settings_obj = Settings(user_id=current_user.id)
        db.session.add(settings_obj)
        db.session.commit()
        
    settings_data = {
        'gmail_address': settings_obj.gmail_address,
        'daily_limit': settings_obj.daily_limit,
        'delay_seconds': settings_obj.delay_seconds,
        'schedule_time': settings_obj.schedule_time,
        'sent_today': settings_obj.sent_today
    }
    
    # Get campaigns
    campaigns = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    campaigns_data = []
    for c in campaigns:
        total = len(c.contacts)
        sent = len([x for x in c.contacts if x.status == 'Sent'])
        failed = len([x for x in c.contacts if x.status == 'Failed'])
        campaigns_data.append({
            'id': c.id,
            'name': c.name,
            'subject': c.subject,
            'status': c.status,
            'created_at': c.created_at.strftime('%Y-%m-%d'),
            'total_contacts': total,
            'sent_contacts': sent,
            'failed_contacts': failed
        })
        
    # Get recent logs
    recent_logs = EmailLog.query.filter_by(user_id=current_user.id).order_by(EmailLog.timestamp.desc()).limit(8).all()
    logs_data = []
    for l in recent_logs:
        logs_data.append({
            'contact_email': l.contact_email,
            'contact_name': l.contact_name,
            'status': l.status,
            'error_message': l.error_message,
            'timestamp': l.timestamp.strftime('%H:%M')
        })
        
    return jsonify({
        'stats': stats,
        'settings': settings_data,
        'campaigns': campaigns_data,
        'recent_logs': logs_data
    })


# --- CSV UPLOAD & CONTACTS ---

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_contacts():
    # If client sends JSON data (e.g. selected contacts list with checkboxes)
    if request.is_json:
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        new_campaign_name = data.get('new_campaign_name', '').strip()
        contacts_data = data.get('contacts', [])
        
        if not contacts_data:
            return jsonify({'message': 'No contacts selected for import.'}), 400
            
        try:
            if campaign_id == 'new':
                if not new_campaign_name:
                    return jsonify({'message': 'Please specify a name for the new campaign.'}), 400
                campaign = Campaign(
                    user_id=current_user.id,
                    name=new_campaign_name,
                    subject="No Subject",
                    body_html="<p>No content composed yet.</p>",
                    status='Draft'
                )
                db.session.add(campaign)
                db.session.flush()
            else:
                campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
                if not campaign:
                    return jsonify({'message': 'Target campaign not found.'}), 404
            
            contacts_added = 0
            seen_emails = set()
            
            existing_contacts = Contact.query.filter_by(campaign_id=campaign.id).all()
            for c in existing_contacts:
                seen_emails.add(c.email.lower())
                
            from email_validator import validate_email, EmailNotValidError
            
            for item in contacts_data:
                email = item.get('email', '').strip()
                name = item.get('name', '').strip()
                
                if not email:
                    continue
                    
                try:
                    valid = validate_email(email, check_deliverability=False)
                    email = valid.email.lower()
                except EmailNotValidError:
                    continue
                    
                if email in seen_emails:
                    continue
                    
                seen_emails.add(email)
                
                contact = Contact(
                    user_id=current_user.id,
                    campaign_id=campaign.id,
                    email=email,
                    name=name,
                    status='Pending'
                )
                db.session.add(contact)
                contacts_added += 1
                
            db.session.commit()
            return jsonify({
                'success': True,
                'message': f"Successfully imported {contacts_added} contacts to campaign '{campaign.name}'."
            })
        except Exception as e:
            db.session.rollback()
            log_to_file(Config.ERROR_LOG, f"JSON contacts import exception: {str(e)}")
            return jsonify({'message': f"An error occurred while importing contacts: {str(e)}"}), 500

    campaign_id = request.form.get('campaign_id')
    new_campaign_name = request.form.get('new_campaign_name', '').strip()
    csv_file = request.files.get('csv_file')
    
    if not csv_file:
        return jsonify({'message': 'No file uploaded.'}), 400
        
    filename = csv_file.filename.lower()
    
    try:
        # Determine file type and parse accordingly
        if filename.endswith('.csv'):
            stream = StringIO(csv_file.stream.read().decode("utf-8", errors='ignore'), newline=None)
            reader = csv.reader(stream)
            rows = list(reader)
        elif filename.endswith(('.xlsx', '.xls', '.xlsm', '.xlsb', '.ods')):
            import pandas as pd
            try:
                # Read Excel spreadsheet using pandas
                df = pd.read_excel(csv_file)
                df = df.fillna("")
                headers = [str(h) for h in df.columns]
                rows = [headers] + df.values.tolist()
            except Exception as ex:
                return jsonify({'message': f'Failed to parse Excel spreadsheet: {str(ex)}'}), 400
        else:
            return jsonify({'message': 'Unsupported file format. Please upload CSV or Excel (.xlsx, .xls) files.'}), 400
            
        if len(rows) < 2:
            return jsonify({'message': 'File is empty or missing headers.'}), 400
            
        # Smart header mapping
        headers = [str(h).strip().lower() for h in rows[0]]
        
        # Look for email index
        email_idx = -1
        email_terms = ['email', 'email address', 'emailid', 'email_address', 'mail', 'mail address', 'contact email']
        for term in email_terms:
            if term in headers:
                email_idx = headers.index(term)
                break
        if email_idx == -1:
            for idx, h in enumerate(headers):
                if 'email' in h or 'mail' in h:
                    email_idx = idx
                    break
                    
        if email_idx == -1:
            return jsonify({'message': "File must contain an 'email' column (e.g. 'email', 'email address', 'mail')."}), 400
            
        # Look for name index
        name_idx = -1
        name_terms = ['name', 'full name', 'fullname', 'contact name', 'recipient name', 'customer name', 'username', 'first name']
        for term in name_terms:
            if term in headers:
                name_idx = headers.index(term)
                break
        if name_idx == -1:
            for idx, h in enumerate(headers):
                if 'name' in h:
                    name_idx = idx
                    break
        
        if campaign_id == 'new':
            if not new_campaign_name:
                return jsonify({'message': 'Please specify a name for the new campaign.'}), 400
            campaign = Campaign(
                user_id=current_user.id,
                name=new_campaign_name,
                subject="No Subject",
                body_html="<p>No content composed yet.</p>",
                status='Draft'
            )
            db.session.add(campaign)
            db.session.flush()
        else:
            campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
            if not campaign:
                return jsonify({'message': 'Target campaign not found.'}), 404
        
        contacts_added = 0
        seen_emails = set()
        
        existing_contacts = Contact.query.filter_by(campaign_id=campaign.id).all()
        for c in existing_contacts:
            seen_emails.add(c.email.lower())
            
        from email_validator import validate_email, EmailNotValidError
        
        for row in rows[1:]:
            if not row or len(row) <= email_idx:
                continue
                
            email = str(row[email_idx]).strip()
            name = str(row[name_idx]).strip() if name_idx != -1 and len(row) > name_idx else ''
            
            if not email:
                continue
                
            try:
                valid = validate_email(email, check_deliverability=False)
                email = valid.email.lower()
            except EmailNotValidError:
                continue
                
            if email in seen_emails:
                continue
                
            seen_emails.add(email)
            
            contact = Contact(
                user_id=current_user.id,
                campaign_id=campaign.id,
                email=email,
                name=name,
                status='Pending'
            )
            db.session.add(contact)
            contacts_added += 1
            
        db.session.commit()
        return jsonify({
            'success': True,
            'message': f"Successfully imported {contacts_added} contacts to campaign '{campaign.name}'."
        })
        
    except Exception as e:
        db.session.rollback()
        log_to_file(Config.ERROR_LOG, f"CSV parsing exception: {str(e)}")
        return jsonify({'message': f"An error occurred while importing contacts: {str(e)}"}), 500


@app.route('/api/campaigns', methods=['GET'])
@login_required
def get_campaigns():
    # Helper to get user's campaigns
    campaigns = Campaign.query.filter_by(user_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    campaigns_data = []
    for c in campaigns:
        campaigns_data.append({
            'id': c.id,
            'name': c.name,
            'subject': c.subject,
            'status': c.status,
            'contacts_count': len(c.contacts)
        })
    return jsonify({'campaigns': campaigns_data})


@app.route('/api/campaigns/<int:campaign_id>', methods=['GET'])
@login_required
def get_campaign_detail(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign not found'}), 404
        
    import json
    attach_list = []
    if campaign.attachments:
        try:
            attach_list = json.loads(campaign.attachments)
        except:
            pass
            
    return jsonify({
        'id': campaign.id,
        'name': campaign.name,
        'subject': campaign.subject,
        'body_html': campaign.body_html,
        'attachments': attach_list
    })


@app.route('/api/save-campaign', methods=['POST'])
@login_required
def save_campaign_content():
    campaign_id = request.form.get('campaign_id')
    subject = request.form.get('subject', '').strip()
    body_html = request.form.get('body_html', '').strip()
    save_as_template = request.form.get('save_as_template') == 'true'
    template_name = request.form.get('template_name', '').strip()
    attachments = request.files.getlist('attachments')
    
    if not campaign_id or not subject or not body_html:
        return jsonify({'message': 'Campaign selection, subject and body content are required.'}), 400
        
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign list not found.'}), 404
        
    try:
        campaign.subject = subject
        campaign.body_html = body_html
        
        # Save uploaded files as attachments
        import json
        existing_attachments = []
        if campaign.attachments:
            try:
                existing_attachments = json.loads(campaign.attachments)
            except:
                pass
                
        # Make attachments directory
        attach_dir = os.path.join(Config.UPLOAD_FOLDER, 'attachments', str(campaign.id))
        os.makedirs(attach_dir, exist_ok=True)
        
        for file in attachments:
            if file and file.filename != '':
                filename = file.filename
                file.save(os.path.join(attach_dir, filename))
                if filename not in existing_attachments:
                    existing_attachments.append(filename)
                    
        campaign.attachments = json.dumps(existing_attachments) if existing_attachments else None
        
        if save_as_template and template_name:
            new_template = EmailTemplate(
                user_id=current_user.id,
                name=template_name,
                subject=subject,
                body_html=body_html
            )
            db.session.add(new_template)
            
        db.session.commit()
        return jsonify({'success': True, 'message': 'Campaign content and attachments saved successfully.'})
        
    except Exception as e:
        db.session.rollback()
        log_to_file(Config.ERROR_LOG, f"Campaign save exception: {str(e)}")
        return jsonify({'message': f'Error saving campaign: {str(e)}'}), 500


@app.route('/api/campaigns/<int:campaign_id>/status', methods=['POST'])
@login_required
def campaign_status_change(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign not found'}), 404
        
    data = request.get_json() or {}
    new_status = data.get('status')
    
    if new_status not in ['Running', 'Paused', 'Stopped', 'Draft']:
        return jsonify({'message': 'Invalid status state'}), 400
        
    if new_status == 'Running':
        settings = Settings.query.filter_by(user_id=current_user.id).first()
        if not settings or not settings.gmail_address or not settings.gmail_app_password:
            return jsonify({
                'message': 'Unable to start. Please configure your Gmail SMTP settings first.'
            }), 400
            
    campaign.status = new_status
    db.session.commit()
    return jsonify({'success': True, 'message': f'Campaign status updated to {new_status}'})


@app.route('/api/campaigns/<int:campaign_id>/retry', methods=['POST'])
@login_required
def campaign_retry_failed(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign not found'}), 404
        
    try:
        failed_contacts = Contact.query.filter_by(campaign_id=campaign.id, status='Failed').all()
        for contact in failed_contacts:
            contact.status = 'Pending'
            contact.error_message = None
            
        campaign.status = 'Running'
        db.session.commit()
        return jsonify({'success': True, 'message': f'Marked {len(failed_contacts)} failed emails for retry.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Failed to reset contacts: {str(e)}'}), 500


@app.route('/api/campaigns/<int:campaign_id>/reset', methods=['POST'])
@login_required
def campaign_reset_contacts(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign not found'}), 404
        
    try:
        contacts = Contact.query.filter_by(campaign_id=campaign.id).all()
        for contact in contacts:
            contact.status = 'Pending'
            contact.error_message = None
            contact.last_attempt = None
            
        campaign.status = 'Draft'
        db.session.commit()
        return jsonify({'success': True, 'message': f'Reset all {len(contacts)} contacts to Pending.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Failed to reset campaign: {str(e)}'}), 500


@app.route('/api/campaigns/<int:campaign_id>/attachments/<string:filename>/delete', methods=['POST'])
@login_required
def delete_campaign_attachment(campaign_id, filename):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign not found'}), 404
        
    import json
    try:
        attach_list = []
        if campaign.attachments:
            attach_list = json.loads(campaign.attachments)
            
        if filename in attach_list:
            attach_list.remove(filename)
            campaign.attachments = json.dumps(attach_list) if attach_list else None
            
            # Delete file from disk
            filepath = os.path.join(Config.UPLOAD_FOLDER, 'attachments', str(campaign.id), filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                
            db.session.commit()
            return jsonify({'success': True, 'message': f'Attachment {filename} deleted.', 'attachments': attach_list})
        else:
            return jsonify({'message': 'Attachment not found in campaign list.'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting attachment: {str(e)}'}), 500


@app.route('/api/campaigns/<int:campaign_id>/delete', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    campaign = Campaign.query.filter_by(id=campaign_id, user_id=current_user.id).first()
    if not campaign:
        return jsonify({'message': 'Campaign not found'}), 404
        
    try:
        db.session.delete(campaign)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Campaign and all associated contact records deleted.'})
    except Exception as e:
        db.session.rollback()
        log_to_file(Config.ERROR_LOG, f"Delete campaign exception: {str(e)}")
        return jsonify({'message': 'Failed to delete campaign.'}), 500


# --- TEMPLATE LIBRARY ---

@app.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    templates = EmailTemplate.query.filter_by(user_id=current_user.id).order_by(EmailTemplate.created_at.desc()).all()
    templates_data = []
    for t in templates:
        templates_data.append({
            'id': t.id,
            'name': t.name,
            'subject': t.subject,
            'body_preview': t.body_html[:100],
            'created_at': t.created_at.strftime('%Y-%m-%d')
        })
    return jsonify({'templates': templates_data})


@app.route('/api/templates/<int:template_id>', methods=['GET'])
@login_required
def get_template_detail(template_id):
    template = EmailTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not template:
        return jsonify({'message': 'Template not found'}), 404
        
    return jsonify({
        'id': template.id,
        'name': template.name,
        'subject': template.subject,
        'body_html': template.body_html
    })


@app.route('/api/templates/<int:template_id>/delete', methods=['POST'])
@login_required
def delete_template(template_id):
    template = EmailTemplate.query.filter_by(id=template_id, user_id=current_user.id).first()
    if not template:
        return jsonify({'message': 'Template not found'}), 404
        
    try:
        db.session.delete(template)
        db.session.commit()
        return jsonify({'success': True, 'message': f"Template '{template.name}' deleted successfully."})
    except Exception as e:
        db.session.rollback()
        log_to_file(Config.ERROR_LOG, f"Delete template exception: {str(e)}")
        return jsonify({'message': 'Failed to delete template.'}), 500


# --- SMTP SETTINGS ---

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def user_settings():
    settings_obj = Settings.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        data = request.get_json() or {}
        gmail_address = data.get('gmail_address', '').strip()
        gmail_app_password = data.get('gmail_app_password', '').strip()
        daily_limit = int(data.get('daily_limit', 20))
        delay_seconds = int(data.get('delay_seconds', 2))
        schedule_time = data.get('schedule_time', '09:00').strip()
        
        if not settings_obj:
            settings_obj = Settings(user_id=current_user.id)
            db.session.add(settings_obj)
            
        try:
            settings_obj.gmail_address = gmail_address
            settings_obj.gmail_app_password = gmail_app_password
            settings_obj.daily_limit = daily_limit
            settings_obj.delay_seconds = delay_seconds
            settings_obj.schedule_time = schedule_time
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'SMTP configuration saved successfully.'})
        except Exception as e:
            db.session.rollback()
            log_to_file(Config.ERROR_LOG, f"Settings save error: {str(e)}")
            return jsonify({'message': f"Error saving settings: {str(e)}"}), 500
            
    # GET settings
    if not settings_obj:
        settings_obj = Settings(user_id=current_user.id)
        db.session.add(settings_obj)
        db.session.commit()
        
    return jsonify({
        'gmail_address': settings_obj.gmail_address,
        'gmail_app_password': settings_obj.gmail_app_password,
        'daily_limit': settings_obj.daily_limit,
        'delay_seconds': settings_obj.delay_seconds,
        'schedule_time': settings_obj.schedule_time
    })


@app.route('/api/settings/test-smtp', methods=['POST'])
@login_required
def smtp_verify():
    data = request.get_json() or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not email or not password:
        return jsonify({'message': 'Gmail credentials cannot be empty.'}), 400
        
    success, msg = test_smtp_connection(email, password)
    if success:
        return jsonify({'success': True, 'message': msg})
    else:
        return jsonify({'message': msg}), 400


@app.route('/api/send-email', methods=['POST'])
@login_required
def send_single_email():
    settings_obj = Settings.query.filter_by(user_id=current_user.id).first()
    if not settings_obj:
        return jsonify({'message': 'Please configure your Gmail SMTP settings in Settings first.'}), 400
        
    recipient_email = request.form.get('recipient_email', '').strip()
    recipient_name = request.form.get('recipient_name', '').strip()
    subject = request.form.get('subject', '').strip()
    body_html = request.form.get('body_html', '').strip()
    attachments = request.files.getlist('attachments')
    
    if not recipient_email or not subject or not body_html:
        return jsonify({'message': 'Recipient email, subject, and body are required.'}), 400
        
    if not settings_obj.gmail_address or not settings_obj.gmail_app_password:
        return jsonify({'message': 'Please configure your Gmail SMTP settings before sending.'}), 400
        
    from email_validator import validate_email, EmailNotValidError
    try:
        valid = validate_email(recipient_email, check_deliverability=False)
        recipient_email = valid.email
    except EmailNotValidError:
        return jsonify({'message': 'Please enter a valid recipient email address.'}), 400
        
    # Reset daily counter if calendar day changed
    from datetime import date
    today = date.today()
    if settings_obj.last_reset_date < today:
        settings_obj.sent_today = 0
        settings_obj.last_reset_date = today
        db.session.commit()
        
    if settings_obj.sent_today >= settings_obj.daily_limit:
        return jsonify({'message': f'Daily send limit reached ({settings_obj.daily_limit}). Try again tomorrow or increase the limit in Settings.'}), 400
        
    attachment_paths = []
    temp_dir = os.path.join(Config.UPLOAD_FOLDER, 'single', str(current_user.id))
    try:
        if attachments:
            os.makedirs(temp_dir, exist_ok=True)
            for file in attachments:
                if file and file.filename:
                    filepath = os.path.join(temp_dir, file.filename)
                    file.save(filepath)
                    attachment_paths.append(filepath)
                    
        success, error_msg = send_campaign_email(
            settings_obj,
            recipient_email,
            recipient_name,
            subject,
            body_html,
            campaign_name='Single Email',
            attachments=attachment_paths or None
        )
        
        email_log = EmailLog(
            user_id=current_user.id,
            campaign_id=None,
            contact_email=recipient_email,
            contact_name=recipient_name or None,
            status='Sent' if success else 'Failed',
            error_message=error_msg
        )
        db.session.add(email_log)
        
        if success:
            settings_obj.sent_today += 1
            db.session.commit()
            return jsonify({'success': True, 'message': f'Email sent successfully to {recipient_email}.'})
        else:
            db.session.commit()
            return jsonify({'message': f'Failed to send email: {error_msg}'}), 500
            
    except Exception as e:
        db.session.rollback()
        log_to_file(Config.ERROR_LOG, f"Single email send exception: {str(e)}")
        return jsonify({'message': f'An error occurred while sending: {str(e)}'}), 500
    finally:
        for path in attachment_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


# --- LOGS LIST & EXPORTS ---

@app.route('/api/logs', methods=['GET'])
@login_required
def view_logs():
    query = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    
    log_query = EmailLog.query.filter_by(user_id=current_user.id)
    
    if query:
        log_query = log_query.filter(
            (EmailLog.contact_email.like(f"%{query}%")) | 
            (EmailLog.contact_name.like(f"%{query}%"))
        )
        
    if status in ['Sent', 'Failed']:
        log_query = log_query.filter_by(status=status)
        
    logs = log_query.order_by(EmailLog.timestamp.desc()).all()
    logs_data = []
    for l in logs:
        logs_data.append({
            'timestamp': l.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'campaign_name': l.campaign.name if l.campaign else 'Deleted Campaign',
            'contact_name': l.contact_name,
            'contact_email': l.contact_email,
            'status': l.status,
            'error_message': l.error_message
        })
    return jsonify({'logs': logs_data})


@app.route('/api/logs/download/<type>', methods=['GET'])
@login_required
def download_logs(type):
    if type not in ['all', 'sent', 'failed']:
        return jsonify({'message': 'Invalid log category.'}), 400
        
    log_query = EmailLog.query.filter_by(user_id=current_user.id)
    if type == 'sent':
        log_query = log_query.filter_by(status='Sent')
    elif type == 'failed':
        log_query = log_query.filter_by(status='Failed')
        
    logs = log_query.order_by(EmailLog.timestamp.desc()).all()
    
    def generate_csv():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Log ID', 'Timestamp (UTC)', 'Campaign', 'Recipient Name', 'Recipient Email', 'Status', 'Details'])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        for log in logs:
            campaign_name = log.campaign.name if log.campaign else 'Deleted Campaign'
            writer.writerow([
                log.id, 
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'), 
                campaign_name, 
                log.contact_name or '', 
                log.contact_email, 
                log.status, 
                log.error_message or 'Success'
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)
            
    headers = {
        'Content-Disposition': f'attachment; filename=email_logs_{type}_{datetime.now().strftime("%Y%m%d%H%M")}.csv',
        'Content-Type': 'text/csv'
    }
    
    return Response(generate_csv(), headers=headers)


if __name__ == '__main__':
    try:
        app.run(debug=True, port=5000)
    finally:
        stop_scheduler()
