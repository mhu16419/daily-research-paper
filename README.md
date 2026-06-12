# Daily Research Papers

Automated daily digest of the latest papers on **LLM for Code** and **LLM for Software Engineering**.

Papers are fetched from arXiv and Semantic Scholar, deduplicated, and summarized using Claude Haiku. Results are published daily as markdown files.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python3 search_papers.py
```

## Automation

The script runs daily via cron:

```bash
0 9 * * * /home/mhu20/paper-agent/search_papers.py
```

## Archive

| Date | Link |
|------|------|
| 2026-06-12 | [papers/2026-06-12.md](papers/2026-06-12.md) |

---

*Built with Claude & Anthropic API*
