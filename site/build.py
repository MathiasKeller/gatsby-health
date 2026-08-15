#!/usr/bin/env python3
"""
Build the Gatsby health-record site.

Reads   data/gatsby_data.yaml
Writes  docs/            (this is what GitHub Pages serves)
Also    copies sources/ and images/ into docs/ so every file has a stable,
        directly linkable URL.

Run:    python3 site/build.py
"""

import json
import os
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
import markdown as md

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gatsby_data.yaml"
OUT = ROOT / "docs"
STATIC = Path(__file__).resolve().parent / "static"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

COLOUR_HEX = {"red": "#B33A34", "amber": "#9E6209", "green": "#24664A",
              "blue": "#3A5F94", "grey": "#6F7C89"}

STATUS_BADGE = {"active": "b-red", "recurrent": "b-amber", "unresolved": "b-amber",
                "monitoring": "b-green", "treated": "b-green", "open": "b-grey",
                "overdue": "b-red", "scheduled": "b-blue", "due": "b-amber",
                "future": "b-grey"}


# ── helpers ──────────────────────────────────────────────────────────────

def esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def to_date(v):
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
    return None


def fmt(v, style="long"):
    """Format a date for display. Falls back to the raw string."""
    d = to_date(v)
    if not d:
        return esc(v) if v else "—"
    if style == "short":
        return f"{d.day} {MONTHS[d.month-1]} {str(d.year)[2:]}"
    if style == "num":
        return d.strftime("%d.%m.%Y")
    return f"{d.day} {MONTHS[d.month-1]} {d.year}"


TAG_RE = re.compile(r"`\[([VOIQ])\]`")
SRC_RE = re.compile(r"`\[(S\d+)\]`")


TAG_TITLE = {"V": "From a veterinary document", "O": "Owner observation",
             "I": "Inference — not a diagnosis", "Q": "Unverified or contradicted"}


def enrich(html):
    """Turn `[V]` evidence tags and `[S2]` source refs into styled chips."""
    def tag_sub(m):
        k = m.group(1)
        return f'<span class="tag tag-{k}" title="{TAG_TITLE[k]}">{k}</span>'
    html = TAG_RE.sub(tag_sub, html)
    html = SRC_RE.sub(lambda m: f'<a class="srcref" href="documents.html#{m.group(1)}">{m.group(1)}</a>', html)
    return html


def markdown(text):
    if not text:
        return ""
    # Substitute evidence tags first: markdown leaves inline HTML alone, but would
    # otherwise wrap `[V]` in <code> and the pattern would no longer match.
    return md.markdown(enrich(str(text)), extensions=["tables", "sane_lists"])


def inline(text):
    """Light inline markdown for short strings: bold, italics, code, tags."""
    if text is None:
        return ""
    s = esc(text)
    s = re.sub(r"`\[([VOIQ])\]`", r"[[TAG:\1]]", s)
    s = re.sub(r"`\[(S\d+)\]`", r"[[SRC:\1]]", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+?)`", r"<code>\1</code>", s)
    s = s.replace("[[TAG:", '<span class="tag tag-').replace("]]", "</span>")
    s = re.sub(r'<span class="tag tag-([VOIQ])', r'<span class="tag tag-\1">\1', s)
    s = re.sub(r'\[\[SRC:(S\d+)', r'<a class="srcref" href="documents.html#\1">\1', s)
    return s


def strip_tags(html):
    return re.sub(r"<[^>]+>", "", html)


def demark(text):
    """Strip markdown emphasis so search titles read as plain text."""
    t = str(text or "")
    t = re.sub(r"`\[[VOIQ]\]`|`\[S\d+\]`", "", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\1", t)
    t = t.replace("`", "").replace(">", "").strip(" -—#")
    return re.sub(r"\s+", " ", t).strip()


# ── layout ───────────────────────────────────────────────────────────────

NAV = [
    ("Record", [
        ("index.html", "At a glance", None),
        ("timeline.html", "Timeline", None),
        ("observations.html", "Observations", None),
    ]),
    ("Problems", "PROBLEMS"),
    ("Clinical", [
        ("medications.html", "Medications", None),
        ("labs.html", "Lab results", None),
        ("preventive.html", "Preventive care", None),
        ("anaesthesia.html", "Anaesthesia", None),
    ]),
    ("Archive", [
        ("documents.html", "Documents", None),
        ("images.html", "Images", None),
        ("care-team.html", "Care team", None),
        ("reference.html", "Notes & glossary", None),
        ("print.html", "Print full record", None),
    ]),
]


def nav_html(active, problems):
    out = []
    for title, items in NAV:
        out.append('<div class="nav-group">')
        out.append(f'<span class="nav-label">{esc(title)}</span>')
        if items == "PROBLEMS":
            for p in problems:
                href = f"problem-{p['slug']}.html"
                cls = " is-active" if href == active else ""
                hexc = COLOUR_HEX.get(p.get("colour", "grey"), "#6F7C89")
                out.append(
                    f'<a class="{cls.strip()}" href="{href}">'
                    f'<span class="n-id">{esc(p["id"])}</span>'
                    f'<span>{esc(p["short"])}</span>'
                    f'<span class="n-flag" style="background:{hexc}"></span></a>')
        else:
            for href, label, _ in items:
                cls = " is-active" if href == active else ""
                out.append(f'<a class="{cls.strip()}" href="{href}">{esc(label)}</a>')
        out.append("</div>")
    return "\n".join(out)


