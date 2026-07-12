from flask import Flask, render_template, request, jsonify
from movie_recommender import recommend, recommend_by_id          # loads pkl once at startup
from tmdb_api import (
    fetch_movie_details,
    tmdb_recommend,
    tmdb_recommend_by_id,
    tmdb_search_multi,
    get_trending_movies,
)

app = Flask(__name__)


@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    suggestions = tmdb_search_multi(query)
    return jsonify(suggestions)


@app.route('/', methods=['GET', 'POST'])
def home():
    movie_data     = []
    searched_movie = ""
    trending_movies = []

    if request.method == 'GET':
        trending_movies = get_trending_movies()  
    if request.method == 'POST':
        movie_name     = request.form['movie'].strip()
        tmdb_id        = request.form.get('tmdb_id', '').strip()
        media_type     = request.form.get('media_type', '').strip()
        searched_movie = movie_name

        local_titles = []
        api_recs = []

        if tmdb_id.isdigit() and media_type:
            tmdb_id_val = int(tmdb_id)
            if media_type == 'movie':
                local_titles = recommend_by_id(tmdb_id_val)
            api_recs = tmdb_recommend_by_id(tmdb_id_val, media_type)
        else:
            local_titles = recommend(movie_name)
            api_recs = tmdb_recommend(movie_name)

        if not local_titles:
            movie_data = api_recs
        else:
            # Deduplicate local titles against API recommendations
            api_titles_set = {item['title'].lower().strip() for item in api_recs if 'title' in item}
            unique_local_titles = [t for t in local_titles if t.lower().strip() not in api_titles_set]
            
            # Select up to 5 local titles (or 10 if API returned nothing)
            local_limit = 10 if not api_recs else 5
            local_selection = unique_local_titles[:local_limit]
            
            # Fill the remaining slots with API recommendations to sum to 10
            api_selection = api_recs[:(10 - len(local_selection))]
            
            # Fetch details for the local selections in parallel, preserving original ranking order
            local_details_dict = {}
            if local_selection:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=5) as pool:
                    futures = {pool.submit(fetch_movie_details, m): m for m in local_selection}
                    for future in as_completed(futures):
                        title = futures[future]
                        detail = future.result()
                        if detail:
                            local_details_dict[title] = detail
            
            local_details = [local_details_dict[title] for title in local_selection if title in local_details_dict]
            
            # Merge lists (local recommendations first, followed by API recommendations)
            movie_data = local_details + api_selection

    return render_template(
        'index.html',
        movies=movie_data,
        trending_movies=trending_movies,
        searched_movie=searched_movie,
    )


if __name__ == '__main__':
    app.run(debug=True)
