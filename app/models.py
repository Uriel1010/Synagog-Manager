# file: app/models.py
from datetime import datetime
from app import db, login_manager, bcrypt
from flask_login import UserMixin
from sqlalchemy import Index # Import Index

# User loader required by Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id)) # Use db.session.get for primary key lookup

# Basic User model for authentication
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    # Don't store passwords directly! Store the hash.
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # Simple role check

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# --- Synagogue App Models ---

class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(120), nullable=False)
    gregorian_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hebrew_date = db.Column(db.String(100)) # e.g., "15 Nisan 5784"
    details = db.Column(db.String(200)) # Torah portion or Holiday type
    purchases = db.relationship('Purchase', backref='event', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Event {self.event_name} ({self.id})>'

class Buyer(db.Model):
    __tablename__ = 'buyers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    barcode_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    purchases = db.relationship('Purchase', backref='buyer', lazy='dynamic') # Don't cascade delete buyers if purchase exists

    __table_args__ = (Index('ix_buyers_barcode_id', 'barcode_id'), ) # Explicit index

    def __repr__(self):
        return f'<Buyer {self.name} ({self.barcode_id})>'

class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    barcode_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    is_unique = db.Column(db.Boolean, default=False)
    purchases = db.relationship('Purchase', backref='item', lazy='dynamic') # Don't cascade delete items

    __table_args__ = (Index('ix_items_barcode_id', 'barcode_id'), ) # Explicit index

    def __repr__(self):
        return f'<Item {self.name} ({self.barcode_id})>'

class Purchase(db.Model):
    __tablename__ = 'purchases'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('buyers.id'), nullable=False, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False) # Use Float or Numeric/Decimal depending on precision needs
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    is_manual_entry = db.Column(db.Boolean, default=False)
    manual_entry_notes = db.Column(db.String(300))

    # Relationships defined via backref in Event, Buyer, Item

    def __repr__(self):
        return f'<Purchase {self.id} - Event: {self.event_id}, Buyer: {self.buyer_id}, Item: {self.item_id}>'

# No separate PurchaseDetail model needed, we can construct this info via queries/joins