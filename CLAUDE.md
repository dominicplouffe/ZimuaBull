# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZimuaBull is a Django-based financial analysis application that tracks and analyzes stock market data. It features multiple Django apps:

- **zimuabull**: Core stock analysis with models for exchanges, symbols, daily data, and predictions
- **core**: Django project configuration and main settings

## Architecture

### Stock Analysis Pipeline
The application uses a scanner-based architecture for data collection:
- `zimuabull/scanners/tse.py`: TSE (Toronto Stock Exchange) scanner for fetching stock data
- `zimuabull/tasks/scan.py`: Celery task that orchestrates the scanning process
- Data flows: External APIs → Scanners → Models → REST API → Frontend

### Data Models
Key models in `zimuabull/models.py`:
- **Exchange**: Stock exchanges with country information
- **Symbol**: Stock symbols linked to exchanges, includes technical indicators (OBV status, close trends, accuracy)
- **DaySymbol**: Daily stock data with OHLCV and technical analysis fields
- **DayPrediction**: Trading predictions with buy/sell prices and sentiment
- **Favorite**: User favorites for symbols

### Background Processing
- Uses Celery with Redis as broker for background tasks
- Scheduled tasks in `core/settings.py` CELERY_BEAT_SCHEDULE:
  - Stock scanning daily at 3:05 AM
- Queue name: "pidashtasks"

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Run development server
python manage.py runserver

# Django admin
python manage.py createsuperuser
```

### Background Tasks
```bash
# Start Celery worker (requires Redis running)
celery -A core worker -l info -Q pidashtasks

# Start Celery beat scheduler
celery -A core beat -l info
```

### Docker Deployment
```bash
# Build and run with Docker Compose
cd docker
docker-compose up --build
```

## API Endpoints

The application exposes REST API endpoints via Django REST Framework:
- `/api/symbols/`: Symbol CRUD operations
- `/api/daysymbols/`: Daily stock data with filtering by symbol
- `/api/daypredictions/`: Trading predictions with filtering
- `/api/favorites/`: User favorites management (requires authentication)

Key filtering capabilities:
- Filter by symbol: `?symbol__symbol=AAPL`
- Order by date: `?ordering=date`

## Technical Configuration

### Environment Variables
- `ENV`: Set to "prod" for production mode
- `DEBUG`: Controls Django debug mode (currently hardcoded to True)
- `CELERY_BROKER_URL`: Redis URL for Celery (default: redis://localhost:6379)
- `TRUSTED_ORIGIN`: CSRF trusted origins

### Database
- Uses SQLite in development (`db.sqlite3`)
- Production database path: `../db.sqlite3/db.sqlite3`

### CORS Configuration
- Allows React frontend on localhost:3001
- Production URL: https://zimua.dplouffe.ca
- Full CORS configuration for cross-origin requests

## File Structure Notes

- Settings are in `core/settings.py` with comprehensive Celery and CORS configuration
- Main Django app logic in `zimuabull/` directory
- Scanner implementations in `zimuabull/scanners/`
- Background tasks in `zimuabull/tasks/`
- Docker configuration in `docker/` directory