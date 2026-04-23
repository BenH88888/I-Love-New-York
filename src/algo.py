from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
import numpy as np
from models import Place

DEFAULT_SBERT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

PIPELINE_INDEX = {
    # ("tfidf", False): {...}
    # ("tfidf", True): {...}
    # ("sbert", False): {...}
    # ("sbert", True): {...}
}

SBERT_MODEL = None

SBERT_EMBEDDINGS_CACHE = {}


def _places_signature(places):
    if not places:
        return ()
    return tuple(place.id for place in places)


def get_sbert_model():
    global SBERT_MODEL
    if SBERT_MODEL is None:
        from sentence_transformers import SentenceTransformer
        SBERT_MODEL = SentenceTransformer(DEFAULT_SBERT_MODEL)
    return SBERT_MODEL


def _build_combined_text(place):
    name = place.name or ""
    description = place.description or ""
    address = place.formatted_address or ""
    price = str(place.price_level) if place.price_level is not None else ""
    reviews = place.reviews_text_combined or ""

    return f"{name} {description} {address} {price} {reviews}".strip()


def _empty_index():
    return {
        "places": [],
        "base_model": None,
        "use_svd": False,
        "vectorizer": None,          # TF-IDF only
        "encoder": None,             # SBERT only
        "raw_doc_vectors": None,     # before SVD
        "doc_vectors": None,         # after optional SVD
        "svd": None,
        "feature_names": None,       # TF-IDF only
    }


def _build_tfidf_vectors(texts):
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words="english",
        max_df=0.4,
        min_df=1,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    return {
        "vectorizer": vectorizer,
        "encoder": None,
        "raw_doc_vectors": tfidf_matrix,
        "feature_names": feature_names,
    }


def _build_sbert_vectors(texts):
    global SBERT_EMBEDDINGS_CACHE

    texts_key = tuple(texts)
    if texts_key in SBERT_EMBEDDINGS_CACHE:
        embeddings = SBERT_EMBEDDINGS_CACHE[texts_key]
    else:
        encoder = get_sbert_model()
        embeddings = encoder.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        SBERT_EMBEDDINGS_CACHE[texts_key] = embeddings

    return {
        "vectorizer": None,
        "encoder": get_sbert_model(),
        "raw_doc_vectors": embeddings,
        "feature_names": None,
    }


