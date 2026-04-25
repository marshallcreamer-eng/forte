from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import bcrypt

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(200), nullable=False, unique=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default='staff')  # admin | staff
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'), self.password_hash.encode('utf-8')
        )

    @property
    def initials(self):
        parts = self.name.split()
        return (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else self.name[:2].upper()


class Event(db.Model):
    __tablename__ = 'events'
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    date        = db.Column(db.Date, nullable=False)
    end_date    = db.Column(db.Date)
    # category: holiday | admissions | academic | community | achievement | recurring
    category    = db.Column(db.String(30), default='community')
    source      = db.Column(db.String(20), default='manual')  # preloaded | imported | manual
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    drafts = db.relationship('Draft', backref='event', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id':          self.id,
            'title':       self.title,
            'description': self.description or '',
            'date':        self.date.isoformat(),
            'end_date':    self.end_date.isoformat() if self.end_date else None,
            'category':    self.category,
            'source':      self.source,
        }

    def draft_summary(self):
        """Return per-platform status for dashboard display."""
        summary = {}
        for d in sorted(self.drafts, key=lambda x: x.generated_at, reverse=True):
            if d.platform not in summary:
                summary[d.platform] = {
                    'id':           d.id,
                    'status':       d.status,
                    'content':      d.content,
                    'photo_brief':  d.photo_brief or '',
                    'scheduled_for': d.scheduled_for.isoformat() if d.scheduled_for else None,
                }
        return summary


class Category(db.Model):
    __tablename__ = 'categories'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(60), nullable=False)
    slug       = db.Column(db.String(40), nullable=False, unique=True)
    color      = db.Column(db.String(7), default='#64748b')
    is_preset  = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=99)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'slug': self.slug, 'color': self.color,
            'is_preset': self.is_preset, 'sort_order': self.sort_order,
        }


class Draft(db.Model):
    __tablename__ = 'drafts'
    id            = db.Column(db.Integer, primary_key=True)
    event_id      = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    platform      = db.Column(db.String(20), nullable=False)
    content       = db.Column(db.Text, nullable=False)
    photo_brief   = db.Column(db.Text, default='')   # what photo to take
    tone_override = db.Column(db.String(200), default='')
    # status: needs_post | draft_ready | scheduled | posted
    status        = db.Column(db.String(20), default='draft_ready')
    scheduled_for = db.Column(db.DateTime)
    generated_at  = db.Column(db.DateTime, default=datetime.utcnow)
    copied_at     = db.Column(db.DateTime)

    def to_dict(self):
        return {
            'id':            self.id,
            'event_id':      self.event_id,
            'platform':      self.platform,
            'content':       self.content,
            'photo_brief':   self.photo_brief or '',
            'tone_override': self.tone_override or '',
            'status':        self.status,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'generated_at':  self.generated_at.isoformat(),
        }
