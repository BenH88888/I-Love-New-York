from app import app
from algo import (
    rebuild_search_index,
    print_latent_dimensions,
    print_query_dimension_analysis,
    compare_search_methods,
    print_result_match_explanation,
    get_results_svd,
)
from models import Place

with app.app_context():
    places = Place.query.all()
    rebuild_search_index(places=places)

    print_latent_dimensions(top_terms=8, top_dims=10)

    query = "Best parks for walking"
    print_query_dimension_analysis(query, top_k=5)

    comparison = compare_search_methods(query, top=5)

    svd_results = get_results_svd(query, top=3)
    for result in svd_results:
        print_result_match_explanation(query, result["id"], top_k=4)