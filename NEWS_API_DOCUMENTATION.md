# News API Documentation

## Overview

The News API provides access to financial news articles with AI-powered sentiment analysis. News articles are fetched from Yahoo Finance using yfinance and analyzed using GPT-4o-mini for sentiment scoring.

**Key Features:**
- Real-time financial news from Yahoo Finance
- AI sentiment analysis (1-10 scale)
- Multi-symbol support (one article can relate to multiple stocks)
- Flexible filtering by date, sentiment, and symbols
- Automatic updates every 30 minutes during market hours

---

## Base URL

```
http://your-domain.com/api
```

---

## Endpoints

### 1. List All News Articles

**Endpoint:** `GET /api/news/`

**Description:** Get all news articles with optional filtering. Returns paginated results sorted by most recent first.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `days` | integer | No | 7 | Number of days of history to retrieve |
| `page_size` | integer | No | 30 | Results per page (max: 100) |
| `page` | integer | No | 1 | Page number for pagination |
| `has_sentiment` | boolean | No | - | Filter by sentiment presence (`true`/`false`) |
| `sentiment_min` | integer | No | - | Minimum sentiment score (1-10) |
| `sentiment_max` | integer | No | - | Maximum sentiment score (1-10) |
| `symbol` | string | No | - | Filter by stock symbol (requires `exchange`) |
| `exchange` | string | No | - | Exchange code (e.g., NASDAQ, TSE) |

**Example Request:**
```bash
GET /api/news/?days=3&has_sentiment=true&page_size=20
```

**Example Response:**
```json
{
  "count": 45,
  "next": "http://your-domain.com/api/news/?page=2",
  "previous": null,
  "results": [
    {
      "id": 123,
      "url": "https://finance.yahoo.com/news/article-slug",
      "title": "Apple Announces New Product Line",
      "snippet": "Apple Inc. today unveiled a new line of products that are expected to drive growth...",
      "source": "Reuters",
      "published_date": "2025-10-11T18:05:18Z",
      "thumbnail_url": "https://image-url.com/thumbnail.jpg",
      "sentiment_score": 8,
      "symbol_count": 2,
      "created_at": "2025-10-11T18:10:00Z"
    },
    {
      "id": 124,
      "url": "https://finance.yahoo.com/news/another-article",
      "title": "Markets Rally on Strong Economic Data",
      "snippet": "Stock markets surged today following the release of better-than-expected...",
      "source": "Bloomberg",
      "published_date": "2025-10-11T16:30:00Z",
      "thumbnail_url": "https://image-url.com/thumbnail2.jpg",
      "sentiment_score": 9,
      "symbol_count": 5,
      "created_at": "2025-10-11T16:35:00Z"
    }
  ]
}
```

**Response Fields:**
- `id`: Unique news article ID
- `url`: Link to the full article
- `title`: Article headline
- `snippet`: Article summary/preview text
- `source`: News source (e.g., Reuters, Bloomberg)
- `published_date`: When the article was published (ISO 8601)
- `thumbnail_url`: Article image/thumbnail URL
- `sentiment_score`: AI sentiment score (1-10, null if not analyzed)
- `symbol_count`: Number of symbols related to this article
- `created_at`: When the article was added to our database

---

### 2. Get Single News Article (Detailed)

**Endpoint:** `GET /api/news/{id}/`

**Description:** Get full details for a specific news article, including complete sentiment analysis and all related symbols.

**Path Parameters:**
- `id` (integer, required): News article ID

**Example Request:**
```bash
GET /api/news/123/
```

**Example Response:**
```json
{
  "id": 123,
  "url": "https://finance.yahoo.com/news/article-slug",
  "title": "Apple Announces New Product Line",
  "snippet": "Apple Inc. today unveiled a new line of products that are expected to drive significant growth in the next quarter. The announcement includes innovations in AI and sustainability...",
  "source": "Reuters",
  "published_date": "2025-10-11T18:05:18Z",
  "thumbnail_url": "https://image-url.com/thumbnail.jpg",
  "sentiment": {
    "sentiment_score": 8,
    "justification": "The article highlights positive product announcements and innovation, indicating strong market positioning for Apple. The emphasis on growth and new technology suggests favorable investor sentiment.",
    "description": "Apple has announced a new product line featuring AI innovations and sustainability initiatives. The company expects significant growth from these launches. Market analysts view this as a positive development for the tech sector.",
    "model_name": "gpt-4o-mini",
    "analyzed_at": "2025-10-11T18:10:15Z"
  },
  "symbols": [
    {
      "symbol": "AAPL",
      "exchange": "NASDAQ",
      "is_primary": true
    },
    {
      "symbol": "MSFT",
      "exchange": "NASDAQ",
      "is_primary": false
    }
  ],
  "created_at": "2025-10-11T18:10:00Z"
}
```

