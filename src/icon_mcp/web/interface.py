"""Web interface - generates HTML and JS for icon selection UI."""

from __future__ import annotations

from ..lang import t, get_current_language


class WebInterface:
    """Generates the HTML/JS for the icon selection web UI."""

    def __init__(self, port: int = 3000):
        self.port = port

    def generate_html(self, search_id: str = "") -> str:
        """Generate the main HTML page."""
        lang = get_current_language()
        title = t("web.title")
        subtitle = t("web.subtitle")
        search_placeholder = t("web.searchPlaceholder")
        send_btn = t("web.sendSelected")
        no_selected = t("web.noIconsSelected")
        loading = t("web.loading")
        prev_text = t("web.previous")
        next_text = t("web.next")

        return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 24px 32px;
            text-align: center;
        }}
        .header h1 {{ font-size: 28px; margin-bottom: 6px; }}
        .header p {{ opacity: 0.85; font-size: 14px; }}
        .search-bar {{
            max-width: 600px;
            margin: 16px auto 0;
            display: flex;
            gap: 8px;
        }}
        .search-bar input {{
            flex: 1;
            padding: 10px 16px;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            outline: none;
        }}
        .main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
            display: flex;
            gap: 24px;
        }}
        .icon-area {{ flex: 1; }}
        .sidebar {{
            width: 280px;
            flex-shrink: 0;
        }}
        .icon-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 16px;
        }}
        .icon-card {{
            background: white;
            border-radius: 12px;
            padding: 20px 16px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }}
        .icon-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.1);
        }}
        .icon-card.selected {{
            border: 2px solid #667eea;
            background: #f0f0ff;
        }}
        .icon-preview {{
            width: 64px;
            height: 64px;
            margin: 0 auto 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .icon-preview img, .icon-preview svg {{
            max-width: 100%;
            max-height: 100%;
        }}
        .icon-name {{
            font-size: 13px;
            color: #555;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .icon-card .btn {{
            margin-top: 10px;
            padding: 6px 16px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            cursor: pointer;
            background: #667eea;
            color: white;
            transition: background 0.2s;
        }}
        .icon-card .btn:hover {{ background: #5a6fd6; }}
        .icon-card .btn.selected-btn {{
            background: #4caf50;
        }}
        .sidebar-box {{
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            position: sticky;
            top: 24px;
        }}
        .sidebar-box h3 {{
            font-size: 16px;
            margin-bottom: 12px;
            color: #333;
        }}
        .selected-list {{
            max-height: 400px;
            overflow-y: auto;
        }}
        .selected-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px;
            border-bottom: 1px solid #eee;
            font-size: 13px;
        }}
        .selected-item .remove-btn {{
            margin-left: auto;
            background: none;
            border: none;
            color: #e74c3c;
            cursor: pointer;
            font-size: 16px;
        }}
        .send-btn {{
            width: 100%;
            padding: 12px;
            margin-top: 16px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .send-btn:hover {{ opacity: 0.9; }}
        .send-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 24px;
            flex-wrap: wrap;
        }}
        .pagination button {{
            padding: 8px 14px;
            border: 1px solid #ddd;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-size: 14px;
        }}
        .pagination button:hover {{ background: #f0f0f0; }}
        .pagination button:disabled {{ opacity: 0.4; cursor: not-allowed; }}
        .pagination button.active {{
            background: #667eea;
            color: white;
            border-color: #667eea;
        }}
        .pagination .page-info {{
            font-size: 14px;
            color: #666;
        }}
        .loading {{
            text-align: center;
            padding: 60px;
            font-size: 16px;
            color: #999;
        }}
        .spinner {{
            display: inline-block;
            width: 36px;
            height: 36px;
            border: 3px solid #eee;
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 12px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .message {{
            padding: 12px 20px;
            border-radius: 8px;
            margin: 16px 0;
            font-size: 14px;
            display: none;
        }}
        .message.success {{ background: #d4edda; color: #155724; display: block; }}
        .message.error {{ background: #f8d7da; color: #721c24; display: block; }}
        @media (max-width: 768px) {{
            .main {{ flex-direction: column; padding: 16px; }}
            .sidebar {{ width: 100%; }}
            .icon-grid {{ grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>{subtitle}</p>
        <div class="search-bar">
            <input type="text" id="filterInput" placeholder="{search_placeholder}"
                   oninput="filterIcons(this.value)">
        </div>
    </div>
    <div class="main">
        <div class="icon-area">
            <div id="message" class="message"></div>
            <div id="loading" class="loading" style="display:none;">
                <div class="spinner"></div>
                <div>{loading}</div>
            </div>
            <div id="iconGrid" class="icon-grid"></div>
            <div id="pagination" class="pagination" style="display:none;">
                <button id="prevBtn" onclick="goToPage(currentPage-1)">{prev_text}</button>
                <span id="pageNumbers"></span>
                <button id="nextBtn" onclick="goToPage(currentPage+1)">{next_text}</button>
            </div>
        </div>
        <div class="sidebar">
            <div class="sidebar-box">
                <h3 id="selectedTitle">{no_selected}</h3>
                <div id="selectedList" class="selected-list"></div>
                <button class="send-btn" id="sendBtn" onclick="sendSelectedIcons()" disabled>
                    {send_btn}
                </button>
            </div>
        </div>
    </div>
    <script>
        const SEARCH_ID = '{search_id}';
        const WS_PORT = {self.port};
    </script>
    <script src="/site.js"></script>
</body>
</html>"""

    def generate_js(self) -> str:
        """Generate client-side JavaScript."""
        selected_text = t("web.selectedCount")
        no_selected = t("web.noIconsSelected")
        select_btn = t("web.selectButton")
        selected_btn = t("web.selectedButton")
        error_text = t("web.error")
        send_text = t("web.sendSelected")

        return f"""
// === MCP Icon Server - Client JS ===
let selectedIcons = new Map();
let currentIcons = [];
let allIcons = [];
let websocket = null;
let currentPage = 1;
let totalPages = 1;
let pageSize = 15;

// Initialize
document.addEventListener('DOMContentLoaded', function() {{
    if (SEARCH_ID) {{
        connectWebSocket();
        loadCachedResults(1);
    }}
}});

function connectWebSocket() {{
    try {{
        websocket = new WebSocket('ws://localhost:' + WS_PORT + '/ws?searchId=' + SEARCH_ID);
        websocket.onopen = function() {{
            console.log('WebSocket connected');
            setInterval(function() {{
                if (websocket && websocket.readyState === WebSocket.OPEN) {{
                    websocket.send(JSON.stringify({{type: 'ping'}}));
                }}
            }}, 30000);
        }};
        websocket.onmessage = function(event) {{
            const data = JSON.parse(event.data);
            console.log('WS message:', data);
        }};
        websocket.onclose = function() {{
            console.log('WebSocket disconnected');
            setTimeout(connectWebSocket, 3000);
        }};
    }} catch(e) {{
        console.error('WebSocket error:', e);
    }}
}}

async function loadCachedResults(page) {{
    const loading = document.getElementById('loading');
    const grid = document.getElementById('iconGrid');
    loading.style.display = 'block';
    grid.innerHTML = '';

    try {{
        const resp = await fetch('/api/cache?searchId=' + SEARCH_ID + '&page=' + page + '&pageSize=' + pageSize);
        const data = await resp.json();
        if (data.error) {{
            showMessage(data.error, 'error');
            return;
        }}
        currentIcons = data.icons || [];
        allIcons = currentIcons;
        totalPages = data.totalPages || 1;
        currentPage = data.page || 1;
        displayIcons(currentIcons);
        updatePagination();
    }} catch(e) {{
        showMessage('{error_text}: ' + e.message, 'error');
    }} finally {{
        loading.style.display = 'none';
    }}
}}

function displayIcons(icons) {{
    const grid = document.getElementById('iconGrid');
    grid.innerHTML = '';
    icons.forEach(function(icon, index) {{
        const card = document.createElement('div');
        card.className = 'icon-card' + (selectedIcons.has(icon.id) ? ' selected' : '');
        card.onclick = function() {{ toggleSelection(icon); }};

        let preview = '';
        if (icon.show_svg) {{
            preview = icon.show_svg;
        }} else if (icon.icon) {{
            preview = '<img src="' + icon.icon + '" alt="' + (icon.name||'') + '">';
        }} else {{
            preview = '<span style="font-size:32px;color:#ccc;">&#128196;</span>';
        }}

        const isSelected = selectedIcons.has(icon.id);
        card.innerHTML =
            '<div class="icon-preview">' + preview + '</div>' +
            '<div class="icon-name">' + (icon.name || 'icon-' + icon.id) + '</div>' +
            '<button class="btn ' + (isSelected ? 'selected-btn' : '') + '">' +
            (isSelected ? '{selected_btn}' : '{select_btn}') + '</button>';
        grid.appendChild(card);
    }});
}}

function toggleSelection(icon) {{
    if (selectedIcons.has(icon.id)) {{
        selectedIcons.delete(icon.id);
    }} else {{
        selectedIcons.set(icon.id, icon);
    }}
    displayIcons(currentIcons);
    updateSelectedList();
}}

function updateSelectedList() {{
    const list = document.getElementById('selectedList');
    const title = document.getElementById('selectedTitle');
    const btn = document.getElementById('sendBtn');
    const count = selectedIcons.size;

    title.textContent = count > 0 ? '{selected_text}'.replace('{{count}}', count) : '{no_selected}';
    btn.disabled = count === 0;

    list.innerHTML = '';
    selectedIcons.forEach(function(icon, id) {{
        const item = document.createElement('div');
        item.className = 'selected-item';
        item.innerHTML =
            '<span>' + (icon.name || 'icon-' + id) + '</span>' +
            '<button class="remove-btn" onclick="event.stopPropagation(); removeSelected(' + id + ')">x</button>';
        list.appendChild(item);
    }});
}}

function removeSelected(id) {{
    selectedIcons.delete(id);
    displayIcons(currentIcons);
    updateSelectedList();
}}

function filterIcons(query) {{
    if (!query) {{
        currentIcons = allIcons;
    }} else {{
        const q = query.toLowerCase();
        currentIcons = allIcons.filter(function(icon) {{
            return (icon.name || '').toLowerCase().includes(q);
        }});
    }}
    displayIcons(currentIcons);
}}

function updatePagination() {{
    const pag = document.getElementById('pagination');
    const nums = document.getElementById('pageNumbers');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    if (totalPages <= 1) {{
        pag.style.display = 'none';
        return;
    }}
    pag.style.display = 'flex';
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;

    nums.innerHTML = '';
    const maxVisible = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage < maxVisible - 1) {{
        startPage = Math.max(1, endPage - maxVisible + 1);
    }}

    for (let i = startPage; i <= endPage; i++) {{
        const btn = document.createElement('button');
        btn.textContent = i;
        btn.className = i === currentPage ? 'active' : '';
        btn.onclick = function() {{ goToPage(i); }};
        nums.appendChild(btn);
    }}
}}

function goToPage(page) {{
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    loadCachedResults(page);
}}

async function sendSelectedIcons() {{
    if (selectedIcons.size === 0) return;

    const icons = Array.from(selectedIcons.values());
    try {{
        const resp = await fetch('/api/save', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ icons: icons, searchId: SEARCH_ID }})
        }});
        const data = await resp.json();
        if (data.success) {{
            showMessage('Sent ' + icons.length + ' icons to MCP client!', 'success');
            setTimeout(function() {{ window.close(); }}, 2000);
        }} else {{
            showMessage(data.error || 'Send failed', 'error');
        }}
    }} catch(e) {{
        showMessage('Error: ' + e.message, 'error');
    }}
}}

function showMessage(text, type) {{
    const msg = document.getElementById('message');
    msg.textContent = text;
    msg.className = 'message ' + type;
    if (type === 'success') {{
        setTimeout(function() {{ msg.style.display = 'none'; }}, 5000);
    }}
}}
"""
