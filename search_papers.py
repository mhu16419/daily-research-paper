#!/usr/bin/env python3
"""Daily paper search agent for LLM for Code / Software Engineering topics."""

import os
import sys
import time
import datetime
import requests
import feedparser
import anthropic

TOPICS = [
    "LLM for code",
    "LLM for software engineering",
    "large language model code generation",
    "large language model software engineering",
]

ARXIV_CATEGORIES = ["cs.SE", "cs.PL", "cs.AI", "cs.LG"]

MODEL = "claude-haiku-4-5-20251001"
MAX_PAPERS = 30  # cap before dedup


def fetch_arxiv(query: str, max_results: int = 15) -> list[dict]:
    base = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    resp = requests.get(base, params=params, timeout=30)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    papers = []
    for entry in feed.entries:
        papers.append({
            "title": entry.title.replace("\n", " ").strip(),
            "authors": ", ".join(a.name for a in entry.get("authors", [])[:4]),
            "abstract": entry.summary.replace("\n", " ").strip()[:400],
            "url": entry.link,
            "source": "arXiv",
            "date": entry.get("published", "")[:10],
        })
    return papers


def fetch_semantic_scholar(query: str, limit: int = 10) -> list[dict]:
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,abstract,year,externalIds,url",
        "sort": "relevance",
    }
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  S2 rate-limit, waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as e:
            print(f"  Semantic Scholar error: {e}", file=sys.stderr)
            return []
    else:
        print("  Semantic Scholar: giving up after 3 attempts", file=sys.stderr)
        return []

    papers = []
    for p in data.get("data", []):
        authors = ", ".join(a["name"] for a in p.get("authors", [])[:4])
        abstract = (p.get("abstract") or "")[:400]
        paper_url = p.get("url") or ""
        if not paper_url:
            pid = p.get("paperId", "")
            paper_url = f"https://www.semanticscholar.org/paper/{pid}"
        papers.append({
            "title": p.get("title", ""),
            "authors": authors,
            "abstract": abstract,
            "url": paper_url,
            "source": "S2",
            "date": str(p.get("year", "")),
        })
    return papers


def dedup(papers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in papers:
        key = p["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def summarize_with_haiku(papers: list[dict], today: str) -> str:
    client = anthropic.Anthropic()

    paper_list = "\n\n".join(
        f"[{i+1}] **{p['title']}**\n"
        f"Authors: {p['authors']}\n"
        f"Source: {p['source']} | Date: {p['date']}\n"
        f"URL: {p['url']}\n"
        f"Abstract: {p['abstract']}"
        for i, p in enumerate(papers)
    )

    prompt = f"""You are a research assistant. Below are today's ({today}) papers on "LLM for Code" and "LLM for Software Engineering".

Your task:
1. Write a 2-3 sentence **daily highlight** summarizing the most interesting trends.
2. Group the papers into thematic categories (e.g., Code Generation, Bug Fixing, Testing, Program Repair, Agents, Benchmarks, etc.).
3. For each paper, write one crisp sentence describing the key contribution.

Output format (markdown):

## Daily Highlight
<2-3 sentences>

## Papers by Theme

### <Theme 1>
- **[Title](url)** — <one-sentence contribution>

### <Theme 2>
...

---
*{len(papers)} papers collected from arXiv and Semantic Scholar.*

Here are the papers:

{paper_list}
"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def save_markdown(content: str, today: str):
    path = os.path.join(os.path.dirname(__file__), "papers", f"{today}.md")
    header = f"# Daily Papers — {today}\n\n> Topics: LLM for Code, LLM for Software Engineering\n\n"
    with open(path, "w") as f:
        f.write(header + content)
    print(f"Saved: {path}")
    return path


def update_index():
    papers_dir = os.path.join(os.path.dirname(__file__), "papers")
    files = sorted(
        [f for f in os.listdir(papers_dir) if f.endswith(".md")],
        reverse=True,
    )
    lines = ["# Paper Archive\n", "| Date | Link |\n", "|------|------|\n"]
    for f in files:
        date = f.replace(".md", "")
        lines.append(f"| {date} | [papers/{f}](papers/{f}) |\n")
    with open(os.path.join(os.path.dirname(__file__), "README.md"), "w") as f:
        f.writelines(lines)


def git_commit_push(today: str):
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    cmds = [
        f"cd {repo_dir} && git add papers/{today}.md README.md",
        f'cd {repo_dir} && git commit -m "papers: add {today} daily digest"',
        f"cd {repo_dir} && git push",
    ]
    for cmd in cmds:
        ret = os.system(cmd)
        if ret != 0:
            print(f"Warning: command failed: {cmd}", file=sys.stderr)


def main():
    today = datetime.date.today().isoformat()
    print(f"=== Paper Agent — {today} ===")

    all_papers = []
    for topic in TOPICS:
        print(f"Fetching arXiv: {topic!r}")
        all_papers.extend(fetch_arxiv(topic, max_results=10))
        time.sleep(1)
        print(f"Fetching Semantic Scholar: {topic!r}")
        all_papers.extend(fetch_semantic_scholar(topic, limit=8))
        time.sleep(5)  # S2 rate-limit is strict

    all_papers = dedup(all_papers)[:MAX_PAPERS]
    print(f"Unique papers after dedup: {len(all_papers)}")

    print("Summarizing with Claude Haiku...")
    summary = summarize_with_haiku(all_papers, today)

    save_markdown(summary, today)
    update_index()
    git_commit_push(today)
    print("Done.")


if __name__ == "__main__":
    main()
