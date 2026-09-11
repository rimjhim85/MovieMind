
import os
import random
import sqlite3

import pandas as pd
import requests

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    jsonify,
    url_for,
    flash
)

from dotenv import load_dotenv
from flask_mail import Mail, Message


# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    'SECRET_KEY',
    'moviemind_secret_key'
)

API_KEY = os.getenv('TMDB_KEY')


# =========================================================
# MAIL CONFIGURATION
# =========================================================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASS')

mail = Mail(app)


# =========================================================
# LOAD DATASET
# =========================================================

try:

    df = pd.read_csv(
        'IMDB-Movie-Data.csv'
    )

    df.columns = df.columns.str.strip()

    ALL_TITLES = df['Title'].astype(str).tolist()

except Exception as e:

    print(
        f"Error loading CSV: {e}"
    )

    ALL_TITLES = []

    df = pd.DataFrame()


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    with sqlite3.connect(
        'database.db'
    ) as conn:

        c = conn.cursor()


        # USERS
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                email TEXT
            )
            '''
        )


        # SEARCH HISTORY
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                movie_name TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )


        # POSTER CACHE
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS poster_cache (
                title TEXT PRIMARY KEY,
                url TEXT
            )
            '''
        )


        # LIKES / WATCHLIST
        c.execute(
            '''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                movie TEXT,
                liked INTEGER DEFAULT 0,
                watchlist INTEGER DEFAULT 0,
                UNIQUE(user_id, movie)
            )
            '''
        )


        conn.commit()


# =========================================================
# FETCH POSTER FROM TMDB
# =========================================================

def fetch_poster(title):

    # First check local cache
    try:

        with sqlite3.connect(
            'database.db'
        ) as conn:

            c = conn.cursor()

            c.execute(
                '''
                SELECT url
                FROM poster_cache
                WHERE title=?
                ''',
                (title,)
            )

            data = c.fetchone()

            if data:

                return data[0]

    except Exception as e:

        print(
            f"Poster cache error: {e}"
        )


    # No API key
    if not API_KEY:

        return (
            'https://via.placeholder.com/'
            '500x750?text=No+Image'
        )


    try:

        response = requests.get(

            'https://api.themoviedb.org/3/search/movie',

            params={
                'api_key': API_KEY,
                'query': title,
                'include_adult': 'false',
                'language': 'en-US'
            },

            timeout=8

        )

        response.raise_for_status()

        data = response.json()

        results = data.get(
            'results',
            []
        )


        if results:

            path = results[0].get(
                'poster_path'
            )

        else:

            path = None


        if path:

            full = (
                'https://image.tmdb.org/t/p/w500'
                + path
            )

        else:

            full = (
                'https://via.placeholder.com/'
                '500x750?text=No+Image'
            )


    except Exception as e:

        print(
            f"Poster error for '{title}': {e}"
        )

        full = (
            'https://via.placeholder.com/'
            '500x750?text=Error'
        )


    # Save in cache
    try:

        with sqlite3.connect(
            'database.db'
        ) as conn:

            conn.execute(
                '''
                INSERT OR REPLACE INTO poster_cache
                (title, url)
                VALUES (?, ?)
                ''',
                (title, full)
            )

            conn.commit()

    except Exception as e:

        print(
            f"Could not cache poster: {e}"
        )


    return full


# =========================================================
# HOME
# =========================================================

