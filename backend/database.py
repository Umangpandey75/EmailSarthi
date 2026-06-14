from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(256), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    settings = db.relationship('Settings', back_populates='user', uselist=False, cascade='all, delete-orphan')
    campaigns = db.relationship('Campaign', back_populates='user', cascade='all, delete-orphan')
    templates = db.relationship('EmailTemplate', back_populates='user', cascade='all, delete-orphan')
    logs = db.relationship('EmailLog', back_populates='user', cascade='all, delete-orphan')
    jobs = db.relationship('SchedulerJob', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    
    gmail_address = db.Column(db.String(120), nullable=True)
    gmail_app_password = db.Column(db.String(120), nullable=True)
    daily_limit = db.Column(db.Integer, default=20, nullable=False)
    delay_seconds = db.Column(db.Integer, default=2, nullable=False)
    schedule_time = db.Column(db.String(5), default="09:00", nullable=False)  # format: HH:MM
    
    # Rate Limiting trackers
    last_reset_date = db.Column(db.Date, default=date.today, nullable=False)
    sent_today = db.Column(db.Integer, default=0, nullable=False)
    
    user = db.relationship('User', back_populates='settings')


class Campaign(db.Model):
    __tablename__ = 'campaigns'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Draft', nullable=False)  # Draft, Scheduled, Running, Paused, Stopped, Completed
    attachments = db.Column(db.Text, nullable=True) # Stores list of file names in JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='campaigns')
    contacts = db.relationship('Contact', back_populates='campaign', cascade='all, delete-orphan')
    logs = db.relationship('EmailLog', back_populates='campaign', cascade='all, delete-orphan')
    jobs = db.relationship('SchedulerJob', back_populates='campaign', cascade='all, delete-orphan')


class Contact(db.Model):
    __tablename__ = 'contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    
    email = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default='Pending', nullable=False)  # Pending, Sent, Failed
    last_attempt = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    campaign = db.relationship('Campaign', back_populates='contacts')


class EmailTemplate(db.Model):
    __tablename__ = 'templates'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    body_html = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='templates')


class EmailLog(db.Model):
    __tablename__ = 'logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='SET NULL'), nullable=True)
    
    contact_email = db.Column(db.String(120), nullable=False)
    contact_name = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), nullable=False)  # Sent, Failed
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    error_message = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', back_populates='logs')
    campaign = db.relationship('Campaign', back_populates='logs')


class SchedulerJob(db.Model):
    __tablename__ = 'scheduler_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=False)
    
    run_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Pending', nullable=False)  # Pending, Running, Completed, Failed
    error_message = db.Column(db.Text, nullable=True)
    
    user = db.relationship('User', back_populates='jobs')
    campaign = db.relationship('Campaign', back_populates='jobs')
