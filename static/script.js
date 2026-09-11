/* =====================================================
   MOVIEMIND
   Frontend JavaScript
===================================================== */

let activeMovieTitle = '';
let activeMovieData = null;


/* =====================================================
   SECURITY / HTML ESCAPE
===================================================== */

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value ?? '';
    return div.innerHTML;
}


/* =====================================================
   PROVIDER URLS
===================================================== */

/*
   TMDB gives us the provider name and provider ID,
   but it does not always provide a direct URL to the
   exact movie on every streaming service.

   So for known providers we create a movie-specific
   search URL. Otherwise we use TMDB's India availability
   page supplied by the backend.
*/

function getProviderUrl(provider, fallbackUrl = '#') {

    const name = String(provider.name || '').toLowerCase();
    const title = encodeURIComponent(activeMovieTitle);

    /*
       Netflix
    */
    if (name.includes('netflix')) {
        return `https://www.netflix.com/search?q=${title}`;
    }

    /*
       Amazon Prime Video
    */
    if (
        name.includes('prime video') ||
        name.includes('amazon prime') ||
        name === 'prime'
    ) {
        return `https://www.primevideo.com/search/ref=atv_nb_sr?phrase=${title}`;
    }

    /*
       JioHotstar / Hotstar
    */
    if (
        name.includes('jiohotstar') ||
        name.includes('hotstar')
    ) {
        return `https://www.hotstar.com/in/search?q=${title}`;
    }

    /*
       ZEE5
    */
    if (name.includes('zee5')) {
        return `https://www.zee5.com/search?q=${title}`;
    }

    /*
       Sony LIV
    */
    if (
        name.includes('sony liv') ||
        name.includes('sonyliv')
    ) {
        return `https://www.sonyliv.com/search?q=${title}`;
    }

    /*
       Apple TV
    */
    if (
        name.includes('apple tv') ||
        name.includes('itunes')
    ) {
        return `https://tv.apple.com/in/search?term=${title}`;
    }

    /*
       YouTube
    */
    if (name.includes('youtube')) {
        return `https://www.youtube.com/results?search_query=${title}`;
    }

    /*
       Google Play / Google TV
    */
    if (
        name.includes('google play') ||
        name.includes('google tv')
    ) {
        return `https://www.google.com/search?q=${title}+movie+watch`;
    }

    /*
       MX Player
    */
    if (name.includes('mx player')) {
        return `https://www.mxplayer.in/search?query=${title}`;
    }

    /*
       Lionsgate Play
    */
    if (name.includes('lionsgate')) {
        return `https://www.lionsgateplay.com/search?query=${title}`;
    }

    /*
       Discovery+
    */
    if (name.includes('discovery')) {
        return `https://www.discoveryplus.com/in/search?q=${title}`;
    }

    /*
       Aha
    */
    if (name === 'aha' || name.includes('aha')) {
        return `https://www.aha.video/search?q=${title}`;
    }

    /*
       Sun NXT
    */
    if (name.includes('sun nxt')) {
        return `https://www.sunnxt.com/search/${title}`;
    }

    /*
       Fallback
    */
    return fallbackUrl || '#';
}


/* =====================================================
   TOAST
===================================================== */

