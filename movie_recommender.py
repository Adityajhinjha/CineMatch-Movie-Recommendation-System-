
import pickle
import numpy as np

with open('movies.pkl', 'rb') as f:
    movies = pickle.load(f)           

with open('similarity.pkl', 'rb') as f:
    similarity_data = pickle.load(f)

top_indices = similarity_data['indices']


def recommend(movie: str, movies_df=movies, top_idxs=top_indices) -> list[str]:
    """Return up to 10 titles most similar to *movie* (case-insensitive)."""
    if not isinstance(movie, str):
        return []

    try:
        movie = movie.lower().strip()
        matches = movies_df[movies_df['title'].str.lower().str.contains(movie, regex=False)]
        if matches.empty:
            return []

        idx = matches.index[0]
        if idx >= len(top_idxs):
            return []

        similar_indices = top_idxs[idx][:10]

        return [
            movies_df.iloc[i].title
            for i in similar_indices
        ]
    except Exception as e:
        print(f"Error in recommend: {e}")
        return []


def recommend_by_id(movie_id: int, movies_df=movies, top_idxs=top_indices) -> list[str]:
    """Return up to 10 titles most similar to the movie with TMDB ID *movie_id* (offline)."""
    try:
        matches = movies_df[movies_df['movie_id'] == movie_id]
        if matches.empty:
            return []

        idx = matches.index[0]
        if idx >= len(top_idxs):
            return []

        similar_indices = top_idxs[idx][:10]

        return [
            movies_df.iloc[i].title
            for i in similar_indices
        ]
    except Exception as e:
        print(f"Error in recommend_by_id: {e}")
        return []




if __name__ == '__main__':
    print("Testing loaded similarity arrays:")
    print("Indices shape:", top_indices.shape)
    print("Example matches for first movie:", [movies.iloc[i].title for i in top_indices[0][:5]])