**Response Fields (Additional to List View):**
- `sentiment`: Full sentiment analysis object
  - `sentiment_score`: Score from 1 (very negative) to 10 (very positive)
  - `justification`: AI explanation for the sentiment score (1-3 sentences)
  - `description`: AI summary of the article's market impact (3 sentences)
  - `model_name`: AI model used for analysis
  - `analyzed_at`: When sentiment analysis was performed
- `symbols`: Array of related stock symbols
  - `symbol`: Stock ticker (e.g., AAPL)
  - `exchange`: Exchange code (e.g., NASDAQ)
  - `is_primary`: Whether this is the primary symbol mentioned

---

### 3. Get News by Symbol

**Endpoint:** `GET /api/news/by-symbol/`

**Description:** Convenience endpoint to get recent news for a specific stock symbol with full details.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `symbol` | string | **Yes** | - | Stock symbol (e.g., AAPL) |
| `exchange` | string | **Yes** | - | Exchange code (e.g., NASDAQ) |
| `limit` | integer | No | 10 | Number of articles to return (max: 50) |

**Example Request:**
```bash
GET /api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ&limit=10
```

**Example Response:**
```json
{
  "symbol": "AAPL",
  "exchange": "NASDAQ",
  "company_name": "Apple Inc.",
  "news_count": 10,
  "news": [
    {
      "id": 123,
      "url": "https://finance.yahoo.com/news/article-slug",
      "title": "Apple Announces New Product Line",
      "snippet": "Apple Inc. today unveiled...",
      "source": "Reuters",
      "published_date": "2025-10-11T18:05:18Z",
      "thumbnail_url": "https://image-url.com/thumbnail.jpg",
      "sentiment": {
        "sentiment_score": 8,
        "justification": "The article highlights positive product announcements...",
        "description": "Apple has announced a new product line...",
        "model_name": "gpt-4o-mini",
        "analyzed_at": "2025-10-11T18:10:15Z"
      },
      "symbols": [
        {
          "symbol": "AAPL",
          "exchange": "NASDAQ",
          "is_primary": true
        }
      ],
      "created_at": "2025-10-11T18:10:00Z"
    }
  ]
}
```

---

### 4. Trigger Sentiment Analysis

**Endpoint:** `POST /api/news/analyze-sentiment/`

**Description:** Manually trigger sentiment analysis for news articles. Used when sentiment analysis hasn't been run yet or needs to be refreshed.

**Request Body:**
```json
{
  "news_id": 123
}
```
Or leave empty `{}` to analyze all pending articles.

**Example Request:**
```bash
POST /api/news/analyze-sentiment/
Content-Type: application/json

{
  "news_id": 123
}
```

**Example Response (Specific Article):**
```json
{
  "message": "Sentiment analysis queued for news article 123",
  "task_id": "abc-123-def-456",
  "news_title": "Apple Announces New Product Line"
}
```

**Example Response (All Pending):**
```json
{
  "message": "Sentiment analysis queued for 15 news articles",
  "task_id": "abc-123-def-456",
  "pending_count": 15
}
```

---

## Common Use Cases

### Use Case 1: Home Page News Feed

**Goal:** Show latest market news with sentiment on the home page.

**Endpoint:**
```bash
GET /api/news/?days=1&has_sentiment=true&page_size=10
```

**Implementation:**
```javascript
// Fetch latest news with sentiment
const response = await fetch('/api/news/?days=1&has_sentiment=true&page_size=10');
const data = await response.json();

// Display news cards
data.results.forEach(article => {
  displayNewsCard({
    title: article.title,
    source: article.source,
    image: article.thumbnail_url,
    sentiment: article.sentiment_score,
    symbolCount: article.symbol_count,
    url: article.url,
    publishedDate: article.published_date
  });
});
```

**Visual Suggestion:**
- Show sentiment as color-coded badge (green 7-10, yellow 4-6, red 1-3)
- Display number of related symbols as a tag
- Sort by most recent first

---

### Use Case 2: Symbol Detail Page

**Goal:** Show news related to a specific stock on its detail page.

**Endpoint:**
```bash
GET /api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ&limit=5
```