function showToast(message, icon = 'fa-check') {

    const container =
        document.getElementById('toast-container');

    if (!container) return;

    const toast =
        document.createElement('div');

    toast.className = 'toast';

    toast.innerHTML = `
        <i class="fas ${icon}"></i>
        <span>${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {

        toast.classList.add('hide');

        setTimeout(() => toast.remove(), 250);

    }, 2200);
}


/* =====================================================
   RECENT SEARCH
===================================================== */

function searchRecent(movie) {

    const input =
        document.getElementById('movieSearch');

    const form =
        document.getElementById('searchForm');

    if (input && form) {

        input.value = movie;

        form.submit();

    }
}
/* =====================================================
   SEARCH AUTOCOMPLETE
===================================================== */

function setupSearch() {

    const searchInput = document.getElementById('movieSearch');
    const suggestionsBox = document.getElementById('suggestions-box');

    if (!searchInput || !suggestionsBox) return;

    let selectedIndex = -1;
    let currentMatches = [];

    function renderSuggestions(value) {

        suggestionsBox.innerHTML = '';
        selectedIndex = -1;
        currentMatches = [];

        const query = value.trim().toLowerCase();

        if (!query) {
            suggestionsBox.style.display = 'none';
            return;
        }

        /*
         * Better ranking:
         * 1. Exact title
         * 2. Starts with query
         * 3. Word starts with query
         * 4. Contains query
         */
        currentMatches = allMovies
            .map(movie => {

                const title = String(movie);
                const lower = title.toLowerCase();

                let score = 0;

                if (lower === query) {
                    score = 1000;
                }
                else if (lower.startsWith(query)) {
                    score = 900;
                }
                else if (
                    lower.split(/\s+/).some(word =>
                        word.startsWith(query)
                    )
                ) {
                    score = 800;
                }
                else if (lower.includes(query)) {
                    score = 600;
                }

                return {
                    movie: title,
                    score: score
                };

            })
            .filter(item => item.score > 0)
            .sort((a, b) => {

                if (b.score !== a.score) {
                    return b.score - a.score;
                }

                return a.movie.localeCompare(b.movie);

            })
            .slice(0, 8);

        if (!currentMatches.length) {

            suggestionsBox.innerHTML = `
                <div class="search-no-results">
                    <i class="fas fa-magnifying-glass"></i>
                    <span>No movies found</span>
                </div>
            `;

            suggestionsBox.style.display = 'block';
            return;
        }

        currentMatches.forEach((item, index) => {

            const suggestion = document.createElement('div');

            suggestion.className = 'search-suggestion';
            suggestion.dataset.index = index;

            suggestion.innerHTML = `
                <i class="fas fa-film"></i>
                <span>${escapeHtml(item.movie)}</span>
            `;

            /*
             * mousedown instead of click prevents the
             * input blur from closing the dropdown first.
             */
            suggestion.addEventListener('mousedown', function(event) {

                event.preventDefault();

                searchInput.value = item.movie;
                suggestionsBox.innerHTML = '';
                suggestionsBox.style.display = 'none';
                selectedIndex = -1;

                /*
                 * Selecting a suggestion should actually
                 * submit the Flask search form.
                 */
                document.getElementById('searchForm').submit();

            });

            suggestionsBox.appendChild(suggestion);

        });

        suggestionsBox.style.display = 'block';
    }


    function updateHighlight() {

        const items = suggestionsBox.querySelectorAll(
            '.search-suggestion'
        );

        items.forEach(item => {
            item.classList.remove('selected');
        });

        if (
            selectedIndex >= 0 &&
            selectedIndex < items.length
        ) {

            items[selectedIndex].classList.add('selected');

            items[selectedIndex].scrollIntoView({
                block: 'nearest'
            });

        }
    }


    searchInput.addEventListener('input', function() {
        renderSuggestions(this.value);
    });


    searchInput.addEventListener('keydown', function(event) {

        const items = suggestionsBox.querySelectorAll(
            '.search-suggestion'
        );

        if (event.key === 'ArrowDown') {

            if (!items.length) return;

            event.preventDefault();

            selectedIndex++;

            if (selectedIndex >= items.length) {
                selectedIndex = 0;
            }

            updateHighlight();
        }

        else if (event.key === 'ArrowUp') {

            if (!items.length) return;

            event.preventDefault();

            selectedIndex--;

            if (selectedIndex < 0) {
                selectedIndex = items.length - 1;
            }

            updateHighlight();
        }

        else if (event.key === 'Enter') {

            if (
                selectedIndex >= 0 &&
                selectedIndex < currentMatches.length
            ) {

                event.preventDefault();

                searchInput.value =
                    currentMatches[selectedIndex].movie;

                suggestionsBox.innerHTML = '';
                suggestionsBox.style.display = 'none';

                document.getElementById('searchForm').submit();
            }
        }

        else if (event.key === 'Escape') {

            suggestionsBox.innerHTML = '';
            suggestionsBox.style.display = 'none';

            selectedIndex = -1;
        }

    });


    document.addEventListener('click', function(event) {

        if (
            !searchInput.contains(event.target) &&
            !suggestionsBox.contains(event.target)
        ) {

            suggestionsBox.innerHTML = '';
            suggestionsBox.style.display = 'none';

            selectedIndex = -1;
        }

    });

}

/* =====================================================
   MOVIE CARD EVENTS
===================================================== */

function setupMovieCards() {

    const cards =
        document.querySelectorAll(
            '.movie-card[data-movie]'
        );

    cards.forEach(card => {

        card.addEventListener(
            'click',
            function () {

                const movie =
                    this.dataset.movie;

                openMovieDetails(movie);

            }
        );

        card.addEventListener(
            'keydown',
            function (event) {

                if (
                    event.key === 'Enter' ||
                    event.key === ' '
                ) {

                    event.preventDefault();

                    openMovieDetails(
                        this.dataset.movie
                    );

                }

            }
        );

    });

}


/* =====================================================
   FETCH MOVIE DETAILS
===================================================== */

async function fetchMovieDetails(title) {

    const response =
        await fetch(
            '/movie_details',
            {
                method: 'POST',

                headers: {
                    'Content-Type':
                        'application/json'
                },

                body: JSON.stringify({
                    title: title
                })
            }
        );

    if (!response.ok) {

        throw new Error(
            'Could not load movie details'
        );

    }

    return await response.json();

}


/* =====================================================
   OPEN MOVIE DETAILS
===================================================== */

async function openMovieDetails(title) {

    activeMovieTitle = title;

    activeMovieData = null;

    setModalLoading(title);

    try {

        const data =
            await fetchMovieDetails(title);

        activeMovieData = data;

        renderMovieDetails(data);

    }
    catch (error) {

        console.error(error);

        document.getElementById(
            'modalOverview'
        ).textContent =
            'Movie details are temporarily unavailable.';

        document.getElementById(
            'providersContent'
        ).innerHTML = `
            <div class="provider-empty">
                Availability could not be checked right now.
            </div>
        `;

    }

}


/* =====================================================
   MODAL LOADING
===================================================== */

function setModalLoading(title) {

    const modal =
        document.getElementById(
            'movieModal'
        );

    document.getElementById(
        'modalTitle'
    ).textContent = title;

    document.getElementById(
        'modalMeta'
    ).innerHTML =
        '<span>Loading details...</span>';

    document.getElementById(
        'modalGenres'
    ).innerHTML = '';

    document.getElementById(
        'modalOverview'
    ).textContent =
        'Fetching movie information...';

    document.getElementById(
        'providersContent'
    ).innerHTML = `
        <div class="provider-loading">
            <span class="spinner"></span>
            Checking availability...
        </div>
    `;

    document.getElementById(
        'modalPoster'
    ).src = '';

    document.getElementById(
        'modalBackdrop'
    ).style.backgroundImage = '';

    modal.classList.add('open');

    modal.setAttribute(
        'aria-hidden',
        'false'
    );

    document.body.classList.add(
        'modal-open'
    );

}


/* =====================================================
   RENDER MOVIE DETAILS
===================================================== */

function renderMovieDetails(data) {

    const poster =
        data.poster || '';

    const backdrop =
        data.backdrop ||
        poster;

    const modalPoster =
        document.getElementById(
            'modalPoster'
        );

    modalPoster.src = poster;

    modalPoster.alt =
        data.title ||
        activeMovieTitle;

    document.getElementById(
        'modalBackdrop'
    ).style.backgroundImage =
        backdrop
            ? `url("${backdrop}")`
            : '';

    document.getElementById(
        'modalTitle'
    ).textContent =
        data.title ||
        activeMovieTitle;


    /* ---------- META ---------- */

    const meta = [];

    if (data.rating) {

        meta.push(`
            <span class="rating">
                <i class="fas fa-star"></i>
                ${Number(data.rating).toFixed(1)}
            </span>
        `);

    }

    if (data.year) {

        meta.push(`
            <span>
                ${escapeHtml(String(data.year))}
            </span>
        `);

    }

    if (data.runtime) {

        meta.push(`
            <span>
                ${escapeHtml(String(data.runtime))} min
            </span>
        `);

    }

    document.getElementById(
        'modalMeta'
    ).innerHTML =
        meta.join('<span>•</span>');


    /* ---------- GENRES ---------- */

    const genres =
        data.genres || [];

    document.getElementById(
        'modalGenres'
    ).innerHTML =
        genres
            .map(
                genre => `
                    <span class="genre-pill">
                        ${escapeHtml(genre)}
                    </span>
                `
            )
            .join('');


    /* ---------- DESCRIPTION ---------- */

    document.getElementById(
        'modalOverview'
    ).textContent =
        data.overview ||
        'No overview is available for this movie.';


    /* ---------- BUTTONS ---------- */

    document.getElementById(
        'modalTrailerButton'
    ).onclick =
        () => openTrailer(activeMovieTitle);

    document.getElementById(
        'modalLikeButton'
    ).onclick =
        () => interact(
            activeMovieTitle,
            'liked'
        );

    document.getElementById(
        'modalWatchlistButton'
    ).onclick =
        () => interact(
            activeMovieTitle,
            'watchlist'
        );


    /* ---------- PROVIDERS ---------- */

    renderProviders(
        data.providers || {}
    );

}


/* =====================================================
   PROVIDERS
===================================================== */

/* =====================================================
   PROVIDERS
===================================================== */

/*
 * Returns both the URL and the type of destination.
 *
 * type:
 *   "search"       -> provider search page
 *   "availability" -> TMDB's India availability page
 *   "none"         -> no useful destination
 */
function getProviderLink(providerName, movieTitle, fallbackLink) {

    const name =
        String(providerName || '').toLowerCase();

    const query =
        encodeURIComponent(movieTitle || '');


    /* Netflix */
    if (name.includes('netflix')) {

        return {
            url: `https://www.netflix.com/search?q=${query}`,
            type: 'search'
        };

    }


    /* Prime Video */
    if (
        name.includes('prime video') ||
        name.includes('amazon prime') ||
        name === 'prime'
    ) {

        return {
            url: `https://www.primevideo.com/search/ref=atv_nb_sr?phrase=${query}`,
            type: 'search'
        };

    }


    /* JioHotstar / Hotstar
       Use Google site search instead of Hotstar's
       sometimes-unreliable direct search route.
    */
    if (
        name.includes('jiohotstar') ||
        name.includes('jio hotstar') ||
        name.includes('hotstar')
    ) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:hotstar.com ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* ZEE5 */
    if (name.includes('zee5')) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:zee5.com ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* Sony LIV */
    if (
        name.includes('sony liv') ||
        name.includes('sonyliv')
    ) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:sonyliv.com ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* Apple TV */
    if (
        name.includes('apple tv') ||
        name.includes('itunes')
    ) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:tv.apple.com ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* YouTube */
    if (name.includes('youtube')) {

        return {
            url:
                `https://www.youtube.com/results?search_query=` +
                encodeURIComponent(
                    `${movieTitle} full movie official`
                ),
            type: 'search'
        };

    }


    /* MX Player */
    if (name.includes('mx player')) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:mxplayer.in ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* Lionsgate Play */
    if (name.includes('lionsgate')) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:lionsgateplay.com ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* Aha */
    if (name === 'aha' || name.includes('aha')) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:aha.video ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /* Sun NXT */
    if (name.includes('sun nxt')) {

        return {
            url:
                `https://www.google.com/search?q=` +
                encodeURIComponent(
                    `site:sunnxt.com ${movieTitle}`
                ),
            type: 'search'
        };

    }


    /*
     * Unknown provider:
     * use TMDB's India availability page.
     */
    if (fallbackLink) {

        return {
            url: fallbackLink,
            type: 'availability'
        };

    }


    return {
        url: '#',
        type: 'none'
    };

}


