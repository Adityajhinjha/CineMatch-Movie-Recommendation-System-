import os
import time
import requests
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(current_dir, ".env"))

API_KEY = os.getenv("TMDB_API_KEY")
if not API_KEY:
    print("WARNING: TMDB_API_KEY is not set in the .env file. API requests will fail.")
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


def _extract_watch_providers(watch_data: dict) -> list[dict]:
    try:
        # Prioritize India (IN), fall back to US
        providers = watch_data.get("IN") or watch_data.get("US") or {}
        tmdb_url = providers.get("link")
        flatrate = providers.get("flatrate", [])
        return [
            {
                "name": p.get("provider_name"),
                "logo": f"https://image.tmdb.org/t/p/w92{p.get('logo_path')}" if p.get("logo_path") else None,
                "tmdb_url": tmdb_url
            }
            for p in flatrate
        ]
    except Exception as e:
        print("Error extracting watch providers:", e)
        return []


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

        details  = _get(f"https://api.themoviedb.org/3/movie/{movie_id}",
                        {"append_to_response": "videos,watch/providers"})
        
        # Extract trailer
        videos = details.get("videos", {}).get("results", [])
        trailer = ""
        for v in videos:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer = f"https://www.youtube.com/watch?v={v['key']}"
                break
                
        # Extract watch providers
        watch_data = details.get("watch/providers", {}).get("results", {})
        watch_providers = _extract_watch_providers(watch_data)
        
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
            "watch_providers": watch_providers,
        }
    except Exception as e:
        print("fetch_movie_details error:", e)
        return None

def _build_full_detail(movie: dict) -> dict | None:
    """Fetch per-movie details + trailer in one shot (called concurrently)."""
    try:
        movie_id = movie["id"]

        details_data = _get(f"https://api.themoviedb.org/3/movie/{movie_id}",
                            {"append_to_response": "videos,watch/providers"})
        
        # Extract trailer
        videos = details_data.get("videos", {}).get("results", [])
        trailer = ""
        for v in videos:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer = f"https://www.youtube.com/watch?v={v['key']}"
                break
                
        # Extract watch providers
        watch_data = details_data.get("watch/providers", {}).get("results", {})
        watch_providers = _extract_watch_providers(watch_data)

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
            "watch_providers": watch_providers,
        }
    except Exception as e:
        print("_build_full_detail error:", e)
        return None

def _fetch_tv_trailer(tv_id: int) -> str:
    try:
        data = _get(f"https://api.themoviedb.org/3/tv/{tv_id}/videos")
        for v in data.get("results", []):
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                return f"https://www.youtube.com/watch?v={v['key']}"
    except Exception as e:
        print("TV Trailer error:", e)
    return ""


def _build_tv_detail(tv_show: dict) -> dict | None:
    """Fetch per-show details + trailer in one shot (called concurrently)."""
    try:
        tv_id = tv_show["id"]
        details_data = _get(f"https://api.themoviedb.org/3/tv/{tv_id}",
                            {"append_to_response": "videos,watch/providers"})
        
        # Extract trailer
        videos = details_data.get("videos", {}).get("results", [])
        trailer = ""
        for v in videos:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                trailer = f"https://www.youtube.com/watch?v={v['key']}"
                break
                
        # Extract watch providers
        watch_data = details_data.get("watch/providers", {}).get("results", {})
        watch_providers = _extract_watch_providers(watch_data)

        genres = [g["name"] for g in details_data.get("genres", [])]

        seasons = details_data.get("number_of_seasons", 1)
        runtime_str = f"{seasons} Season" if seasons == 1 else f"{seasons} Seasons"

        return {
            "title":        tv_show.get("name") or details_data.get("name"),
            "overview":     tv_show.get("overview") or details_data.get("overview"),
            "rating":       tv_show.get("vote_average") or details_data.get("vote_average"),
            "poster":       _poster(tv_show.get("poster_path") or details_data.get("poster_path")),
            "trailer":      trailer,
            "release_date": details_data.get("first_air_date") or tv_show.get("first_air_date"),
            "runtime":      runtime_str,
            "language":     (details_data.get("original_language") or "").upper() or "Not Available",
            "genres":       genres,
            "media_type":   "tv",
            "watch_providers": watch_providers,
        }
    except Exception as e:
        print("_build_tv_detail error:", e)
        return None


def tmdb_search_multi(query: str) -> list[dict]:
    """Search TMDB for movies/TV shows matching query, returning top 7 items."""
    try:
        data = _get("https://api.themoviedb.org/3/search/multi", {"query": query})
        results = data.get("results", [])
        parsed = []
        for item in results:
            media_type = item.get("media_type")
            if media_type not in ("movie", "tv"):
                continue

            title = item.get("title") if media_type == "movie" else item.get("name")
            date_str = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
            year = date_str.split("-")[0] if date_str else ""

            parsed.append({
                "id": item["id"],
                "title": title,
                "year": year,
                "media_type": media_type,
                "poster": _poster(item.get("poster_path")),
            })
            if len(parsed) >= 7:
                break
        return parsed
    except Exception as e:
        print("tmdb_search_multi error:", e)
        return []


def tmdb_recommend_by_id(tmdb_id: int, media_type: str) -> list[dict]:
    """Fetch recommendations for a specific movie or TV show by TMDB ID."""
    try:
        if media_type == "tv":
            rec_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/recommendations"
            sim_url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/similar"
            builder = _build_tv_detail
        else:
            rec_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/recommendations"
            sim_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/similar"
            builder = _build_full_detail

        rec_data = _get(rec_url)
        results = rec_data.get("results", [])

        if not results:
            sim_data = _get(sim_url)
            results = sim_data.get("results", [])

        items_to_fetch = results[:10]
        recommendations = []

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(builder, item): item for item in items_to_fetch}
            for future in as_completed(futures):
                detail = future.result()
                if detail:
                    recommendations.append(detail)

        return recommendations
    except Exception as e:
        print("tmdb_recommend_by_id error:", e)
        return []


def tmdb_recommend(movie_name: str) -> list[dict]:
    """Return up to 5 TMDB recommendations, fetched in parallel."""
    try:
        data = _get("https://api.themoviedb.org/3/search/multi",
                    {"query": movie_name})
        results = data.get("results", [])
        if not results:
            return []

        target = None
        for r in results:
            if r.get("media_type") in ("movie", "tv"):
                target = r
                break

        if not target:
            return []

        return tmdb_recommend_by_id(target["id"], target["media_type"])
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