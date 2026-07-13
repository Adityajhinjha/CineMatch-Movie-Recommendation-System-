
import os
import pickle
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))

movies_path = os.path.join(current_dir, 'movies.pkl')
with open(movies_path, 'rb') as f:
    movies = pickle.load(f)           

similarity_path = os.path.join(current_dir, 'similarity.pkl')
with open(similarity_path, 'rb') as f:
    similarity_data = pickle.load(f)

top_indices = similarity_data['indices']


import pandas as pd

NUM_SIMILAR_TITLES = 10


def recommend(movie: str, movies_df=None, top_idxs=None) -> list[str]:
    """Return up to 10 titles most similar to *movie* (case-insensitive)."""
    if not isinstance(movie, str):
        return []

    movies_df = movies if movies_df is None else movies_df
    top_idxs = top_indices if top_idxs is None else top_idxs

    if not isinstance(movies_df, pd.DataFrame) or not isinstance(top_idxs, np.ndarray):
        return []

    try:
        movie = movie.lower().strip()
        matches = movies_df[movies_df['title'].str.lower().str.contains(movie, regex=False)]
        if matches.empty:
            return []

        idx = matches.index[0]
        if idx >= len(top_idxs):
            return []

        similar_indices = top_idxs[idx]
        if len(similar_indices) == 0:
            return []
        similar_indices = similar_indices[:NUM_SIMILAR_TITLES]

        return [
            movies_df.iloc[i].title
            for i in similar_indices
        ]
    except (AttributeError, ValueError, KeyError, IndexError) as e:
        print(f"Linter-safe error in recommend: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in recommend: {e}")
        return []


def recommend_by_id(movie_id: int, movies_df=None, top_idxs=None) -> list[str]:
    """Return up to 10 titles most similar to the movie with TMDB ID *movie_id* (offline)."""
    if not isinstance(movie_id, (int, np.integer)) or movie_id <= 0:
        return []

    movies_df = movies if movies_df is None else movies_df
    top_idxs = top_indices if top_idxs is None else top_idxs

    if not isinstance(movies_df, pd.DataFrame) or not isinstance(top_idxs, np.ndarray):
        return []

    try:
        matches = movies_df[movies_df['movie_id'] == movie_id]
        if matches.empty:
            return []

        idx = matches.index[0]
        if idx >= len(top_idxs):
            return []

        similar_indices = top_idxs[idx]
        if len(similar_indices) == 0:
            return []
        similar_indices = similar_indices[:NUM_SIMILAR_TITLES]

        return [
            movies_df.iloc[i].title
            for i in similar_indices
        ]
    except (AttributeError, ValueError, KeyError, IndexError) as e:
        print(f"Linter-safe error in recommend_by_id: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error in recommend_by_id: {e}")
        return []




if __name__ == '__main__':
    print("Testing loaded similarity arrays:")
    print("Indices shape:", top_indices.shape)
    print("Example matches for first movie:", [movies.iloc[i].title for i in top_indices[0][:5]])
