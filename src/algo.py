from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from models import Place


SEARCH_INDEX = {
    "places": [],
    "vectorizer": None,
    "tfidf_matrix": None,
    "svd": None,
    "doc_vectors": None,
}


def _build_combined_text(place):
    name = place.name or ""
    description = place.description or ""
    address = place.formatted_address or ""
    price = str(place.price_level) if place.price_level is not None else ""
    reviews = place.reviews_text_combined or ""

    return f"{name} {description} {address} {price} {reviews}".strip()


def build_search_index(places=None):
    global SEARCH_INDEX

    if places is None:
        places = Place.query.all()

    places = list(places)

    if len(places) == 0:
        SEARCH_INDEX = {
            "places": [],
            "vectorizer": None,
            "tfidf_matrix": None,
            "svd": None,
            "doc_vectors": None,
        }
        return

    combined = [_build_combined_text(place) for place in places]

    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        max_df=0.9,
        min_df=1
    )

    tfidf_matrix = vectorizer.fit_transform(combined)

    n_docs, n_terms = tfidf_matrix.shape
    use_svd = min(n_docs - 1, n_terms - 1) >= 2

    svd = None
    doc_vectors = tfidf_matrix

    if use_svd:
        n_components = min(100, n_docs - 1, n_terms - 1)
        svd = TruncatedSVD(n_components=n_components, random_state=4300)
        doc_vectors = svd.fit_transform(tfidf_matrix)

    SEARCH_INDEX = {
        "places": places,
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "svd": svd,
        "doc_vectors": doc_vectors,
    }


def rebuild_search_index(places=None):
    build_search_index(places=places)


def get_results(query, top=10, places=None):
    if places is not None:
        build_search_index(places=places)

    if not query or not query.strip():
        return []

    if SEARCH_INDEX["vectorizer"] is None or len(SEARCH_INDEX["places"]) == 0:
        build_search_index(places=places)

    vectorizer = SEARCH_INDEX["vectorizer"]
    svd = SEARCH_INDEX["svd"]
    doc_vectors = SEARCH_INDEX["doc_vectors"]
    indexed_places = SEARCH_INDEX["places"]

    query_vector = vectorizer.transform([query.lower().strip()])

    if svd is not None:
        query_vector = svd.transform(query_vector)

    similarities = cosine_similarity(query_vector, doc_vectors)[0]

    if similarities.size == 0 or similarities.max() <= 0:
        return []

    best_indices = np.argsort(-similarities)[:top]

    results = []
    for i in best_indices:
        if similarities[i] <= 0:
            continue

        p = indexed_places[i]
        results.append({
            "id": p.id,
            "name": p.name or "",
            "description": p.description or "",
            "rating": p.rating if p.rating is not None else 0,
            "price_level": p.price_level or "",
            "formatted_address": p.formatted_address or "",
            "website_url": p.website_url or "",
            "latitude": p.latitude if p.latitude is not None else 0,
            "longitude": p.longitude if p.longitude is not None else 0,
            "reviews_text_combined": p.reviews_text_combined or "",
        })

    return results


def get_results_svd(query, top=10, places=None):
    return get_results(query=query, top=top, places=places)



