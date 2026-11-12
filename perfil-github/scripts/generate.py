#!/usr/bin/env python3
"""Genera los banners SVG del perfil con datos reales de GitHub.

Solo usa la libreria estandar. Si la API falla (limite de peticiones, sin red)
usa la web publica o, en ultima instancia, el ultimo valor guardado en
assets/stats.json, asi que nunca deja los banners rotos.
"""
import base64
import html
import json
import os
import re
import urllib.request
from pathlib import Path

USER = os.environ.get("GH_USER", "Jonas26-hash")
TOKEN = os.environ.get("GH_TOKEN")
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ASSETS / "stats.json"

BG = "#0d1117"
PANEL = "#161b22"
BLUE = "#58a6ff"
PURPLE = "#a371f7"
CYAN = "#39d0ff"
GREEN = "#3fb950"
TXT = "#e6edf3"
MUTED = "#8b949e"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "'Fira Code', 'JetBrains Mono', Consolas, 'DejaVu Sans Mono', monospace"
LANG_COLORS = {
    "Java": "#e76f00", "Kotlin": "#a97bff", "TypeScript": "#3178c6",
    "Python": "#3572a5", "JavaScript": "#f1e05a", "HTML": "#e34c26",
    "CSS": "#9b6bff", "SCSS": "#c6538c", "MDX": "#fcb32c",
}
LEVELS = ["#161b22", "#17365d", "#1f6feb", "#58a6ff", "#b6e3ff"]
e = html.escape

DEFAULTS = {"stars": 75, "followers": 2, "repos": 40, "contributions": 0,
            "active_days": 0, "langs": [["Java", 14], ["Kotlin", 4], ["TypeScript", 4], ["Python", 4], ["HTML", 6]]}


