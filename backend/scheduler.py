import time
import os
from datetime import datetime, date
import threading
from database import db, Campaign, Contact, Settings, EmailLog, SchedulerJob
from mailer import send_campaign_email, log_to_file
from config import Config

# Global variable to track active scheduler thread
_scheduler_thread = None
_scheduler_lock = threading.Lock()
scheduler_running = False

def get_current_local_time():
    return datetime.now().strftime('%H:%M')

def scheduler_loop(app):
    """Main background loop for the scheduler."""
    global scheduler_running
    print("Email campaign scheduler thread started.")
    
    with app.app_context():
        # On thread start, ensure any campaigns marked 'Running' from a previous crash
        # are safely handled. We can either keep them running or pause them.
        pass

    while scheduler_running:
        try:
            with app.app_context():
                # 1. Reset daily limits for settings where calendar day has changed
                today = date.today()
                settings_to_reset = Settings.query.filter(Settings.last_reset_date < today).all()
                for setting in settings_to_reset:
                    setting.sent_today = 0
                    setting.last_reset_date = today
                if settings_to_reset:
                    db.session.commit()
                
                # 2. Find campaigns in 'Running' state
                running_campaigns = Campaign.query.filter_by(status='Running').all()
                
                for campaign in running_campaigns:
                    user_settings = Settings.query.filter_by(user_id=campaign.user_id).first()
                    
                    if not user_settings:
                        # Skip campaign if user hasn't configured settings
                        continue
                        
                    # Check schedule window
                    if user_settings.schedule_time:
                        current_time = get_current_local_time()
                        if current_time < user_settings.schedule_time:
                            # It's before the daily scheduled sending window, skip for now
                            continue
                            
                    # Check daily limit
                    if user_settings.sent_today >= user_settings.daily_limit:
                        # Limit reached for today. We log it and skip this user's campaigns
                        log_msg = f"LIMIT REACHED: User {campaign.user_id} daily limit ({user_settings.daily_limit}) reached. Delaying campaign '{campaign.name}'."
                        print(log_msg)
                        # We don't pause the campaign automatically, so it resumes tomorrow.
                        continue
                    
                    # Find next pending contact
                    next_contact = Contact.query.filter_by(
                        campaign_id=campaign.id, 
                        status='Pending'
                    ).first()
                    
                    if not next_contact:
                        # If no pending, mark campaign completed
                        campaign.status = 'Completed'
                        db.session.commit()
                        log_to_file(Config.SENT_LOG, f"CAMPAIGN COMPLETED: '{campaign.name}' finished sending.")
                        continue
                    
                    # Process Email Sending
                    # Increment settings limit counter before sending to prevent race conditions
                    user_settings.sent_today += 1
                    db.session.commit()
                    
                    # Resolve attachments
                    campaign_attachments = []
                    if campaign.attachments:
                        import json
                        try:
                            filenames = json.loads(campaign.attachments)
                            for fname in filenames:
                                fpath = os.path.join(Config.UPLOAD_FOLDER, 'attachments', str(campaign.id), fname)
                                if os.path.exists(fpath):
                                    campaign_attachments.append(fpath)
                        except Exception as e:
                            pass

                    print(f"Sending email in campaign '{campaign.name}' to {next_contact.email}...")
                    
                    success, error_msg = send_campaign_email(
                        settings=user_settings,
                        recipient_email=next_contact.email,
                        recipient_name=next_contact.name,
                        subject=campaign.subject,
                        body_html=campaign.body_html,
                        campaign_name=campaign.name,
                        attachments=campaign_attachments
                    )
                    
                    # Update contact status
                    if success:
                        next_contact.status = 'Sent'
                    else:
                        next_contact.status = 'Failed'
                        next_contact.error_message = error_msg
                        if error_msg and "Authentication failed" in error_msg:
                            user_settings.sent_today = max(0, user_settings.sent_today - 1)
                            
                    next_contact.last_attempt = datetime.utcnow()
                    
                    # Insert Log record
                    new_log = EmailLog(
                        user_id=campaign.user_id,
                        campaign_id=campaign.id,
                        contact_email=next_contact.email,
                        contact_name=next_contact.name,
                        status='Sent' if success else 'Failed',
                        error_message=error_msg
                    )
                    db.session.add(new_log)
                    db.session.commit()
                    
                    # Apply individual mail delay (throttle rate)
                    if user_settings.delay_seconds > 0:
                        time.sleep(user_settings.delay_seconds)
                        
        except Exception as e:
            err_msg = f"Scheduler main loop error: {str(e)}"
            print(err_msg)
            # Log to file
            log_to_file(Config.ERROR_LOG, err_msg)
            
        # Idle sleep between queue polls (e.g. 5 seconds)
        time.sleep(5)

def start_scheduler(app):
    """Starts the background scheduler thread if not already running."""
    global _scheduler_thread, scheduler_running
    
    # Avoid starting thread multiple times in Flask development server due to hot reloader
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true' and app.debug:
        print("Skipping scheduler startup in master process (loader). Will start in reloaded worker.")
        return
        
    with _scheduler_lock:
        if not scheduler_running:
            scheduler_running = True
            _scheduler_thread = threading.Thread(target=scheduler_loop, args=(app,), daemon=True)
            _scheduler_thread.start()
            print("Background email scheduler started successfully.")

def stop_scheduler():
    """Signals the scheduler thread to stop."""
    global scheduler_running
    with _scheduler_lock:
        if scheduler_running:
            scheduler_running = False
            print("Background email scheduler stop signal sent.")