def page(active, title, eyebrow, heading, lede, body, D, wide=False):
    problems = D["problems"]
    urgent = sum(1 for p in problems if p["status"] == "active")
    meta = D["meta"]
    chip = ""
    if urgent:
        chip = (f'<a class="brand-chip" href="index.html#now"><span class="dot"></span>'
                f'{urgent} active</a>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(meta['site_title'])}</title>
<meta name="description" content="Veterinary health record for Gatsby, a Siberian cat in Zürich.">
<meta name="robots" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="data:image/svg+xml,&lt;svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'&gt;&lt;rect width='32' height='32' rx='7' fill='%23141A21'/&gt;&lt;text x='16' y='23' font-size='19' text-anchor='middle' fill='%23fff' font-family='Georgia,serif'&gt;G&lt;/text&gt;&lt;/svg&gt;">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>

<div class="topbar">
  <button class="tb-btn" id="navToggle" aria-label="Open navigation" aria-expanded="false">
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#3A4855" stroke-width="1.8" stroke-linecap="round"><path d="M2 4.5h14M2 9h14M2 13.5h14"/></svg>
  </button>
  <a class="tb-name" href="index.html">{esc(meta['site_title'])}</a>
  <span class="tb-page">{esc(eyebrow)}</span>
  <button class="tb-btn" id="searchToggleM" aria-label="Search">
    <svg width="17" height="17" viewBox="0 0 18 18" fill="none" stroke="#3A4855" stroke-width="1.8" stroke-linecap="round"><circle cx="8" cy="8" r="5.4"/><path d="M12 12l4 4"/></svg>
  </button>
</div>

<div class="scrim" id="scrim"></div>

<div class="shell">
  <aside class="sidebar">
    <div class="brand">
      <a class="brand-name" href="index.html">{esc(meta['site_title'])}</a>
      <span class="brand-sub">{esc(meta['site_subtitle'])}</span>
      {chip}
    </div>
    <div style="padding:14px 12px 0">
      <button class="searchbtn" id="searchToggle">
        <svg width="15" height="15" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="8" cy="8" r="5.4"/><path d="M12 12l4 4"/></svg>
        Search the record <kbd>/</kbd>
      </button>
    </div>
    <nav class="nav">{nav_html(active, problems)}</nav>
    <div class="sidebar-foot">
      Updated {fmt(meta['compiled'])}<br>
      Version {esc(meta['version'])}<br>
      <span style="color:#4E5A67">Generated from gatsby_data.yaml</span>
    </div>
  </aside>

  <main class="main" id="main">
    <div class="wrap">
      <header class="page-head">
        <div class="eyebrow">{esc(eyebrow)}</div>
        <h1>{heading}</h1>
        {f'<p class="lede">{lede}</p>' if lede else ''}
      </header>
      {body}
    </div>
  </main>
</div>

<div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-label="Search">
  <div class="sheet-bg" data-close></div>
  <div class="sheet-box">
    <div class="sheet-in">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="#6B7885" stroke-width="1.8" stroke-linecap="round"><circle cx="8" cy="8" r="5.4"/><path d="M12 12l4 4"/></svg>
      <input id="q" type="text" placeholder="Search events, drugs, findings, documents…" autocomplete="off" spellcheck="false">
      <button class="btn btn-ghost" data-close style="padding:5px 10px;font-size:12px">Esc</button>
    </div>
    <div class="sheet-res" id="res"></div>
  </div>
</div>

<div class="lb" id="lb" role="dialog" aria-modal="true" aria-label="Image viewer">
  <button class="lb-x" id="lbx" aria-label="Close">×</button>
  <img id="lbi" alt="">
  <div class="lb-cap" id="lbc"></div>
</div>

<script src="search.js"></script>
<script src="app.js"></script>
</body>
</html>"""


# ── components ───────────────────────────────────────────────────────────

def ev_problems(e):
    """A timeline event may belong to one problem or several."""
    v = e.get("problem")
    if not v:
        return []
    return v if isinstance(v, list) else [v]


def badge(status, label=None):
    cls = STATUS_BADGE.get(status, "b-grey")
    return f'<span class="badge {cls}"><span class="dot"></span>{esc(label or status)}</span>'


def img_url(f):
    return f"images/{f}"


def health_map(D):
    """Signature element: problem bands across a shared time axis."""
    tl = [e for e in D["timeline"] if to_date(e.get("date"))]
    dates = [to_date(e["date"]) for e in tl]
    lo, hi = date(2025, 4, 1), max(max(dates), date(2026, 9, 1))
    span = (hi - lo).days

    problems = D["problems"]
    row_h, top, left, right = 30, 34, 104, 14
    W, H = 860, top + row_h * len(problems) + 26
    plot = W - left - right

    def x(d):
        return left + plot * max(0.0, min(1.0, (d - lo).days / span))

    parts = [f'<svg class="healthmap" viewBox="0 0 {W} {H}" role="img" '
             f'aria-label="Timeline of active problem periods">']

    # month/quarter grid
    y, m = 2025, 4
    while date(y, m, 1) <= hi:
        d = date(y, m, 1)
        if d >= lo:
            px = x(d)
            parts.append(f'<line class="hm-grid" x1="{px:.1f}" y1="{top-14}" x2="{px:.1f}" y2="{H-20}"/>')
            if m in (1, 4, 7, 10):
                lab = f"{MONTHS[m-1]} {str(y)[2:]}"
                parts.append(f'<text x="{px+4:.1f}" y="{top-18}">{lab}</text>')
        m += 3
        if m > 12:
            m -= 12
            y += 1

    # today marker
    today = to_date(D["meta"]["compiled"])
    tx = x(today)
    parts.append(f'<line class="hm-today" x1="{tx:.1f}" y1="{top-14}" x2="{tx:.1f}" y2="{H-20}"/>')
    parts.append(f'<text x="{tx-4:.1f}" y="{H-6}" text-anchor="end" fill="#B33A34">today</text>')

    for i, p in enumerate(problems):
        yy = top + i * row_h
        hexc = COLOUR_HEX.get(p.get("colour", "grey"), "#6F7C89")
        parts.append(f'<text class="hm-name" x="0" y="{yy+13}">{esc(p["short"])}</text>')
        parts.append(f'<rect x="{left}" y="{yy+4}" width="{plot}" height="15" rx="3" fill="#EDF0F3"/>')

        ev = [e for e in tl if p["id"] in ev_problems(e)]
        evd = sorted(to_date(e["date"]) for e in ev)
        start = to_date(p.get("band_start")) or (evd[0] if evd else None)
        end = to_date(p.get("band_end")) or (evd[-1] if evd else None)

        if start:
            if p["status"] in ("active", "recurrent", "unresolved", "open"):
                end = max(end or today, today)
            x0 = x(start)
            x1 = max(x(end or start), x0 + 11)      # keep short bands visible
            op = ".92" if p["status"] == "active" else ".55"
            parts.append(f'<rect class="hm-band" x="{x0:.1f}" y="{yy+4}" width="{x1-x0:.1f}" '
                         f'height="15" rx="3" fill="{hexc}" fill-opacity="{op}"><title>'
                         f'{esc(p["title"])} — {esc(p["status_label"])}</title></rect>')
            for e in ev:
                px = x(to_date(e["date"]))
                parts.append(f'<circle class="hm-ev" cx="{px:.1f}" cy="{yy+11.5}" r="2.6" '
                             f'fill="#141A21" fill-opacity=".62"><title>'
                             f'{fmt(e["date"])} — {esc(e["title"])}</title></circle>')
        else:
            parts.append(f'<text x="{left+8}" y="{yy+15}" fill="#97A2AD">no dated events</text>')

    parts.append("</svg>")
    legend = ('<div class="map-legend">'
              '<span><i style="background:#B33A34"></i>Active</span>'
              '<span><i style="background:#9E6209"></i>Recurrent or unresolved</span>'
              '<span><i style="background:#24664A"></i>Treated or monitoring</span>'
              '<span><i style="background:#141A21;opacity:.6;width:8px;border-radius:50%"></i>Recorded event</span>'
              '</div>')
    return f'<div class="map-scroll">{"".join(parts)}</div>{legend}'


def weight_chart(D):
    ws = [w for w in D["weights"] if to_date(w.get("date"))]
    ws.sort(key=lambda w: to_date(w["date"]))
    if len(ws) < 2:
        return ""
    ds = [to_date(w["date"]) for w in ws]
    vs = [float(w["kg"]) for w in ws]
    lo_d, hi_d = ds[0], ds[-1]
    span = max((hi_d - lo_d).days, 1)
    lo_v, hi_v = min(vs) - .4, max(vs) + .4
    W, H, pl, pr, pt, pb = 860, 190, 44, 14, 18, 30
    pw, ph = W - pl - pr, H - pt - pb

    def X(d):
        return pl + pw * (d - lo_d).days / span

    def Y(v):
        return pt + ph * (1 - (v - lo_v) / (hi_v - lo_v))

    pts = [(X(d), Y(v)) for d, v in zip(ds, vs)]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area = line + f" L{pts[-1][0]:.1f},{pt+ph:.1f} L{pts[0][0]:.1f},{pt+ph:.1f} Z"

    g = [f'<svg class="wchart" viewBox="0 0 {W} {H}" role="img" aria-label="Weight over time">']
    for gv in [4.0, 4.5, 5.0, 5.5, 6.0]:
        if lo_v <= gv <= hi_v:
            yy = Y(gv)
            g.append(f'<line class="w-grid" x1="{pl}" y1="{yy:.1f}" x2="{W-pr}" y2="{yy:.1f}"/>')
            g.append(f'<text x="{pl-8}" y="{yy+3.5:.1f}" text-anchor="end">{gv:.1f}</text>')
    g.append(f'<path class="w-area" d="{area}"/>')
    g.append(f'<path class="w-line" d="{line}"/>')
    for (x, y), w, d in zip(pts, ws, ds):
        g.append(f'<circle class="w-dot" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>'
                 f'{fmt(d)} — {w["kg"]} kg</title></circle>')
    for d in (ds[0], ds[-1]):
        anchor = "start" if d == ds[0] else "end"
        g.append(f'<text x="{X(d):.1f}" y="{H-8}" text-anchor="{anchor}">{fmt(d, "short")}</text>')
    g.append("</svg>")
    return "".join(g)


def timeline_items(events, D, show_year=True):
    imgs = {i["id"]: i for i in D["images"]}
    out, year = [], None
    for e in events:
        d = to_date(e.get("date"))
        if show_year and d and d.year != year:
            year = d.year
            out.append(f'<div class="tl-year"><span>{year}</span></div>')
        cls = "tl-item"
        if e.get("milestone"):
            cls += " is-milestone"
        if e.get("alert"):
            cls += " is-alert"
        if e.get("scheduled"):
            cls += " is-sched"
        anchor = f'id="{d.isoformat()}"' if d else ""

        chips = []
        if e.get("tag"):
            chips.append(f'<span class="tag tag-{e["tag"]}">{e["tag"]}</span>')
        if e.get("source"):
            chips.append(f'<a class="srcref" href="documents.html#{e["source"]}">{e["source"]}</a>')
        if e.get("scheduled"):
            chips.append('<span class="badge b-blue"><span class="dot"></span>Scheduled</span>')

        thumbs = ""
        if e.get("images"):
            t = []
            for iid in e["images"]:
                im = imgs.get(iid)
                if im:
                    t.append(f'<img src="{img_url(im["file"])}" alt="{esc(im["region"])}" loading="lazy" '
                             f'data-zoom="{img_url(im["file"])}" '
                             f'data-cap="{esc(im["id"])} · {esc(im["region"])} · {fmt(im["date"])}">')
            if t:
                thumbs = f'<div class="tl-thumbs">{"".join(t)}</div>'

        meta = []
        if e.get("provider"):
            meta.append(f'<span class="tl-prov">{esc(e["provider"])}</span>')
        for pid in ev_problems(e):
            p = next((x for x in D["problems"] if x["id"] == pid), None)
            if p:
                meta.append(f'<a href="problem-{p["slug"]}.html">{esc(p["id"])} {esc(p["short"])}</a>')

        out.append(f"""<div class="{cls}" {anchor}>
  <div class="tl-date">{fmt(e.get("date"))} {"".join(chips)}</div>
  <div class="tl-title">{inline(e.get("title"))}</div>
  {f'<p class="tl-detail">{inline(e.get("detail"))}</p>' if e.get("detail") else ''}
  {f'<div class="tl-meta">{" · ".join(meta)}</div>' if meta else ''}
  {thumbs}
</div>""")
    return f'<div class="tl">{"".join(out)}</div>'


# ── pages ────────────────────────────────────────────────────────────────

def p_index(D):
    pt, meta = D["patient"], D["meta"]
    active = [p for p in D["problems"] if p["status"] == "active"]
    overdue = [r for r in D["recalls"] if r["status"] == "overdue"]
    sched = [r for r in D["recalls"] if r["status"] == "scheduled"]

    b = []

    if sched:
        s = sched[0]
        b.append(f"""<div class="alert alert-teal">
  <h3>Next appointment</h3>
  <p style="font-size:17px;margin-bottom:4px"><strong>{fmt(s['due'])}</strong> — {inline(s['item'])}</p>
  <p class="small mb0" style="color:var(--accent-deep)">Preparation checklist is on this page, below.</p>
</div>""")

    b.append(f"""<div class="stats">
  <div class="stat"><div class="stat-k">Age</div><div class="stat-v">4 <small>years</small></div></div>
  <div class="stat"><div class="stat-k">Weight</div><div class="stat-v">{pt['current_weight_kg']} <small>kg</small></div></div>
  <div class="stat"><div class="stat-k">Active problems</div><div class="stat-v">{len(active)}</div></div>
  <div class="stat"><div class="stat-k">Overdue</div><div class="stat-v">{len(overdue)}</div></div>
  <div class="stat"><div class="stat-k">Documents</div><div class="stat-v">{len(D['sources'])}</div></div>
</div>""")

    b.append(f"""<h2>Health map</h2>
<p class="muted small" style="margin-top:-6px;max-width:64ch">Each band shows the period over which
a problem has been under investigation or treatment. Dots are recorded events. The overlap is the
point: no single clinic has held the whole picture.</p>
<div class="card">{health_map(D)}</div>""")

    # active problems
    b.append('<h2 id="now">Active now</h2><div class="grid grid-2">')
    for p in active:
        b.append(f"""<div class="card">
  <div class="card-hd">
    <div style="flex:1">
      <div class="mono small muted">{esc(p['id'])}</div>
      <h3 style="margin:2px 0 0">{esc(p['title'])}</h3>
    </div>
    {badge(p['status'], p['status_label'])}
  </div>
  <p class="small muted mb0">Diagnosis: {esc(p['diagnosis'])}</p>
  <p style="margin-top:12px" class="mb0"><a href="problem-{p['slug']}.html">Open the full record →</a></p>
</div>""")
    b.append("</div>")

    # identity
    b.append(f"""<h2>Identity</h2>
<div class="card">
<dl class="kv">
  <dt>Name</dt><dd>{esc(pt['call_name'])} <span class="muted small">registered as {esc(pt['passport_name'])} in the passport</span></dd>
  <dt>Breed</dt><dd>{esc(pt['breed'])} · <span class="mono">{esc(pt['breed_code'])}</span> <span class="muted small">{esc(pt['breed_code_meaning'])}</span></dd>
  <dt>Sex</dt><dd>{esc(pt['sex'])} <span class="muted small">{fmt(pt['neutered_date'])}</span></dd>
  <dt>Born</dt><dd>{fmt(pt['dob'])}</dd>
  <dt>Microchip</dt><dd><span class="mono">{esc(pt['microchip'])}</span> <span class="muted small">{esc(pt['microchip_location'])}, {fmt(pt['microchip_date'])}</span></dd>
  <dt>Passport</dt><dd><span class="mono">{esc(pt['passport_no'])}</span> <span class="muted small">issued {fmt(pt['passport_issued'])}</span></dd>
  <dt>ANIS</dt><dd>Registered {fmt(pt['anis_registered'])}</dd>
  <dt>Housing</dt><dd>{esc(pt['housing'])}</dd>
  <dt>Owners</dt><dd>{esc(pt['owners'])} · {esc(pt['location'])}</dd>
  <dt>Origin</dt><dd>{esc(pt['origin_summary'])}</dd>
</dl>
</div>""")

    # critical background
    b.append("""<h2>What a new vet needs to know first</h2>""")
    b.append(f"""<div class="card">
<ul style="margin:0;padding-left:18px;line-height:1.75">
  <li><strong>August 2025 — severe deep infection of the left forelimb.</strong> Septic arthritis of MCP joint IV, tendovaginitis of the deep digital flexor tendon, phlegmon, polyostotic osteomyelitis. Resolved on four weeks of amoxicillin-clavulanate. <strong>No foreign body was ever found.</strong> <a class="srcref" href="documents.html#S2">S2</a></li>
  <li><strong>September 2025 — pustules and crusts on both ear margins with generalised itching.</strong> The recommended dermatology workup was <strong>never carried out</strong>. <a class="srcref" href="documents.html#S4">S4</a></li>
  <li><strong>October 2025 — heart structurally and functionally normal</strong>, sinus arrhythmia only. Fit for anaesthesia at that time. <a class="srcref" href="documents.html#S5">S5</a></li>
  <li><strong>August 2025 — creatinine mildly elevated at 171 µmol/l.</strong> The recommended recheck was never done. <a class="srcref" href="documents.html#S2">S2</a></li>
  <li><strong>FeLV / FIV — never tested</strong> in four years. Testing scheduled for 17 August 2026.</li>
  <li><strong>Rabies vaccination lapsed 3 April 2026.</strong></li>
</ul>
</div>""")

    # drug responses + anaesthesia
    rows = "".join(
        f"<tr><td><strong>{esc(m['drug'])}</strong><div class='muted small'>{esc(m['generic'])}</div></td>"
        f"<td>{inline(m['response'])}</td></tr>"
        for m in D["medications_past"] if m.get("key") or m["drug"].startswith(("Onsior", "Apoquel", "Inflacam")))
    b.append(f"""<h2>Known drug responses</h2>
<div class="tbl-scroll"><table><thead><tr><th>Drug</th><th>Response</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small muted" style="margin-top:10px">Full register on the <a href="medications.html">medications page</a>.</p>""")

    an = "".join(f"<li>{fmt(a['date'])} — {esc(a['procedure'])} <span class='muted small'>({esc(a['provider'])})</span></li>"
                 for a in D["anaesthesia"])
    b.append(f"""<h2>Anaesthesia history</h2>
<div class="card"><ul style="margin:0;padding-left:18px;line-height:1.8">{an}</ul>
<p class="small muted" style="margin-top:12px" >No known drug reactions or anaesthetic complications to date.
<a href="anaesthesia.html">Full anaesthesia record →</a></p></div>""")

    # urgent checklist
    items = "".join(f"<li>{markdown(a['text'])}</li>" for a in D["actions_urgent"])
    b.append(f"""<h2>Before Monday's appointment</h2>
<div class="card"><ul class="checklist">{items}</ul></div>""")

    if overdue:
        rows = "".join(f"<tr><td class='mono'>{fmt(r['due'])}</td><td>{inline(r['item'])}</td>"
                       f"<td>{badge(r['status'])}</td></tr>" for r in overdue)
        b.append(f"""<h2>Overdue</h2>
<div class="tbl-scroll"><table><thead><tr><th>Was due</th><th>Item</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div>""")

    b.append(f"""<h2>Baseline for him personally</h2>
<div class="card"><dl class="kv">
{"".join(f"<dt>{esc(x['label'])}</dt><dd class='mono'>{esc(x['value'])}</dd>" for x in D['baseline'])}
</dl>
<p class="small muted" style="margin-top:14px;margin-bottom:0">{esc(D['temperament'])}</p></div>""")

    b.append("""<hr class="sep">
<p class="small muted">Evidence tags used throughout:
<span class="tag tag-V">V</span> from a veterinary document ·
<span class="tag tag-O">O</span> owner observation ·
<span class="tag tag-I">I</span> inference, not a diagnosis ·
<span class="tag tag-Q">Q</span> unverified or contradicted.</p>""")

    return page("index.html", "At a glance", "At a glance",
                f"{esc(D['patient']['call_name'])}",
                f"Siberian cat, born {fmt(D['patient']['dob'])}. "
                f"Health record assembled from {len(D['sources'])} veterinary documents and "
                f"{len(D['images'])} images across seven practices in four countries.",
                "\n".join(b), D)


