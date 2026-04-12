from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import os
from models import Place
from sklearn.decomposition import TruncatedSVD


current_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_directory)


def get_results(query, top=10, places=None):
    if places is None:
        places = Place.query.all()
    combined = []
    for p in places:
        name = p.name if p.name else ""
        description = p.description if p.description else ""
        address = p.formatted_address if p.formatted_address else ""
        price = p.price_level if p.price_level else ""
        reviews_text_combined = p.reviews_text_combined if p.reviews_text_combined else ""
        combined += [name + " " + description + " " + address+ " " + price + " " + reviews_text_combined]

    if len(combined) == 0:
        return []

    vectorizer = TfidfVectorizer(max_features=5000, stop_words = "english", max_df= .9, min_df=1)
    words = vectorizer.fit_transform(combined)
    lower = query.lower()
    vector = vectorizer.transform([lower])
    value = cosine_similarity(vector, words)[0]
    if value.max() == 0:
        return []
    best = np.argsort(-value)[:top]
    results = []
    for i in best:
        if value[i] > 0:
            p = places[i]
            print(p.price_level)
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
                "reviews_text_combined": p.reviews_text_combined if p.reviews_text_combined else ""
            })
    return results

def get_results_svd(query, top=10, places=None):
    if places is None:
        places = Place.query.all()
    combined = []
    for p in places:
        name = p.name if p.name else ""
        description = p.description if p.description else ""
        address = p.formatted_address if p.formatted_address else ""
        price = p.price_level if p.price_level else ""
        combined += [name + " " + description + " " + address+ " " + price]

    if len(combined) == 0:
        return []

    vectorizer = TfidfVectorizer(max_features=5000, stop_words = "english", max_df= .9, min_df=1)
    words = vectorizer.fit_transform(combined)
    n_docs, n_terms = words.shape
    n_components = min(100, n_docs - 1, n_terms - 1)
    svd = TruncatedSVD(n_components=n_components, random_state=4300)
    words_svd = svd.fit_transform(words)
    lower = query.lower()
    vector = vectorizer.transform([lower])
    query_svd = svd.transform(vector)
    value = cosine_similarity(query_svd, words_svd)[0]
    if value.max() == 0:
        return []
    best = np.argsort(-value)[:top]
    results = []
    for i in best:
        if value[i] > 0:
            p = places[i]
            print(p.price_level)
            print(value[i])
            results.append({
                "id": p.id,
                "name": p.name or "",
                "description": p.description or "",
                "rating": p.rating if p.rating is not None else 0,
                "price_level": p.price_level or "",
                "formatted_address": p.formatted_address or "",
                "website_url": p.website_url or "",
                "latitude": p.latitude if p.latitude is not None else 0,
                "longitude": p.longitude if p.longitude is not None else 0
            })
    return results