function renderProviders(providers) {

    const container =
        document.getElementById(
            'providersContent'
        );

    if (!container) return;


    const groups = [

        ['flatrate', 'Stream'],

        ['free', 'Free'],

        ['ads', 'Free with Ads'],

        ['rent', 'Rent'],

        ['buy', 'Buy']

    ];


    let html = '';


    groups.forEach(
        ([key, label]) => {

            const items =
                Array.isArray(
                    providers[key]
                )
                    ? providers[key]
                    : [];


            if (!items.length) return;


            html += `
                <div class="provider-group">

                    <div class="provider-group-title">
                        ${escapeHtml(label)}
                    </div>

                    <div class="provider-list">
            `;


            items.forEach(provider => {

                const name =
                    String(
                        provider.name ||
                        'Streaming service'
                    );


                /*
                 * Provider logo
                 */
                const logo =
                    provider.logo
                        ? `
                            <img
                                src="${escapeHtml(provider.logo)}"
                                alt="${escapeHtml(name)}"
                                loading="lazy"
                            >
                        `
                        : `
                            <span class="provider-logo-fallback">
                                <i class="fas fa-tv"></i>
                            </span>
                        `;


                /*
                 * Get destination
                 */
                const destination =
                    getProviderLink(
                        name,
                        activeMovieTitle,
                        providers.link
                    );


                /*
                 * Decide button text
                 */
                let action = 'Watch';


                if (key === 'rent') {
                    action = 'Rent';
                }

                if (key === 'buy') {
                    action = 'Buy';
                }


                /*
                 * If we're sending the user to a
                 * search page, don't falsely call it
                 * "Watch".
                 */
                if (destination.type === 'search') {

                    action = 'Search';

                }


                /*
                 * Unknown provider with no link:
                 * don't show a useless button.
                 */
                const button =
                    destination.type !== 'none'
                        ? `
                            <a
                                class="provider-link"
                                href="${escapeHtml(destination.url)}"
                                target="_blank"
                                rel="noopener noreferrer"
                                aria-label="${escapeHtml(action)} ${escapeHtml(name)}"
                            >
                                ${action}

                                <i class="fas fa-arrow-up-right-from-square"></i>
                            </a>
                        `
                        : '';


                html += `

                    <div class="provider-item">

                        <span class="provider-name">

                            ${logo}

                            <span>
                                ${escapeHtml(name)}
                            </span>

                        </span>

                        ${button}

                    </div>

                `;

            });


            html += `
                    </div>
                </div>
            `;

        }
    );


    if (!html) {

        html = `
            <div class="provider-empty">

                <i class="fas fa-tv"></i>

                <p>
                    No streaming or rental options
                    were found for India right now.
                </p>

                <small>
                    Availability can change by region
                    and over time.
                </small>

            </div>
        `;

    }
    else {

        html += `
            <div class="provider-note">

                <i class="fas fa-circle-info"></i>

                Availability shown for India.
                Streaming catalogs can change.

            </div>
        `;

    }


    container.innerHTML = html;

}