**Implementation:**
```javascript
// Fetch news for specific symbol
const response = await fetch('/api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ&limit=5');
const data = await response.json();

// Display in symbol page news section
displaySymbolNews({
  symbol: data.symbol,
  companyName: data.company_name,
  newsCount: data.news_count,
  articles: data.news
});
```

**Visual Suggestion:**
- Show 5 most recent articles
- Include sentiment justification on hover/click
- Link to full article
- Show "View More News" button if more than 5 articles available

---

### Use Case 3: Positive News Dashboard

**Goal:** Show only positive/bullish news across all stocks.

**Endpoint:**
```bash
GET /api/news/?sentiment_min=7&has_sentiment=true&days=3&page_size=20
```

**Implementation:**
```javascript
// Fetch positive news
const response = await fetch('/api/news/?sentiment_min=7&has_sentiment=true&days=3&page_size=20');
const data = await response.json();

// Display in "Market Movers" or "Bullish News" section
data.results.forEach(article => {
  displayBullishNews({
    title: article.title,
    sentiment: article.sentiment_score,
    symbols: article.symbol_count,
    source: article.source,
    url: article.url
  });
});
```

---

### Use Case 4: News with Multi-Symbol Relationships

**Goal:** Show news that affects multiple stocks (e.g., industry news, partnerships).

**Endpoint:**
```bash
GET /api/news/?has_sentiment=true&page_size=20
```

**Filter Client-Side:**
```javascript
const response = await fetch('/api/news/?has_sentiment=true&page_size=20');
const data = await response.json();

// Filter for articles affecting multiple symbols
const multiSymbolNews = data.results.filter(article => article.symbol_count > 1);

// Display with "Affects X stocks" badge
multiSymbolNews.forEach(article => {
  displayMultiSymbolNews({
    title: article.title,
    affectedStocks: article.symbol_count,
    sentiment: article.sentiment_score,
    url: article.url
  });
});
```

---

### Use Case 5: Sentiment Distribution

**Goal:** Show sentiment distribution across recent news.

**Endpoint (Multiple Requests):**
```bash
GET /api/news/?sentiment_min=7&has_sentiment=true&days=7  # Positive
GET /api/news/?sentiment_min=4&sentiment_max=6&has_sentiment=true&days=7  # Neutral
GET /api/news/?sentiment_max=3&has_sentiment=true&days=7  # Negative
```

**Implementation:**
```javascript
// Fetch all sentiment categories
const [positive, neutral, negative] = await Promise.all([
  fetch('/api/news/?sentiment_min=7&has_sentiment=true&days=7').then(r => r.json()),
  fetch('/api/news/?sentiment_min=4&sentiment_max=6&has_sentiment=true&days=7').then(r => r.json()),
  fetch('/api/news/?sentiment_max=3&has_sentiment=true&days=7').then(r => r.json())
]);

// Display sentiment breakdown
displaySentimentChart({
  positive: positive.count,
  neutral: neutral.count,
  negative: negative.count
});
```

---

## Sentiment Score Guide

The sentiment analysis uses a 1-10 scale:

| Score Range | Label | Color | Meaning |
|------------|-------|-------|---------|
| 1-3 | Very Negative | 🔴 Red | Clear risks, harmful implications dominate |
| 4-6 | Neutral/Mixed | 🟡 Yellow | Balanced tone, uncertainty, or mixed signals |
| 7-10 | Positive | 🟢 Green | Favorable outlook, opportunity-focused |

**Justification Field:**
- Provides 1-3 sentences explaining WHY the score was assigned
- Highlights key factors from the article
- Useful for displaying on hover or in expanded view

**Description Field:**
- Provides 3 sentences summarizing the article's market impact
- Written from an investor's perspective
- Useful as article preview text

---

## Data Update Frequency

**News Fetching:**
- Automatic: Every 30 minutes during market hours (9 AM - 4 PM, weekdays)
- Manual: Via management command or when users request specific symbols

**Sentiment Analysis:**
- Automatic: Triggered immediately after new news is fetched
- Manual: Via `/api/news/analyze-sentiment/` endpoint
- Asynchronous: Runs in background via Celery workers

