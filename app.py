import pandas as pd
import sqlite3
import requests
import os
from flask import Flask, render_template, request, redirect, session, jsonify, url_for, flash, session
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'moviemind_secret_key')
API_KEY = os.getenv('TMDB_KEY')

# Load Dataset
try:
    df = pd.read_csv('IMDB-Movie-Data.csv')
    df.columns = df.columns.str.strip()
    ALL_TITLES = df['Title'].tolist()
except Exception as e:
    print(f"Error loading CSV: {e}")
    ALL_TITLES = []

def init_db():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS searches (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, movie_name TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS poster_cache (title TEXT PRIMARY KEY, url TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS interactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, movie TEXT, liked INTEGER DEFAULT 0, watchlist INTEGER DEFAULT 0, UNIQUE(user_id, movie))''')
        conn.commit()

init_db()

def fetch_poster(title):
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT url FROM poster_cache WHERE title=?", (title,))
        data = c.fetchone()
        if data: return data[0]
    
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={API_KEY}&query={title}"
        r = requests.get(url).json()
        path = r['results'][0]['poster_path'] if r.get('results') else None
        full = f"https://image.tmdb.org/t/p/w500{path}" if path else "https://via.placeholder.com/200x300?text=No+Image"
    except:
        full = "https://via.placeholder.com/200x300?text=Error"
    
    with sqlite3.connect('database.db') as conn:
        conn.execute("INSERT OR REPLACE INTO poster_cache VALUES (?,?)", (title, full))
        conn.commit()
    return full

@app.route('/', methods=['GET','POST'])
def home():
    if 'user_id' not in session: return redirect('/login')
    
    results = []
    not_found = False
    query = request.form.get('movie_name')
    
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        
        if query:
            search_match = df[df['Title'].str.lower() == query.lower()]
            if not search_match.empty:
                genre = search_match.iloc[0]['Genre'].split(',')[0]
                recommend_matches = df[df['Genre'].str.contains(genre, case=False) & (df['Title'].str.lower() != query.lower())].head(10)
                results = [(r['Title'], fetch_poster(r['Title'])) for _, r in recommend_matches.iterrows()]
                
                c.execute("INSERT INTO searches (user_id, movie_name) VALUES (?,?)", (session['user_id'], query))
                conn.commit()
            else:
                not_found = True

        c.execute("SELECT DISTINCT movie_name FROM searches WHERE user_id=? ORDER BY timestamp DESC LIMIT 5", (session['user_id'],))
        history = [x[0] for x in c.fetchall()]
        
        c.execute("SELECT movie_name FROM searches GROUP BY movie_name ORDER BY COUNT(*) DESC LIMIT 5")
        top_movies = [x[0] for x in c.fetchall()] or df.head(5)['Title'].tolist()
        trending = [(m, fetch_poster(m)) for m in top_movies]
        
        recommendations = [(r['Title'], fetch_poster(r['Title'])) for _, r in df.sample(5).iterrows()]
        u_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    return render_template("index.html", results=results, trending=trending, history=history, 
                           user_count=u_count, recommendations=recommendations, 
                           not_found=not_found, is_searching=bool(query), all_titles=ALL_TITLES)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session: return redirect('/login')
    msg = ""
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        if request.method == 'POST':
            new_name, new_pass = request.form.get('username'), request.form.get('password')
            try:
                c.execute("UPDATE users SET username=?, password=? WHERE id=?", (new_name, new_pass, session['user_id']))
                conn.commit()
                session['username'] = new_name
                msg = "Profile updated successfully!"
            except: msg = "Username already taken!"

        c.execute("SELECT movie FROM interactions WHERE user_id=? AND liked=1 GROUP BY movie", (session['user_id'],))
        liked = [(m[0], fetch_poster(m[0])) for m in c.fetchall()]
        c.execute("SELECT movie FROM interactions WHERE user_id=? AND watchlist=1 GROUP BY movie", (session['user_id'],))
        watchlist = [(m[0], fetch_poster(m[0])) for m in c.fetchall()]
    return render_template("profile.html", liked=liked, watchlist=watchlist, msg=msg)

# আপনার app.py এর interact রাউটটি অনেকটা এরকম হওয়া উচিত:
@app.route('/interact', methods=['POST'])
def interact():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    data = request.json
    action, movie = data.get('action'), data.get('movie')
    
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, liked, watchlist FROM interactions WHERE user_id=? AND movie=?", (session['user_id'], movie))
        row = c.fetchone()
        
        if row:
            # যদি আগে থেকেই ১ থাকে তবে ০ করে দেবে (Remove করবে)
            # যদি ০ থাকে তবে ১ করে দেবে (Add করবে)
            c.execute(f"UPDATE interactions SET {action} = 1 - {action} WHERE id=?", (row[0],))
        else:
            c.execute(f"INSERT INTO interactions (user_id, movie, {action}) VALUES (?,?,1)", (session['user_id'], movie))
        conn.commit()
    return jsonify({"status": "success"})
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            # SQL কোয়েরি দিয়ে ইউজার চেক করা হচ্ছে
            c.execute("SELECT id, username, password FROM users WHERE username=?", (username,))
            user = c.fetchone()

        if user:
            # ইউজার পাওয়া গেলে পাসওয়ার্ড চেক করা
            db_user_id, db_username, db_password = user
            if db_password == password:
                session['user_id'] = db_user_id
                session['username'] = db_username
                return redirect(url_for('home'))
            else:
                # পাসওয়ার্ড ভুল হলে
                flash("Wrong password! Try again.", "error")
                return redirect(url_for('login'))
        else:
            # অ্যাকাউন্ট না থাকলে এই মেসেজটি ট্রিগার হবে
            flash("You don't have an account. Please create a new account.", "no_account")
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        u, p = request.form['username'], request.form['password']
        try:
            with sqlite3.connect('database.db') as conn:
                conn.execute("INSERT INTO users (username,password) VALUES (?,?)",(u,p))
                conn.commit()
                user = conn.execute("SELECT id FROM users WHERE username=?", (u,)).fetchone()
                session['user_id'], session['username'] = user[0], u
            return redirect('/')
        except: return "Error"
    return render_template('signup.html')

@app.route('/clear_history', methods=['POST'])
def clear_history():
    with sqlite3.connect('database.db') as conn:
        conn.execute("DELETE FROM searches WHERE user_id=?", (session['user_id'],))
        conn.commit()
    return jsonify({"status": "success"})

@app.route('/delete_account', methods=['POST'])
def delete_account():
    uid = session['user_id']
    with sqlite3.connect('database.db') as conn:
        conn.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.execute("DELETE FROM searches WHERE user_id=?", (uid,))
        conn.execute("DELETE FROM interactions WHERE user_id=?", (uid,))
        conn.commit()
    session.clear()
    return jsonify({"status": "success"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
@app.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('password')
        
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            # ইউজার ডাটাবেসে আছে কি না চেক করা
            c.execute("SELECT id FROM users WHERE username=?", (username,))
            user = c.fetchone()
            
            if user:
                # পাসওয়ার্ড আপডেট করা
                c.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
                conn.commit()
                flash("Password changed successfully! Please login.", "success")
                return redirect(url_for('login'))
            else:
                flash("Username not found!", "error")
                return redirect(url_for('forget_password'))
                
    return render_template('forget_password.html')
if __name__ == "__main__":
    app.run(debug=True)