/* =====================================================
   TRAILER
===================================================== */

async function openTrailer(title) {

    const modal =
        document.getElementById(
            'trailerModal'
        );

    const frame =
        document.getElementById(
            'videoFrame'
        );

    document.getElementById(
        'trailerTitle'
    ).textContent =
        `${title} — Official Trailer`;

    frame.innerHTML = `
        <div class="trailer-loading">

            <span class="spinner"></span>

            Loading trailer...

        </div>
    `;

    modal.classList.add('open');

    modal.setAttribute(
        'aria-hidden',
        'false'
    );

    document.body.classList.add(
        'modal-open'
    );

    try {

        let data;

        if (
            activeMovieData &&
            activeMovieTitle === title
        ) {

            data =
                activeMovieData;

        }
        else {

            data =
                await fetchMovieDetails(title);

        }

        activeMovieData = data;

        activeMovieTitle = title;

        if (data.trailer_key) {

            frame.innerHTML = `

                <iframe

                    src="
                        https://www.youtube.com/embed/${encodeURIComponent(
                            data.trailer_key
                        )}?rel=0
                    "

                    title="${escapeHtml(title)} trailer"

                    allow="
                        accelerometer;
                        autoplay;
                        clipboard-write;
                        encrypted-media;
                        gyroscope;
                        picture-in-picture;
                        web-share
                    "

                    allowfullscreen>

                </iframe>

            `;

        }
        else {

            frame.innerHTML = `

                <div class="provider-empty trailer-message">

                    <i class="fas fa-film"></i>

                    <p>
                        No trailer was found
                        for this movie.
                    </p>

                </div>

            `;

        }

    }
    catch (error) {

        console.error(error);

        frame.innerHTML = `

            <div class="provider-empty trailer-message">

                Trailer is temporarily unavailable.

            </div>

        `;

    }

}


