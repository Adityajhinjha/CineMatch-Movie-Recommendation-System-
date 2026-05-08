import os
import time
import requests
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
HEADERS = {"User-Agent": "Mozilla/5.0"}

_trending_cache: dict = {"data": None, "ts": 0.0}
TRENDING_TTL = 3600          # 1 hour


def _get(url: str, params: dict = {}) -> dict:
    """Thin wrapper — raises on HTTP error so callers can catch cleanly."""
    r = requests.get(url, params={"api_key": API_KEY, **params},
                     headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def _fetch_trailer(movie_id: int) -> str:
    try:
        data = _get(f"https://api.themoviedb.org/3/movie/{movie_id}/videos")
        for v in data.get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                return f"https://www.youtube.com/watch?v={v['key']}"
    except Exception as e:
        print("Trailer error:", e)
    return ""


def _poster(path: str | None) -> str:
    return f"https://image.tmdb.org/t/p/w500{path}" if path else ""

@lru_cache(maxsize=512)
def fetch_movie_details(movie_name: str) -> dict | None:
    """Search TMDB for *movie_name* and return a full detail dict (cached)."""
    try:
        data = _get("https://api.themoviedb.org/3/search/movie",
                    {"query": movie_name})
        results = data.get("results")
        if not results:
            return None

        movie    = results[0]
        movie_id = movie["id"]

        details  = _get(f"https://api.themoviedb.org/3/movie/{movie_id}")
        trailer  = _fetch_trailer(movie_id)
        genres   = [g["name"] for g in details.get("genres", [])]

        return {
            "title":        details.get("title") or movie.get("title"),
            "overview":     details.get("overview") or movie.get("overview"),
            "rating":       details.get("vote_average") or movie.get("vote_average"),
            "poster":       _poster(details.get("poster_path") or movie.get("poster_path")),
            "movie_id":     movie_id,
            "trailer":      trailer,
            "release_date": details.get("release_date", ""),
            "runtime":      details.get("runtime") or "Not Available",
            "language":     (details.get("original_language") or "").upper() or "Not Available",
            "genres":       genres,
        }
    except Exception as e:
        print("fetch_movie_details error:", e)
        return None

def _build_full_detail(movie: dict) -> dict | None:
    """Fetch per-movie details + trailer in one shot (called concurrently)."""
    try:
        movie_id = movie["id"]

        details_data = _get(f"https://api.themoviedb.org/3/movie/{movie_id}")
        trailer      = _fetch_trailer(movie_id)

        genres = [g["name"] for g in details_data.get("genres", [])]

        return {
            "title":        movie.get("title"),
            "overview":     movie.get("overview"),
            "rating":       movie.get("vote_average"),
            "poster":       _poster(movie.get("poster_path")),
            "trailer":      trailer,
            "release_date": details_data.get("release_date"),
            "runtime":      details_data.get("runtime") or "Not Available",
            "language":     (details_data.get("original_language") or "").upper()
                            or "Not Available",
            "genres":       genres,
        }
    except Exception as e:
        print("_build_full_detail error:", e)
        return None


def tmdb_recommend(movie_name: str) -> list[dict]:
    """Return up to 5 TMDB recommendations, fetched in parallel."""
    try:
        data = _get("https://api.themoviedb.org/3/search/movie",
                    {"query": movie_name})
        if not data.get("results"):
            return []

        movie_id = data["results"][0]["id"]

        rec_data = _get(f"https://api.themoviedb.org/3/movie/{movie_id}/recommendations")
        results  = rec_data.get("results", [])

        if not results:
            sim_data = _get(f"https://api.themoviedb.org/3/movie/{movie_id}/similar")
            results  = sim_data.get("results", [])
        movies_to_fetch = results[:5]
        recommendations = []

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_build_full_detail, m): m
                       for m in movies_to_fetch}
            for future in as_completed(futures):
                detail = future.result()
                if detail:
                    recommendations.append(detail)

        return recommendations

    except Exception as e:
        print("tmdb_recommend error:", e)
        return []
    
def get_trending_movies() -> list[dict]:
    global _trending_cache

    if (time.time() - _trending_cache["ts"] < TRENDING_TTL
            and _trending_cache["data"] is not None):
        return _trending_cache["data"]       # serve from cache

    try:
        data    = _get("https://api.themoviedb.org/3/trending/movie/day")
        raw     = data.get("results", [])[:10]

        trending = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_build_full_detail, m): m for m in raw}
            for future in as_completed(futures):
                detail = future.result()
                if detail:
                    trending.append(detail)

        _trending_cache = {"data": trending, "ts": time.time()}
        return trending

    except Exception as e:
        print("get_trending_movies error:", e)
        return _trending_cache["data"] or [] 


def get_movie_details(movie_name: str) -> dict:
    """Convenience wrapper — reuses the cached fetch_movie_details."""
    detail = fetch_movie_details(movie_name)
    return detail or {}