def p_timeline(D):
    ev = sorted(D["timeline"], key=lambda e: (to_date(e["date"]) or date(1900, 1, 1)))
    b = [f'<div class="card card-tight"><div class="row"><span class="mono small muted">'
         f'{len(ev)} recorded events · {fmt(ev[0]["date"], "short")} to {fmt(ev[-1]["date"], "short")}</span>'
         f'<a class="btn btn-ghost" href="observations.html" style="margin-left:auto">Record an observation</a></div></div>']
    b.append(timeline_items(ev, D))
    return page("timeline.html", "Timeline", "Timeline", "Everything, in order",
                "Every dated event from every source, with links back to the original document.",
                "\n".join(b), D)


def p_problem(D, p):
    ev = sorted([e for e in D["timeline"] if p["id"] in ev_problems(e)],
                key=lambda e: to_date(e["date"]) or date(1900, 1, 1))
    imgs = [i for i in D["images"]
            if any(i["id"] in (e.get("images") or []) for e in ev)]

    b = [f"""<div class="card card-tight">
<dl class="kv">
  <dt>Status</dt><dd>{badge(p['status'], p['status_label'])}</dd>
  <dt>Onset</dt><dd>{fmt(p['onset'])}</dd>
  <dt>Diagnosis</dt><dd>{esc(p['diagnosis'])}</dd>
</dl></div>"""]

    b.append(f'<div class="prose">{markdown(p["body"])}</div>')

    if ev:
        b.append("<h2>Events</h2>")
        b.append(timeline_items(ev, D, show_year=True))

    if imgs:
        b.append("<h2>Imaging</h2><div class='gallery'>")
        for i in imgs:
            b.append(shot(i))
        b.append("</div>")

    return page(f"problem-{p['slug']}.html", p["title"], f"Problem {p['id']}",
                esc(p["title"]), None, "\n".join(b), D)


