# News Scraper System

A comprehensive news scraping and analysis system to identify market and software development news that can generate financial profits.

## Project Structure

```
news-scraper/
├── news-scraper-backend/     # FastAPI backend with web scraping
├── news-scraper-frontend/    # React frontend dashboard
└── README.md                 # This file
```

## Features

- **Daily News Scraping**: Automated scraping at 0 AM daily from worldwide sources
- **Data Categorization**: Separate and store news by market/software/crypto categories
- **Advanced Profit Analysis**: Enhanced sentiment analysis and profit opportunity scoring (0-10 scale)
- **Web Dashboard**: React UI to browse, filter, and analyze scraped data
- **Real-time Updates**: Live monitoring and alerts for high-potential opportunities
- **Profit Opportunities**: Identify high-scoring investment opportunities
- **Market Trends**: Track category-specific trends and market movements
- **Company Mentions**: Monitor major tech companies and their profit potential
- **Profit Alerts**: High-priority notifications for exceptional opportunities
- **Enhanced News Sources**: 10+ major financial and tech news sources

## Quick Start

### Backend
```bash
cd news-scraper-backend
poetry run fastapi dev app/main.py
```

### Frontend
```bash
cd news-scraper-frontend
npm run dev
```

## Technology Stack

- **Backend**: FastAPI, Python, Selenium (web scraping), SQLite (in-memory)
- **Frontend**: React, TypeScript, Tailwind CSS, shadcn/ui, Recharts
- **Deployment**: Fly.io (backend), Static hosting (frontend)

## Enhanced Profit Analysis Features

### 🎯 **Profit Opportunities**
- **Smart Scoring**: AI-powered profit potential scoring (0-10 scale)
- **Category Analysis**: Different scoring weights for market, software, crypto, startup, and investment news
- **Company Recognition**: Automatic detection and scoring of major tech companies
- **Keyword Analysis**: 50+ profit-related keywords with weighted scoring
- **Time Sensitivity**: Breaking news and exclusive content get higher scores

### 📊 **Market Trends**
- **Category Trends**: Track profit score trends by category
- **Confidence Scoring**: Statistical confidence in trend predictions
- **Historical Analysis**: Compare recent vs. historical performance
- **Visual Charts**: Interactive trend visualization

### 🚨 **Profit Alerts**
- **Configurable Thresholds**: Set custom alert levels (default: 8.0+ score)
- **Urgency Levels**: High/Medium priority based on profit score
- **Real-time Notifications**: Immediate alerts for exceptional opportunities
- **Source Tracking**: Track which sources generate the most alerts

### 🏢 **Company Mentions**
- **Major Company Tracking**: Monitor 30+ major tech companies
- **Mention Analysis**: Count and analyze company mentions
- **Profit Correlation**: Average profit scores for company-related news
- **Trend Identification**: Identify which companies are trending

### 📰 **Enhanced News Sources**
- **TechCrunch**: Startup and tech innovation news
- **Hacker News**: Software development and tech trends
- **CoinDesk**: Cryptocurrency and blockchain news
- **Reuters Tech**: Market and technology news
- **Yahoo Finance**: Financial market news
- **CNBC Tech**: Technology and market analysis
- **VentureBeat**: Startup and venture capital news
- **Cointelegraph**: Cryptocurrency and blockchain
- **TechRadar**: Technology news and reviews
- **Seeking Alpha**: Investment analysis and opportunities

### 🔍 **Advanced Filtering**
- **Profit Score Filtering**: Filter by minimum profit score
- **Category Filtering**: Filter by news category
- **Sentiment Filtering**: Filter by sentiment analysis
- **Search Functionality**: Full-text search across titles and content
- **Date Range Filtering**: Filter by publication date