# ------------------------------------------------------------------ datos
def http(url, accept="application/json"):
    headers = {"User-Agent": "profile-visuals", "Accept": accept}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def fetch_api():
    user = json.loads(http(f"https://api.github.com/users/{USER}"))
    repos, page = [], 1
    while True:
        chunk = json.loads(http(f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}"))
        repos += chunk
        if len(chunk) < 100:
            break
        page += 1
    langs = {}
    for r in repos:
        if not r.get("fork") and r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    return {
        "stars": sum(r["stargazers_count"] for r in repos),
        "followers": user["followers"],
        "repos": user["public_repos"],
        "langs": sorted(langs.items(), key=lambda kv: -kv[1]),
    }


def fetch_web():
    langs, repos, page = {}, 0, 1
    while page <= 5:
        h = http(f"https://github.com/{USER}?tab=repositories&page={page}", "text/html")
        items = re.split(r'<li[^>]*itemprop="owns"', h)[1:]
        if not items:
            break
        for it in items:
            repos += 1
            if "Forked from" in it:
                continue
            m = re.search(r'itemprop="programmingLanguage">([^<]+)<', it)
            if m:
                langs[m.group(1)] = langs.get(m.group(1), 0) + 1
        page += 1
    out = {"repos": repos, "langs": sorted(langs.items(), key=lambda kv: -kv[1])}
    h = http(f"https://github.com/{USER}", "text/html")
    m = re.search(r'text-bold color-fg-default">(\d+)</span>\s*followers', h)
    if m:
        out["followers"] = int(m.group(1))
    return out


def fetch_calendar():
    h = http(f"https://github.com/users/{USER}/contributions", "text/html")
    tips = {}
    for m in re.finditer(r'<tool-tip[^>]*?for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)</tool-tip>', h):
        txt = m.group(2).strip()
        n = 0 if txt.lower().startswith("no ") else int((re.search(r"\d+", txt) or [0])[0] or 0)
        tips[m.group(1)] = n
    cells = []
    for m in re.finditer(r'<td[^>]*?data-date="(\d{4}-\d{2}-\d{2})"[^>]*?id="(contribution-day-component-(\d+)-(\d+))"[^>]*?data-level="(\d)"', h):
        date, cid, row, col, lvl = m.groups()
        cells.append({"date": date, "row": int(row), "col": int(col), "level": int(lvl), "count": tips.get(cid, 0)})
    total = re.search(r"([\d,]+)\s+contributions\s+in\s+the\s+last\s+year", h)
    total = int(total.group(1).replace(",", "")) if total else sum(c["count"] for c in cells)
    return cells, total


MARKUP = {"HTML", "CSS", "SCSS", "MDX", "Markdown", "Jupyter Notebook"}


def code_langs(d):
    return [(n, c) for n, c in d["langs"] if n not in MARKUP]


def load_data():
    data = dict(DEFAULTS)
    if CACHE.exists():
        try:
            data.update(json.loads(CACHE.read_text()))
        except Exception:
            pass
    for fn in (fetch_api, fetch_web):
        try:
            data.update(fn())
            print(f"datos de perfil via {fn.__name__}")
            break
        except Exception as ex:
            print(f"{fn.__name__} fallo: {ex}")
    cells = data.get("cells", [])
    try:
        cells, total = fetch_calendar()
        data["contributions"] = total
        data["active_days"] = sum(1 for c in cells if c["count"] > 0)
        data["cells"] = cells
        print(f"calendario: {len(cells)} dias, {total} contribuciones")
    except Exception as ex:
        print(f"calendario fallo: {ex}")
    data["cells"] = cells
    CACHE.write_text(json.dumps(data, ensure_ascii=False))
    return data


# --------------------------------------------------------------- helpers
def svg(w, h, body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CYAN}"/>'
            f'<stop offset="0.5" stop-color="{BLUE}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>'
            f'<linearGradient id="gb" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{w}" y2="0">'
            f'<stop offset="0" stop-color="{CYAN}"/><stop offset="0.5" stop-color="{PURPLE}"/><stop offset="1" stop-color="{BLUE}"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" from="-{w} 0" to="{w} 0" dur="6s" repeatCount="indefinite"/></linearGradient>'
            f'<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3" result="b"/>'
            f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>{defs}</defs>{body}</svg>')


def write(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8")
    print("escrito", name)


def chip(x, y, label, color, size=12.5):
    w = len(label) * size * 0.6 + 22
    return (f'<g transform="translate({x},{y})"><rect width="{w:.0f}" height="26" rx="13" fill="{color}" fill-opacity="0.12" '
            f'stroke="{color}" stroke-opacity="0.55"/><text x="{w/2:.0f}" y="17.5" text-anchor="middle" font-family="{FONT}" '
            f'font-size="{size}" font-weight="600" fill="{color}">{e(label)}</text></g>'), w


def fmt(n):
    return f"{n:,}".replace(",", ".") if n >= 10000 else str(n)


# ----------------------------------------------------------------- hero
def make_hero(d):
    W, H = 830, 210
    avatar = base64.b64encode((ASSETS / "avatar-small.png").read_bytes()).decode()
    langs = [l for l, _ in code_langs(d)[:4]] or ["Java", "Kotlin", "TypeScript", "Python"]
    chips, x = "", 200
    for l in langs:
        c, w = chip(x, 150, l, BLUE)
        chips += c
        x += w + 8
    defs = (f'<clipPath id="card"><rect width="{W}" height="{H}" rx="22"/></clipPath>'
            f'<clipPath id="av"><circle cx="110" cy="105" r="52"/></clipPath>'
            f'<radialGradient id="b1"><stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>'
            f'<radialGradient id="b2"><stop offset="0" stop-color="{PURPLE}" stop-opacity=".35"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>')
    body = f'''<rect width="{W}" height="{H}" rx="22" fill="{BG}"/>
<g clip-path="url(#card)">
<circle cx="160" cy="20" r="240" fill="url(#b1)"><animate attributeName="cx" values="120;300;120" dur="10s" repeatCount="indefinite"/></circle>
<circle cx="720" cy="200" r="240" fill="url(#b2)"><animate attributeName="cx" values="760;560;760" dur="12s" repeatCount="indefinite"/></circle>
</g>
<rect x="22" y="22" width="{W-44}" height="{H-44}" rx="16" fill="{PANEL}" fill-opacity="0.55" stroke="{BLUE}" stroke-opacity="0.35"/>
<image href="data:image/png;base64,{avatar}" x="58" y="53" width="104" height="104" clip-path="url(#av)" preserveAspectRatio="xMidYMid slice"/>
<circle cx="110" cy="105" r="58" fill="none" stroke="url(#g)" stroke-width="3" stroke-dasharray="40 14" stroke-linecap="round">
<animateTransform attributeName="transform" type="rotate" from="0 110 105" to="360 110 105" dur="14s" repeatCount="indefinite"/></circle>
<text x="200" y="62" font-family="{MONO}" font-size="13" letter-spacing="3" fill="{MUTED}" font-weight="700">@{e(USER.lower())}</text>
<text x="200" y="110" font-family="{FONT}" font-size="44" font-weight="800" fill="url(#g)">TechTonic | Dev</text>
<text x="200" y="136" font-family="{FONT}" font-size="15" fill="{MUTED}">Estudiante de Ingeniería de Sistemas · Full Stack &amp; Android</text>
{chips}
<text x="715" y="108" text-anchor="middle" font-family="{FONT}" font-size="54" font-weight="800" fill="{BLUE}">{fmt(d["stars"])}</text>
<text x="715" y="132" text-anchor="middle" font-family="{MONO}" font-size="11" letter-spacing="3" fill="{MUTED}" font-weight="700">TOTAL STARS</text>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="21" fill="none" stroke="url(#gb)" stroke-width="2" opacity="0.8"/>'''
    write("hero.svg", svg(W, H, body, defs))


# ------------------------------------------------------------- terminal
def make_terminal(d):
    W, H = 830, 440
    ascii_lines = (ASSETS / "ascii.txt").read_text().split("\n")
    langs = ", ".join(l for l, _ in code_langs(d)[:4]) or "Java, Kotlin"
    rows = [
        ("Subject", "TechTonic | Dev"),
        ("Handle", f"@{USER.lower()}"),
        ("Role", "Estudiante · Ing. de Sistemas"),
        ("Status", "Building | Learning | Shipping"),
        ("Languages", langs),
        ("Repositories", str(d["repos"])),
        ("Contributions", str(d["contributions"])),
        ("Stars", str(d["stars"])),
        ("Followers", str(d["followers"])),
        ("Active Days", str(d["active_days"])),
        ("Contact", f"github.com/{USER}"),
    ]
    ascii_svg = ""
    xs = " ".join(str(72 + 6 * i) for i in range(46))  # paso fijo: no depende de la fuente
    for i, ln in enumerate(ascii_lines):
        ascii_svg += (f'<text x="{xs}" y="{112 + i * 10.5:.1f}" xml:space="preserve" '
                      f'font-family="{MONO}" font-size="10" fill="url(#ag)">{e(ln)}</text>')
    info = ""
    for i, (k, v) in enumerate(rows):
        y = 118 + i * 25
        info += (f'<text x="434" y="{y}" font-family="{MONO}" font-size="12.5" font-weight="700" fill="{BLUE}">{e(k)}</text>'
                 f'<line x1="528" y1="{y-4}" x2="548" y2="{y-4}" stroke="{MUTED}" stroke-opacity="0.5" stroke-dasharray="2 3"/>'
                 f'<text x="560" y="{y}" font-family="{MONO}" font-size="12.5" fill="{TXT}">{e(v)}</text>')
    defs = (f'<clipPath id="lp"><rect x="24" y="64" width="372" height="354" rx="14"/></clipPath>'
            f'<linearGradient id="ag" gradientUnits="userSpaceOnUse" x1="0" y1="100" x2="0" y2="380">'
            f'<stop offset="0" stop-color="{CYAN}"/><stop offset="0.5" stop-color="{GREEN}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>'
            f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GREEN}" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="{GREEN}" stop-opacity="0.28"/><stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></linearGradient>')
    body = f'''<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>
<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="17" fill="none" stroke="url(#gb)" stroke-width="2" opacity="0.8"/>
<circle cx="26" cy="24" r="6" fill="#ff5f56"/><circle cx="46" cy="24" r="6" fill="#ffbd2e"/><circle cx="66" cy="24" r="6" fill="#27c93f"/>
<text x="{W/2}" y="28" text-anchor="middle" font-family="{MONO}" font-size="12" fill="{MUTED}">{e(USER.lower())}@github ~ $ ./profile-scan --live</text>
<circle cx="758" cy="24" r="4" fill="{BLUE}"><animate attributeName="opacity" values="1;0.2;1" dur="1.6s" repeatCount="indefinite"/></circle>
<text x="770" y="28" font-family="{MONO}" font-size="11" font-weight="700" fill="{BLUE}" letter-spacing="1">LIVE</text>
<line x1="0" y1="46" x2="{W}" y2="46" stroke="{BLUE}" stroke-opacity="0.25"/>
<rect x="24" y="64" width="372" height="354" rx="14" fill="{PANEL}" fill-opacity="0.5" stroke="{BLUE}" stroke-opacity="0.35"/>
<rect x="414" y="64" width="392" height="354" rx="14" fill="{PANEL}" fill-opacity="0.5" stroke="{BLUE}" stroke-opacity="0.35"/>
<text x="40" y="84" font-family="{MONO}" font-size="10" letter-spacing="2" fill="{MUTED}">VISUAL.MAP</text>
<text x="430" y="84" font-family="{MONO}" font-size="10" letter-spacing="2" fill="{MUTED}">SYSTEM.INFO</text>
{ascii_svg}
<g clip-path="url(#lp)"><rect x="24" y="64" width="372" height="60" fill="url(#scan)"><animate attributeName="y" values="40;380;40" dur="5s" repeatCount="indefinite"/></rect></g>
{info}
<text x="434" y="400" font-family="{MONO}" font-size="12.5" fill="{GREEN}">$</text>
<rect x="448" y="389" width="8" height="14" fill="{GREEN}"><animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/></rect>'''
    write("terminal.svg", svg(W, H, body, defs))


# ---------------------------------------------------------------- stats
def make_stats(d):
    W, H = 830, 150
    items = [("STARS", d["stars"], 100, BLUE), ("CONTRIBUCIONES", d["contributions"], 500, CYAN),
             ("REPOSITORIOS", d["repos"], 60, PURPLE), ("SEGUIDORES", d["followers"], 10, GREEN)]
    gap, cw = 14, (W - 40 - 14 * 3) / 4
    body = f'<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>'
    for i, (lab, val, cap, col) in enumerate(items):
        x = 20 + i * (cw + gap)
        pct = max(0.03, min(1, val / cap)) * (cw - 36)
        body += f'''<g><rect x="{x:.0f}" y="18" width="{cw:.0f}" height="{H-36}" rx="14" fill="{PANEL}" fill-opacity="0.7" stroke="{col}" stroke-opacity="0.45"/>
<text x="{x+18:.0f}" y="48" font-family="{MONO}" font-size="11" letter-spacing="2" font-weight="700" fill="{MUTED}">{lab}</text>
<text x="{x+18:.0f}" y="94" font-family="{FONT}" font-size="38" font-weight="800" fill="{col}">{fmt(val)}</text>
<rect x="{x+18:.0f}" y="108" width="{cw-36:.0f}" height="6" rx="3" fill="#21262d"/>
<rect x="{x+18:.0f}" y="108" width="{pct:.0f}" height="6" rx="3" fill="{col}"><animate attributeName="width" values="0;{pct:.0f}" dur="1.4s" fill="freeze"/></rect></g>'''
    body += f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="17" fill="none" stroke="url(#gb)" stroke-width="1.5" opacity="0.6"/>'
    write("stats.svg", svg(W, H, body))


# ------------------------------------------------------------ lenguajes
def make_languages(d):
    langs = [tuple(x) for x in code_langs(d)[:5]] or [("Java", 1)]
    total = sum(n for _, n in code_langs(d)) or 1
    W, H = 830, 80 + len(langs) * 36
    body = f'''<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>
<text x="30" y="40" font-family="{MONO}" font-size="16" font-weight="700" fill="{TXT}">Lenguajes</text>
<text x="{W-30}" y="40" text-anchor="end" font-family="{MONO}" font-size="12" fill="{MUTED}">por repositorio · stack.scan</text>'''
    for i, (name, n) in enumerate(langs):
        y = 80 + i * 36
        col = LANG_COLORS.get(name, BLUE)
        pct = n / total
        bw = 470 * pct / (langs[0][1] / total)
        body += f'''<circle cx="40" cy="{y}" r="6" fill="{col}"/>
<text x="58" y="{y+5}" font-family="{MONO}" font-size="13" font-weight="700" fill="{col}">{e(name)}</text>
<rect x="190" y="{y-4}" width="470" height="8" rx="4" fill="#21262d"/>
<rect x="190" y="{y-4}" width="{bw:.0f}" height="8" rx="4" fill="{col}"><animate attributeName="width" values="0;{bw:.0f}" dur="1.4s" fill="freeze"/></rect>
<text x="{W-30}" y="{y+5}" text-anchor="end" font-family="{MONO}" font-size="13" fill="{TXT}">{pct*100:.0f}%</text>'''
    body += f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="17" fill="none" stroke="url(#gb)" stroke-width="1.5" opacity="0.6"/>'
    write("languages.svg", svg(W, H, body))


# -------------------------------------------------------------- heatmap
def make_heatmap(d):
    cells = d.get("cells", [])
    W, step, size = 830, 14, 11
    ncols = (max(c["col"] for c in cells) + 1) if cells else 53
    x0, y0 = (W - ncols * step) // 2, 74
    H = y0 + 7 * step + 58
    body = f'''<rect width="{W}" height="{H}" rx="18" fill="{BG}"/>
<text x="{x0}" y="34" font-family="{MONO}" font-size="11" letter-spacing="2" font-weight="700" fill="{GREEN}">SNAKE TRAIL</text>
<text x="{x0}" y="54" font-family="{FONT}" font-size="16" font-weight="700" fill="{TXT}">{d["contributions"]} contribuciones en el último año</text>
<text x="{W-x0}" y="34" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2" font-weight="700" fill="{BLUE}">LIVE</text>'''
    months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    seen = None
    for c in sorted((c for c in cells if c["row"] == 0), key=lambda c: c["col"]):
        mth = int(c["date"][5:7])
        if mth != seen:
            seen = mth
            body += f'<text x="{x0 + c["col"] * step}" y="{y0 - 6}" font-family="{MONO}" font-size="9.5" fill="{MUTED}">{months[mth-1]}</text>'
    for c in cells:
        body += (f'<rect x="{x0 + c["col"] * step}" y="{y0 + c["row"] * step}" width="{size}" height="{size}" rx="2.5" '
                 f'fill="{LEVELS[c["level"]]}"><title>{c["date"]}: {c["count"]}</title></rect>')
    # serpiente que recorre el calendario
    top, bot = y0 + size / 2, y0 + 6 * step + size / 2
    path = f"M{x0 + size/2},{top}"
    for col in range(ncols):
        cx = x0 + col * step + size / 2
        if col:
            path += f" H{cx}"
        path += f" V{bot if col % 2 == 0 else top}"
    dur = max(20, ncols * 1.1)
    body += f'<g filter="url(#glow)">'
    for k in range(7, -1, -1):
        r = 5.2 - k * 0.38
        op = 1 - k * 0.11
        col = CYAN if k == 0 else BLUE
        body += (f'<circle r="{r:.1f}" fill="{col}" opacity="{op:.2f}"><animateMotion dur="{dur:.0f}s" repeatCount="indefinite" '
                 f'begin="-{k * 0.45:.2f}s" path="{path}"/></circle>')
    body += '</g>'
    ly = y0 + 7 * step + 28
    lx = W - x0 - (5 * 16 + 70)
    body += f'<text x="{lx}" y="{ly+9}" font-family="{MONO}" font-size="10" fill="{MUTED}">Menos</text>'
    for i, col in enumerate(LEVELS):
        body += f'<rect x="{lx + 40 + i * 16}" y="{ly}" width="{size}" height="{size}" rx="2.5" fill="{col}"/>'
    body += f'<text x="{lx + 40 + 5 * 16 + 4}" y="{ly+9}" font-family="{MONO}" font-size="10" fill="{MUTED}">Más</text>'
    body += f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="17" fill="none" stroke="url(#gb)" stroke-width="1.5" opacity="0.6"/>'
    write("heatmap.svg", svg(W, H, body))


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    data = load_data()
    make_hero(data)
    make_terminal(data)
    make_stats(data)
    make_languages(data)
    make_heatmap(data)