**Typical Latency:**
- News appears in API: Within seconds of fetching
- Sentiment analysis: 5-30 seconds after news is fetched (depends on queue)

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Both 'symbol' and 'exchange' parameters are required"
}
```

### 404 Not Found
```json
{
  "error": "Symbol AAPL not found on exchange NASDAQ"
}
```

### 404 Not Found (News Article)
```json
{
  "detail": "Not found."
}
```

---

## Pagination

All list endpoints support pagination:

**Request:**
```bash
GET /api/news/?page=2&page_size=20
```

**Response:**
```json
{
  "count": 156,
  "next": "http://your-domain.com/api/news/?page=3&page_size=20",
  "previous": "http://your-domain.com/api/news/?page=1&page_size=20",
  "results": [...]
}
```

**Fields:**
- `count`: Total number of results
- `next`: URL for next page (null if last page)
- `previous`: URL for previous page (null if first page)
- `results`: Array of news articles for current page

---

## Best Practices

### 1. Caching
```javascript
// Cache news data for 5 minutes
const CACHE_DURATION = 5 * 60 * 1000;
let newsCache = {
  data: null,
  timestamp: null
};

async function getNews() {
  const now = Date.now();
  if (newsCache.data && (now - newsCache.timestamp) < CACHE_DURATION) {
    return newsCache.data;
  }

  const response = await fetch('/api/news/?days=1&has_sentiment=true');
  newsCache.data = await response.json();
  newsCache.timestamp = now;
  return newsCache.data;
}
```

### 2. Error Handling
```javascript
async function fetchNews() {
  try {
    const response = await fetch('/api/news/?has_sentiment=true');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch news:', error);
    // Show user-friendly error message
    displayError('Unable to load news. Please try again later.');
    return { results: [] };
  }
}
```

### 3. Loading States
```javascript
function NewsComponent() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadNews() {
      setLoading(true);
      try {
        const data = await fetchNews();
        setNews(data.results);
      } finally {
        setLoading(false);
      }
    }
    loadNews();
  }, []);

  if (loading) return <LoadingSpinner />;
  return <NewsList articles={news} />;
}
```

### 4. Real-time Updates
```javascript
// Poll for new news every 5 minutes
setInterval(async () => {
  const latestNews = await fetch('/api/news/?page_size=5').then(r => r.json());
  updateNewsIfNew(latestNews.results);
}, 5 * 60 * 1000);
```

---

## UI/UX Recommendations

### News Card Design
```
┌─────────────────────────────────────────────┐
│ [Thumbnail]  Apple Announces New Product    │
│              Line                            │
│                                              │
│              Apple Inc. today unveiled a    │
│              new line of products...        │
│                                              │
│  [Reuters]   [Oct 11, 6:05 PM]             │
│  [🟢 8/10]   [2 stocks] [Read more →]      │
└─────────────────────────────────────────────┘
```

**Elements:**
1. **Thumbnail**: Article image (use `thumbnail_url`)
2. **Title**: Article headline (bold, 2-3 lines max)
3. **Snippet**: Preview text (gray, 3-4 lines max)
4. **Source**: News source name
5. **Date**: Published date (relative format: "2 hours ago")
6. **Sentiment Badge**: Color-coded score (green/yellow/red)
7. **Symbol Count**: "Affects X stocks" tag
8. **Link**: "Read more" or click entire card

### Sentiment Indicator Examples

**Badge Style:**
```css
.sentiment-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 12px;
}

.sentiment-positive {
  background: #d4edda;
  color: #155724;
}

.sentiment-neutral {
  background: #fff3cd;
  color: #856404;
}

.sentiment-negative {
  background: #f8d7da;
  color: #721c24;
}
```

**Icon Style:**
```
🟢 8/10  (Positive)
🟡 5/10  (Neutral)
🔴 2/10  (Negative)
```

---

## Testing

### Test Data
Use these parameters to get test data:

**Get news with sentiment:**
```bash
GET /api/news/?has_sentiment=true&page_size=5
```

**Get specific article:**
```bash
GET /api/news/1/
```

**Get news for AAPL:**
```bash
GET /api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ
```

### Fetch Test News
Run this command to populate with test data:
```bash
.venv/bin/python manage.py fetch_news --symbol AAPL --exchange NASDAQ --analyze
.venv/bin/python manage.py fetch_news --symbol GOOG --exchange NASDAQ --analyze
.venv/bin/python manage.py fetch_news --symbol MSFT --exchange NASDAQ --analyze
```

---

## Support

For questions or issues with the News API, contact the backend team or refer to:
- Main API Documentation: `/api/` (browsable API)
- Swagger/OpenAPI: (if available)
- GitHub Issues: (if applicable)

**Last Updated:** October 11, 2025
**API Version:** 1.0
