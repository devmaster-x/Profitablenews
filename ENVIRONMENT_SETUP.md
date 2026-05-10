# Environment Setup Guide

## Backend Environment Variables

The backend uses Pydantic Settings for configuration. Create a `.env` file in the `news-scraper-backend/` directory:

```bash
# Environment Configuration
ENVIRONMENT=development

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

# Scraping Configuration
SCRAPING_TIMEOUT=30
MAX_ARTICLES_PER_SOURCE=50

# Scheduler Configuration
DEFAULT_SCRAPING_TIME=00:00
SCHEDULER_CHECK_INTERVAL=60

# CORS Configuration
CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173", "*"]
CORS_CREDENTIALS=true

# Logging Configuration
LOG_LEVEL=INFO

# Chrome/Selenium Configuration
CHROME_HEADLESS=true
CHROME_NO_SANDBOX=true
CHROME_DISABLE_DEV_SHM=true
CHROME_DISABLE_GPU=true
CHROME_WINDOW_SIZE=1920,1080

# User Agent
USER_AGENT=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
```

## Frontend Environment Variables

The frontend uses Vite environment variables. Create a `.env` file in the `news-scraper-frontend/` directory:

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000

# App Configuration
VITE_APP_NAME=News Scraper Dashboard
VITE_APP_VERSION=1.0.0

# Feature Flags
VITE_ENABLE_REAL_TIME_UPDATES=true
VITE_ENABLE_PROFIT_ANALYSIS=true
VITE_ENABLE_MARKET_TRENDS=true
```

## System Requirements

### Backend Requirements
- Python 3.12+
- Poetry (for dependency management)
- Chrome/Chromium browser (for Selenium web scraping)
- ChromeDriver (automatically managed by Selenium)

### Frontend Requirements
- Node.js 18+
- npm or yarn

## Installation Steps

### 1. Backend Setup
```bash
cd news-scraper-backend

# Install dependencies
poetry install

# Create .env file (see above)
# Run the application
poetry run python -m app.main
```

### 2. Frontend Setup
```bash
cd news-scraper-frontend

# Install dependencies
npm install

# Create .env file (see above)
# Run the development server
npm run dev
```

## Default Configuration

### Backend Defaults
- **Host**: 0.0.0.0 (accessible from any IP)
- **Port**: 8000
- **Database**: In-memory SQLite (no setup required)
- **Scraping**: Daily at 00:00 (midnight)
- **CORS**: Allows all origins (development)

### Frontend Defaults
- **Port**: 5173 (Vite default)
- **API URL**: http://localhost:8000
- **Hot Reload**: Enabled

## Production Configuration

For production deployment, update the environment variables:

### Backend Production
```bash
ENVIRONMENT=production
API_DEBUG=false
CORS_ORIGINS=["https://yourdomain.com"]
CHROME_HEADLESS=true
```

### Frontend Production
```bash
VITE_API_BASE_URL=https://api.yourdomain.com
```

## Troubleshooting

### Common Issues

1. **Chrome/Selenium Issues**
   - Ensure Chrome is installed
   - Check ChromeDriver compatibility
   - Try setting `CHROME_HEADLESS=false` for debugging

2. **CORS Issues**
   - Verify CORS_ORIGINS includes your frontend URL
   - Check that CORS_CREDENTIALS matches your setup

3. **Port Conflicts**
   - Change API_PORT if 8000 is in use
   - Change frontend port with `npm run dev -- --port 3001`

4. **Scraping Failures**
   - Check internet connectivity
   - Verify news source URLs are accessible
   - Review logs for specific error messages

### Logging

- Backend logs are available in the console
- Set `LOG_LEVEL=DEBUG` for detailed logging
- Frontend errors appear in browser console

## Security Notes

- **Development**: CORS allows all origins for easy development
- **Production**: Restrict CORS_ORIGINS to specific domains
- **API Keys**: No external API keys required (all scraping is public)
- **Database**: In-memory storage (data is lost on restart) 