/* =====================================================
   CLOSE TRAILER
===================================================== */

function closeTrailer() {

    const modal =
        document.getElementById(
            'trailerModal'
        );

    const frame =
        document.getElementById(
            'videoFrame'
        );

    modal.classList.remove('open');

    modal.setAttribute(
        'aria-hidden',
        'true'
    );

    frame.innerHTML = '';

    if (
        !document
            .getElementById('movieModal')
            .classList
            .contains('open')
    ) {

        document.body.classList.remove(
            'modal-open'
        );

    }

}


/* =====================================================
   CLOSE MOVIE MODAL
===================================================== */

function closeMovieModal() {

    const modal =
        document.getElementById(
            'movieModal'
        );

    modal.classList.remove('open');

    modal.setAttribute(
        'aria-hidden',
        'true'
    );

    if (
        !document
            .getElementById('trailerModal')
            .classList
            .contains('open')
    ) {

        document.body.classList.remove(
            'modal-open'
        );

    }

}


/* =====================================================
   LIKE / WATCHLIST
===================================================== */

function interact(movie, action, button = null) {

    fetch(
        '/interact',
        {
            method: 'POST',

            headers: {
                'Content-Type':
                    'application/json'
            },

            body: JSON.stringify({
                movie: movie,
                action: action
            })
        }
    )

    .then(response => {

        if (response.status === 401) {

            showToast(
                'Please log in to save movies.',
                'fa-lock'
            );

            return null;
        }

        return response.json();

    })

    .then(data => {

        if (!data) return;

        if (data.status !== 'success') {

            showToast(
                data.message ||
                'Something went wrong.',
                'fa-circle-exclamation'
            );

            return;
        }


        /*
         * Find the button.
         */

        let targetButton = button;

        if (!targetButton) {

            if (action === 'liked') {

                targetButton =
                    document.getElementById(
                        'modalLikeButton'
                    );

            }
            else if (action === 'watchlist') {

                targetButton =
                    document.getElementById(
                        'modalWatchlistButton'
                    );

            }

        }


        /*
         * Current state.
         */

        let newState = false;

        if (targetButton) {

            const isActive =
                targetButton.dataset.active === 'true';

            newState = !isActive;

            targetButton.dataset.active =
                newState ? 'true' : 'false';


            /*
             * LIKE
             */

            if (action === 'liked') {

                targetButton.innerHTML =
                    newState
                        ? '<i class="fas fa-heart"></i> Liked'
                        : '<i class="far fa-heart"></i> Like';

                targetButton.classList.toggle(
                    'active',
                    newState
                );

            }


            /*
             * WATCHLIST
             */

            if (action === 'watchlist') {

                targetButton.innerHTML =
                    newState
                        ? '<i class="fas fa-check"></i> In Watchlist'
                        : '<i class="far fa-bookmark"></i> Watchlist';

                targetButton.classList.toggle(
                    'active',
                    newState
                );

            }

        }


        /*
         * Toast
         */

        if (action === 'liked') {

            showToast(
                newState
                    ? 'Added to liked movies'
                    : 'Removed from liked movies',
                newState
                    ? 'fa-heart'
                    : 'fa-heart-crack'
            );

        }
        else if (action === 'watchlist') {

            showToast(
                newState
                    ? 'Added to your watchlist'
                    : 'Removed from your watchlist',
                'fa-bookmark'
            );

        }

    })

    .catch(error => {

        console.error(error);

        showToast(
            'Could not update your list.',
            'fa-circle-exclamation'
        );

    });

}


