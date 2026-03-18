"""
Routes: React app serving and places search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import json
import os
from flask import send_from_directory, request, jsonify
from models import db, Place

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────


def json_search(query):
    if not query or not query.strip():
        query = ""
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
            'longitude': place.longitude
        })
    return matches


def register_routes(app):
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