def shot(i):
    return f"""<div class="shot" data-kind="{esc(i['kind'])}">
  <button data-zoom="{img_url(i['file'])}" data-cap="{esc(i['id'])} · {esc(i['region'])} · {esc(i['view'])} · {fmt(i['date'])}">
    <img src="{img_url(i['file'])}" alt="{esc(i['region'])}, {esc(i['view'])}" loading="lazy">
  </button>
  <div class="shot-cap">
    <div class="shot-id">{esc(i['id'])}</div>
    <div class="shot-t">{esc(i['region'])}</div>
    <div class="shot-m">{esc(i['view'])} · {fmt(i['date'], 'short')}</div>
  </div>
</div>"""


def p_images(D):
    kinds = [("all", "All"), ("xray", "Radiographs"), ("dental", "Dental"), ("clinical", "Clinical photos")]
    chips = "".join(f'<button class="chip{" is-on" if k == "all" else ""}" data-filter="{k}">{esc(l)}</button>'
                    for k, l in kinds)
    notes = [i for i in D["images"] if i.get("note")]
    b = [f'<div class="filters">{chips}</div>',
         f'<div class="gallery" id="gal">{"".join(shot(i) for i in D["images"])}</div>']
    if notes:
        b.append("<h2>Annotations</h2>")
        for i in notes:
            b.append(f'<div class="card card-tight"><div class="row" style="align-items:flex-start">'
                     f'<span class="doc-id">{esc(i["id"])}</span>'
                     f'<div style="flex:1"><strong>{esc(i["region"])} — {esc(i["view"])}</strong>'
                     f'<p class="small mb0" style="margin-top:4px">{inline(i["note"])}</p></div></div></div>')
    b.append("""<h2>Not held</h2>
<div class="card"><ul style="margin:0;padding-left:18px;line-height:1.8">
<li><strong>CT study, 25–26 August 2025, Tierspital</strong> — written report only, no images</li>
<li><strong>Ultrasound study, 25–26 August 2025, Tierspital</strong> — written report only</li>
<li><strong>Echocardiogram and ECG traces, 2 October 2025</strong> — measurements only</li>
</ul></div>""")
    return page("images.html", "Images", "Archive", "Images",
                f"{len(D['images'])} radiographs and clinical photographs. Tap any image to enlarge.",
                "\n".join(b), D)


def p_documents(D):
    b = []
    have = 0
    for s in D["sources"]:
        f = s.get("file")
        exists = bool(f) and (ROOT / "sources" / f).exists()
        if exists:
            have += 1
            act = f'<a class="btn btn-primary" href="sources/{esc(f)}" target="_blank" rel="noopener">Open PDF</a>'
        elif f:
            act = '<span class="btn btn-pending">Not yet uploaded</span>'
        else:
            act = '<span class="btn btn-pending">No file</span>'

        meta = [fmt(s["date"], "short") if not isinstance(s["date"], str) else esc(s["date"])]
        if s.get("lang"):
            meta.append(esc(s["lang"]))
        if s.get("pages"):
            meta.append(f'{s["pages"]} pp')
        sup = ' <span class="badge b-grey"><span class="dot"></span>Superseded</span>' if s.get("superseded") else ""

        b.append(f"""<div class="doc" id="{esc(s['id'])}">
  <span class="doc-id">{esc(s['id'])}</span>
  <div class="doc-body">
    <p class="doc-title">{esc(s['title'])}{sup}</p>
    <div class="doc-meta"><span>{" · ".join(meta)}</span></div>
    <div class="small muted" style="margin-top:4px">{esc(s['author'])}</div>
    {f'<div class="mono small muted" style="margin-top:4px;opacity:.7">sources/{esc(f)}</div>' if f else ''}
  </div>
  <div class="doc-act">{act}</div>
</div>""")

    head = ""
    if have < len([s for s in D["sources"] if s.get("file")]):
        head = f"""<div class="alert alert-amber">
<h3>Some documents are not yet published</h3>
<p class="mb0">{have} of {len([s for s in D['sources'] if s.get('file')])} PDFs are in the repository.
To add one, drop the redacted file into <code>sources/</code> using the exact filename shown below it,
then push. The link appears on its own — nothing else needs changing.</p></div>"""

    body = head + f'<div class="card">{"".join(b)}</div>'

    body += """<h2>Records still to obtain</h2>"""
    rows = "".join(f"<tr><td>{badge('overdue' if r['priority']=='High' else ('due' if r['priority']=='Medium' else 'future'), r['priority'])}</td>"
                   f"<td>{inline(r['item'])}</td><td class='small muted'>{esc(r['who'])}</td></tr>"
                   for r in D["records_wanted"])
    body += f'<div class="tbl-scroll"><table><thead><tr><th>Priority</th><th>Document</th><th>From</th></tr></thead><tbody>{rows}</tbody></table></div>'

    return page("documents.html", "Documents", "Archive", "Documents",
                "Every primary source. Each has a permanent link that can be sent to a vet directly.",
                body, D)


def p_medications(D):
    b = []
    if D["medications_current"]:
        rows = "".join(f"<tr><td><strong>{esc(m['drug'])}</strong></td><td>{esc(m['dose'])}</td>"
                       f"<td>{esc(m['route'])}</td><td>{esc(m['indication'])}</td></tr>"
                       for m in D["medications_current"])
        b.append(f'<h2>Current</h2><div class="tbl-scroll"><table><thead><tr><th>Drug</th><th>Dose</th>'
                 f'<th>Route</th><th>For</th></tr></thead><tbody>{rows}</tbody></table></div>')
    else:
        b.append("""<div class="alert alert-teal"><h3>No current medication</h3>
<p class="mb0">Nothing on record as of 13 August 2026.</p></div>""")

    rows = []
    for m in sorted(D["medications_past"], key=lambda m: to_date(m["start"]) or date(1900, 1, 1), reverse=True):
        per = fmt(m["start"], "short")
        if m.get("end"):
            per += f' – {fmt(m["end"], "short")}'
        key = ' <span class="badge b-green"><span class="dot"></span>Key</span>' if m.get("key") else ""
        rows.append(f"""<tr>
  <td class="mono small" style="white-space:nowrap">{per}</td>
  <td><strong>{esc(m['drug'])}</strong>{key}<div class="muted small">{esc(m['generic'])}</div></td>
  <td class="small">{esc(m['dose'])}<div class="muted">{esc(m['route'])}</div></td>
  <td class="small">{esc(m['indication'])}</td>
  <td class="small">{inline(m['response'])}</td>
  <td>{f'<a class="srcref" href="documents.html#{m["source"]}">{m["source"]}</a>' if m.get('source') else ''}</td>
</tr>""")
    b.append(f"""<h2>Everything he has been given</h2>
<div class="tbl-scroll"><table><thead><tr><th>Period</th><th>Drug</th><th>Dose</th>
<th>For</th><th>Response</th><th>Src</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>""")

    for n in D["medication_notes"]:
        b.append(f'<div class="alert alert-amber" style="margin-top:18px">{markdown(n)}</div>')

    return page("medications.html", "Medications", "Clinical", "Medications",
                "Every drug on record, with the observed response where one was documented.",
                "\n".join(b), D)


