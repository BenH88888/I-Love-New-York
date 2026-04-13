"""
Routes: React app serving and places search API.

To enable AI chat, set USE_LLM = True below. See llm_routes.py for AI code.
"""
import os
from flask import send_from_directory, request, jsonify
from models import db, Place
from algo import get_results_svd, rebuild_search_index

# ── AI toggle ────────────────────────────────────────────────────────────────
USE_LLM = False
# USE_LLM = True
# ─────────────────────────────────────────────────────────────────────────────

PLACES_CACHE = []


def refresh_places_cache(app=None):
    global PLACES_CACHE
    if app is not None:
        with app.app_context():
            PLACES_CACHE = Place.query.all()
    else:
        PLACES_CACHE = Place.query.all()

    rebuild_search_index(places=PLACES_CACHE)


def json_search(query, top=10):
    if not query or not query.strip():
        return []

    if not PLACES_CACHE:
        refresh_places_cache()

    results = get_results_svd(query, top=top, places=PLACES_CACHE)

    if results == []:
        fallback_results = (
            db.session.query(Place)
            .filter(Place.name.ilike(f'%{query}%'))
            .limit(top)
            .all()
        )

        matches = []
        for place in fallback_results:
            matches.append({
                'id': place.id,
                'name': place.name or "",
                'description': place.description or "",
                'rating': place.rating if place.rating is not None else 0,
                'price_level': place.price_level or "",
                'formatted_address': place.formatted_address or "",
                'website_url': place.website_url or "",
                'latitude': place.latitude if place.latitude is not None else 0,
                'longitude': place.longitude if place.longitude is not None else 0,
                'reviews_text_combined': place.reviews_text_combined or ""
            })
        return matches

    return results[:top]


def register_routes(app):
    refresh_places_cache(app)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')

    @app.route("/api/config")
    def config():
        return jsonify({"use_llm": USE_LLM})

    @app.route("/api/places")
    def places_search():
        text = request.args.get("name", "")
        return jsonify(json_search(text, top=10))

    if USE_LLM:
        from llm_routes import register_chat_route
        register_chat_route(app, json_search)