@app.route(
    '/',
    methods=['GET', 'POST']
)
def home():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )


    results = []

    not_found = False

    query = request.form.get(
        'movie_name'
    )


    with sqlite3.connect(
        'database.db'
    ) as conn:

        c = conn.cursor()


        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        if query:

            query = query.strip()


            if not df.empty:

                search_match = df[
                    df['Title']
                    .astype(str)
                    .str.lower()
                    ==
                    query.lower()
                ]

            else:

                search_match = pd.DataFrame()


            if not search_match.empty:

                raw_genre = str(
                    search_match.iloc[0].get(
                        'Genre',
                        ''
                    )
                )


                main_genre = (
                    raw_genre
                    .split(',')[0]
                    .strip()
                )


                # Find recommendations
                if not df.empty:

                    recommend_matches = df[
                        df['Genre']
                        .astype(str)
                        .str.contains(
                            main_genre,
                            case=False,
                            na=False
                        )
                        &
                        (
                            df['Title']
                            .astype(str)
                            .str.lower()
                            != query.lower()
                        )
                    ].head(10)

                else:

                    recommend_matches = pd.DataFrame()


                results = [

                    (
                        str(row['Title']),
                        fetch_poster(
                            str(row['Title'])
                        )
                    )

                    for _, row
                    in recommend_matches.iterrows()

                ]


                # Save search
                c.execute(
                    '''
                    INSERT INTO searches
                    (user_id, movie_name)
                    VALUES (?, ?)
                    ''',
                    (
                        session['user_id'],
                        query
                    )
                )

                conn.commit()


            else:

                not_found = True


        # -------------------------------------------------
        # HISTORY
        # -------------------------------------------------

        c.execute(
            '''
            SELECT DISTINCT movie_name
            FROM searches
            WHERE user_id=?
            ORDER BY timestamp DESC
            LIMIT 5
            ''',
            (
                session['user_id'],
            )
        )

        history = [
            row[0]
            for row in c.fetchall()
        ]


        # -------------------------------------------------
        # TRENDING
        # -------------------------------------------------

        c.execute(
            '''
            SELECT movie_name
            FROM searches
            GROUP BY movie_name
            ORDER BY COUNT(*) DESC
            LIMIT 5
            '''
        )

        top_movies = [
            row[0]
            for row in c.fetchall()
        ]


        if not top_movies and not df.empty:

            top_movies = (
                df.head(5)['Title']
                .astype(str)
                .tolist()
            )


        trending = [

            (
                movie,
                fetch_poster(movie)
            )

            for movie in top_movies

        ]


        # -------------------------------------------------
        # RANDOM RECOMMENDATIONS
        # -------------------------------------------------

        if not df.empty:

            sample_size = min(
                5,
                len(df)
            )

            sample = df.sample(
                sample_size
            )

            recommendations = [

                (
                    str(row['Title']),
                    fetch_poster(
                        str(row['Title'])
                    )
                )

                for _, row in sample.iterrows()

            ]

        else:

            recommendations = []


        # -------------------------------------------------
        # USER COUNT
        # -------------------------------------------------

        u_count = c.execute(
            '''
            SELECT COUNT(*)
            FROM users
            '''
        ).fetchone()[0]


    return render_template(

        'index.html',

        results=results,

        trending=trending,

        history=history,

        user_count=u_count,

        recommendations=recommendations,

        not_found=not_found,

        is_searching=bool(query),

        all_titles=ALL_TITLES,

        is_admin=session.get(
            'is_admin',
            False
        )

    )


# =========================================================
# PROFILE
# =========================================================

@app.route(
    '/profile',
    methods=['GET', 'POST']
)
def profile():

    if 'user_id' not in session:

        return redirect(
            url_for('login')
        )


    msg = ""

    is_admin_account = (
        session.get(
            'username',
            ''
        ).lower()
        == 'admin'
    )


    with sqlite3.connect(
        'database.db'
    ) as conn:

        c = conn.cursor()


        # -------------------------------------------------
        # UPDATE PROFILE
        # -------------------------------------------------

        if request.method == 'POST':

            if is_admin_account:

                flash(
                    'Action prohibited: Admin credentials cannot be modified.',
                    'error'
                )

                return redirect(
                    url_for('profile')
                )


            new_name = request.form.get(
                'username'
            )

            new_pass = request.form.get(
                'password'
            )


            try:

                c.execute(
                    '''
                    UPDATE users
                    SET username=?, password=?
                    WHERE id=?
                    ''',
                    (
                        new_name,
                        new_pass,
                        session['user_id']
                    )
                )

                conn.commit()


                session['username'] = new_name


                flash(
                    'Profile updated successfully!',
                    'success'
                )


                return redirect(
                    url_for('profile')
                )


            except sqlite3.IntegrityError:

                flash(
                    'Username already taken! Choose another one.',
                    'error'
                )

                return redirect(
                    url_for('profile')
                )


            except Exception as e:

                print(
                    f"Profile update error: {e}"
                )

                flash(
                    'Something went wrong. Please try again.',
                    'error'
                )

                return redirect(
                    url_for('profile')
                )


        # -------------------------------------------------
        # LIKED MOVIES
        # -------------------------------------------------

        c.execute(
            '''
            SELECT movie
            FROM interactions
            WHERE user_id=?
            AND liked=1
            GROUP BY movie
            ''',
            (
                session['user_id'],
            )
        )

        liked = [

            (
                row[0],
                fetch_poster(row[0])
            )

            for row in c.fetchall()

        ]


        # -------------------------------------------------
        # WATCHLIST
        # -------------------------------------------------

        c.execute(
            '''
            SELECT movie
            FROM interactions
            WHERE user_id=?
            AND watchlist=1
            GROUP BY movie
            ''',
            (
                session['user_id'],
            )
        )

        watchlist = [

            (
                row[0],
                fetch_poster(row[0])
            )

            for row in c.fetchall()

        ]


    return render_template(

        'profile.html',

        liked=liked,

        watchlist=watchlist,

        is_admin=is_admin_account

    )