def p_labs(D):
    b = []
    for panel in D["labs"]:
        rows = []
        for r in panel["results"]:
            v, lo, hi = r["value"], r.get("low"), r.get("high")
            cls, track = "", '<div class="track"></div>'
            if lo is not None or hi is not None:
                l = lo if lo is not None else (hi * .5)
                h = hi if hi is not None else (lo * 1.5)
                pad = (h - l) * .85 or 1
                a, bb = l - pad, h + pad
                a, bb = min(a, v - pad * .15), max(bb, v + pad * .15)
                sp = bb - a or 1
                rl, rw = (l - a) / sp * 100, (h - l) / sp * 100
                mk = (v - a) / sp * 100
                if hi is not None and v > hi:
                    cls = "lab-hi"
                elif lo is not None and v < lo:
                    cls = "lab-lo"
                track = (f'<div class="track"><div class="track-line"></div>'
                         f'<div class="track-ref" style="left:{rl:.1f}%;width:{rw:.1f}%"></div>'
                         f'<div class="track-mark" style="left:calc({mk:.1f}% - 1.5px)"></div></div>')
            if lo is None and hi is None:
                refline = "no reference interval"
            elif lo is None:
                refline = f"ref &lt; {hi} {esc(r['unit'])}"
            elif hi is None:
                refline = f"ref &gt; {lo} {esc(r['unit'])}"
            else:
                refline = f"ref {lo}–{hi} {esc(r['unit'])}"
            rows.append(f"""<div class="lab-row {cls}">
  <div class="lab-name">{esc(r['name'])}<div class="muted mono" style="font-size:10.5px">{refline}</div></div>
  <div class="lab-val">{v} <small>{esc(r['unit'])}</small></div>
  {track}
</div>""")
        note = f'<p class="small muted" style="margin-top:16px">{esc(panel.get("note",""))}</p>' if panel.get("note") else ""
        b.append(f"""<h2>{esc(panel['panel'])} — {fmt(panel['date'])}</h2>
<div class="card">
  <div class="row" style="margin-bottom:14px"><span class="mono small muted">{esc(panel['provider'])}</span>
  <a class="srcref" href="documents.html#{panel['source']}" style="margin-left:auto">{panel['source']}</a></div>
  {"".join(rows)}
  {note}
</div>""")

    if D.get("labs_scheduled"):
        rows = "".join(f"<tr><td class='mono'>{fmt(s['date'])}</td><td>{esc(s['tests'])}</td>"
                       f"<td class='small muted'>{esc(s['provider'])}</td></tr>" for s in D["labs_scheduled"])
        b.append(f'<h2>Scheduled</h2><div class="tbl-scroll"><table><thead><tr><th>Date</th>'
                 f'<th>Tests</th><th>Provider</th></tr></thead><tbody>{rows}</tbody></table></div>')

    li = "".join(f"<li>{esc(x)}</li>" for x in D["labs_never_done"])
    b.append(f"""<h2>Never done</h2><div class="alert alert-amber">
<ul style="margin:0;padding-left:18px;line-height:1.8">{li}</ul></div>""")

    return page("labs.html", "Lab results", "Clinical", "Lab results",
                "Values against their reference intervals. The bar shows where each result falls.",
                "\n".join(b), D)


def p_preventive(D):
    b = []
    rows = "".join(
        f"<tr><td class='mono' style='white-space:nowrap'>{fmt(v['date'],'short')}</td>"
        f"<td><strong>{esc(v['vaccine'])}</strong><div class='muted small'>{esc(v['type'])}</div></td>"
        f"<td class='mono small'>{esc(v.get('batch') or '—')}</td>"
        f"<td class='mono small'>{fmt(v['valid_until'],'short') if v.get('valid_until') else '—'}</td>"
        f"<td class='small muted'>{esc(v['by'])}</td></tr>" for v in D["vaccinations"])
    b.append(f"""<div class="alert alert-red"><h3>Rabies cover lapsed</h3>
<p class="mb0">The last rabies vaccination expired on <strong>3 April 2026</strong>. For an indoor-only
cat in Switzerland this carries no direct disease risk, but it blocks travel and some boarding
facilities require it.</p></div>
<h2>Vaccinations</h2>
<div class="tbl-scroll"><table><thead><tr><th>Date</th><th>Vaccine</th><th>Batch</th>
<th>Valid until</th><th>Given by</th></tr></thead><tbody>{rows}</tbody></table></div>""")

    rows = "".join(f"<tr><td class='mono' style='white-space:nowrap'>{fmt(p['date'],'short')}</td>"
                   f"<td>{esc(p['product'])}</td><td class='small muted'>{esc(p['purpose'])}</td></tr>"
                   for p in D["parasite_control"])
    b.append(f"""<h2>Parasite control</h2>
<div class="tbl-scroll"><table><thead><tr><th>Date</th><th>Product</th><th>Purpose</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="small muted" style="margin-top:10px">{esc(D['parasite_note'])}</p>""")

    b.append(f"""<h2>Weight</h2><div class="card">{weight_chart(D)}
<p class="small muted" style="margin-top:10px;margin-bottom:0">{esc(D['weight_note'])}</p></div>""")

    rows = "".join(f"<tr><td class='mono' style='white-space:nowrap'>{fmt(r['due'],'short')}</td>"
                   f"<td>{inline(r['item'])}</td><td>{badge(r['status'])}</td></tr>"
                   for r in sorted(D["recalls"], key=lambda r: to_date(r["due"]) or date(2100, 1, 1)))
    b.append(f"""<h2>Recall schedule</h2>
<div class="tbl-scroll"><table><thead><tr><th>Due</th><th>Item</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div>""")

    rows = "".join(f"<tr><td><strong>{esc(r['condition'])}</strong></td><td class='small'>{esc(r['relevance'])}</td>"
                   f"<td class='small'>{esc(r['status'])}</td></tr>" for r in D["breed_risks"])
    b.append(f"""<h2>Breed risk — Siberian</h2>
<div class="tbl-scroll"><table><thead><tr><th>Condition</th><th>Relevance</th><th>Status</th></tr></thead>
<tbody>{rows}</tbody></table></div>""")

    return page("preventive.html", "Preventive care", "Clinical", "Preventive care",
                "Vaccinations, parasite control, weight, and what falls due when.", "\n".join(b), D)


def p_anaesthesia(D):
    rows = "".join(
        f"<tr><td class='mono' style='white-space:nowrap'>{fmt(a['date'],'short')}</td>"
        f"<td>{esc(a['procedure'])}</td><td class='small muted'>{esc(a['provider'])}</td>"
        f"<td class='small'>{esc(a['protocol'])}</td><td class='small'>{esc(a['complications'])}</td></tr>"
        for a in D["anaesthesia"])
    notes = "".join(f"<li>{inline(n)}</li>" for n in D["anaesthesia_notes"])
    b = f"""<div class="tbl-scroll"><table><thead><tr><th>Date</th><th>Procedure</th><th>Provider</th>
<th>Protocol</th><th>Complications</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>For the anaesthetist</h2>
<div class="alert alert-teal"><ul style="margin:0;padding-left:18px;line-height:1.8">{notes}</ul></div>"""
    return page("anaesthesia.html", "Anaesthesia", "Clinical", "Anaesthesia record",
                "Four general anaesthetics on record. Protocols were not supplied by the practices.",
                b, D)


