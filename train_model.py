import pandas as pd
import numpy as np
import ast
import pickle

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# LOAD DATASETS

movies = pd.read_csv("tmdb_5000_movies.csv")
credits = pd.read_csv("tmdb_5000_credits.csv")


# MERGE DATASETS

movies = movies.merge(credits, on='title')


# KEEP IMPORTANT COLUMNS

movies = movies[['movie_id',
                 'title',
                 'overview',
                 'genres',
                 'keywords',
                 'cast',
                 'crew']]


# REMOVE MISSING VALUES

movies.dropna(inplace=True)
movies.reset_index(drop=True, inplace=True)


# HELPER FUNCTIONS

def convert(text):

    L = []

    for i in ast.literal_eval(text):
        L.append(i['name'])

    return L


def convert_cast(text):

    L = []
    counter = 0

    for i in ast.literal_eval(text):

        if counter != 3:
            L.append(i['name'])
            counter += 1

        else:
            break

    return L


def fetch_director(text):

    L = []

    for i in ast.literal_eval(text):

        if i['job'] == 'Director':
            L.append(i['name'])

    return L


# APPLY TRANSFORMATIONS

movies['genres'] = movies['genres'].apply(convert)

movies['keywords'] = movies['keywords'].apply(convert)

movies['cast'] = movies['cast'].apply(convert_cast)

movies['crew'] = movies['crew'].apply(fetch_director)

movies['overview'] = movies['overview'].apply(lambda x: x.split())


# REMOVE SPACES

movies['genres'] = movies['genres'].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

movies['keywords'] = movies['keywords'].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

movies['cast'] = movies['cast'].apply(
    lambda x: [i.replace(" ", "") for i in x]
)

movies['crew'] = movies['crew'].apply(
    lambda x: [i.replace(" ", "") for i in x]
)


# CREATE TAGS

movies['title_words'] = movies['title'].apply(lambda x: x.split())

movies['tags'] = (
    movies['title_words'] * 2 +
    movies['overview'] * 3 +
    movies['genres'] * 5 +
    movies['keywords'] * 3 +
    movies['cast'] * 2 +
    movies['crew'] * 4
)


# FINAL DATAFRAME

new_df = movies[['movie_id', 'title', 'tags']]

new_df['tags'] = new_df['tags'].apply(lambda x: " ".join(x))

new_df['tags'] = new_df['tags'].apply(lambda x: x.lower())


# VECTORIZATION

tfidf = TfidfVectorizer(
    max_features=5000,
    stop_words='english'
)

vectors = tfidf.fit_transform(new_df['tags']).toarray()


# COSINE SIMILARITY

similarity_matrix = cosine_similarity(vectors)

# Precompute and store only top 50 matches to save disk and memory space
top_indices = []
top_scores = []

for i in range(len(similarity_matrix)):
    scores = similarity_matrix[i]
    # Sort in descending order of similarity
    sorted_indices = np.argsort(scores)[::-1]
    # Exclude the movie itself (index i)
    filtered_indices = [idx for idx in sorted_indices if idx != i]
    # Keep top 50
    top_indices.append(filtered_indices[:50])
    top_scores.append(scores[filtered_indices[:50]].astype(np.float16))

top_indices = np.array(top_indices, dtype=np.int16)
top_scores = np.array(top_scores, dtype=np.float16)

similarity_data = {
    'indices': top_indices,
    'scores': top_scores
}


# RECOMMEND FUNCTION

def recommend(movie):
    movie = movie.lower().strip()
    matching_movies = new_df[
        new_df['title'].str.lower().str.contains(movie, regex=False)
    ]
    if matching_movies.empty:
        return []
    index = matching_movies.index[0]
    
    similar_indices = top_indices[index][:5]
    recommended_movies = []
    for i in similar_indices:
        recommended_movies.append(new_df.iloc[i].title)
    return recommended_movies


# TEST

print("Testing local recommendation for 'Avatar':")
print(recommend("Avatar"))


# SAVE FILES

pickle.dump(new_df, open('movies.pkl', 'wb'))
pickle.dump(similarity_data, open('similarity.pkl', 'wb'))

print("\nModel files saved successfully.")