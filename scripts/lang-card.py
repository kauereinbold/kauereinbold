#!/usr/bin/env python3
"""Compute languages from lines *authored by Kaue* across local git repos and
render an SVG card (dark + light), then inject it into README.md between the
<!-- LANGS:START --> / <!-- LANGS:END --> markers.

Counts added lines in commits whose author matches AUTHOR_RE, grouped by file
extension -> language. Programming languages only (markup/config/docs excluded).

Run locally (needs local repo clones):
  REPOS="/path/to/repoA,/path/to/repoB" python3 scripts/lang-card.py
Env: REPOS (comma-separated local repo paths, required), TOP (default: 6).
"""
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
ASSETS = ROOT / "assets"
TOP = int(os.environ.get("TOP", "6"))
AUTHOR_RE = "reinbold|Kaue"  # matches name + email; old commits use a *.reinbold email


def target_repos():
    # Local repo paths come from the environment, never hardcoded (this file is public).
    env = os.environ.get("REPOS", "").strip()
    if not env:
        raise SystemExit("Set REPOS to comma-separated local repo paths, e.g. "
                         "REPOS=\"$HOME/repos/a,$HOME/repos/b\" python3 scripts/lang-card.py")
    paths = [p.strip() for p in env.split(",") if p.strip()]
    return [Path(p) for p in paths if (Path(p) / ".git").is_dir()]

EXT2LANG = {
    "cs": "C#", "ts": "TypeScript", "tsx": "TypeScript", "js": "JavaScript",
    "jsx": "JavaScript", "mjs": "JavaScript", "py": "Python", "sql": "SQL",
    "go": "Go", "sol": "Solidity", "dart": "Dart", "cpp": "C++", "cc": "C++",
    "cxx": "C++", "java": "Java", "kt": "Kotlin", "rb": "Ruby", "rs": "Rust",
    "php": "PHP", "css": "CSS", "scss": "CSS", "html": "HTML", "sh": "Shell",
}
LANG_COLOR = {
    "C#": "#178600", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Python": "#3572A5", "SQL": "#e38c00", "Go": "#00ADD8", "Solidity": "#AA6746",
    "Dart": "#00B4AB", "C++": "#f34b7d", "Java": "#b07219", "Kotlin": "#A97BFF",
    "Ruby": "#701516", "Rust": "#dea584", "PHP": "#4F5D95", "CSS": "#563d7c",
    "HTML": "#e34c26", "Shell": "#89e051",
}


EXCLUDE = re.compile(
    r"(^|/)(node_modules|bower_components|wwwroot|dist|build|out|bin|obj|vendor|"
    r"packages|Content|Scripts|coverage|\.venv|venv|site-packages|__snapshots__|"
    r"migrations|lib)/"
    r"|\.min\.(js|css)$|\.bundle\.|\.generated\.|-lock\.|\.lock$", re.IGNORECASE)


def count_lines():
    totals = defaultdict(int)
    for repo in target_repos():
        try:
            out = subprocess.run(
                ["git", "-C", str(repo), "log", "--all", "-i", "-E",
                 f"--author={AUTHOR_RE}", "--numstat", "--pretty=tformat:"],
                capture_output=True, text=True, timeout=120).stdout
        except Exception:
            continue
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            add, _del, path = parts
            if add == "-" or not path or EXCLUDE.search(path):
                continue
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            lang = EXT2LANG.get(ext)
            if lang:
                totals[lang] += int(add)
    return totals


def svg(rows, total, palette):
    """Segmented-bar layout: one stacked bar + a two-column legend."""
    bg, border, text, muted = palette
    font = "Segoe UI,system-ui,sans-serif"
    W = 440
    bar_x, bar_y, bar_w, bar_h = 24, 52, W - 48, 16
    legend_top, legend_h = 88, 26
    rows_per_col = (len(rows) + 1) // 2
    H = legend_top + rows_per_col * legend_h + 6
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" role="img" aria-label="Most used languages">',
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="{bg}" stroke="{border}"/>',
         f'<text x="24" y="32" fill="{text}" font-family="{font}" '
         f'font-size="16" font-weight="600">Most used languages</text>']
    # stacked bar (clipped to rounded corners)
    p.append(f'<clipPath id="barclip"><rect x="{bar_x}" y="{bar_y}" '
             f'width="{bar_w}" height="{bar_h}" rx="{bar_h//2}"/></clipPath>')
    segs, x = [], float(bar_x)
    for lang, lines in rows:
        seg = bar_w * lines / total if total else 0
        color = LANG_COLOR.get(lang, "#8b949e")
        segs.append(f'<rect x="{x:.1f}" y="{bar_y}" width="{seg:.1f}" height="{bar_h}" fill="{color}"/>')
        x += seg
    p.append(f'<g clip-path="url(#barclip)">{"".join(segs)}</g>')
    # legend, two columns
    for i, (lang, lines) in enumerate(rows):
        pct = 100 * lines / total if total else 0
        color = LANG_COLOR.get(lang, "#8b949e")
        lx = 24 + (i % 2) * (W // 2 - 8)
        ly = legend_top + (i // 2) * legend_h
        p.append(f'<circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{color}"/>')
        p.append(f'<text x="{lx+16}" y="{ly}" fill="{text}" font-family="{font}" '
                 f'font-size="12.5">{lang} {pct:.1f}%</text>')
    p.append("</svg>")
    return "\n".join(p)


def inject(text, key, content):
    s, e = f"<!-- {key}:START -->", f"<!-- {key}:END -->"
    pat = re.compile(re.escape(s) + r".*?" + re.escape(e), re.DOTALL)
    return pat.sub(f"{s}\n{content}\n{e}", text) if pat.search(text) else text


def main():
    totals = count_lines()
    rows = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:TOP]
    total = sum(v for _, v in rows)
    ASSETS.mkdir(exist_ok=True)
    dark = ("#161b22", "#30363d", "#c9d1d9", "#8b949e")
    light = ("#ffffff", "#d0d7de", "#1f2328", "#656d76")
    (ASSETS / "langs-dark.svg").write_text(svg(rows, total, dark), encoding="utf-8")
    (ASSETS / "langs-light.svg").write_text(svg(rows, total, light), encoding="utf-8")
    card = ('<picture>\n'
            '  <source media="(prefers-color-scheme: dark)" srcset="assets/langs-dark.svg">\n'
            '  <img src="assets/langs-light.svg" alt="Most used languages by lines authored" width="420">\n'
            '</picture>')
    README.write_text(inject(README.read_text(encoding="utf-8"), "LANGS", card), encoding="utf-8")
    print("Languages (lines authored):")
    for lang, n in rows:
        print(f"  {lang:12} {n:>8,}  {100*n/total:5.1f}%")


if __name__ == "__main__":
    main()
