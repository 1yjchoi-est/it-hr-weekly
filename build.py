#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IT HR 위클리 — 정적 사이트 생성기 (표준 라이브러리만 사용).

data/site.json + data/issues/*.json  ->  dist/ (index.html, issues/*.html, feed.xml, assets/)

사용법:
    python build.py            # dist/ 로 빌드
    python build.py --serve    # 빌드 후 http://localhost:8000 로 미리보기
"""
import json
import os
import shutil
import stat
import sys
import time
from datetime import datetime, timezone, timedelta
from html import escape
from pathlib import Path

# Windows 콘솔(cp949)에서도 한글·기호 출력이 깨지지 않도록 UTF-8 강제
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
ASSETS = ROOT / "assets"

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


# ----------------------------------------------------------------------------- helpers
def _force_remove(func, path, _exc):
    """rmtree onexc 핸들러: 읽기 전용 속성 해제 후 재시도."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def robust_rmtree(path: Path, retries: int = 5):
    """Windows/OneDrive 동기화로 디렉터리가 일시적으로 잠겨도 견디게 삭제한다.
    끝내 디렉터리 자체를 못 지우면 내부 파일만이라도 비우고 진행한다."""
    for attempt in range(retries):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onexc=_force_remove)
            return
        except PermissionError:
            time.sleep(0.4 * (attempt + 1))
    # 마지막 폴백: 내용물만 제거(디렉터리 핸들이 잡혀 있어도 파일은 보통 지워짐)
    if path.exists():
        for child in path.glob("*"):
            try:
                if child.is_dir():
                    shutil.rmtree(child, onexc=_force_remove)
                else:
                    child.unlink()
            except OSError:
                pass


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fmt_date(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d")
        return f"{d.year}년 {d.month}월 {d.day}일 ({WEEKDAYS[d.weekday()]})"
    except ValueError:
        return iso


def rfc822(iso: str) -> str:
    try:
        d = datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=KST)
    except ValueError:
        d = datetime.now(KST)
    return d.strftime("%a, %d %b %Y %H:%M:%S %z")


def load_issues():
    issues = []
    issue_dir = DATA / "issues"
    if issue_dir.exists():
        for p in sorted(issue_dir.glob("*.json")):
            issues.append(load_json(p))
    # 최신호가 먼저 오도록 날짜 내림차순 정렬
    issues.sort(key=lambda x: x.get("date", ""), reverse=True)
    return issues


# ----------------------------------------------------------------------------- templates
def head(site, title, desc, base, canonical=""):
    accent = escape(site.get("accent", "#4f46e5"))
    og = ""
    if canonical:
        og = f'<meta property="og:url" content="{escape(canonical)}">'
    return f"""<!doctype html>
<html lang="{escape(site.get('locale','ko-KR'))}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<meta name="theme-color" content="{accent}">
<meta property="og:type" content="article">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:site_name" content="{escape(site.get('title',''))}">
{og}
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{escape(site.get('title',''))}" href="{base}feed.xml">
<link rel="stylesheet" href="{base}assets/styles.css">
</head>
<body>"""


def topbar(site, base, nav_issues=True):
    nav = (
        f'<a href="{base}index.html#latest">최신호</a>'
        f'<a href="{base}index.html#archive">지난호</a>'
        f'<a href="{base}feed.xml">RSS</a>'
        if nav_issues else ""
    )
    return f"""<header class="topbar"><div class="wrap">
<a class="brand" href="{base}index.html"><span class="logo">HR</span><span>{escape(site.get('title',''))}</span></a>
<nav>{nav}</nav>
</div></header>"""


def footer(site, base):
    email = escape(site.get("editorEmail", ""))
    sub = escape(site.get("subscribeNote", ""))
    disc = escape(site.get("disclaimer", ""))
    return f"""<footer class="site"><div class="wrap">
<div class="ft-brand"><span class="logo" style="width:24px;height:24px;border-radius:7px;display:inline-grid;place-items:center;background:linear-gradient(135deg,var(--accent),var(--accent-dark));color:#fff;font-size:12px;font-weight:800;">HR</span> {escape(site.get('title',''))}</div>
<p>{escape(site.get('tagline',''))} · 발행 {escape(site.get('publisher',''))}</p>
<p>{sub} 문의: <a href="mailto:{email}">{email}</a></p>
<p class="disclaimer">⚠️ {disc}</p>
<div class="ftnav"><a href="{base}index.html">홈</a><a href="{base}feed.xml">RSS 구독</a><a href="mailto:{email}">구독 문의</a></div>
</div></footer>
</body></html>"""


def render_card(item):
    cat = escape(item.get("category", ""))
    eff = escape(item.get("effectiveDate", ""))
    tag = f'<span class="pill">{cat}</span>' if cat else ""
    eff_html = f'<span class="eff">📅 {eff}</span>' if eff else ""
    summary = f'<p>{escape(item.get("summary",""))}</p>' if item.get("summary") else ""
    changed = ""
    if item.get("whatChanged"):
        changed = (
            f'<div class="kv"><span class="k">무엇이 바뀌었나</span>'
            f'<span class="v">{escape(item["whatChanged"])}</span></div>'
        )
    impact = ""
    if item.get("itImpact"):
        impact = (
            f'<div class="kv impact"><span class="k">💼 IT 인사 시사점</span>'
            f'<span class="v">{escape(item["itImpact"])}</span></div>'
        )
    sources = render_sources(item)
    return f"""<article class="card">
<div class="tags">{tag}{eff_html}</div>
<h3>{escape(item.get('headline',''))}</h3>
{summary}
{changed}
{impact}
{sources}
</article>"""


def render_sources(item):
    srcs = item.get("sources")
    if not srcs and item.get("sourceUrl"):
        srcs = [{"name": item.get("sourceName", "출처"), "url": item["sourceUrl"]}]
    if not srcs:
        return ""
    links = " · ".join(
        f'<a href="{escape(s["url"])}" target="_blank" rel="noopener">{escape(s.get("name","출처"))}</a>'
        for s in srcs if s.get("url")
    )
    return f'<div class="sources"><b>출처</b> {links}</div>' if links else ""


def render_stats(stats):
    if not stats:
        return ""
    cells = []
    for s in stats:
        v = escape(s.get("value", ""))
        l = escape(s.get("label", ""))
        if s.get("url"):
            l = f'<a href="{escape(s["url"])}" target="_blank" rel="noopener">{l}</a>'
        cells.append(f'<div class="stat"><div class="v">{v}</div><div class="l">{l}</div></div>')
    return f'<div class="stats">{"".join(cells)}</div>'


def render_lawwatch(rows):
    if not rows:
        return ""
    trs = []
    for r in rows:
        law = escape(r.get("law", ""))
        if r.get("url"):
            law = f'<a href="{escape(r["url"])}" target="_blank" rel="noopener">{law}</a>'
        trs.append(
            "<tr>"
            f'<td class="law">{law}</td>'
            f'<td><span class="status">{escape(r.get("status",""))}</span></td>'
            f'<td>{escape(r.get("effectiveDate",""))}</td>'
            f'<td>{escape(r.get("note",""))}</td>'
            "</tr>"
        )
    return f"""<div class="table-scroll"><table class="lawwatch">
<thead><tr><th>법령·법안</th><th>상태</th><th>시점</th><th>한줄 메모</th></tr></thead>
<tbody>{"".join(trs)}</tbody></table></div>"""


def render_checklist(items):
    if not items:
        return ""
    lis = "".join(f"<li>{escape(x)}</li>" for x in items)
    return f'<ul class="checklist">{lis}</ul>'


# ----------------------------------------------------------------------------- pages
def build_issue_page(site, issue):
    base = "../"
    slug = issue["slug"]
    title = f"{issue.get('headline','')} · {site.get('title','')}"
    desc = issue.get("intro", "")[:155]
    canonical = ""
    if site.get("baseUrl"):
        canonical = site["baseUrl"].rstrip("/") + f"/issues/{slug}.html"

    sections_html = []
    for sec in issue.get("sections", []):
        cards = "".join(render_card(it) for it in sec.get("items", []))
        sections_html.append(
            f"""<section class="block">
<div class="section-head"><span class="emoji">{escape(sec.get('emoji',''))}</span><h2>{escape(sec.get('title',''))}</h2></div>
{cards}
</section>"""
        )

    stats = render_stats(issue.get("quickStats"))
    lawwatch = render_lawwatch(issue.get("lawWatch"))
    lawwatch_block = (
        f"""<section class="block">
<div class="section-head"><span class="emoji">🗓️</span><h2>주목할 입법·시행 캘린더</h2></div>
{lawwatch}
</section>"""
        if lawwatch else ""
    )
    checklist = render_checklist(issue.get("actionItems"))
    checklist_block = (
        f"""<section class="block">
<div class="section-head"><span class="emoji">✅</span><h2>이번 주 HR 실무 체크리스트</h2></div>
{checklist}
</section>"""
        if checklist else ""
    )
    source_note = (
        f'<div class="note">📎 {escape(issue["sourceNote"])}</div>'
        if issue.get("sourceNote") else ""
    )

    html = (
        head(site, title, desc, base, canonical)
        + topbar(site, base)
        + f"""<main class="wrap">
<div class="masthead">
<span class="issue-no">제{issue.get('issueNumber','')}호</span>
<h1>{escape(issue.get('headline',''))}</h1>
<div class="meta-line"><time datetime="{escape(issue.get('date',''))}">🗓️ {fmt_date(issue.get('date',''))}</time><span>{escape(issue.get('weekLabel',''))}</span></div>
</div>
<div class="intro">{escape(issue.get('intro',''))}</div>
{stats}
{"".join(sections_html)}
{lawwatch_block}
{checklist_block}
{source_note}
<a class="backlink" href="../index.html">← 모든 호 보기</a>
</main>"""
        + footer(site, base)
    )
    out = DIST / "issues" / f"{slug}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def build_index(site, issues):
    base = ""
    title = f"{site.get('title','')} — {site.get('tagline','')}"
    desc = site.get("description", "")

    cards = []
    for i, issue in enumerate(issues):
        latest = '<span class="latest">최신호</span>' if i == 0 else ""
        featured = " featured" if i == 0 else ""
        anchor = ' id="latest"' if i == 0 else ""
        cards.append(
            f"""<a class="issue-card{featured}" href="issues/{escape(issue['slug'])}.html"{anchor}>
<div class="row">{latest}<span class="when">제{issue.get('issueNumber','')}호 · {fmt_date(issue.get('date',''))} · {escape(issue.get('weekLabel',''))}</span></div>
<h3>{escape(issue.get('headline',''))}</h3>
<p>{escape(issue.get('intro','')[:120])}…</p>
<div class="more">읽어보기 →</div>
</a>"""
        )
    archive = "".join(cards) if cards else '<p class="note">아직 발행된 호가 없습니다.</p>'

    html = (
        head(site, title, desc, base, site.get("baseUrl", ""))
        + topbar(site, base, nav_issues=True)
        + f"""<main class="wrap">
<section class="hero">
<div class="eyebrow">매주 월요일 발행 · IT·테크 HR 전용</div>
<h1>{escape(site.get('title',''))}</h1>
<p class="lead">{escape(site.get('description',''))}</p>
<div class="cta">
<a class="btn" href="#latest">최신호 읽기</a>
<a class="btn ghost" href="feed.xml">RSS로 구독</a>
</div>
</section>
<section class="block" id="archive">
<div class="section-head"><span class="emoji">📰</span><h2>발행 호</h2></div>
<div class="issue-list">{archive}</div>
</section>
<div class="note">📬 {escape(site.get('subscribeNote',''))}</div>
</main>"""
        + footer(site, base)
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")


def build_feed(site, issues):
    items = []
    for issue in issues:
        link = ""
        if site.get("baseUrl"):
            link = site["baseUrl"].rstrip("/") + f"/issues/{issue['slug']}.html"
        else:
            link = f"issues/{issue['slug']}.html"
        items.append(
            "<item>"
            f"<title>{escape('제%s호 · %s' % (issue.get('issueNumber',''), issue.get('headline','')))}</title>"
            f"<link>{escape(link)}</link>"
            f"<guid isPermaLink=\"false\">{escape(issue['slug'])}</guid>"
            f"<pubDate>{rfc822(issue.get('date',''))}</pubDate>"
            f"<description>{escape(issue.get('intro',''))}</description>"
            "</item>"
        )
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>{escape(site.get('title',''))}</title>
<link>{escape(site.get('baseUrl',''))}</link>
<description>{escape(site.get('description',''))}</description>
<language>{escape(site.get('locale','ko-KR'))}</language>
{"".join(items)}
</channel></rss>"""
    (DIST / "feed.xml").write_text(feed, encoding="utf-8")


def copy_assets():
    dst = DIST / "assets"
    robust_rmtree(dst)
    shutil.copytree(ASSETS, dst, dirs_exist_ok=True)
    (DIST / ".nojekyll").write_text("", encoding="utf-8")


# ----------------------------------------------------------------------------- main
def build():
    site = load_json(DATA / "site.json")
    issues = load_issues()
    robust_rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)
    copy_assets()
    for issue in issues:
        build_issue_page(site, issue)
    build_index(site, issues)
    build_feed(site, issues)
    print(f"✓ 빌드 완료: {len(issues)}개 호 → {DIST}")
    for issue in issues:
        print(f"   - 제{issue.get('issueNumber')}호 [{issue.get('date')}] {issue.get('slug')}.html")


def serve():
    import http.server
    import socketserver
    os.chdir(DIST)
    port = 8000
    with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
        print(f"▶ 미리보기: http://localhost:{port}  (Ctrl+C 로 종료)")
        httpd.serve_forever()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve()