def p_care_team(D):
    b = []
    for c in D["care_team"]:
        cur = ' <span class="badge b-green"><span class="dot"></span>Current</span>' if c.get("current") else ""
        b.append(f"""<div class="doc">
  <div class="doc-body">
    <p class="doc-title">{esc(c['name'])}{cur}</p>
    <div class="small" style="margin-bottom:3px">{esc(c['people'])}</div>
    <div class="small muted">{esc(c['role'])}</div>
    <div class="doc-meta" style="margin-top:6px"><span>{esc(c['period'])}</span><span>{esc(c['contact'])}</span></div>
  </div>
</div>""")
    return page("care-team.html", "Care team", "Archive", "Care team",
                "Seven practices in four countries. No one of them has held the whole record.",
                f'<div class="card">{"".join(b)}</div>', D)


def p_reference(D):
    b = []
    b.append("<h2>Observations from assembling the record</h2>")
    b.append('<p class="muted small" style="margin-top:-6px;max-width:64ch">These are inferences '
             '<span class="tag tag-I">I</span>, not diagnoses. They are material for a veterinarian '
             'to consider, not conclusions to act on.</p>')
    for a in D["analysis"]:
        b.append(f'<div class="card"><h3 style="margin-top:0">{esc(a["title"])}</h3>'
                 f'<div class="prose">{markdown(a["body"])}</div></div>')

    rows = "".join(f"<tr><td><strong>{inline(s['claim'])}</strong></td><td class='small muted'>{esc(s['origin'])}</td>"
                   f"<td class='small'>{esc(s['correction'])}</td></tr>" for s in D["superseded"])
    b.append(f"""<h2>Superseded — do not act on</h2>
<p class="muted small" style="margin-top:-6px;max-width:64ch">Kept so that old claims can be recognised
and dismissed if they resurface in someone's notes.</p>
<div class="tbl-scroll"><table><thead><tr><th>Claim</th><th>Where it came from</th>
<th>What actually applies</th></tr></thead><tbody>{rows}</tbody></table></div>""")

    li = "".join(f"<li>{esc(f)}</li>" for f in D["facts_missing"])
    b.append(f"""<h2>Still unknown</h2><div class="card">
<ul style="margin:0;padding-left:18px;line-height:1.8">{li}</ul></div>""")

    rows = "".join(f"<tr><td class='mono small'>{esc(g['de'])}</td><td>{esc(g['en'])}</td></tr>"
                   for g in D["glossary"])
    b.append(f"""<h2>German to English</h2>
<p class="muted small" style="margin-top:-6px">Most of the source documents are in German.</p>
<div class="tbl-scroll"><table><thead><tr><th>German / Latin</th><th>English</th></tr></thead>
<tbody>{rows}</tbody></table></div>""")

    rows = "".join(f"<tr><td class='mono'>{esc(c['version'])}</td><td class='mono small'>{fmt(c['date'],'short')}</td>"
                   f"<td class='small'>{esc(c['change'])}</td></tr>" for c in D["changelog"])
    b.append(f"""<h2>Changelog</h2>
<div class="tbl-scroll"><table><thead><tr><th>Version</th><th>Date</th><th>Change</th></tr></thead>
<tbody>{rows}</tbody></table></div>""")

    return page("reference.html", "Notes & glossary", "Archive", "Notes & glossary",
                "Analysis, corrections, unknowns, and a German–English glossary for the source documents.",
                "\n".join(b), D)


def p_observations(D):
    obs = sorted(D.get("observations") or [],
                 key=lambda o: str(o.get("datetime") or o.get("date") or ""), reverse=True)

    if obs:
        items = []
        for o in obs:
            bits = []
            if o.get('severity'):
                bits.append(f"Severity: {esc(o['severity'])}")
            if o.get('body_part'):
                bits.append(f"Body part: {esc(o['body_part'])}")
            if o.get('vet_contacted'):
                bits.append(f"Vet contacted: {esc(o['vet_contacted'])}")
            if o.get('issue'):
                bits.append(f"Issue #{esc(o['issue'])}")
            meta = " · ".join(bits)
            photos = ""
            if o.get('photos'):
                photos = ('<div class="tl-thumbs">' + "".join(
                    f'<img src="{esc(u)}" alt="Observation photo" loading="lazy" '
                    f'data-zoom="{esc(u)}" data-cap="{esc(o.get("title",""))}">'
                    for u in o['photos']) + '</div>')
            items.append(f"""<div class="tl-item">
  <div class="tl-date">{esc(o.get('datetime') or o.get('date'))}
    <span class="tag tag-O">O</span>
    {badge('scheduled', o.get('category','—'))}</div>
  <div class="tl-title">{inline(o.get('title',''))}</div>
  <p class="tl-detail">{inline(o.get('detail',''))}</p>
  <div class="tl-meta">{meta}</div>
  {photos}
</div>""")
        log = f'<h2>Log</h2><div class="tl">{"".join(items)}</div>'
    else:
        log = """<div class="empty">
  <p class="empty-t">No observations logged yet</p>
  <p class="empty-d">Record the first sign of anything — a limp, a change in appetite, a new spot —
  and it lands in the timeline with a timestamp.</p>
</div>"""

    composer = """<h2>Record an observation</h2>
<div class="card">
  <p class="hint" style="margin-top:0">Fill this in, then either open a GitHub issue with one tap
  (fastest, from the phone) or copy the block and paste it into <code>data/gatsby_data.yaml</code>.</p>

  <div class="form-2">
    <div class="form-row"><label for="oDate">Date</label><input type="date" id="oDate"></div>
    <div class="form-row"><label for="oTime">Time</label><input type="time" id="oTime"></div>
  </div>
  <div class="form-2">
    <div class="form-row"><label for="oCat">Category</label>
      <select id="oCat">
        <option>Lameness</option><option>Skin or coat</option><option>Oral or tongue</option>
        <option>Paws</option><option>Appetite or drinking</option><option>Litter tray</option>
        <option>Breathing</option><option>Behaviour</option><option>Weight</option><option>Other</option>
      </select></div>
    <div class="form-row"><label for="oSev">Severity</label>
      <select id="oSev"><option>Mild</option><option>Moderate</option><option>Marked</option></select></div>
  </div>
  <div class="form-row"><label for="oPart">Body part <span style="text-transform:none;letter-spacing:0">(optional)</span></label>
    <input type="text" id="oPart" placeholder="e.g. left front paw"></div>
  <div class="form-row"><label for="oTitle">One-line summary</label>
    <input type="text" id="oTitle" placeholder="e.g. Slight limp on the left front leg after jumping down"></div>
  <div class="form-row"><label for="oDetail">What you saw</label>
    <textarea id="oDetail" placeholder="What it looked like, how long it lasted, what he was doing beforehand, anything that made it better or worse."></textarea></div>
  <div class="form-row"><label for="oVet">Vet contacted</label>
    <select id="oVet"><option>No</option><option>Yes — appointment booked</option><option>Yes — advice by phone</option></select></div>

  <h3>Generated entry</h3>
  <pre class="out" id="oOut">Fill in the fields above.</pre>
  <div class="row">
    <button class="btn btn-primary" id="oCopy">Copy YAML</button>
    <a class="btn btn-ghost" id="oIssue" href="#" target="_blank" rel="noopener">Open a GitHub issue</a>
  </div>
  <p class="hint" style="margin-top:14px;margin-bottom:0">Paste the copied block under
  <code>observations:</code> in <code>data/gatsby_data.yaml</code>, keeping newest at the top.
  Push, and the site rebuilds itself.</p>
</div>"""

    return page("observations.html", "Observations", "Record", "Observations",
                "Your own log between veterinary visits. The first sign of something is often the "
                "most useful thing in a record — this is where it goes.",
                log + composer, D)


