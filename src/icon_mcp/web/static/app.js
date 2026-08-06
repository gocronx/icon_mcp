// === MCP Icon Server - Client JS ===
let selectedIcons = new Map();
let currentIcons = [];
let allIcons = [];
let websocket = null;
let currentPage = 1;
let totalPages = 1;
let pageSize = 15;

// i18n placeholders replaced at serve time
const I18N = {
    selectedCount: "{{i18n_selectedCount}}",
    noIconsSelected: "{{i18n_noIconsSelected}}",
    selectButton: "{{i18n_selectButton}}",
    selectedButton: "{{i18n_selectedButton}}",
    error: "{{i18n_error}}",
    sendSelected: "{{i18n_sendSelected}}",
};

// Initialize
document.addEventListener("DOMContentLoaded", function () {
    if (SEARCH_ID) {
        connectWebSocket();
        loadCachedResults(1);
    }
});

function connectWebSocket() {
    try {
        websocket = new WebSocket(
            "ws://localhost:" + WS_PORT + "/ws?searchId=" + SEARCH_ID
        );
        websocket.onopen = function () {
            console.log("WebSocket connected");
            setInterval(function () {
                if (websocket && websocket.readyState === WebSocket.OPEN) {
                    websocket.send(JSON.stringify({ type: "ping" }));
                }
            }, 30000);
        };
        websocket.onmessage = function (event) {
            const data = JSON.parse(event.data);
            console.log("WS message:", data);
        };
        websocket.onclose = function () {
            console.log("WebSocket disconnected");
            setTimeout(connectWebSocket, 3000);
        };
    } catch (e) {
        console.error("WebSocket error:", e);
    }
}

async function loadCachedResults(page) {
    const loading = document.getElementById("loading");
    const grid = document.getElementById("iconGrid");
    loading.style.display = "block";
    grid.innerHTML = "";

    try {
        const resp = await fetch(
            "/api/cache?searchId=" +
                SEARCH_ID +
                "&page=" +
                page +
                "&pageSize=" +
                pageSize
        );
        const data = await resp.json();
        if (data.error) {
            showMessage(data.error, "error");
            return;
        }
        currentIcons = data.icons || [];
        allIcons = currentIcons;
        totalPages = data.totalPages || 1;
        currentPage = data.page || 1;
        displayIcons(currentIcons);
        updatePagination();
    } catch (e) {
        showMessage(I18N.error + ": " + e.message, "error");
    } finally {
        loading.style.display = "none";
    }
}

function displayIcons(icons) {
    const grid = document.getElementById("iconGrid");
    grid.innerHTML = "";
    icons.forEach(function (icon) {
        const card = document.createElement("div");
        card.className =
            "icon-card" + (selectedIcons.has(icon.id) ? " selected" : "");
        card.onclick = function () {
            toggleSelection(icon);
        };

        let preview = "";
        if (icon.show_svg) {
            preview = icon.show_svg;
        } else if (icon.icon) {
            preview =
                '<img src="' +
                icon.icon +
                '" alt="' +
                (icon.name || "") +
                '">';
        } else {
            preview = '<span style="font-size:32px;color:#ccc;">&#128196;</span>';
        }

        const isSelected = selectedIcons.has(icon.id);
        card.innerHTML =
            '<div class="icon-preview">' +
            preview +
            "</div>" +
            '<div class="icon-name">' +
            (icon.name || "icon-" + icon.id) +
            "</div>" +
            '<button class="btn ' +
            (isSelected ? "selected-btn" : "") +
            '">' +
            (isSelected ? I18N.selectedButton : I18N.selectButton) +
            "</button>";
        grid.appendChild(card);
    });
}

function toggleSelection(icon) {
    if (selectedIcons.has(icon.id)) {
        selectedIcons.delete(icon.id);
    } else {
        selectedIcons.set(icon.id, icon);
    }
    displayIcons(currentIcons);
    updateSelectedList();
}

function updateSelectedList() {
    const list = document.getElementById("selectedList");
    const title = document.getElementById("selectedTitle");
    const btn = document.getElementById("sendBtn");
    const count = selectedIcons.size;

    title.textContent =
        count > 0
            ? I18N.selectedCount.replace("{count}", count)
            : I18N.noIconsSelected;
    btn.disabled = count === 0;

    list.innerHTML = "";
    selectedIcons.forEach(function (icon, id) {
        const item = document.createElement("div");
        item.className = "selected-item";
        item.innerHTML =
            "<span>" +
            (icon.name || "icon-" + id) +
            "</span>" +
            '<button class="remove-btn" onclick="event.stopPropagation(); removeSelected(' +
            id +
            ')">×</button>';
        list.appendChild(item);
    });
}

function removeSelected(id) {
    selectedIcons.delete(id);
    displayIcons(currentIcons);
    updateSelectedList();
}

function filterIcons(query) {
    if (!query) {
        currentIcons = allIcons;
    } else {
        const q = query.toLowerCase();
        currentIcons = allIcons.filter(function (icon) {
            return (icon.name || "").toLowerCase().includes(q);
        });
    }
    displayIcons(currentIcons);
}

function updatePagination() {
    const pag = document.getElementById("pagination");
    const nums = document.getElementById("pageNumbers");
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");

    if (totalPages <= 1) {
        pag.style.display = "none";
        return;
    }
    pag.style.display = "flex";
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;

    nums.innerHTML = "";
    const maxVisible = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) {
        startPage = Math.max(1, endPage - maxVisible + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement("button");
        btn.textContent = i;
        btn.className = i === currentPage ? "active" : "";
        btn.onclick = function () {
            goToPage(i);
        };
        nums.appendChild(btn);
    }
}

function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadCachedResults(page);
}

async function sendSelectedIcons() {
    if (selectedIcons.size === 0) return;

    const icons = Array.from(selectedIcons.values());
    try {
        const resp = await fetch("/api/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ icons: icons, searchId: SEARCH_ID }),
        });
        const data = await resp.json();
        if (data.success) {
            showMessage(
                "Sent " + icons.length + " icons to MCP client!",
                "success"
            );
            setTimeout(function () {
                window.close();
            }, 2000);
        } else {
            showMessage(data.error || "Send failed", "error");
        }
    } catch (e) {
        showMessage("Error: " + e.message, "error");
    }
}

function showMessage(text, type) {
    const msg = document.getElementById("message");
    msg.textContent = text;
    msg.className = "message " + type;
    if (type === "success") {
        setTimeout(function () {
            msg.style.display = "none";
        }, 5000);
    }
}
