import csv
import json
import os
from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import inspect, text

load_dotenv()
from flask_cors import CORS
from models import Place, db
from routes import register_routes

# src/ directory and project root (one level up)
current_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_directory)

# Serve React build files from <project_root>/frontend/dist
app = Flask(__name__,
    static_folder=os.path.join(project_root, 'frontend', 'dist'),
    static_url_path='')
CORS(app)

# Configure SQLite database - using 3 slashes for relative path
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with app
db.init_app(app)

# Function to initialize database, change this to your own database initialization logic
def init_db():
    with app.app_context():
        # Create tables if they don't exist yet
        db.create_all()

        # Ensure the new column exists on the existing table schema.
        inspector = inspect(db.engine)
        if 'places' in inspector.get_table_names():
            existing_columns = [col['name'] for col in inspector.get_columns('places')]
            if 'reviews_text_combined' not in existing_columns:
                db.session.execute(text('ALTER TABLE places ADD COLUMN reviews_text_combined TEXT'))
                db.session.commit()
                print('Added missing column reviews_text_combined to places table')

        # Populate the places table only when it is empty.
        if Place.query.count() == 0:
            csv_path = os.path.join(project_root, 'src', 'data', 'all_places_refined.csv')

            with open(csv_path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for info in reader:
                    place = Place(
                        name=info['name'],
                        price_level=str(info['price_level']) if info['price_level'] else None,
                        rating=float(info['rating']) if info['rating'] else None,
                        description=info['description'] if info['description'] else None,
                        website_url=info['website_url'] if info['website_url'] else None,
                        formatted_address=info['formatted_address'] if info['formatted_address'] else None,
                        latitude=float(info['latitude']) if info['latitude'] else None,
                        longitude=float(info['longitude']) if info['longitude'] else None,
                        reviews_text_combined=info['reviews_text_combined'] if info['reviews_text_combined'] else None
                    )
                    db.session.add(place)
            db.session.commit()
            print("Database initialized with places data")
        else:
            print("Places table already contains data; skipping CSV import")
            

        

init_db()

# Register routes
register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)
