import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from movie_recommender import recommend, recommend_by_id          # loads pkl once at startup
from tmdb_api import (
    fetch_movie_details,
    tmdb_recommend,
    tmdb_recommend_by_id,
    tmdb_search_multi,
    get_trending_movies,
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "cine-match-super-secret-key-1234")

# Configure database: Fallback to SQLite if DATABASE_URL is not set
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

if not db_url:
    # Serverless platforms (like Vercel) have a read-only filesystem, except for /tmp/
    if os.getenv("VERCEL") or "AWS_LAMBDA_FUNCTION_NAME" in os.environ:
        app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:////tmp/cine_match.db"
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///cine_match.db"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID", "placeholder-please-replace"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "placeholder-please-replace"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# ── Database Models ───────────────────────────────────────────────────

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    profile_pic = db.Column(db.String(255))
    google_id = db.Column(db.String(100), unique=True, nullable=False)

class WatchlistItem(db.Model):
    __tablename__ = 'watchlist_items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    movie_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    poster = db.Column(db.String(255))
    rating = db.Column(db.String(20))
    overview = db.Column(db.Text)
    trailer = db.Column(db.String(255))

    user = db.relationship('User', backref=db.backref('watchlist', lazy=True, cascade='all, delete-orphan'))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Auto-create tables and prepopulate guest user
with app.app_context():
    db.create_all()
    guest = User.query.filter_by(email="guest@cinematch.local").first()
    if not guest:
        guest = User(
            email="guest@cinematch.local",
            name="Guest User",
            profile_pic="",
            google_id="guest_account"
        )
        db.session.add(guest)
        db.session.commit()

# ── Auth Routes ───────────────────────────────────────────────────────

@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/login/google')
def login_google():
    redirect_uri = url_for('login_google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/login/google/callback')
def login_google_callback():
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')
        if not user_info:
            flash("Failed to retrieve Google user profile details.", "error")
            return redirect(url_for('login'))
        
        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name', 'Google User')
        profile_pic = user_info.get('picture', '')

        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            # Also check by email to merge accounts if needed
            user = User.query.filter_by(email=email).first()
            if user:
                user.google_id = google_id
            else:
                user = User(email=email, google_id=google_id, name=name, profile_pic=profile_pic)
                db.session.add(user)
            db.session.commit()

        login_user(user)
        flash(f"Successfully signed in as {user.name}!", "success")
        return redirect(url_for('home'))
    except Exception as e:
        flash(f"Error during login: {e}", "error")
        return redirect(url_for('login'))

@app.route('/login/guest')
def login_guest():
    guest = User.query.filter_by(email="guest@cinematch.local").first()
    if guest:
        login_user(guest)
        flash("Logged in as Guest!", "success")
    else:
        flash("Guest login is currently unavailable.", "error")
    return redirect(url_for('home'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Successfully logged out.", "success")
    return redirect(url_for('home'))

def _is_guest():
    """Return True if the current user is the shared guest account."""
    return (current_user.is_authenticated
            and current_user.email == "guest@cinematch.local")

# ── Watchlist Routes ──────────────────────────────────────────────────

@app.route('/watchlist')
@login_required
def watchlist():
    if _is_guest():
        flash("Sign in with Google to use your personal watchlist.", "info")
        return redirect(url_for('login'))
    items = WatchlistItem.query.filter_by(user_id=current_user.id).all()
    serialized_items = []
    for item in items:
        serialized_items.append({
            'id': item.id,
            'movie_id': item.movie_id,
            'title': item.title,
            'poster': item.poster,
            'rating': item.rating,
            'overview': item.overview,
            'trailer': item.trailer,
            'release_date': '',
            'runtime': '',
            'language': '',
            'genres': [],
            'watch_providers': []
        })
    return render_template('watchlist.html', items=items, serialized_items=serialized_items)

@app.route('/watchlist/add', methods=['POST'])
def watchlist_add():
    if not current_user.is_authenticated:
        flash("Please log in to add movies to your watchlist.", "info")
        return redirect(url_for('login'))
    if _is_guest():
        flash("Sign in with Google to save movies to your watchlist.", "info")
        return redirect(request.referrer or url_for('home'))

    movie_id = request.form.get('movie_id')
    title = request.form.get('title')
    poster = request.form.get('poster')
    rating = request.form.get('rating')
    overview = request.form.get('overview')
    trailer = request.form.get('trailer')

    if not movie_id or not title:
        flash("Missing movie information.", "error")
        return redirect(request.referrer or url_for('home'))

    # Check if already added
    existing = WatchlistItem.query.filter_by(user_id=current_user.id, movie_id=int(movie_id)).first()
    if existing:
        flash(f"'{title}' is already in your watchlist.", "info")
    else:
        item = WatchlistItem(
            user_id=current_user.id,
            movie_id=int(movie_id),
            title=title,
            poster=poster,
            rating=rating,
            overview=overview,
            trailer=trailer
        )
        db.session.add(item)
        db.session.commit()
        flash(f"Added '{title}' to your watchlist!", "success")

    return redirect(request.referrer or url_for('home'))

@app.route('/watchlist/remove', methods=['POST'])
@login_required
def watchlist_remove():
    movie_id = request.form.get('movie_id')
    if not movie_id:
        flash("Missing movie ID.", "error")
        return redirect(url_for('watchlist'))

    item = WatchlistItem.query.filter_by(user_id=current_user.id, movie_id=int(movie_id)).first()
    if item:
        title = item.title
        db.session.delete(item)
        db.session.commit()
        flash(f"Removed '{title}' from your watchlist.", "success")
    else:
        flash("Item not found in watchlist.", "error")

    return redirect(request.referrer or url_for('watchlist'))

# ── Main Routes ───────────────────────────────────────────────────────

@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    suggestions = tmdb_search_multi(query)
    return jsonify(suggestions)


@app.route('/', methods=['GET', 'POST'])
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

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

    # Pass guest flag so the template can hide watchlist UI for guests
    is_guest = _is_guest()
    user_watchlist_ids = []
    if current_user.is_authenticated and not is_guest:
        user_watchlist_ids = [item.movie_id for item in current_user.watchlist]

    return render_template(
        'index.html',
        movies=movie_data,
        trending_movies=trending_movies,
        searched_movie=searched_movie,
        user_watchlist_ids=user_watchlist_ids,
        is_guest=is_guest
    )


if __name__ == '__main__':
    app.run(debug=True)