# =========================================================
# LIKE / WATCHLIST
# =========================================================

@app.route(
    '/interact',
    methods=['POST']
)
def interact():

    if 'user_id' not in session:

        return jsonify({
            'status': 'error',
            'message': 'Not logged in'
        }), 401


    data = request.get_json(
        silent=True
    ) or {}


    action = data.get(
        'action'
    )

    movie = data.get(
        'movie'
    )


    # Only allow these two fields
    if action not in [
        'liked',
        'watchlist'
    ]:

        return jsonify({
            'status': 'error',
            'message': 'Invalid action'
        }), 400


    if not movie:

        return jsonify({
            'status': 'error',
            'message': 'Movie is required'
        }), 400


    with sqlite3.connect(
        'database.db'
    ) as conn:

        c = conn.cursor()


        c.execute(
            '''
            SELECT id, liked, watchlist
            FROM interactions
            WHERE user_id=?
            AND movie=?
            ''',
            (
                session['user_id'],
                movie
            )
        )


        row = c.fetchone()


        if row:

            column_value = row[1] \
                if action == 'liked' \
                else row[2]


            new_value = 0 \
                if column_value \
                else 1


            c.execute(
                f'''
                UPDATE interactions
                SET {action}=?
                WHERE id=?
                ''',
                (
                    new_value,
                    row[0]
                )
            )


        else:

            c.execute(
                f'''
                INSERT INTO interactions
                (user_id, movie, {action})
                VALUES (?, ?, 1)
                ''',
                (
                    session['user_id'],
                    movie
                )
            )


        conn.commit()


    return jsonify({
        'status': 'success'
    })


# =========================================================
# LOGIN
# =========================================================

@app.route(
    '/login',
    methods=['GET', 'POST']
)
def login():

    if request.method == 'POST':

        username = request.form.get(
            'username'
        )

        password = request.form.get(
            'password'
        )


        # -------------------------------------------------
        # ADMIN
        # -------------------------------------------------

        admin_pass = os.getenv(
            'ADMIN_PASSWORD'
        )


        if (
            username == 'admin'
            and password == admin_pass
        ):

            session['user_id'] = 0

            session['username'] = 'admin'

            session['is_admin'] = True


            return redirect(
                url_for('home')
            )


        # -------------------------------------------------
        # NORMAL USER
        # -------------------------------------------------

        with sqlite3.connect(
            'database.db'
        ) as conn:

            c = conn.cursor()


            c.execute(
                '''
                SELECT id, username, password
                FROM users
                WHERE username=?
                ''',
                (
                    username,
                )
            )


            user = c.fetchone()


        if user:

            db_user_id = user[0]

            db_username = user[1]

            db_password = user[2]


            if db_password == password:

                session['user_id'] = (
                    db_user_id
                )

                session['username'] = (
                    db_username
                )

                session['is_admin'] = False


                return redirect(
                    url_for('home')
                )


            else:

                flash(
                    'Wrong password! Try again.',
                    'error'
                )

                return redirect(
                    url_for('login')
                )


        else:

            flash(
                "You don't have an account. Please create a new account.",
                'no_account'
            )

            return redirect(
                url_for('login')
            )


    return render_template(
        'login.html'
    )