def p_print(D):
    """One flat page, print-optimised, for handing over in a consultation."""
    pt = D["patient"]
    ev = sorted(D["timeline"], key=lambda e: to_date(e["date"]) or date(1900, 1, 1))
    b = []

    b.append(f"""<div class="card">
<dl class="kv">
  <dt>Name</dt><dd>{esc(pt['call_name'])} (passport: {esc(pt['passport_name'])})</dd>
  <dt>Breed</dt><dd>{esc(pt['breed'])}, {esc(pt['breed_code'])}</dd>
  <dt>Sex</dt><dd>{esc(pt['sex'])}, {fmt(pt['neutered_date'])}</dd>
  <dt>Born</dt><dd>{fmt(pt['dob'])}</dd>
  <dt>Microchip</dt><dd class="mono">{esc(pt['microchip'])}</dd>
  <dt>Passport</dt><dd class="mono">{esc(pt['passport_no'])}</dd>
  <dt>Weight</dt><dd>{pt['current_weight_kg']} kg ({fmt(pt['current_weight_date'],'short')})</dd>
  <dt>Housing</dt><dd>{esc(pt['housing'])}</dd>
  <dt>Owners</dt><dd>{esc(pt['owners'])}, {esc(pt['location'])}</dd>
  <dt>Origin</dt><dd>{esc(pt['origin_summary'])}</dd>
</dl></div>""")

    b.append("<h2>Problem list</h2>")
    rows = "".join(
        f"<tr><td class='mono'>{esc(p['id'])}</td><td><strong>{esc(p['title'])}</strong></td>"
        f"<td>{esc(p['status_label'])}</td><td class='small'>{esc(p['diagnosis'])}</td></tr>"
        for p in D["problems"])
    b.append(f'<div class="tbl-scroll"><table><thead><tr><th>ID</th><th>Problem</th>'
             f'<th>Status</th><th>Diagnosis</th></tr></thead><tbody>{rows}</tbody></table></div>')

    b.append("<h2>Critical background</h2>")
    b.append("""<div class="card"><ul style="margin:0;padding-left:18px;line-height:1.7">
<li><strong>Aug 2025:</strong> septic arthritis of MCP joint IV, tendovaginitis of the deep digital
flexor tendon, phlegmon, polyostotic osteomyelitis, left forelimb. Resolved on four weeks of
amoxicillin-clavulanate. No foreign body found.</li>
<li><strong>Sep 2025:</strong> pustules and crusts on both ear margins with generalised pruritus.
Dermatology workup requested but never carried out.</li>
<li><strong>Oct 2025:</strong> echocardiogram normal; sinus arrhythmia only.</li>
<li><strong>Aug 2025:</strong> creatinine 171 µmol/l (ref 98–163). Recheck recommended, never done.</li>
<li><strong>FeLV / FIV never tested.</strong> Rabies vaccination lapsed 3 April 2026.</li>
<li>No complete blood count has ever been performed.</li>
</ul></div>""")

    b.append("<h2>Full timeline</h2>")
    b.append(timeline_items(ev, D))

    b.append("<h2>Medication history</h2>")
    rows = "".join(
        f"<tr><td class='mono small'>{fmt(m['start'],'short')}</td><td>{esc(m['drug'])}"
        f"<div class='muted small'>{esc(m['generic'])}</div></td><td class='small'>{esc(m['dose'])}, {esc(m['route'])}</td>"
        f"<td class='small'>{esc(m['indication'])}</td><td class='small'>{strip_tags(inline(m['response']))}</td></tr>"
        for m in sorted(D["medications_past"], key=lambda m: to_date(m["start"]) or date(1900, 1, 1)))
    b.append(f'<div class="tbl-scroll"><table><thead><tr><th>Start</th><th>Drug</th><th>Dose</th>'
             f'<th>For</th><th>Response</th></tr></thead><tbody>{rows}</tbody></table></div>')

    for panel in D["labs"]:
        b.append(f"<h2>{esc(panel['panel'])} — {fmt(panel['date'])}</h2>")
        rows = []
        for r in panel["results"]:
            v, lo, hi = r["value"], r.get("low"), r.get("high")
            flag = ""
            if hi is not None and v > hi:
                flag = "HIGH"
            elif lo is not None and v < lo:
                flag = "LOW"
            ref = "—" if lo is None and hi is None else f"{lo if lo is not None else ''}–{hi if hi is not None else ''}"
            rows.append(f"<tr><td>{esc(r['name'])}</td><td class='mono'>{v} {esc(r['unit'])}</td>"
                        f"<td class='mono small muted'>{ref}</td><td class='mono small'>{flag}</td></tr>")
        b.append(f'<div class="tbl-scroll"><table><thead><tr><th>Parameter</th><th>Result</th>'
                 f'<th>Reference</th><th>Flag</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')

    b.append("<h2>Vaccinations</h2>")
    rows = "".join(f"<tr><td class='mono small'>{fmt(v['date'],'short')}</td><td>{esc(v['vaccine'])}</td>"
                   f"<td class='small'>{esc(v['type'])}</td>"
                   f"<td class='mono small'>{fmt(v['valid_until'],'short') if v.get('valid_until') else '—'}</td></tr>"
                   for v in D["vaccinations"])
    b.append(f'<div class="tbl-scroll"><table><thead><tr><th>Date</th><th>Vaccine</th><th>Type</th>'
             f'<th>Valid until</th></tr></thead><tbody>{rows}</tbody></table></div>')

    b.append("<h2>Anaesthesia</h2>")
    rows = "".join(f"<tr><td class='mono small'>{fmt(a['date'],'short')}</td><td>{esc(a['procedure'])}</td>"
                   f"<td class='small'>{esc(a['provider'])}</td><td class='small'>{esc(a['complications'])}</td></tr>"
                   for a in D["anaesthesia"])
    b.append(f'<div class="tbl-scroll"><table><thead><tr><th>Date</th><th>Procedure</th>'
             f'<th>Provider</th><th>Complications</th></tr></thead><tbody>{rows}</tbody></table></div>')

    b.append("<h2>Source documents</h2>")
    rows = "".join(f"<tr><td class='mono'>{esc(s['id'])}</td><td>{esc(s['title'])}</td>"
                   f"<td class='small muted'>{esc(s['author'])}</td></tr>" for s in D["sources"])
    b.append(f'<div class="tbl-scroll"><table><thead><tr><th>ID</th><th>Document</th>'
             f'<th>Author</th></tr></thead><tbody>{rows}</tbody></table></div>')

    head = ('<div class="no-print" style="margin-bottom:22px">'
            '<button class="btn btn-primary" onclick="window.print()">Print or save as PDF</button> '
            '<a class="btn btn-ghost" href="index.html">Back to the record</a></div>')

    return page("print.html", "Full record", "Print", "Complete record",
                f"Everything on one page, formatted for print. Generated {fmt(D['meta']['compiled'])}.",
                head + "\n".join(b), D)


# ── search index ─────────────────────────────────────────────────────────

def build_index(D):
    idx = []

    def add(kind, title, detail, url):
        idx.append({"k": kind, "t": strip_tags(str(title))[:150],
                    "d": strip_tags(str(detail or ""))[:220], "u": url})

    for p in D["problems"]:
        add("Problem " + p["id"], p["title"], f'{p["status_label"]} · {p["diagnosis"]}',
            f'problem-{p["slug"]}.html')
        for line in re.split(r"\n#{2,3} ", p["body"]):
            head = demark(line.split("\n")[0])[:72]
            if len(line) > 120 and head:
                add("Problem " + p["id"], f'{p["short"]} — {head}',
                    strip_tags(markdown(line))[:200], f'problem-{p["slug"]}.html')

    for e in D["timeline"]:
        d = to_date(e.get("date"))
        add("Timeline", f'{fmt(e.get("date"),"short")} — {e["title"]}', e.get("detail"),
            f'timeline.html#{d.isoformat()}' if d else "timeline.html")

    for m in D["medications_past"] + D["medications_current"]:
        add("Medication", m["drug"], f'{m["generic"]} · {m["indication"]} · {m["response"]}',
            "medications.html")

    for panel in D["labs"]:
        for r in panel["results"]:
            add("Lab", r["name"], f'{r["value"]} {r["unit"]} on {fmt(panel["date"],"short")}', "labs.html")

    for s in D["sources"]:
        add("Document " + s["id"], s["title"], s["author"], f'documents.html#{s["id"]}')

    for i in D["images"]:
        add("Image " + i["id"], f'{i["region"]} — {i["view"]}',
            f'{i["kind"]} · {fmt(i["date"],"short")} · {i["clinic"]}', "images.html")

    for c in D["care_team"]:
        add("Care team", c["name"], f'{c["people"]} · {c["role"]}', "care-team.html")

    for v in D["vaccinations"]:
        add("Vaccination", v["vaccine"], f'{v["type"]} · {fmt(v["date"],"short")}', "preventive.html")

    for g in D["glossary"]:
        add("Glossary", g["de"], g["en"], "reference.html")

    for s in D["superseded"]:
        add("Superseded", demark(s["claim"]), s["correction"], "reference.html")

    for a in D["analysis"]:
        add("Note", a["title"], strip_tags(markdown(a["body"]))[:200], "reference.html")

    for r in D["recalls"]:
        add("Recall", r["item"], f'{r["status"]} · due {fmt(r["due"],"short")}', "preventive.html")

    return idx


# ── JS ───────────────────────────────────────────────────────────────────

