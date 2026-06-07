import os
import re
import html
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid, formatdate
from datetime import datetime
from config import Config

def strip_tags(html_content):
    """Dynamically converts HTML email body content into high-quality clean plain-text."""
    if not html_content:
        return ""
    # Replace block level elements with newlines
    text = html_content
    # Replace <br> or <br/> or <br /> with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    # Replace closing paragraph, div, table row, list, and heading tags with newlines
    text = re.sub(r'</?(p|div|tr|h[1-6]|ul|ol)>', '\n', text, flags=re.IGNORECASE)
    # Replace list items with bullet point
    text = re.sub(r'<li>', '\n- ', text, flags=re.IGNORECASE)
    # Remove all other HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Clean up trailing/leading whitespace per line
    lines = [line.strip() for line in text.split('\n')]
    # Remove excessive blank lines (allow max 1 consecutive empty line)
    cleaned_lines = []
    for line in lines:
        if line:
            cleaned_lines.append(line)
        elif not cleaned_lines or cleaned_lines[-1] != "":
            cleaned_lines.append("")
    
    return "\n".join(cleaned_lines).strip()

def log_to_file(file_path, message):
    """Utility to append timestamps and log messages to target log file."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Failed to write to log file {file_path}: {e}")

def test_smtp_connection(email_address, app_password):
    """Tests SMTP connection and credentials validity."""
    if not email_address or not app_password:
        return False, "SMTP settings are incomplete."
    
    try:
        # Connect to Gmail SMTP
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(email_address, app_password)
        server.quit()
        return True, "SMTP Connection successful!"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Please verify your Gmail App Password."
    except Exception as e:
        return False, f"SMTP Connection failed: {str(e)}"

def send_campaign_email(settings, recipient_email, recipient_name, subject, body_html, campaign_name="Campaign", attachments=None):
    """
    Sends a personalized campaign email.
    Returns (success_status, error_message)
    """
    if not settings or not settings.gmail_address or not settings.gmail_app_password:
        err = "SMTP configuration missing or incomplete."
        log_to_file(Config.ERROR_LOG, f"CONFIG ERROR: {err}")
        return False, err
        
    # Replace personalization tags
    # Handle optional recipient name
    safe_name = recipient_name if recipient_name else "there"
    
    personalized_subject = subject.replace("{name}", safe_name).replace("{email}", recipient_email)
    personalized_body = body_html.replace("{name}", safe_name).replace("{email}", recipient_email)
    
    try:
        # Establish TLS SMTP connection
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.starttls()
        server.login(settings.gmail_address, settings.gmail_app_password)
        
        # Build mixed multipart message for attachments
        msg = MIMEMultipart('mixed')
        msg['From'] = settings.gmail_address
        msg['To'] = recipient_email
        msg['Subject'] = personalized_subject
        
        # Explicitly append delivery headers to increase inbox deliverability
        msg['Date'] = formatdate(localtime=True)
        sender_domain = settings.gmail_address.split('@')[-1] if '@' in settings.gmail_address else 'gmail.com'
        msg['Message-ID'] = make_msgid(domain=sender_domain)
        msg['MIME-Version'] = '1.0'
        
        # Body alternative (HTML/Text) nested block
        msg_alternative = MIMEMultipart('alternative')
        
        # Dynamic plain text alternative generated from the personalized HTML body
        plain_text = strip_tags(personalized_body)
        if not plain_text:
            plain_text = f"Hello {safe_name},\n\nPlease view this message in HTML format."
            
        part1 = MIMEText(plain_text, 'plain', 'utf-8')
        part2 = MIMEText(personalized_body, 'html', 'utf-8')
        
        msg_alternative.attach(part1)
        msg_alternative.attach(part2)
        msg.attach(msg_alternative)
        
        # Append attachments if present
        if attachments:
            for filepath in attachments:
                if not os.path.exists(filepath):
                    continue
                filename = os.path.basename(filepath)
                ctype, encoding = mimetypes.guess_type(filepath)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                
                with open(filepath, 'rb') as f:
                    part = MIMEBase(maintype, subtype)
                    part.set_payload(f.read())
                    
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(part)
        
        # Send
        server.sendmail(settings.gmail_address, recipient_email, msg.as_string())
        server.quit()
        
        # Log success
        log_msg = f"SUCCESS: Sent email to {recipient_email} ({safe_name}) for '{campaign_name}'"
        log_to_file(Config.SENT_LOG, log_msg)
        return True, None
        
    except smtplib.SMTPAuthenticationError:
        err_msg = "Authentication failed. Invalid Gmail address or App Password."
        log_to_file(Config.FAILED_LOG, f"FAILED: To {recipient_email} - Error: {err_msg}")
        return False, err_msg
    except Exception as e:
        err_msg = str(e)
        log_to_file(Config.FAILED_LOG, f"FAILED: To {recipient_email} - Error: {err_msg}")
        log_to_file(Config.ERROR_LOG, f"SYSTEM ERROR: Exception during send to {recipient_email} - {err_msg}")
        return False, err_msg
