"""
LLM chat route — only loaded when USE_LLM = True in routes.py.
Adds a POST /api/chat endpoint that performs LLM-driven RAG.

Setup:
  1. Add API_KEY=your_key to .env
  2. Set USE_LLM = True in routes.py
"""
import json
import os
import re
import logging
from flask import request, jsonify, Response, stream_with_context
from infosci_spark_client import LLMClient

logger = logging.getLogger(__name__)


def rewrite_query(client: LLMClient, user_message: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a search-query optimiser for a New York City places database. "
                "The database contains restaurants, museums, parks, landmarks, and hotels. "
                "Each record has a name, description, address, price level, category, and user reviews.\n\n"
                "Your ONLY job: convert the user's question into a short, keyword-rich search "
                "query (3-8 words) that will retrieve the most relevant places from a TF-IDF index. "
                "Output ONLY the query — no explanation, no punctuation, no quotes."
            ),
        },
        {"role": "user", "content": user_message},
    ]
    response = client.chat(messages)
    rewritten = (response.get("content") or user_message).strip()
    logger.info(f"Rewritten query: '{rewritten}'  (original: '{user_message}')")
    return rewritten

def build_rag_context(places: list) -> str:
    if not places:
        return "No relevant places were found in the database."
 
    lines = []
    for i, p in enumerate(places, start=1):
        score = f"{p['similarity_score'] * 100:.1f}%" if p.get("similarity_score") else "N/A"
        lines.append(
            f"[{i}] {p['name']}\n"
            f"    Address : {p.get('formatted_address', 'N/A')}\n"
            f"    Rating  : {p.get('rating', 'N/A')}  |  Price: {p.get('price_level', 'N/A')}  |  Match: {score}\n"
            f"    About   : {p.get('description', '')}\n"
            f"    Reviews : {(p.get('reviews_text_combined') or '')[:300]}"
        )
    return "\n\n".join(lines)



def register_chat_route(app, json_search):
    """Register the /api/chat SSE endpoint. Called from routes.py."""

    @app.route("/api/summary", methods=["POST"])
    def summary():
        data = request.get_json() or {}
        place = data.get("place", {})
        query = data.get("query", "")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an enthusiastic NYC local guide. "
                    "Write 2-3 sentences explaining what makes this place special "
                    "and why it's a great match for the user's search. "
                    "Be specific — mention details from the reviews. Be warm and helpful."
                )
            },
            {
                "role": "user",
                "content": (
                    f"User searched for: {query}\n\n"
                    f"Place: {place.get('name')}\n"
                    f"Description: {place.get('description')}\n"
                    f"Reviews: {(place.get('reviews_text_combined') or '')[:500]}"
                )
            }
        ]

        try:
            client = LLMClient(api_key=os.getenv("API_KEY"))
            raw = client.chat(messages)
            response = (raw.get("content") if isinstance(raw, dict) else raw or "").strip()
            return jsonify({"summary": response})
        except Exception as e:
            logger.error(f"Summary failed: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chat", methods=["POST"])
    def chat():
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()
        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        api_key = os.getenv("API_KEY")
        if not api_key:
            return jsonify({"error": "API_KEY not set — add it to your .env file"}), 500

        client = LLMClient(api_key=api_key)
        modified_query = rewrite_query(client, user_message)

        ir_response = json_search(modified_query, top=10)
        places = ir_response.get("results", []) if isinstance(ir_response, dict) else ir_response
        dimensions = ir_response.get("dimensions", []) if isinstance(ir_response, dict) else []
        context_text = build_rag_context(places)
 
        rag_messages = [
            {
                "role": "system",
                "content": (
                    "You are a friendly New York City local guide. "
                    "Answer the user's question using ONLY the place information provided below. "
                    "Be concise (3-5 sentences). "
                    "Reference specific places by name and mention why each is relevant. "
                    "End with: 'See the results panel on the left for full details.'"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Place information retrieved from our database:\n\n"
                    f"{context_text}\n\n"
                    f"User question: {user_message}"
                ),
            },
        ]

        def generate():
            yield f"data: {json.dumps({'modified_query': modified_query, 'places': places, 'dimensions': dimensions})}\n\n"
            try:
                for chunk in client.chat(rag_messages, stream=True):
                    if chunk.get("content"):
                        yield f"data: {json.dumps({'content': chunk['content']})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': 'Streaming error occurred'})}\n\n"
 
            yield "data: [DONE]\n\n"
 
        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