/* =====================================================
   CLEAR HISTORY
===================================================== */

function clearHistory() {

    if (
        !confirm(
            'Do you really want to clear all your search history?'
        )
    ) {

        return;

    }

    fetch(
        '/clear_history',
        {
            method: 'POST'
        }
    )

    .then(response =>
        response.json()
    )

    .then(data => {

        if (
            data.status === 'success'
        ) {

            location.reload();

        }

    });

}


/* =====================================================
   DELETE ACCOUNT
===================================================== */

function deleteAccount() {

    const message =
        'Are you absolutely sure? This will delete your profile and history permanently!';

    if (!confirm(message)) {

        return;

    }

    fetch(
        '/delete_account',
        {
            method: 'POST'
        }
    )

    .then(response =>
        response.json()
    )

    .then(data => {

        if (
            data.status === 'success'
        ) {

            window.location.href =
                '/signup';

        }

    });

}


/* =====================================================
   REMOVE FROM PROFILE LIST
===================================================== */

function removeFromList(
    movieTitle,
    actionType
) {

    if (
        !confirm(
            `Remove "${movieTitle}" from your ${actionType} list?`
        )
    ) {

        return;

    }

    fetch(
        '/interact',
        {
            method: 'POST',

            headers: {
                'Content-Type':
                    'application/json'
            },

            body: JSON.stringify({
                movie: movieTitle,
                action: actionType
            })
        }
    )

    .then(response =>
        response.json()
    )

    .then(data => {

        if (
            data.status === 'success'
        ) {

            location.reload();

        }

    })

    .catch(error =>
        console.error(error)
    );

}


