import pandas as pd
import sqlite3
import requests
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from dotenv import load_dotenv
import os

# 1. Load environment variables
load_dotenv()

app = Flask(__name__)

# 2. Set API Key and Secret Key from .env (with fallbacks)
API_KEY = os.getenv('TMDB_KEY')
# Use the string from .env, or a fallback if .env isn't found
app.secret_key = os.getenv('SECRET_KEY', 'moviemind_default_secret_123')

# 3. Load Data
try:
    df = pd.read_csv('IMDB-Movie-Data.csv')
    df.columns = df.columns.str.strip()
except Exception as e:
    print(f"Error loading CSV: {e}")
    df = pd.DataFrame(columns=['Title', 'Genre', 'Rating', 'Description', 'Director', 'Year'])

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, movie_name TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS poster_cache (title TEXT PRIMARY KEY, url TEXT)')
        conn.commit()

init_db()

# --- 2. LOGIC FUNCTIONS ---
def fetch_poster(title):
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT url FROM poster_cache WHERE title=?", (title,))
        cached = c.fetchone()
        if cached: return cached[0]
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={title}"
        r = requests.get(url, timeout=2).json()
        path = r['results'][0].get('poster_path') if r.get('results') else None
        final_url = f"https://image.tmdb.org/t/p/w500{path}" if path else "https://via.placeholder.com/200x300"
        with sqlite3.connect('database.db') as conn:
            conn.execute("INSERT OR REPLACE INTO poster_cache VALUES (?,?)", (title, final_url))
        return final_url
    except: return "https://via.placeholder.com/200x300"

# --- 3. ROUTES ---

@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session: return redirect(url_for('login'))
    results = []
    query = request.form.get('movie_name') or request.args.get('auto_search')

    if query:
        with sqlite3.connect('database.db') as conn:
            conn.execute("INSERT INTO searches (user_id, movie_name) VALUES (?,?)", (session['user_id'], query))
        
        match = df[df['Title'].str.lower() == query.lower()]
        if not match.empty:
            g = match.iloc[0]['Genre'].split(',')[0].strip()
            recs = df[df['Genre'].str.contains(g)].sort_values(by='Rating', ascending=False).head(10)
            results = [(r['Title'], fetch_poster(r['Title'])) for _, r in recs.iterrows()]

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT DISTINCT movie_name FROM searches WHERE user_id=? ORDER BY id DESC LIMIT 5", (session['user_id'],))
        recent = [r[0] for r in c.fetchall()]

    return render_template('index.html', results=results, recent=recent)

@app.route('/autocomplete')
def autocomplete():
    q = request.args.get('q', '').lower()
    matches = df[df['Title'].str.lower().str.contains(q, na=False)]['Title'].head(8).tolist()
    return jsonify(matches)

@app.route('/surprise')
def surprise():
    min_r = float(request.args.get('rating', 8.0))
    pool = df[df['Rating'] >= min_r]
    lucky_movie = pool.sample(n=1).iloc[0]['Title'] if not pool.empty else df.sample(n=1).iloc[0]['Title']
    return redirect(f'/?auto_search={lucky_movie}')

@app.route('/clear_history')
def clear_history():
    if 'user_id' in session:
        with sqlite3.connect('database.db') as conn:
            conn.execute("DELETE FROM searches WHERE user_id=?", (session['user_id'],))
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        with sqlite3.connect('database.db') as conn:
            user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
            if user:
                session['user_id'], session['username'] = user[0], user[1]
                return redirect(url_for('home'))
            else:
                return "Invalid username or password"
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        with sqlite3.connect('database.db') as conn:
            existing_user = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
            
            if existing_user:
                if existing_user[2] == p:
                    session['user_id'], session['username'] = existing_user[0], existing_user[1]
                    return redirect('/?existing=true')
                else:
                    return "Account exists with a different password!"
            
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password) VALUES (?,?)", (u, p))
            conn.commit()
            session['user_id'], session['username'] = cursor.lastrowid, u
            return redirect(url_for('home'))
            
    return render_template('signup.html')

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' in session:
        user_id = session['user_id']
        with sqlite3.connect('database.db') as conn:
            conn.execute("DELETE FROM searches WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
        session.clear()
    return redirect(url_for('signup'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- 4. RENDER DEPLOYMENT CONFIG ---
if __name__ == "__main__":
    # Get port from environment for Render, default to 5000 for local
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' is required for Render to map the port correctly
    app.run(host='0.0.0.0', port=port)