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

        recommended = []
        is_local = False

        if tmdb_id.isdigit() and media_type:
            tmdb_id_val = int(tmdb_id)
            if media_type == 'movie':
                recommended = recommend_by_id(tmdb_id_val)
                if recommended:
                    is_local = True
            
            if not recommended:
                movie_data = tmdb_recommend_by_id(tmdb_id_val, media_type)
        else:
            recommended = recommend(movie_name)
            if recommended:
                is_local = True
            else:
                movie_data = tmdb_recommend(movie_name)

        if is_local and recommended:
            # fetch all 5 details in parallel
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(fetch_movie_details, m): m
                           for m in recommended}
                for future in as_completed(futures):
                    detail = future.result()
                    if detail:
                        movie_data.append(detail)

    return render_template(
        'index.html',
        movies=movie_data,
        trending_movies=trending_movies,
        searched_movie=searched_movie,
    )


if __name__ == '__main__':
    app.run(debug=True)
