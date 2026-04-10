"""
Routes: React app serving and places search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
from flask import send_from_directory, request, jsonify
from models import db, Place
from algo import get_results

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────


# Cache places at startup to avoid querying all rows each request
PLACES_CACHE = []

def refresh_places_cache(app=None):
    global PLACES_CACHE
    if app is not None:
        with app.app_context():
            PLACES_CACHE = Place.query.all()
    else:
        PLACES_CACHE = Place.query.all()


def json_search(query):
    if not query or not query.strip():
        query = ""

    if not PLACES_CACHE:
        refresh_places_cache()

    results = get_results(query, places=PLACES_CACHE)

    if results == []:
        results = db.session.query(Place).filter(
            Place.name.ilike(f'%{query}%')
        ).all()
        matches = []
        for place in results:
            matches.append({
                'id': place.id,
                'name': place.name,
                'description': place.description,
                'rating': place.rating,
                'price_level': place.price_level,
                'formatted_address': place.formatted_address,
                'website_url': place.website_url,
                'latitude': place.latitude,
                'longitude': place.longitude,
                'reviews_text_combined': place.reviews_text_combined
            })
        print("name")
        return matches
    return results


def register_routes(app):
    # Ensure the in-memory cache is initialized after DB setup
    refresh_places_cache(app)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')

    @app.route("/api/config")
    def config():
        return jsonify({"use_llm": USE_LLM})

    @app.route("/api/places")
    def places_search():
        text = request.args.get("name", "")
        return jsonify(json_search(text))

    if USE_LLM:
        from llm_routes import register_chat_route
        register_chat_route(app, json_search)
