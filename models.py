from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Subsection(db.Model):
    """Subsections within main sections"""
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, nullable=False)  # References section ID from constants
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)  # For custom ordering of subsections
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with media
    media_items = db.relationship('Media', backref='subsection', lazy=True, cascade='all, delete-orphan')

class Media(db.Model):
    """Media items (images, videos, PDFs) for subsections"""
    id = db.Column(db.Integer, primary_key=True)
    subsection_id = db.Column(db.Integer, db.ForeignKey('subsection.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'image', 'video', or 'pdf'
    file_path = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    order = db.Column(db.Integer, default=0)  # For custom ordering of media
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Kiosk(db.Model):
    """Kiosks for interactive displays"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with videos
    videos = db.relationship('Video', backref='kiosk', lazy=True, cascade='all, delete-orphan')

class Video(db.Model):
    """Videos that belong to a kiosk"""
    id = db.Column(db.Integer, primary_key=True)
    kiosk_id = db.Column(db.Integer, db.ForeignKey('kiosk.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with buttons
    buttons = db.relationship('Button', backref='video', lazy=True, cascade='all, delete-orphan')

class Button(db.Model):
    """Buttons for videos"""
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Button {self.title}>'

class ButtonMedia(db.Model):
    """Media items for buttons"""
    id = db.Column(db.Integer, primary_key=True)
    button_id = db.Column(db.Integer, db.ForeignKey('button.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # image, video, etc.
    file_path = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship with Button
    button = db.relationship('Button', backref=db.backref('media_items', lazy=True, cascade='all, delete-orphan'))

class Home(db.Model):
    __tablename__ = 'homes'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class HomeMedia(db.Model):
    __tablename__ = 'home_media'
    
    id = db.Column(db.Integer, primary_key=True)
    home_id = db.Column(db.Integer, db.ForeignKey('homes.id', ondelete='CASCADE'), nullable=False)
    media_type = db.Column(db.String(50), nullable=False)  # 'photo', 'floor_plan', 'isometric', 'video'
    file_path = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    home = db.relationship('Home', backref=db.backref('media_items', lazy=True, cascade='all, delete-orphan'))

class FloorPlan(db.Model):
    __tablename__ = 'floor_plans'

    id = db.Column(db.Integer, primary_key=True)
    site_dimension = db.Column(db.String(100), nullable=False)
    facing = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    floors = db.Column(db.String(20), nullable=False)
    floor_plan_path = db.Column(db.String(500), nullable=False)
    elevation_path = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'site_dimension': self.site_dimension,
            'facing': self.facing,
            'type': self.type,
            'floors': self.floors,
            'floor_plan_path': self.floor_plan_path,
            'elevation_path': self.elevation_path,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        } 