import pandas as pd
import sqlite3
import requests
import os
import random
from flask import Flask, render_template, request, redirect, session, jsonify, url_for, flash, session
from dotenv import load_dotenv
from flask_mail import Mail, Message 

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'moviemind_secret_key')
API_KEY = os.getenv('TMDB_KEY')
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER') 
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')
mail = Mail(app)
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
        # আগের সব লাইন মুছে শুধু এই ৪টি টেবিল রাখুন
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            username TEXT UNIQUE, 
            password TEXT, 
            email TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            movie_name TEXT, 
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS poster_cache (
            title TEXT PRIMARY KEY, 
            url TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            movie TEXT, 
            liked INTEGER DEFAULT 0, 
            watchlist INTEGER DEFAULT 0, 
            UNIQUE(user_id, movie))''')
        conn.commit()

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
            query = query.strip() # Clean user input
            # Use a more flexible search match
            search_match = df[df['Title'].str.lower() == query.lower()]
            
            if not search_match.empty:
                # 1. Get the genre and STRIP trailing spaces
                raw_genre = search_match.iloc[0]['Genre']
                main_genre = raw_genre.split(',')[0].strip() 
                
                # 2. Find recommendations (Improved filter)
                recommend_matches = df[
                    df['Genre'].str.contains(main_genre, case=False, na=False) & 
                    (df['Title'].str.lower() != query.lower())
                ].head(10)
                
                # 3. Fetch posters (Note: this makes 10 API calls, it might be slow)
                results = [(r['Title'], fetch_poster(r['Title'])) for _, r in recommend_matches.iterrows()]
                
                c.execute("INSERT INTO searches (user_id, movie_name) VALUES (?,?)", (session['user_id'], query))
                conn.commit()
            else:
                not_found = True

        # Keep your existing history/trending logic below...
        c.execute("SELECT DISTINCT movie_name FROM searches WHERE user_id=? ORDER BY timestamp DESC LIMIT 5", (session['user_id'],))
        history = [x[0] for x in c.fetchall()]
        
        c.execute("SELECT movie_name FROM searches GROUP BY movie_name ORDER BY COUNT(*) DESC LIMIT 5")
        top_movies = [x[0] for x in c.fetchall()] or df.head(5)['Title'].tolist()
        trending = [(m, fetch_poster(m)) for m in top_movies]
        
        recommendations = [(r['Title'], fetch_poster(r['Title'])) for _, r in df.sample(5).iterrows()]
        u_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    return render_template("index.html", results=results, trending=trending, history=history, 
                           user_count=u_count, recommendations=recommendations, 
                           not_found=not_found, is_searching=bool(query), all_titles=ALL_TITLES, is_admin=session.get('is_admin', False))
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session: 
        return redirect('/login')
    
    msg = ""
    # ১. ইউজার অ্যাডমিন কি না চেক করা (যাতে প্রোফাইল এডিট করতে না পারে)
    is_admin_account = session.get('username', '').lower() == 'admin'
    
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        
        if request.method == 'POST':
            # ২. অ্যাডমিন যদি প্রোফাইল এডিট করার চেষ্টা করে তবে বাধা দেওয়া
            if is_admin_account:
                flash("Action prohibited: Admin credentials cannot be modified.", "error")
                return redirect(url_for('profile'))
            
            new_name = request.form.get('username')
            new_pass = request.form.get('password')
            
            try:
                # ৩. ডাটাবেস আপডেট লজিক
                c.execute("UPDATE users SET username=?, password=? WHERE id=?", 
                          (new_name, new_pass, session['user_id']))
                conn.commit()
                session['username'] = new_name
                flash("Profile updated successfully!", "success")
                return redirect(url_for('profile'))
            except sqlite3.IntegrityError:
                # যদি ইউজারনেম অন্য কেউ আগে নিয়ে থাকে
                flash("Username already taken! Choose another one.", "error")
                return redirect(url_for('profile'))
            except Exception as e:
                flash("Something went wrong. Please try again.", "error")
                return redirect(url_for('profile'))

        # ৪. লাইকড মুভি এবং ওয়াচলিস্ট ডেটা আনা
        c.execute("SELECT movie FROM interactions WHERE user_id=? AND liked=1 GROUP BY movie", (session['user_id'],))
        liked = [(m[0], fetch_poster(m[0])) for m in c.fetchall()]
        
        c.execute("SELECT movie FROM interactions WHERE user_id=? AND watchlist=1 GROUP BY movie", (session['user_id'],))
        watchlist = [(m[0], fetch_poster(m[0])) for m in c.fetchall()]
        
    return render_template("profile.html", liked=liked, watchlist=watchlist, is_admin=is_admin_account)

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
        #admin password check
        admin_pass = os.getenv('ADMIN_PASSWORD')
        
        if username == 'admin' and password == admin_pass:
            session['user_id'] = 0
            session['username'] = 'admin'
            session['is_admin'] = True # অ্যাডমিন হিসেবে চিহ্নিত করা
            return redirect(url_for('home'))
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
        u = request.form.get('username')
        p = request.form.get('password')
        e = request.form.get('email')
        
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            
            # ইউজারনেম চেক
            if c.execute("SELECT id FROM users WHERE username=?", (u,)).fetchone():
                flash("This username is already taken!", "error")
                return redirect(url_for('signup'))
            
            # ইমেইল চেক
            if c.execute("SELECT id FROM users WHERE email=?", (e,)).fetchone():
                flash("Email already registered!", "error")
                return redirect(url_for('signup'))
            
            try:
                c.execute("INSERT INTO users (username, password, email) VALUES (?,?,?)", (u, p, e))
                conn.commit()
                
                # সেশন সেট করা
                user = c.execute("SELECT id FROM users WHERE username=?", (u,)).fetchone()
                session['user_id'] = user[0]
                session['username'] = u
                session['is_admin'] = False
                
                flash("Account created successfully!", "success")
                return redirect(url_for('home'))
            except Exception as err:
                flash("Database Error: " + str(err), "error")
                return redirect(url_for('signup'))

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
@app.route('/send_otp', methods=['POST']) # এখানে শুধুমাত্র POST রাখুন
def send_otp():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        with sqlite3.connect('database.db') as conn:
            user = conn.execute("SELECT id FROM users WHERE username=? AND email=?", (username, email)).fetchone()
            
        if not user:
            flash("Username and Email do not match!", "error")
            return redirect(url_for('forget_password'))

        # অ্যাডমিন চেক
        if username.lower() == 'admin':
            flash("Admin password cannot be changed via this portal.", "error")
            return redirect(url_for('forget_password'))

        # OTP তৈরি এবং পাঠানো
        otp = random.randint(100000, 999999)
        session['reset_otp'] = str(otp) # সেশনে স্ট্রিং হিসেবে রাখুন
        session['reset_user'] = username

        try:
            msg = Message("MovieMind Reset OTP", sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f"Your OTP for password reset is: {otp}"
            mail.send(msg)
            flash("OTP sent to your email!", "success")
            return render_template('verify_otp.html') 
        except Exception as e:
            flash("Failed to send email. Check your connection.", "error")
            return redirect(url_for('forget_password'))
    
    # কেউ যদি সরাসরি /send_otp ইউআরএলে ঢুকতে চায় (GET request)
    return redirect(url_for('login'))# নতুন একটি HTML লাগবে OTP এন্ট্রি করার জন্য

@app.route('/verify_otp')
def verify_otp_page():
    # সেশনে ওটিপি না থাকলে সরাসরি ফরগেট পাসওয়ার্ড পেজে পাঠিয়ে দেবে
    if 'reset_otp' not in session: 
        return redirect(url_for('forget_password'))
    return render_template('verify_otp.html')

@app.route('/verify_and_update', methods=['POST'])
def verify_and_update():
    if 'reset_otp' not in session:
        return redirect(url_for('login'))
    
    entered_otp = request.form.get('otp')
    new_password = request.form.get('password')
    
    # ওটিপি চেক করা হচ্ছে
    if entered_otp and str(entered_otp) == str(session.get('reset_otp')):
        username = session.get('reset_user')
        with sqlite3.connect('database.db') as conn:
            conn.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
            conn.commit()
        
        # কাজ শেষ হলে সেশন থেকে ওটিপি ডেটা মুছে ফেলা
        session.pop('reset_otp', None)
        session.pop('reset_user', None)
        
        flash("Password updated successfully!", "success")
        return redirect(url_for('login'))
    else:
        flash("Invalid OTP! Please try again.", "error")
        return redirect(url_for('verify_otp_page')) # ভুল হলে ওটিপি পেজেই রিডাইরেক্ট করবে
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'username' not in session or not session.get('is_admin'): 
        flash("You do not have permission to access the Admin Panel.", "error")
        return redirect(url_for('home'))

    with sqlite3.connect('database.db') as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # এখানে u.email যোগ করা হয়েছে
        c.execute("""
            SELECT u.id, u.username, u.email, u.password, 
            (SELECT COUNT(*) FROM searches WHERE user_id = u.id) as search_count,
            (SELECT COUNT(*) FROM interactions WHERE user_id = u.id AND liked = 1) as like_count,
            (SELECT COUNT(*) FROM interactions WHERE user_id = u.id AND watchlist = 1) as watchlist_count
            FROM users u
        """)
        users_list = c.fetchall()
        
        c.execute("""
            SELECT u.username, s.movie_name, s.timestamp 
            FROM searches s 
            JOIN users u ON s.user_id = u.id 
            ORDER BY s.timestamp DESC LIMIT 100
        """)
        global_searches = c.fetchall()

    return render_template('admin.html', users=users_list, searches=global_searches)
@app.route('/forget_password')
def forget_password():
    session.pop('reset_otp', None) # পুরনো ওটিপি মুছে ফেলা
    session.pop('reset_user', None)
    return render_template('forget_password.html')
if __name__ == "__main__":
    init_db()
    app.run(debug=True)