APP_JS = r"""
(function () {
  'use strict';

  // ---- mobile nav ----
  var body = document.body;
  function closeNav(){ body.classList.remove('nav-open');
    var t=document.getElementById('navToggle'); if(t) t.setAttribute('aria-expanded','false'); }
  var nt = document.getElementById('navToggle');
  if (nt) nt.addEventListener('click', function () {
    var open = body.classList.toggle('nav-open');
    nt.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  var sc = document.getElementById('scrim');
  if (sc) sc.addEventListener('click', closeNav);

  // ---- search ----
  var sheet = document.getElementById('sheet'),
      q = document.getElementById('q'),
      res = document.getElementById('res'),
      sel = -1, hits = [];

  function openSearch(){ sheet.classList.add('is-open'); q.value=''; sel=-1;
    render(window.GATSBY_INDEX.slice(0,12)); setTimeout(function(){q.focus();},40); closeNav(); }
  function closeSearch(){ sheet.classList.remove('is-open'); }

  ['searchToggle','searchToggleM'].forEach(function(id){
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', openSearch);
  });
  Array.prototype.forEach.call(sheet.querySelectorAll('[data-close]'), function(el){
    el.addEventListener('click', closeSearch);
  });

  document.addEventListener('keydown', function (e) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === '/' && !typing) { e.preventDefault(); openSearch(); }
    if (e.key === 'Escape') { closeSearch(); closeLb(); closeNav(); }
    if (sheet.classList.contains('is-open') && hits.length) {
      if (e.key === 'ArrowDown'){ e.preventDefault(); sel=Math.min(sel+1,hits.length-1); mark(); }
      if (e.key === 'ArrowUp'){ e.preventDefault(); sel=Math.max(sel-1,0); mark(); }
      if (e.key === 'Enter' && sel >= 0){ e.preventDefault(); location.href = hits[sel].u; }
    }
  });

  function mark(){
    var els = res.querySelectorAll('.sr');
    Array.prototype.forEach.call(els, function(el,i){ el.classList.toggle('is-sel', i===sel); });
    if (els[sel]) els[sel].scrollIntoView({block:'nearest'});
  }

  function render(list){
    hits = list;
    if (!list.length){ res.innerHTML = '<div class="sheet-empty">Nothing matched. Try a drug name, a date, a body part, or a document code like S2.</div>'; return; }
    res.innerHTML = list.map(function(r){
      return '<a class="sr" href="'+r.u+'"><div class="sr-k">'+r.k+'</div>'+
             '<div class="sr-t">'+r.t+'</div>'+
             (r.d ? '<div class="sr-d">'+r.d+'</div>' : '')+'</a>';
    }).join('');
  }

  function score(item, terms){
    var hay = (item.t + ' ' + item.d + ' ' + item.k).toLowerCase(), s = 0;
    for (var i=0;i<terms.length;i++){
      var t = terms[i], pos = hay.indexOf(t);
      if (pos < 0) return -1;
      s += 10; if (pos < item.t.length) s += 8; if (pos === 0) s += 5;
    }
    return s;
  }

  if (q) q.addEventListener('input', function(){
    var v = q.value.trim().toLowerCase();
    sel = -1;
    if (!v) { render(window.GATSBY_INDEX.slice(0,12)); return; }
    var terms = v.split(/\s+/);
    var out = [];
    window.GATSBY_INDEX.forEach(function(it){
      var s = score(it, terms);
      if (s > 0) out.push({s:s, it:it});
    });
    out.sort(function(a,b){ return b.s - a.s; });
    render(out.slice(0,30).map(function(o){ return o.it; }));
  });

  // ---- lightbox ----
  var lb = document.getElementById('lb'), lbi = document.getElementById('lbi'),
      lbc = document.getElementById('lbc');
  function closeLb(){ lb.classList.remove('is-open'); lbi.src=''; }
  document.addEventListener('click', function(e){
    var z = e.target.closest('[data-zoom]');
    if (z){ lbi.src = z.getAttribute('data-zoom'); lbc.textContent = z.getAttribute('data-cap')||'';
            lb.classList.add('is-open'); return; }
    if (e.target === lb || e.target.id === 'lbx') closeLb();
  });

  // ---- gallery filters ----
  var chips = document.querySelectorAll('.chip[data-filter]');
  Array.prototype.forEach.call(chips, function(c){
    c.addEventListener('click', function(){
      Array.prototype.forEach.call(chips, function(x){ x.classList.remove('is-on'); });
      c.classList.add('is-on');
      var f = c.getAttribute('data-filter');
      Array.prototype.forEach.call(document.querySelectorAll('.shot'), function(s){
        s.style.display = (f === 'all' || s.getAttribute('data-kind') === f) ? '' : 'none';
      });
    });
  });

  // ---- observation composer ----
  var oOut = document.getElementById('oOut');
  if (oOut) {
    var f = ['oDate','oTime','oCat','oSev','oPart','oTitle','oDetail','oVet'].map(function(id){
      return document.getElementById(id);
    });
    var now = new Date();
    f[0].value = now.toISOString().slice(0,10);
    f[1].value = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');

    function esc(s){ return String(s||'').replace(/"/g,'\\"'); }
    function build(){
      var title = f[5].value.trim(), detail = f[6].value.trim();
      if (!title && !detail) { oOut.textContent = 'Fill in the fields above.'; return ''; }
      var y = '  - datetime: "' + f[0].value + ' ' + f[1].value + '"\n' +
              '    category: "' + esc(f[2].value) + '"\n' +
              '    severity: "' + esc(f[3].value) + '"\n' +
              (f[4].value.trim() ? '    body_part: "' + esc(f[4].value.trim()) + '"\n' : '') +
              '    title: "' + esc(title) + '"\n' +
              '    detail: >\n      ' + (detail || '—').replace(/\n+/g, '\n      ') + '\n' +
              '    vet_contacted: "' + esc(f[7].value) + '"\n' +
              '    tag: O';
      oOut.textContent = y;
      return y;
    }
    f.forEach(function(el){ el.addEventListener('input', build); el.addEventListener('change', build); });
    build();

    var cp = document.getElementById('oCopy');
    cp.addEventListener('click', function(){
      var y = build(); if (!y) return;
      navigator.clipboard.writeText(y).then(function(){
        var t = cp.textContent; cp.textContent = 'Copied';
        setTimeout(function(){ cp.textContent = t; }, 1600);
      });
    });

    var iss = document.getElementById('oIssue');
    function updIssue(){
      var repo = window.GATSBY_REPO || '';
      var title = f[5].value.trim() || 'Observation';
      var url = repo
        ? repo + '/issues/new?template=observation.yml&title=' + encodeURIComponent('[obs] ' + title)
        : '#';
      iss.href = url;
      iss.style.opacity = repo ? '1' : '.5';
      iss.title = repo ? '' : 'Set repo_url in site/build.py to enable this';
    }
    f.forEach(function(el){ el.addEventListener('input', updIssue); });
    updIssue();
  }
})();
"""


# ── main ─────────────────────────────────────────────────────────────────

def main():
    if not DATA.exists():
        sys.exit(f"Missing data file: {DATA}")
    D = yaml.safe_load(DATA.read_text(encoding="utf-8"))

    # ---- set this once you know your repo URL, to enable the issue button ----
    REPO_URL = os.environ.get("GATSBY_REPO_URL", "")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    pages = {
        "index.html": p_index(D),
        "timeline.html": p_timeline(D),
        "observations.html": p_observations(D),
        "medications.html": p_medications(D),
        "labs.html": p_labs(D),
        "preventive.html": p_preventive(D),
        "anaesthesia.html": p_anaesthesia(D),
        "documents.html": p_documents(D),
        "images.html": p_images(D),
        "care-team.html": p_care_team(D),
        "reference.html": p_reference(D),
        "print.html": p_print(D),
    }
    for p in D["problems"]:
        pages[f"problem-{p['slug']}.html"] = p_problem(D, p)

    for name, html in pages.items():
        (OUT / name).write_text(html, encoding="utf-8")

    shutil.copy(STATIC / "style.css", OUT / "style.css")
    (OUT / "app.js").write_text(APP_JS, encoding="utf-8")
    (OUT / "search.js").write_text(
        "window.GATSBY_INDEX=" + json.dumps(build_index(D), ensure_ascii=False) + ";\n"
        "window.GATSBY_REPO=" + json.dumps(REPO_URL) + ";\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    for folder in ("images", "sources"):
        src = ROOT / folder
        if src.exists():
            shutil.copytree(src, OUT / folder, dirs_exist_ok=True)

    n_img = len(list((OUT / "images").rglob("*.jpg"))) if (OUT / "images").exists() else 0
    n_pdf = len(list((OUT / "sources").glob("*.pdf"))) if (OUT / "sources").exists() else 0
    print(f"Built {len(pages)} pages · {n_img} images · {n_pdf} source PDFs · "
          f"{len(build_index(D))} search entries")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