# =========================================================
# SIGNUP
# =========================================================

@app.route(
    '/signup',
    methods=['GET', 'POST']
)
def signup():

    if request.method == 'POST':

        u = request.form.get(
            'username'
        )

        p = request.form.get(
            'password'
        )

        e = request.form.get(
            'email'
        )


        with sqlite3.connect(
            'database.db'
        ) as conn:

            c = conn.cursor()


            # Username check
            existing_username = c.execute(
                '''
                SELECT id
                FROM users
                WHERE username=?
                ''',
                (u,)
            ).fetchone()


            if existing_username:

                flash(
                    'This username is already taken!',
                    'error'
                )

                return redirect(
                    url_for('signup')
                )


            # Email check
            existing_email = c.execute(
                '''
                SELECT id
                FROM users
                WHERE email=?
                ''',
                (e,)
            ).fetchone()


            if existing_email:

                flash(
                    'Email already registered!',
                    'error'
                )

                return redirect(
                    url_for('signup')
                )


            try:

                c.execute(
                    '''
                    INSERT INTO users
                    (username, password, email)
                    VALUES (?, ?, ?)
                    ''',
                    (
                        u,
                        p,
                        e
                    )
                )

                conn.commit()


                user = c.execute(
                    '''
                    SELECT id
                    FROM users
                    WHERE username=?
                    ''',
                    (u,)
                ).fetchone()


                session['user_id'] = (
                    user[0]
                )

                session['username'] = u

                session['is_admin'] = False


                flash(
                    'Account created successfully!',
                    'success'
                )


                return redirect(
                    url_for('home')
                )


            except Exception as err:

                flash(
                    'Database Error: '
                    + str(err),
                    'error'
                )

                return redirect(
                    url_for('signup')
                )


    return render_template(
        'signup.html'
    )


# =========================================================
# CLEAR SEARCH HISTORY
# =========================================================

@app.route(
    '/clear_history',
    methods=['POST']
)
def clear_history():

    if 'user_id' not in session:

        return jsonify({
            'status': 'error'
        }), 401


    with sqlite3.connect(
        'database.db'
    ) as conn:

        conn.execute(
            '''
            DELETE FROM searches
            WHERE user_id=?
            ''',
            (
                session['user_id'],
            )
        )

        conn.commit()


    return jsonify({
        'status': 'success'
    })


# =========================================================
# DELETE ACCOUNT
# =========================================================

