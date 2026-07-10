
import pickle
import numpy as np

with open('movies.pkl', 'rb') as f:
    movies = pickle.load(f)           

with open('similarity.pkl', 'rb') as f:
    similarity_data = pickle.load(f)

top_indices = similarity_data['indices']


def recommend(movie: str) -> list[str]:
    """Return up to 5 titles most similar to *movie* (case-insensitive)."""
    movie = movie.lower().strip()

    matches = movies[movies['title'].str.lower().str.contains(movie, regex=False)]
    if matches.empty:
        return []

    idx = matches.index[0]


    similar_indices = top_indices[idx][:5]

    return [
        movies.iloc[i].title
        for i in similar_indices
    ]



if __name__ == '__main__':
    print("Testing loaded similarity arrays:")
    print("Indices shape:", top_indices.shape)
    print("Example matches for first movie:", [movies.iloc[i].title for i in top_indices[0][:5]])
