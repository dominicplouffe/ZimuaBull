# News API - Quick Reference

## Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/news/` | GET | List all news with filtering |
| `/api/news/{id}/` | GET | Get single article details |
| `/api/news/by-symbol/` | GET | Get news for specific symbol |
| `/api/news/analyze-sentiment/` | POST | Trigger sentiment analysis |

---

## Quick Examples

### Home Page: Latest News
```bash
GET /api/news/?days=1&has_sentiment=true&page_size=10
```

### Symbol Page: News for AAPL
```bash
GET /api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ&limit=5
```

### Positive News Only
```bash
GET /api/news/?sentiment_min=7&has_sentiment=true&days=3
```

### Negative News Only
```bash
GET /api/news/?sentiment_max=3&has_sentiment=true&days=3
```

### News Affecting Multiple Stocks
```bash
GET /api/news/?has_sentiment=true
# Filter client-side for symbol_count > 1
```

---

## Response Format

### List View (Lightweight)
```json
{
  "id": 123,
  "title": "Article Title",
  "snippet": "Summary...",
  "source": "Reuters",
  "published_date": "2025-10-11T18:05:18Z",
  "thumbnail_url": "https://...",
  "sentiment_score": 8,
  "symbol_count": 2
}
```

### Detail View (Full)
```json
{
  "id": 123,
  "title": "Article Title",
  "snippet": "Summary...",
  "sentiment": {
    "sentiment_score": 8,
    "justification": "Why this score...",
    "description": "Market impact summary..."
  },
  "symbols": [
    {"symbol": "AAPL", "exchange": "NASDAQ", "is_primary": true}
  ]
}
```

---

## Sentiment Scale

| Score | Label | Color | Icon |
|-------|-------|-------|------|
| 1-3 | Very Negative | Red | 🔴 |
| 4-6 | Neutral/Mixed | Yellow | 🟡 |
| 7-10 | Positive | Green | 🟢 |

---

## Common Filters

| Filter | Parameter | Example |
|--------|-----------|---------|
| Last N days | `days=N` | `days=3` |
| Has sentiment | `has_sentiment=true` | |
| Positive news | `sentiment_min=7` | |
| Negative news | `sentiment_max=3` | |
| Specific symbol | `symbol=AAPL&exchange=NASDAQ` | |
| Results per page | `page_size=20` | `page_size=20` |

---

## Integration Checklist

- [ ] Display news on home page (last 24 hours)
- [ ] Display news on symbol detail page (symbol-specific)
- [ ] Show sentiment as color-coded badge
- [ ] Show "Affects X stocks" tag
- [ ] Link to full article (opens in new tab)
- [ ] Show relative timestamps ("2 hours ago")
- [ ] Handle pagination for "Load More"
- [ ] Show loading states
- [ ] Handle errors gracefully
- [ ] Cache data for 5 minutes

---

## Sample UI Code

### React Component
```jsx
function NewsFeed() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/news/?days=1&has_sentiment=true&page_size=10')
      .then(res => res.json())
      .then(data => {
        setNews(data.results);
        setLoading(false);
      });
  }, []);

  if (loading) return <Spinner />;

  return (
    <div className="news-feed">
      {news.map(article => (
        <NewsCard key={article.id} article={article} />
      ))}
    </div>
  );
}

function NewsCard({ article }) {
  const sentimentColor =
    article.sentiment_score >= 7 ? 'green' :
    article.sentiment_score <= 3 ? 'red' : 'yellow';

  return (
    <div className="news-card">
      <img src={article.thumbnail_url} alt="" />
      <h3>{article.title}</h3>
      <p>{article.snippet}</p>
      <div className="meta">
        <span className="source">{article.source}</span>
        <span className={`sentiment ${sentimentColor}`}>
          {article.sentiment_score}/10
        </span>
        <span className="symbols">{article.symbol_count} stocks</span>
      </div>
      <a href={article.url} target="_blank">Read more →</a>
    </div>
  );
}
```

---

## Testing URLs

**Local Development:**
```
http://localhost:8000/api/news/?has_sentiment=true&page_size=5
http://localhost:8000/api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ
```

**Production:**
```
https://zimua.dplouffe.ca/api/news/?has_sentiment=true&page_size=5
https://zimua.dplouffe.ca/api/news/by-symbol/?symbol=AAPL&exchange=NASDAQ
```

---

## Need Help?

- Full Documentation: [NEWS_API_DOCUMENTATION.md](./NEWS_API_DOCUMENTATION.md)
- Backend Team: [Contact Info]
- Test Data Command: `.venv/bin/python manage.py fetch_news --symbol AAPL --exchange NASDAQ --analyze`
