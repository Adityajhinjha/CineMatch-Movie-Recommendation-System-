
import pickle
import numpy as np

with open('movies.pkl', 'rb') as f:
    movies = pickle.load(f)           

with open('similarity.pkl', 'rb') as f:
    _sim64 = pickle.load(f)

    similarity = _sim64.astype(np.float32)
    del _sim64                      


def recommend(movie: str) -> list[str]:
    """Return up to 5 titles most similar to *movie* (case-insensitive)."""
    movie = movie.lower().strip()

    matches = movies[movies['title'].str.lower().str.contains(movie, regex=False)]
    if matches.empty:
        return []

    idx = matches.index[0]


    row = similarity[idx]                         
    top_idx = np.argpartition(row, -6)[-6:]     
    top_idx = top_idx[np.argsort(row[top_idx])[::-1]] 

    return [
        movies.iloc[i].title
        for i in top_idx
        if i != idx
    ][:5]



if __name__ == '__main__':
    print("Re-saving similarity.pkl as float32 …")
    with open('similarity.pkl', 'rb') as f:
        sim = pickle.load(f).astype(np.float32)
    with open('similarity.pkl', 'wb') as f:
        pickle.dump(sim, f)
    print(f"Done — {sim.nbytes / 1024**2:.1f} MB (was 176 MB)")
