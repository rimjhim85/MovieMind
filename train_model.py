import pandas as pd
import pickle
from sklearn.metrics.pairwise import cosine_similarity

# Load data
ratings = pd.read_csv('ratings.csv')

# Create pivot table
movie_matrix = ratings.pivot_table(index='userId', columns='movieId', values='rating').fillna(0)

# Compute similarity
similarity = cosine_similarity(movie_matrix)

# Save
pickle.dump((movie_matrix, similarity), open('model.pkl', 'wb'))

print("Model trained successfully!")