@app.route(
    '/delete_account',
    methods=['POST']
)
def delete_account():

    if 'user_id' not in session:

        return jsonify({
            'status': 'error'
        }), 401


    uid = session['user_id']


    # Don't allow admin to delete itself
    if session.get(
        'is_admin',
        False
    ):

        return jsonify({
            'status': 'error',
            'message': 'Admin account cannot be deleted here.'
        }), 403


    with sqlite3.connect(
        'database.db'
    ) as conn:

        conn.execute(
            '''
            DELETE FROM users
            WHERE id=?
            ''',
            (uid,)
        )


        conn.execute(
            '''
            DELETE FROM searches
            WHERE user_id=?
            ''',
            (uid,)
        )


        conn.execute(
            '''
            DELETE FROM interactions
            WHERE user_id=?
            ''',
            (uid,)
        )


        conn.commit()


    session.clear()


    return jsonify({
        'status': 'success'
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect(
        url_for('login')
    )


# =========================================================
# SEND OTP
# =========================================================

@app.route(
    '/send_otp',
    methods=['POST']
)
def send_otp():

    username = request.form.get(
        'username'
    )

    email = request.form.get(
        'email'
    )


    with sqlite3.connect(
        'database.db'
    ) as conn:

        user = conn.execute(
            '''
            SELECT id
            FROM users
            WHERE username=?
            AND email=?
            ''',
            (
                username,
                email
            )
        ).fetchone()


    if not user:

        flash(
            'Username and Email do not match!',
            'error'
        )

        return redirect(
            url_for('forget_password')
        )


    # Admin password cannot be changed
    if username.lower() == 'admin':

        flash(
            'Admin password cannot be changed via this portal.',
            'error'
        )

        return redirect(
            url_for('forget_password')
        )


    # Generate OTP
    otp = random.randint(
        100000,
        999999
    )


    session['reset_otp'] = str(
        otp
    )

    session['reset_user'] = username


    try:

        msg = Message(

            'MovieMind Reset OTP',

            sender=app.config[
                'MAIL_USERNAME'
            ],

            recipients=[email]

        )


        msg.body = (
            f'Your OTP for password reset is: {otp}'
        )


        mail.send(msg)


        flash(
            'OTP sent to your email!',
            'success'
        )


        return render_template(
            'verify_otp.html'
        )


    except Exception as e:

        print(
            f"Email error: {e}"
        )


        flash(
            'Failed to send email. Check your connection.',
            'error'
        )


        return redirect(
            url_for('forget_password')
        )


# =========================================================
# VERIFY OTP PAGE
# =========================================================

@app.route('/verify_otp')
def verify_otp_page():

    if 'reset_otp' not in session:

        return redirect(
            url_for('forget_password')
        )


    return render_template(
        'verify_otp.html'
    )


# =========================================================
# VERIFY OTP + UPDATE PASSWORD
# =========================================================

@app.route(
    '/verify_and_update',
    methods=['POST']
)
def verify_and_update():

    if 'reset_otp' not in session:

        return redirect(
            url_for('login')
        )


    entered_otp = request.form.get(
        'otp'
    )

    new_password = request.form.get(
        'password'
    )


    if (
        entered_otp
        and
        str(entered_otp)
        ==
        str(session.get('reset_otp'))
    ):

        username = session.get(
            'reset_user'
        )


        with sqlite3.connect(
            'database.db'
        ) as conn:

            conn.execute(
                '''
                UPDATE users
                SET password=?
                WHERE username=?
                ''',
                (
                    new_password,
                    username
                )
            )

            conn.commit()


        session.pop(
            'reset_otp',
            None
        )

        session.pop(
            'reset_user',
            None
        )


        flash(
            'Password updated successfully!',
            'success'
        )


        return redirect(
            url_for('login')
        )


    else:

        flash(
            'Invalid OTP! Please try again.',
            'error'
        )


        return redirect(
            url_for('verify_otp_page')
        )


# =========================================================
# MOVIE DETAILS
# =========================================================

@app.route(
    '/movie_details',
    methods=['POST']
)
def movie_details():

    data = request.get_json(
        silent=True
    ) or {}


    title = (
        data.get('title')
        or ''
    ).strip()


    if not title:

        return jsonify({
            'error': 'Movie title is required'
        }), 400


    # -----------------------------------------------------
    # DATASET FALLBACK
    # -----------------------------------------------------

    fallback = {

        'title': title,

        'overview': '',

        'year': None,

        'runtime': None,

        'rating': None,

        'genres': []

    }


    try:

        if not df.empty:

            local = df[
                df['Title']
                .astype(str)
                .str.lower()
                ==
                title.lower()
            ]

        else:

            local = pd.DataFrame()


        if not local.empty:

            row = local.iloc[0]


            fallback = {

                'title':
                    str(
                        row.get(
                            'Title',
                            title
                        )
                    ),

                'overview':
                    str(
                        row.get(
                            'Description',
                            ''
                        )
                    ),

                'year':
                    (
                        int(row['Year'])
                        if pd.notna(
                            row.get('Year')
                        )
                        else None
                    ),

                'runtime':
                    (
                        int(
                            row[
                                'Runtime (Minutes)'
                            ]
                        )
                        if pd.notna(
                            row.get(
                                'Runtime (Minutes)'
                            )
                        )
                        else None
                    ),

                'rating':
                    (
                        float(
                            row['Rating']
                        )
                        if pd.notna(
                            row.get('Rating')
                        )
                        else None
                    ),

                'genres': [

                    g.strip()

                    for g in str(
                        row.get(
                            'Genre',
                            ''
                        )
                    ).split(',')

                    if g.strip()

                ]

            }


    except Exception as e:

        print(
            f"Dataset lookup error: {e}"
        )


    # -----------------------------------------------------
    # NO TMDB KEY
    # -----------------------------------------------------

    if not API_KEY:

        return jsonify({

            **fallback,

            'poster':
                fetch_poster(title),

            'backdrop':
                None,

            'trailer_key':
                None,

            'providers': {}

        })


    try:

        base = (
            'https://api.themoviedb.org/3'
        )


        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        search_response = requests.get(

            f'{base}/search/movie',

            params={

                'api_key':
                    API_KEY,

                'query':
                    title,

                'include_adult':
                    'false',

                'language':
                    'en-US'

            },

            timeout=8

        )


        search_response.raise_for_status()


        search = search_response.json()


        matches = (
            search.get('results')
            or []
        )


        if not matches:

            return jsonify({

                **fallback,

                'poster':
                    fetch_poster(title),

                'backdrop':
                    None,

                'trailer_key':
                    None,

                'providers': {}

            })


        # -------------------------------------------------
        # BEST MATCH
        # -------------------------------------------------

        movie = next(

            (

                item

                for item
                in matches

                if str(
                    item.get(
                        'title',
                        ''
                    )
                ).lower()
                ==
                title.lower()

            ),

            matches[0]

        )


        movie_id = movie.get(
            'id'
        )


        if not movie_id:

            return jsonify({

                **fallback,

                'poster':
                    fetch_poster(title),

                'backdrop':
                    None,

                'trailer_key':
                    None,

                'providers': {}

            })


        # -------------------------------------------------
        # DETAILS
        # -------------------------------------------------

        details_response = requests.get(

            f'{base}/movie/{movie_id}',

            params={

                'api_key':
                    API_KEY,

                'language':
                    'en-US'

            },

            timeout=8

        )


        details_response.raise_for_status()


        details = (
            details_response.json()
        )


        # -------------------------------------------------
        # VIDEOS
        # -------------------------------------------------

        videos_response = requests.get(

            f'{base}/movie/{movie_id}/videos',

            params={

                'api_key':
                    API_KEY,

                'language':
                    'en-US'

            },

            timeout=8

        )


        videos_response.raise_for_status()


        videos = (
            videos_response.json()
        )


        # -------------------------------------------------
        # WATCH PROVIDERS
        # -------------------------------------------------

        watch_response = requests.get(

            f'{base}/movie/{movie_id}/watch/providers',

            params={
                'api_key': API_KEY
            },

            timeout=8

        )


        watch_response.raise_for_status()


        watch = (
            watch_response.json()
        )


        # -------------------------------------------------
        # TRAILER
        # -------------------------------------------------

        trailer = next(

            (

                video

                for video
                in videos.get(
                    'results',
                    []
                )

                if (
                    video.get('site')
                    == 'YouTube'
                    and
                    video.get('type')
                    == 'Trailer'
                    and
                    video.get('official')
                    is True
                )

            ),

            None

        )


        # Fallback to any YouTube trailer
        if not trailer:

            trailer = next(

                (

                    video

                    for video
                    in videos.get(
                        'results',
                        []
                    )

                    if (
                        video.get('site')
                        == 'YouTube'
                        and
                        video.get('type')
                        == 'Trailer'
                    )

                ),

                None

            )


        # -------------------------------------------------
        # INDIA PROVIDERS
        # -------------------------------------------------

        india = (
            watch
            .get('results', {})
            .get('IN', {})
            or {}
        )


        providers = {

            'link':
                india.get('link'),

            'flatrate': [],

            'free': [],

            'ads': [],

            'rent': [],

            'buy': []

        }


        for key in [

            'flatrate',

            'free',

            'ads',

            'rent',

            'buy'

        ]:

            seen = set()


            for item in (
                india.get(key, [])
                or []
            ):

                name = item.get(
                    'provider_name'
                )


                if not name:
                    continue


                if name in seen:
                    continue


                seen.add(name)


                logo_path = item.get(
                    'logo_path'
                )


                logo = None


                if logo_path:

                    logo = (
                        'https://image.tmdb.org/t/p/w92'
                        +
                        logo_path
                    )


                providers[key].append({

                    'name':
                        name,

                    'logo':
                        logo,

                    'provider_id':
                        item.get('provider_id')

                })


        # -------------------------------------------------
        # POSTER
        # -------------------------------------------------

        poster_path = details.get(
            'poster_path'
        )


        if poster_path:

            poster = (
                'https://image.tmdb.org/t/p/w500'
                +
                poster_path
            )

        else:

            poster = fetch_poster(
                title
            )


        # -------------------------------------------------
        # BACKDROP
        # -------------------------------------------------

        backdrop_path = details.get(
            'backdrop_path'
        )


        if backdrop_path:

            backdrop = (
                'https://image.tmdb.org/t/p/w1280'
                +
                backdrop_path
            )

        else:

            backdrop = None


        # -------------------------------------------------
        # YEAR
        # -------------------------------------------------

        release_date = (
            details.get(
                'release_date'
            )
            or ''
        )


        if release_date:

            year = release_date[:4]

        else:

            year = fallback.get(
                'year'
            )


        # -------------------------------------------------
        # GENRES
        # -------------------------------------------------

        genres = [

            genre.get('name')

            for genre
            in details.get(
                'genres',
                []
            )

            if genre.get('name')

        ]


        if not genres:

            genres = fallback.get(
                'genres',
                []
            )


        # -------------------------------------------------
        # RATING
        # -------------------------------------------------

        rating = details.get(
            'vote_average'
        )


        if not rating:

            rating = fallback.get(
                'rating'
            )


        # -------------------------------------------------
        # RUNTIME
        # -------------------------------------------------

        runtime = details.get(
            'runtime'
        )


        if not runtime:

            runtime = fallback.get(
                'runtime'
            )


        # -------------------------------------------------
        # OVERVIEW
        # -------------------------------------------------

        overview = details.get(
            'overview'
        )


        if not overview:

            overview = fallback.get(
                'overview',
                ''
            )


        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        return jsonify({

            'title':
                details.get(
                    'title'
                )
                or fallback['title'],

            'overview':
                overview,

            'year':
                year,

            'runtime':
                runtime,

            'rating':
                rating,

            'genres':
                genres,

            'poster':
                poster,

            'backdrop':
                backdrop,

            'trailer_key':
                (
                    trailer.get('key')
                    if trailer
                    else None
                ),

            'providers':
                providers

        })


    except Exception as e:

        print(
            f"TMDB details error "
            f"for '{title}': {e}"
        )


        return jsonify({

            **fallback,

            'poster':
                fetch_poster(title),

            'backdrop':
                None,

            'trailer_key':
                None,

            'providers':
                {}

        })


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route(
    '/admin/dashboard'
)
def admin_dashboard():

    if (
        'username' not in session
        or
        not session.get(
            'is_admin'
        )
    ):

        flash(
            'You do not have permission to access the Admin Panel.',
            'error'
        )

        return redirect(
            url_for('home')
        )


    with sqlite3.connect(
        'database.db'
    ) as conn:

        conn.row_factory = sqlite3.Row

        c = conn.cursor()


        # -------------------------------------------------
        # USERS
        # -------------------------------------------------

        c.execute(
            '''
            SELECT
                u.id,
                u.username,
                u.email,
                u.password,

                (
                    SELECT COUNT(*)
                    FROM searches
                    WHERE user_id = u.id
                ) AS search_count,

                (
                    SELECT COUNT(*)
                    FROM interactions
                    WHERE user_id = u.id
                    AND liked = 1
                ) AS like_count,

                (
                    SELECT COUNT(*)
                    FROM interactions
                    WHERE user_id = u.id
                    AND watchlist = 1
                ) AS watchlist_count

            FROM users u
            '''
        )


        users_list = c.fetchall()


        # -------------------------------------------------
        # SEARCH HISTORY
        # -------------------------------------------------

        c.execute(
            '''
            SELECT
                u.username,
                s.movie_name,
                s.timestamp

            FROM searches s

            JOIN users u
                ON s.user_id = u.id

            ORDER BY s.timestamp DESC

            LIMIT 100
            '''
        )


        global_searches = c.fetchall()


    return render_template(

        'admin.html',

        users=users_list,

        searches=global_searches

    )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    '/forget_password'
)
def forget_password():

    session.pop(
        'reset_otp',
        None
    )

    session.pop(
        'reset_user',
        None
    )


    return render_template(
        'forget_password.html'
    )


# =========================================================
# RUN
# =========================================================

if __name__ == '__main__':

    init_db()

    app.run(
        debug=True
    )