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
    "doc_vectors_raw": None,
    "feature_names": None,
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
            "doc_vectors_raw": None,
            "feature_names": None,
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
    feature_names = vectorizer.get_feature_names_out()

    n_docs, n_terms = tfidf_matrix.shape
    use_svd = min(n_docs - 1, n_terms - 1) >= 2

    svd = None
    doc_vectors = tfidf_matrix

    if use_svd:
        n_components = min(50, n_docs - 1, n_terms - 1)
        svd = TruncatedSVD(n_components=n_components, random_state=4300)
        doc_vectors = svd.fit_transform(tfidf_matrix)

    SEARCH_INDEX = {
        "places": places,
        "vectorizer": vectorizer,
        "tfidf_matrix": tfidf_matrix,
        "svd": svd,
        "doc_vectors": doc_vectors,
        "doc_vectors_raw": tfidf_matrix,
        "feature_names": feature_names,
    }


def rebuild_search_index(places=None):
    build_search_index(places=places)


def get_latent_dimensions(top_terms=10, top_dims=12):
    if SEARCH_INDEX["svd"] is None or SEARCH_INDEX["feature_names"] is None:
        return []

    svd = SEARCH_INDEX["svd"]
    feature_names = SEARCH_INDEX["feature_names"]

    dimensions = []
    max_dims = min(top_dims, svd.components_.shape[0])

    for dim_idx in range(max_dims):
        component = svd.components_[dim_idx]

        top_term_indices = np.argsort(component)[-top_terms:][::-1]
        top_terms_for_dim = [feature_names[i] for i in top_term_indices]

        dimensions.append({
            "dimension": dim_idx,
            "top_terms": top_terms_for_dim,
        })

    return dimensions


def print_latent_dimensions(top_terms=10, top_dims=12):
    dimensions = get_latent_dimensions(top_terms=top_terms, top_dims=top_dims)

    if not dimensions:
        print("No SVD dimensions available.")
        return

    print("\n=== Latent Dimensions ===")
    for dim in dimensions:
        print(f"\nDimension {dim['dimension']}:")
        print(", ".join(dim["top_terms"]))
    

def analyze_query_dimensions(query, top_k=5):
    if not query or not query.strip():
        return None

    if SEARCH_INDEX["vectorizer"] is None or len(SEARCH_INDEX["places"]) == 0:
        build_search_index()

    vectorizer = SEARCH_INDEX["vectorizer"]
    svd = SEARCH_INDEX["svd"]

    if svd is None:
        return None

    query_vector_raw = vectorizer.transform([query.lower().strip()])
    query_vector_svd = svd.transform(query_vector_raw)[0]

    positive_dims = np.argsort(query_vector_svd)[-top_k:][::-1]
    negative_dims = np.argsort(query_vector_svd)[:top_k]

    return {
        "query": query,
        "positive_dimensions": [
            {
                "dimension": int(i),
                "activation": float(query_vector_svd[i]),
            }
            for i in positive_dims
        ],
        "negative_dimensions": [
            {
                "dimension": int(i),
                "activation": float(query_vector_svd[i]),
            }
            for i in negative_dims
        ],
        "query_vector_svd": query_vector_svd,
    }


def print_query_dimension_analysis(query, top_k=5):
    analysis = analyze_query_dimensions(query, top_k=top_k)

    if analysis is None:
        print("No SVD query analysis available.")
        return

    print(f"\n=== Query Dimension Analysis: '{analysis['query']}' ===")

    print("\nTop POSITIVE dimensions:")
    for item in analysis["positive_dimensions"]:
        print(f"Dimension {item['dimension']}: {item['activation']:.4f}")

    print("\nTop NEGATIVE dimensions:")
    for item in analysis["negative_dimensions"]:
        print(f"Dimension {item['dimension']}: {item['activation']:.4f}")