/* =====================================================
   PROFILE EDIT
===================================================== */
/* =====================================================
   PROFILE EDIT
===================================================== */

function setupProfile() {

    const editButton =
        document.getElementById('editProfileButton');

    const closeButton =
        document.getElementById('closeEditButton');

    const editForm =
        document.getElementById('editForm');

    if (!editForm) return;

    function openEdit() {

        editForm.classList.add('profile-edit-open');

        if (editButton) {
            editButton.innerHTML =
                '<i class="fas fa-times"></i> Cancel Editing';
        }

    }

    function closeEdit() {

        editForm.classList.remove('profile-edit-open');

        if (editButton) {
            editButton.innerHTML =
                '<i class="fas fa-pen"></i> Edit Profile';
        }

    }

    if (editButton) {

        editButton.addEventListener(
            'click',
            function () {

                if (
                    editForm.classList.contains(
                        'profile-edit-open'
                    )
                ) {
                    closeEdit();
                } else {
                    openEdit();
                }

            }
        );

    }

    if (closeButton) {

        closeButton.addEventListener(
            'click',
            closeEdit
        );

    }

}


/* =====================================================
   MODAL KEYBOARD
===================================================== */

document.addEventListener(
    'keydown',
    function (event) {

        if (event.key === 'Escape') {

            closeTrailer();

            closeMovieModal();

        }

    }
);


/* =====================================================
   MODAL BACKDROP CLICK
===================================================== */

document.addEventListener(
    'click',
    function (event) {

        if (
            event.target.id ===
            'movieModal'
        ) {

            closeMovieModal();

        }

        if (
            event.target.id ===
            'trailerModal'
        ) {

            closeTrailer();

        }

    }
);


/* =====================================================
   INITIALIZE
===================================================== */
document.addEventListener(
    'DOMContentLoaded',
    function () {

        setupSearch();

        setupMovieCards();

        setupProfile();

    }
);