from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Place(db.Model):
    __tablename__ = 'places'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    price_level = db.Column(db.String(64))
    rating = db.Column(db.Float)
    description = db.Column(db.Text)
    website_url = db.Column(db.String(256))
    formatted_address = db.Column(db.String(256))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    def __repr__(self):
        return f'Restaurant {self.id}: {self.name}'
    