def explain_result_match(query, place_id, top_k=5):
    if not query or not query.strip():
        return None

    if SEARCH_INDEX["vectorizer"] is None or len(SEARCH_INDEX["places"]) == 0:
        build_search_index()

    vectorizer = SEARCH_INDEX["vectorizer"]
    svd = SEARCH_INDEX["svd"]
    places = SEARCH_INDEX["places"]
    doc_vectors = SEARCH_INDEX["doc_vectors"]

    if svd is None:
        return None

    place_index = None
    for idx, place in enumerate(places):
        if place.id == place_id:
            place_index = idx
            break

    if place_index is None:
        return None

    query_vector_raw = vectorizer.transform([query.lower().strip()])
    query_vector_svd = svd.transform(query_vector_raw)[0]
    doc_vector_svd = doc_vectors[place_index]

    alignment = query_vector_svd * doc_vector_svd

    top_positive = np.argsort(alignment)[-top_k:][::-1]
    top_negative = np.argsort(alignment)[:top_k]

    place = places[place_index]

    return {
        "query": query,
        "place_id": place.id,
        "place_name": place.name,
        "top_positive_matching_dimensions": [
            {
                "dimension": int(i),
                "alignment": float(alignment[i]),
                "query_activation": float(query_vector_svd[i]),
                "document_activation": float(doc_vector_svd[i]),
            }
            for i in top_positive
        ],
        "top_negative_matching_dimensions": [
            {
                "dimension": int(i),
                "alignment": float(alignment[i]),
                "query_activation": float(query_vector_svd[i]),
                "document_activation": float(doc_vector_svd[i]),
            }
            for i in top_negative
        ],
    }


def print_result_match_explanation(query, place_id, top_k=5):
    explanation = explain_result_match(query, place_id, top_k=top_k)

    if explanation is None:
        print("No explanation available.")
        return

    print(f"\n=== Match Explanation ===")
    print(f"Query: {explanation['query']}")
    print(f"Place: {explanation['place_name']} (id={explanation['place_id']})")

    print("\nTop POSITIVE matching dimensions:")
    for item in explanation["top_positive_matching_dimensions"]:
        print(
            f"Dimension {item['dimension']}: "
            f"alignment={item['alignment']:.4f}, "
            f"query={item['query_activation']:.4f}, "
            f"doc={item['document_activation']:.4f}"
        )

    print("\nTop NEGATIVE matching dimensions:")
    for item in explanation["top_negative_matching_dimensions"]:
        print(
            f"Dimension {item['dimension']}: "
            f"alignment={item['alignment']:.4f}, "
            f"query={item['query_activation']:.4f}, "
            f"doc={item['document_activation']:.4f}"
        )


def get_results_no_svd(query, top=10, places=None):
    if places is not None:
        build_search_index(places=places)

    if not query or not query.strip():
        return []

    if SEARCH_INDEX["vectorizer"] is None or len(SEARCH_INDEX["places"]) == 0:
        build_search_index(places=places)

    vectorizer = SEARCH_INDEX["vectorizer"]
    doc_vectors_raw = SEARCH_INDEX["doc_vectors_raw"]
    indexed_places = SEARCH_INDEX["places"]

    query_vector = vectorizer.transform([query.lower().strip()])
    similarities = cosine_similarity(query_vector, doc_vectors_raw)[0]

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


def compare_search_methods(query, top=5):
    no_svd_results = get_results_no_svd(query, top=top)
    svd_results = get_results_svd(query, top=top)

    print(f"\n=== Search Comparison for: '{query}' ===")

    print("\nWITHOUT SVD:")
    for idx, result in enumerate(no_svd_results, start=1):
        print(f"{idx}. {result['name']}")

    print("\nWITH SVD:")
    for idx, result in enumerate(svd_results, start=1):
        print(f"{idx}. {result['name']}")

    return {
        "query": query,
        "without_svd": no_svd_results,
        "with_svd": svd_results,
    }

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
            "similarity_score": float(similarities[i]),
            "tags": get_top_terms_for_place(int(i), top_k=4),
        })

    return results


def get_results_svd(query, top=10, places=None):
    return get_results(query=query, top=top, places=places)

def get_top_terms_for_place(place_index, top_k=4):
    tag_block = {"new", "york", "park", "street", "ave", "ny", "nyc", "city", 
                 "restaurant", "place", "located", "offers", "featuring", "including",
                 "10301", "10001", "staten", "island", "manhattan", "brooklyn", "bronx"}
    tfidf_matrix = SEARCH_INDEX["doc_vectors_raw"]
    feature_names = SEARCH_INDEX["feature_names"]

    if tfidf_matrix is None:
        return []

    row = tfidf_matrix[place_index].toarray()[0]
    top_indices = np.argsort(row)[::-1]

    tags = []
    for i in top_indices:
        term = feature_names[i]
        if term not in tag_block and len(term) > 3:
            tags.append(term)
        if len(tags) >= top_k:
            break

    return tags



