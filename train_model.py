import pandas as pd
import numpy as np
import ast
import pickle

from sklearn.feature_extraction.text import CountVectorizer
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

# REDUCE DATASET SIZE FOR DEPLOYMENT

movies = movies.head(2500)


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

movies['tags'] = (
    movies['overview'] +
    movies['genres'] +
    movies['keywords'] +
    movies['cast'] +
    movies['crew']
)


# FINAL DATAFRAME

new_df = movies[['movie_id', 'title', 'tags']]

new_df['tags'] = new_df['tags'].apply(lambda x: " ".join(x))

new_df['tags'] = new_df['tags'].apply(lambda x: x.lower())


# VECTORIZATION

cv = CountVectorizer(
    max_features=5000,
    stop_words='english'
)

vectors = cv.fit_transform(new_df['tags']).toarray()


# COSINE SIMILARITY

similarity = cosine_similarity(vectors)


# RECOMMEND FUNCTION

def recommend(movie):

    movie = movie.lower()

    matching_movies = new_df[
        new_df['title'].str.lower().str.contains(movie)
    ]

    if matching_movies.empty:
        return []

    index = matching_movies.index[0]

    distances = similarity[index]

    movies_list = sorted(
        list(enumerate(distances)),
        reverse=True,
        key=lambda x: x[1]
    )[1:6]

    recommended_movies = []

    for i in movies_list:

        recommended_movies.append(
            new_df.iloc[i[0]].title
        )

    return recommended_movies


# TEST

recommend("Avatar")


# SAVE FILES

pickle.dump(new_df, open('movies.pkl', 'wb'))

pickle.dump(similarity, open('similarity.pkl', 'wb'))

print("\nModel files saved successfully.")