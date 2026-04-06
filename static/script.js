window.onload = function() {
    // ১. বিদ্যমান URL প্যারামিটার চেক
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('existing') === 'true') {
        alert("Welcome back to your MovieMind account!");
    }

    // ২. অ্যাকাউন্ট স্ট্যাটাস চেক
    checkAccountStatus();
}
window.onload = function() {
    checkAccountStatus();
};

function checkAccountStatus() {
    const flashElement = document.getElementById('flash-data');
    if (flashElement) {
        const category = flashElement.getAttribute('data-category');
        const message = flashElement.getAttribute('data-message');
        const popup = document.getElementById('simple-white-popup');
        const msgText = document.getElementById('simple-popup-message');

        if (category === "no_account") {
            // পপ-আপ দেখানো
            if (popup && msgText) {
                msgText.innerText = message;
                popup.style.display = 'block';

                // ১.৫ সেকেন্ড পর সরাসরি সাইন-আপ পেজে রিডাইরেক্ট
                setTimeout(function() {
                    window.location.href = "/signup";
                }, 1500);
            }
        }
    }
}

// অটো-কমপ্লিট লজিক
const searchInput = document.getElementById('movieSearch');
const suggestionsBox = document.getElementById('suggestions-box');

if (searchInput && suggestionsBox) {
    searchInput.addEventListener('input', function() {
        const val = this.value.toLowerCase().trim();
        suggestionsBox.innerHTML = '';
        
        if (val.length < 1) {
            suggestionsBox.style.display = 'none';
            return;
        }

        const matches = allMovies.filter(m => 
            m.toLowerCase().startsWith(val) || m.toLowerCase().includes(" " + val)
        ).slice(0, 8);

        if (matches.length > 0) {
            matches.forEach(match => {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                div.innerHTML = `<i class="fas fa-search"></i> <span>${match}</span>`;
                div.onclick = function() {
                    searchInput.value = match;
                    suggestionsBox.style.display = 'none';
                    searchInput.closest('form').submit();
                };
                suggestionsBox.appendChild(div);
            });
            suggestionsBox.style.display = 'block';
        } else {
            suggestionsBox.style.display = 'none';
        }
    });

    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
            suggestionsBox.style.display = 'none';
        }
    });
}

// লাইক ও উইশলিস্ট ইন্টারেকশন
function interact(movie, action) {
    fetch('/interact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movie: movie, action: action })
    })
    .then(response => response.json())
    .then(data => {
        if(data.status === 'success') {
            const icon = action === 'liked' ? '❤️' : '➕';
            alert(`${icon} ${movie} has been updated in your ${action} list!`);
        } else {
            alert("Something went wrong. Please login again.");
        }
    })
    .catch(error => console.error('Error:', error));
}

// সার্চ হিস্ট্রি ক্লিয়ার
function clearHistory() {
    if(confirm("Do you really want to clear all your search history?")) {
        fetch('/clear_history', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if(data.status === 'success') { location.reload(); }
        });
    }
}

// অ্যাকাউন্ট ডিলিট
function deleteAccount() {
    const msg = "Are you absolutely sure? This will delete your profile and history permanently!";
    if(confirm(msg)) {
        fetch('/delete_account', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if(data.status === 'success') { window.location.href = '/signup'; }
        });
    }
}
function removeFromList(movieTitle, actionType) {
    if (confirm(`Remove "${movieTitle}" from your ${actionType} list?`)) {
        fetch('/interact', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                movie: movieTitle, 
                action: actionType 
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // পেজ রিফ্রেশ করে লিস্ট আপডেট করবে
                location.reload();
            } else {
                alert("Could not remove the movie. Try again!");
            }
        })
        .catch(error => console.error('Error:', error));
    }
}