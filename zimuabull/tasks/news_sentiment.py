"""
Celery tasks for news sentiment analysis using OpenAI GPT models.
"""

import json
import logging
import os
from datetime import datetime, timezone

from celery import shared_task
from django.db import transaction

from zimuabull.models import News, NewsSentiment

logger = logging.getLogger(__name__)


# --- OpenAI SDK ---
try:
    from openai import OpenAI
except ImportError:
    logger.error("Missing dependency 'openai'. Install with: pip install -U openai")
    OpenAI = None


SYSTEM_PROMPT = """You are a careful financial-news analyst. You read a news article (title, snippet, source, date) and assess its sentiment impact on the stock market.

Return a single JSON object with this exact schema:
{
  "sentiment": <integer 1..10>,
  "justification": <string 1-3 sentences explaining your score>,
  "description": <string exactly 3 sentences summarizing the article and its market impact>
}

Scoring guide (1..10):
1–3 = very negative / mostly harmful implications, clear risks dominate;
4–6 = mixed/neutral to slightly negative or slightly positive; uncertainty or balanced tone;
7–10 = positive / opportunity-focused, favorable outlook dominates.

Rules:
- Use plain language; be concise.
- Assess the sentiment from an investor's perspective.
- If the article discusses multiple topics, weigh the overall market impact.
- Output ONLY the JSON object; no extra text, no code fences.
- Never invent facts not implied by the provided article.
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


def build_user_prompt(news_item):
    """Build user prompt from a News object."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    published = "Unknown"
    if news_item.published_date:
        published = news_item.published_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    prompt = f"""News Article Analysis Request
Now (UTC): {now_iso}

Title: {news_item.title}
Source: {news_item.source or 'Unknown'}
Published: {published}
URL: {news_item.url}

Snippet:
{news_item.snippet or '(No snippet available)'}

Please analyze the sentiment of this news article from a stock market investor's perspective.
"""
    return prompt


def call_openai(model: str, system_prompt: str, user_prompt: str):
    """Call OpenAI API to get sentiment analysis."""
    if not OpenAI:
        raise RuntimeError("OpenAI client not available. Install 'openai' package.")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

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


def parse_sentiment_response(raw_response):
    """Parse the LLM response and extract sentiment data."""
    try:
        parsed = json.loads(raw_response)
        if not isinstance(parsed, dict) or not all(
            k in parsed for k in ("sentiment", "justification", "description")
        ):
            raise ValueError("Missing required keys in response.")
        return parsed
    except Exception:
        # Try to extract JSON from markdown code blocks
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(raw_response[start : end + 1])
                return parsed
            except Exception:
                pass

        # Fallback
        return {
            "sentiment": 5,
            "justification": "Model returned non-parseable JSON; providing a neutral fallback.",
            "description": "The article received coverage, but the exact sentiment could not be parsed automatically. "
                          "Re-run with a different model for a precise score. "
                          "Structured output mode may improve reliability.",
        }


@shared_task
def analyze_news_sentiment(news_id=None, model_name="gpt-4o-mini"):
    """
    Analyze sentiment for news articles.

    Args:
        news_id: Specific news article ID to analyze (optional)
        model_name: OpenAI model to use (default: gpt-4o-mini)

    If news_id is None, analyzes all news articles that don't have sentiment yet.
    """
    if news_id:
        # Analyze a specific news article
        try:
            news_item = News.objects.get(id=news_id)
            _analyze_single_news(news_item, model_name)
            logger.info(f"Analyzed sentiment for news ID {news_id}")
        except News.DoesNotExist:
            logger.error(f"News ID {news_id} not found")
            return

    else:
        # Analyze all news without sentiment
        news_without_sentiment = News.objects.filter(sentiment__isnull=True)
        count = news_without_sentiment.count()

        if count == 0:
            logger.info("No news articles need sentiment analysis")
            return

        logger.info(f"Analyzing sentiment for {count} news articles...")

        analyzed = 0
        failed = 0

        for news_item in news_without_sentiment:
            try:
                _analyze_single_news(news_item, model_name)
                analyzed += 1
            except Exception as e:
                logger.exception(f"Failed to analyze news ID {news_item.id}: {e}")
                failed += 1

        logger.info(f"Sentiment analysis complete: {analyzed} analyzed, {failed} failed")


def _analyze_single_news(news_item, model_name):
    """Analyze sentiment for a single news article."""
    # Build prompt
    user_prompt = build_user_prompt(news_item)

    # Call OpenAI
    raw_response = call_openai(model_name, SYSTEM_PROMPT, user_prompt)

    # Parse response
    sentiment_data = parse_sentiment_response(raw_response)

    # Save to database
    with transaction.atomic():
        NewsSentiment.objects.update_or_create(
            news=news_item,
            defaults={
                "sentiment_score": sentiment_data["sentiment"],
                "justification": sentiment_data["justification"],
                "description": sentiment_data["description"],
                "model_name": model_name,
            }
        )

    logger.info(
        f"Sentiment analyzed for '{news_item.title[:50]}': "
        f"Score {sentiment_data['sentiment']}/10"
    )


@shared_task
def fetch_and_analyze_news_for_symbol(symbol_id, model_name="gpt-4o-mini"):
    """
    Fetch news for a specific symbol and analyze sentiment.

    Args:
        symbol_id: Symbol ID to fetch news for
        model_name: OpenAI model to use for sentiment analysis
    """
    from zimuabull.models import Symbol

    try:
        symbol = Symbol.objects.get(id=symbol_id)
    except Symbol.DoesNotExist:
        logger.error(f"Symbol ID {symbol_id} not found")
        return

    # Fetch news using the management command logic
    from zimuabull.management.commands.fetch_news import Command
    cmd = Command()

    try:
        fetched, new = cmd._fetch_news_for_symbol(symbol)
        logger.info(
            f"Fetched {fetched} news articles for {symbol.symbol} ({new} new)"
        )

        # Analyze sentiment for new articles
        if new > 0:
            analyze_news_sentiment.delay(model_name=model_name)

    except Exception as e:
        logger.exception(f"Failed to fetch news for {symbol.symbol}: {e}")


@shared_task
def fetch_and_analyze_news_task(model_name="gpt-4o-mini", max_symbols=50):
    """
    Scheduled task to fetch news for active symbols and analyze sentiment.

    This task is called by Celery Beat to run periodically.

    Args:
        model_name: OpenAI model to use for sentiment analysis
        max_symbols: Maximum number of symbols to process in this run
    """
    from datetime import timedelta

    from django.utils import timezone

    from zimuabull.models import Symbol

    # Get symbols with recent activity (last 7 days)
    cutoff_date = timezone.now() - timedelta(days=7)
    active_symbols = Symbol.objects.filter(
        updated_at__gte=cutoff_date
    ).order_by("-updated_at")[:max_symbols]

    logger.info(f"Starting news fetch for {active_symbols.count()} active symbols")

    # Fetch news using the management command logic
    from zimuabull.management.commands.fetch_news import Command
    cmd = Command()

    total_fetched = 0
    total_new = 0

    for symbol in active_symbols:
        try:
            fetched, new = cmd._fetch_news_for_symbol(symbol)
            total_fetched += fetched
            total_new += new
        except Exception as e:
            logger.exception(f"Failed to fetch news for {symbol.symbol}: {e}")
            continue

    logger.info(
        f"News fetch complete: {total_fetched} articles fetched, {total_new} new"
    )

    # Analyze sentiment for all new articles
    if total_new > 0:
        logger.info(f"Triggering sentiment analysis for {total_new} new articles")
        analyze_news_sentiment.delay(model_name=model_name)
