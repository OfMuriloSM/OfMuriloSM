#!/usr/bin/env python3
"""Render public portfolio analytics; standard library only."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import math
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

OWNER = "OfMuriloSM"
API = "https://api.github.com"
OUT = Path(__file__).resolve().parents[1] / "assets" / "analytics"

def request(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "obsidian-portfolio"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(API + path, headers=headers), timeout=30) as response:
        return json.load(response)

def collect(fetch=request):
    projects = []
    for page in range(1, 101):
        batch = fetch(f"/users/{OWNER}/repos?type=owner&per_page=100&page={page}")
        if not isinstance(batch, list):
            raise ValueError("Unexpected repository response")
        projects.extend(r for r in batch if r.get("private") is False and r.get("fork") is False and not r.get("archived") and r["name"].lower() != OWNER.lower())
        if len(batch) < 100:
            break
    else:
        raise ValueError("Pagination limit reached")
    languages = Counter()
    for r in projects:
        data = fetch(f"/repos/{OWNER}/{quote(r['name'], safe='')}/languages")
        if not isinstance(data, dict) or any(type(v) is not int or v < 0 for v in data.values()):
            raise ValueError("Unexpected language response")
        languages.update(data)
    return projects, languages

def palette(light):
    return ("#fafafa", "#171717", "#555555", "#d4d4d8", "#ffffff") if light else ("#09090b", "#e4e4e7", "#a1a1aa", "#3f3f46", "#18181b")

def wrap(width, height, title, content, light):
    bg, fg, muted, border, surface = palette(light)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img"><title>{escape(title)}</title><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="8" fill="{bg}" stroke="{border}"/><g font-family="Arial,sans-serif">{content}</g></svg>'

def milestones(projects, date, light):
    _, fg, muted, border, surface = palette(light)
    values = [("Public projects", len(projects), "Original project repositories"), ("Primary languages", len({r["language"] for r in projects if r.get("language")}), "Across these public projects"), ("Forks received", sum(r["forks_count"] for r in projects), "Across these public projects")]
    parts = [f'<text x="19" y="25" font-size="15" font-weight="600" fill="{fg}">Public GitHub milestones</text>']
    for i, (label, value, desc) in enumerate(values):
        parts.append(f'<g transform="translate({18+i*258} 39)"><rect width="248" height="106" rx="6" fill="{surface}" stroke="{border}"/><g transform="translate(18 18)" stroke="{muted}" stroke-width="1.5" fill="none"><path d="M7 2h18v9a9 9 0 0 1-18 0zM7 5H2v5a6 6 0 0 0 6 6m17-11h5v5a6 6 0 0 1-6 6M16 20v8m-7 0h14"/></g><text x="62" y="38" font-size="25" font-weight="700" fill="{fg}">{value}</text><text x="18" y="65" font-size="14" font-weight="600" fill="{fg}">{label}</text><text x="18" y="85" font-size="11" fill="{muted}">{desc}</text></g>')
    parts.append(f'<text x="19" y="163" font-size="10" fill="{muted}">Public snapshot · {date} · Excludes profile, forks and archived repositories</text>')
    return wrap(800, 174, "Public GitHub milestones: " + ", ".join(f"{label}: {value}" for label, value, _ in values), "".join(parts), light)

def language_chart(languages, date, light):
    _, fg, muted, border, _ = palette(light)
    counts = sorted(((k,v) for k,v in languages.items() if v > 0), key=lambda x: (-x[1], x[0]))
    total = sum(v for _,v in counts)
    top = counts[:5]
    if len(counts) > 5:
        top.append(("Other", sum(v for _,v in counts[5:])))
    colors = ["#29292d","#55555c","#797980","#a1a1aa","#c4c4c9","#e1e1e5"] if light else ["#e4e4e7","#bcbcc2","#94949c","#71717a","#52525b","#3f3f46"]
    circumference = 2 * math.pi * 54
    parts = [f'<text x="22" y="30" font-size="17" font-weight="600" fill="{fg}">Public language breakdown</text>', f'<circle cx="110" cy="120" r="54" fill="none" stroke="{border}" stroke-width="18"/>']
    offset = 0
    for i, (name, size) in enumerate(top):
        length = circumference * size / total
        parts.append(f'<circle cx="110" cy="120" r="54" fill="none" stroke="{colors[i]}" stroke-width="18" stroke-dasharray="{length:.4f} {circumference-length:.4f}" stroke-dashoffset="{-offset:.4f}" transform="rotate(-90 110 120)"/>')
        offset += length
        y = 57+i*23
        parts.append(f'<rect x="215" y="{y-10}" width="11" height="11" rx="2" fill="{colors[i]}"/><text x="235" y="{y}" fill="{fg}" font-size="13">{escape(name)}</text><text x="610" y="{y}" text-anchor="end" fill="{muted}" font-size="13">{size/total:.1%}</text>')
    if not total:
        parts.append(f'<text x="215" y="110" fill="{muted}" font-size="14">No public language bytes available</text>')
    parts.append(f'<text x="22" y="206" fill="{muted}" font-size="11">GitHub language bytes · Original public projects · {date}</text>')
    return wrap(640, 220, "Public language breakdown by code size", "".join(parts), light)

def render(projects, languages, date):
    files = {}
    for light in (False, True):
        mode = "light" if light else "dark"
        files[f"milestones-{mode}.svg"] = milestones(projects, date, light)
        files[f"languages-{mode}.svg"] = language_chart(languages, date, light)
    for svg in files.values():
        ET.fromstring(svg)
    return files

def self_test():
    public = {"name": "sample", "private": False, "fork": False, "archived": False, "language": "Python", "forks_count": 2}
    def fixture(path):
        if "/users/" in path:
            return [public, dict(public, name="private", private=True), dict(public, name="fork", fork=True), dict(public, name=OWNER), dict(public, name="archived", archived=True)]
        assert path.endswith("/sample/languages")
        return {"Python": 75, "C#": 25}
    projects, languages = collect(fixture)
    assert len(projects) == 1
    files = render(projects, languages, "2000-01-01")
    assert len(files) == 4
    assert "75.0%" in files["languages-dark.svg"]
    assert "25.0%" in files["languages-light.svg"]
    assert "Forks received: 2" in files["milestones-dark.svg"]
    assert "No public language bytes" in language_chart({}, "2000-01-01", False)
    print("Analytics rendering tests passed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        projects, languages = collect()
        files = render(projects, languages, datetime.now(timezone.utc).date().isoformat())
        OUT.mkdir(parents=True, exist_ok=True)
        for name, svg in files.items():
            path = OUT / name
            temp = path.with_suffix(".tmp")
            temp.write_text(svg + "\n", encoding="utf-8")
            temp.replace(path)
