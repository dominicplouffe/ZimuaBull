# app_name/management/commands/llm_sentiment_news.py
"""
Django management command:
Search DuckDuckGo News → send results to an LLM → get back JSON sentiment.

Setup:
  pip install -U ddgs openai python-dotenv
  export OPENAI_API_KEY=sk-...

Usage:
  python manage.py llm_sentiment_news \
    --query "China launches probe into Qualcomm amid ongoing US trade fight" \
    --max-results 12 \
    --model "gpt-4.1-mini"

The command prints ONLY the JSON object returned by the LLM.
"""

import os
import json
from typing import List, Dict
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError

# --- Search (DuckDuckGo News) ---
try:
    from ddgs import DDGS  # successor to duckduckgo_search
except ImportError as e:
    raise CommandError("Missing dependency 'ddgs'. Install with: pip install -U ddgs") from e

# --- OpenAI SDK ---
try:
    from openai import OpenAI
except ImportError as e:
    raise CommandError("Missing dependency 'openai'. Install with: pip install -U openai") from e


SYSTEM_PROMPT = """You are a careful financial-news analyst. You read a set of news results (title, snippet, source, date, url) about a single topic.
You must infer sentiment by understanding the wording and framing across the articles (no numeric polarity algorithms).
Return a single JSON object with this exact schema:
{
  "sentiment": <integer 1..10>,
  "justification": <string 1-3 sentences explaining your score>,
  "description": <string exactly 3 sentences summarizing what the web coverage says>
}

Scoring guide (1..10):
1–3 = very negative / mostly harmful implications, clear risks dominate;
4–6 = mixed/neutral to slightly negative or slightly positive; uncertainty or balanced tone;
7–10 = positive / opportunity-focused, favorable outlook dominates.

Rules:
- Use plain language; be concise.
- Treat the set of results holistically (do NOT score each item).
- If results conflict, weigh recency, source credibility, and specificity.
- Output ONLY the JSON object; no extra text, no code fences.
- Never invent facts not implied by the provided results.
"""

STRUCTURED_OUTPUT_SCHEMA = {
    "name": "SentimentJSON",
    "schema": {
        "type": "object",
        "properties": {
            "sentiment": {"type": "integer", "minimum": 1, "maximum": 10},
            "justification": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["sentiment", "justification", "description"],
        "additionalProperties": False,
    },
    "strict": True,
}


def fetch_news(query: str, max_results: int = 10) -> List[Dict]:
    items: List[Dict] = []
    with DDGS() as ddgs:
        for it in ddgs.news(keywords=query, max_results=max_results) or []:
            if not it:
                continue
            items.append(
                {
                    "title": (it.get("title") or "")[:220],
                    "snippet": (it.get("body") or "")[:400],
                    "source": it.get("source") or "",
                    "date": it.get("date") or "",
                    "url": it.get("url") or "",
                }
            )
    return items


def build_user_prompt(query: str, items: List[Dict]) -> str:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    header = f"Query: {query}\nNow (UTC): {now_iso}\nNews results ({len(items)} items):\n"
    lines = []
    for idx, it in enumerate(items, 1):
        line = (
            f"- [{idx}] title: {it['title']}\n"
            f"      snippet: {it['snippet']}\n"
            f"      source: {it['source']} | date: {it['date']} | url: {it['url']}"
        )
        lines.append(line)
    if not lines:
        lines.append("- [0] (no results found)")
    return header + "\n".join(lines)


def call_openai(model: str, system_prompt: str, user_prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise CommandError("Missing OPENAI_API_KEY environment variable.")
    client = OpenAI(api_key=api_key)

    # Use standard chat completions API with JSON mode
    chat = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return chat.choices[0].message.content


class Command(BaseCommand):
    help = "Fetch DuckDuckGo news for a query and use an LLM to return a JSON sentiment assessment (score 1–10)."

    def add_arguments(self, parser):
        parser.add_argument("--query", type=str, required=True, help="News search query")
        parser.add_argument("--max-results", type=int, default=10, help="Max news results to fetch (default: 10)")
        parser.add_argument(
            "--model",
            type=str,
            default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            help="OpenAI model (default from OPENAI_MODEL or 'gpt-4.1-mini')",
        )

    def handle(self, *args, **options):
        query = options["query"]
        max_results = options["max_results"]
        model = options["model"]

        items = fetch_news(query, max_results)
        user_prompt = build_user_prompt(query, items)

        raw = call_openai(model, SYSTEM_PROMPT, user_prompt)

        # Print ONLY a single JSON object
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict) or not all(
                k in parsed for k in ("sentiment", "justification", "description")
            ):
                raise ValueError("Missing required keys.")
            self.stdout.write(json.dumps(parsed, ensure_ascii=False))
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(raw[start : end + 1])
                    self.stdout.write(json.dumps(parsed, ensure_ascii=False))
                    return
                except Exception:
                    pass
            fallback = {
                "sentiment": 5,
                "justification": "Model returned non-parseable JSON; providing a neutral fallback.",
                "description": "The queried topic received coverage, but the exact tone could not be parsed automatically. "
                "Re-run with fewer results or a different model for a precise score. "
                "Structured output mode may improve reliability.",
            }
            self.stdout.write(json.dumps(fallback, ensure_ascii=False))
