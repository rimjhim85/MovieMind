document.addEventListener("DOMContentLoaded", () => {
    const box = document.getElementById("searchBox");
    const sug = document.getElementById("suggestions");
    const themeBtn = document.getElementById("themeToggle");

    // Live Search
    box.addEventListener("keyup", async () => {
        let q = box.value;
        if (q.length < 2) { sug.innerHTML = ""; return; }

        try {
            let res = await fetch(`/search?q=${q}`);
            let data = await res.json();
            sug.innerHTML = "";
            data.forEach(m => {
                let d = document.createElement("div");
                d.className = "sug-item";
                d.innerText = m;
                d.onclick = () => {
                    box.value = m;
                    sug.innerHTML = "";
                };
                sug.appendChild(d);
            });
        } catch (err) { console.error("Search failed"); }
    });

    // Theme Switcher
    themeBtn.onclick = () => {
        document.body.classList.toggle("dark-mode");
        document.body.classList.toggle("light-mode");
        const current = document.body.classList.contains("dark-mode") ? "dark" : "light";
        localStorage.setItem("appTheme", current);
    };

    // Load Saved Theme
    if (localStorage.getItem("appTheme") === "light") {
        document.body.classList.remove("dark-mode");
        document.body.classList.add("light-mode");
    }
});