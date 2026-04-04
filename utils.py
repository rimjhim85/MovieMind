import pickle

def recommend_movies(user_id, movies, ratings, model_data, n=5):
    movie_matrix, similarity = model_data

    user_index = user_id - 1  # adjust index

    similar_users = list(enumerate(similarity[user_index]))
    similar_users = sorted(similar_users, key=lambda x: x[1], reverse=True)[1:6]

    recommended = set()

    for user, _ in similar_users:
        user_movies = movie_matrix.iloc[user]
        liked = user_movies[user_movies > 3].index
        recommended.update(liked)

    result = []
    for movie_id in list(recommended)[:n]:
        title = movies[movies['movieId'] == movie_id]['title'].values
        if len(title) > 0:
            result.append(title[0])

    return result