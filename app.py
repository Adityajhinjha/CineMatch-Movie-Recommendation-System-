
from flask import Flask, render_template, request
from movie_recommender import recommend          # loads pkl once at startup
from tmdb_api import (
    fetch_movie_details,
    tmdb_recommend,
    get_trending_movies,
)

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def home():
    movie_data     = []
    searched_movie = ""
    trending_movies = []

    if request.method == 'GET':
        trending_movies = get_trending_movies()  
    if request.method == 'POST':
        movie_name     = request.form['movie'].strip()
        searched_movie = movie_name

        recommended = recommend(movie_name)

        if recommended:
            # fetch all 5 details in parallel
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures = {pool.submit(fetch_movie_details, m): m
                           for m in recommended}
                for future in as_completed(futures):
                    detail = future.result()
                    if detail:
                        movie_data.append(detail)
        else:
            movie_data = tmdb_recommend(movie_name)

    return render_template(
        'index.html',
        movies=movie_data,
        trending_movies=trending_movies,
        searched_movie=searched_movie,
    )


if __name__ == '__main__':
    app.run(debug=True)