def _maybe_apply_svd(raw_vectors, use_svd):
    if not use_svd:
        return None, raw_vectors

    # sparse matrix case (TF-IDF) or dense matrix case (SBERT)
    n_docs = raw_vectors.shape[0]
    n_features = raw_vectors.shape[1]

    if min(n_docs - 1, n_features - 1) < 2:
        return None, raw_vectors

    n_components = min(70, n_docs - 1, n_features - 1)
    svd = TruncatedSVD(n_components=n_components, random_state=4300)
    doc_vectors = svd.fit_transform(raw_vectors)

    # normalize after SVD so cosine similarity behaves nicely
    norms = np.linalg.norm(doc_vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    doc_vectors = doc_vectors / norms

    return svd, doc_vectors


def build_search_index(places=None, base_model="tfidf", use_svd=True):
    global PIPELINE_INDEX

    if places is None:
        places = Place.query.all()

    places = list(places)
    places_sig = _places_signature(places)
    key = (base_model, bool(use_svd), places_sig)

    if len(places) == 0:
        PIPELINE_INDEX[key] = _empty_index()
        PIPELINE_INDEX[key]["base_model"] = base_model
        PIPELINE_INDEX[key]["use_svd"] = bool(use_svd)
        return

    combined = [_build_combined_text(place) for place in places]

    if base_model == "tfidf":
        base = _build_tfidf_vectors(combined)
    elif base_model == "sbert":
        base = _build_sbert_vectors(combined)
    else:
        raise ValueError(f"Unsupported base_model: {base_model}")

    svd, doc_vectors = _maybe_apply_svd(base["raw_doc_vectors"], use_svd)

    PIPELINE_INDEX[key] = {
        "places": places,
        "base_model": base_model,
        "use_svd": bool(use_svd),
        "vectorizer": base["vectorizer"],
        "encoder": base["encoder"],
        "raw_doc_vectors": base["raw_doc_vectors"],
        "doc_vectors": doc_vectors,
        "svd": svd,
        "feature_names": base["feature_names"],
    }


def rebuild_all_search_indices(places=None):
    for base_model in ["tfidf", "sbert"]:
        for use_svd in [False, True]:
            build_search_index(
                places=places,
                base_model=base_model,
                use_svd=use_svd,
            )


def _get_index(places=None, base_model="tfidf", use_svd=True):
    if places is None:
        places = Place.query.all()

    places = list(places)
    places_sig = _places_signature(places)
    key = (base_model, bool(use_svd), places_sig)

    if key not in PIPELINE_INDEX:
        build_search_index(places=places, base_model=base_model, use_svd=use_svd)

    return PIPELINE_INDEX[key]


def _encode_query(query, index):
    text = query.lower().strip()

    if index["base_model"] == "tfidf":
        query_vector = index["vectorizer"].transform([text])
    elif index["base_model"] == "sbert":
        query_vector = index["encoder"].encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    else:
        raise ValueError(f"Unsupported base_model: {index['base_model']}")

    if index["svd"] is not None:
        query_vector = index["svd"].transform(query_vector)

        norms = np.linalg.norm(query_vector, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        query_vector = query_vector / norms

    return query_vector


def get_top_terms_for_place(place_index, places=None, base_model="tfidf", use_svd=False, top_k=4):
    if base_model != "tfidf":
        return []

    index = _get_index(places=places, base_model=base_model, use_svd=use_svd)
    tfidf_matrix = index["raw_doc_vectors"]
    feature_names = index["feature_names"]

    if tfidf_matrix is None or feature_names is None:
        return []

    block = {
        "new", "york", "street", "ave", "ny", "nyc", "city",
        "place", "located", "offers", "featuring", "including",
        "10301", "10001", "11354", "st", "area", "also", "known", "open", "just",
        "like", "great", "good", "best", "near", "east", "west",
        "north", "south", "old", "local", "pl", "rd"
    }

    row = tfidf_matrix[place_index].toarray()[0]
    top_indices = np.argsort(row)[::-1]

    tags = []
    for i in top_indices:
        term = feature_names[i]
        if term not in block and len(term) > 3 and not term.isdigit():
            tags.append(term)
        if len(tags) >= top_k:
            break

    return tags


def get_latent_dimensions(top_terms=10, top_dims=12, base_model="tfidf", use_svd=True):
    index = _get_index(base_model=base_model, use_svd=use_svd)

    if index["svd"] is None:
        return []

    # Only TF-IDF has interpretable feature names
    if base_model != "tfidf" or index["feature_names"] is None:
        return []

    svd = index["svd"]
    feature_names = index["feature_names"]

    block = {
        "new", "york", "street", "ave", "ny", "nyc", "city",
        "place", "located", "offers", "featuring", "including",
        "10301", "10001", "11354", "st", "area", "also", "known", "open", "just",
        "like", "great", "good", "best", "near", "east", "west",
        "north", "south", "old", "local", "pl", "rd"
    }

    dimensions = []
    max_dims = min(top_dims, svd.components_.shape[0])

    for dim_idx in range(max_dims):
        component = svd.components_[dim_idx]
        top_term_indices = np.argsort(component)[-top_terms:][::-1]

        top_terms_for_dim = []
        for i in top_term_indices:
            term = feature_names[i]
            if term not in block and not term.isdigit():
                top_terms_for_dim.append(term)

        if not top_terms_for_dim:
            continue

        dimensions.append({
            "dimension": dim_idx,
            "top_terms": top_terms_for_dim,
        })

    return dimensions


def analyze_query_dimensions(query, top_k=5, base_model="tfidf", use_svd=True):
    index = _get_index(base_model=base_model, use_svd=use_svd)

    if not query or not query.strip():
        return None

    if index["svd"] is None:
        return None

    query_vector = _encode_query(query, index)[0]

    positive_dims = np.argsort(query_vector)[-top_k:][::-1]
    negative_dims = np.argsort(query_vector)[:top_k]

    return {
        "query": query,
        "positive_dimensions": [
            {
                "dimension": int(i),
                "activation": float(query_vector[i]),
            }
            for i in positive_dims
        ],
        "negative_dimensions": [
            {
                "dimension": int(i),
                "activation": float(query_vector[i]),
            }
            for i in negative_dims
        ],
    }

def get_place_dims(place_index, index, dim_lookup, top_k=2):
    if index["svd"] is None or index["doc_vectors"] is None:
        return []
    doc_vector = index["doc_vectors"][place_index]
    pos_indices = np.argsort(doc_vector)[-top_k:][::-1]
    neg_indices = np.argsort(doc_vector)[:top_k]
    dims = []
    seen = set()
    for i in list(pos_indices) + list(neg_indices):
        if i in seen:
            continue
        seen.add(i)
        terms = dim_lookup.get(int(i), [])
        if not terms:
            continue
        dims.append({"dimension": int(i), "activation": float(doc_vector[i]), "terms": terms})
    dims.sort(key=lambda d: d["activation"], reverse=True)
    return dims

def _format_result(place, similarity_score, dims):
    return {
        "id": place.id,
        "name": place.name or "",
        "description": place.description or "",
        "rating": place.rating if place.rating is not None else 0,
        "price_level": place.price_level or "",
        "formatted_address": place.formatted_address or "",
        "website_url": place.website_url or "",
        "latitude": place.latitude if place.latitude is not None else 0,
        "longitude": place.longitude if place.longitude is not None else 0,
        "reviews_text_combined": place.reviews_text_combined or "",
        "similarity_score": float(similarity_score),
        "dims": dims,
    }


def _search(query, top=10, places=None, base_model="tfidf", use_svd=True):
    if not query or not query.strip():
        return {"results": [], "dimensions": []}

    index = _get_index(places=places, base_model=base_model, use_svd=use_svd)

    if len(index["places"]) == 0:
        return {"results": [], "dimensions": []}

    query_vector = _encode_query(query, index)
    similarities = cosine_similarity(query_vector, index["doc_vectors"])[0]

    if similarities.size == 0:
        return {"results": [], "dimensions": []}

    best_indices = np.argsort(-similarities)[:top]
    dim_lookup = {}
    if base_model == "tfidf" and use_svd and index["svd"] is not None:
        latent_dims = get_latent_dimensions(top_terms=4, top_dims=index["svd"].n_components, base_model=base_model, use_svd=use_svd)
        dim_lookup = {d["dimension"]: d["top_terms"] for d in latent_dims}
    results = []
    for i in best_indices:
        if base_model == "tfidf" and similarities[i] <= 0:
            continue

        place = index["places"][i]
        place_dims = [] 
        if base_model == "tfidf" and use_svd:
            place_dims = get_place_dims(i, index, dim_lookup)
        results.append(_format_result(place, similarities[i], place_dims))

    query_dims = []
    analysis = analyze_query_dimensions(
        query,
        top_k=2,
        base_model=base_model,
        use_svd=use_svd,
    )

    if analysis and base_model == "tfidf":

        all_dims = analysis["positive_dimensions"] + analysis["negative_dimensions"]
        query_dims = [
            {
                "dimension": item["dimension"],
                "activation": item["activation"],
                "terms": dim_lookup.get(item["dimension"], []),
            }
            for item in sorted(all_dims, key=lambda x: abs(x["activation"]), reverse=True)
        ]

    return {
        "results": results,
        "dimensions": query_dims,
    }


def get_results_tfidf(query, top=10, places=None):
    return _search(query, top=top, places=places, base_model="tfidf", use_svd=False)


def get_results_tfidf_svd(query, top=10, places=None):
    return _search(query, top=top, places=places, base_model="tfidf", use_svd=True)


def get_results_sbert(query, top=10, places=None):
    return _search(query, top=top, places=places, base_model="sbert", use_svd=False)


def get_results_sbert_svd(query, top=10, places=None):
    return _search(query, top=top, places=places, base_model="sbert", use_svd=True)


def get_results(query, top=10, places=None, base_model="tfidf", use_svd=True):
    if base_model == "tfidf" and not use_svd:
        return get_results_tfidf(query, top=top, places=places)
    if base_model == "tfidf" and use_svd:
        return get_results_tfidf_svd(query, top=top, places=places)
    if base_model == "sbert" and not use_svd:
        return get_results_sbert(query, top=top, places=places)
    if base_model == "sbert" and use_svd:
        return get_results_sbert_svd(query, top=top, places=places)

    raise ValueError(f"Invalid combination: {base_model}, use_svd={use_svd}")


