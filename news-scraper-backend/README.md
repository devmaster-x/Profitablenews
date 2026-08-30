# News Scraper Backend

FastAPI backend for Web3 news scraping.

## Setup

```bash
poetry install
poetry run fastapi dev news_scraper/main.py
```

## API

- GET `/articles` - All articles
- GET `/articles/high-profit` - High-scoring articles (>7.0)
- GET `/articles/category/{category}` - Filter by category
- POST `/scrape` - Trigger manual scrape
- Docs: http://localhost:8000/docs

## Web3 Features

- **14 sources**: CoinDesk, Cointelegraph, Decrypt, The Block, etc.
- **200+ keywords**: Bitcoin, Ethereum, DeFi, NFTs, Layer 2s
- **13 categories**: CRYPTO, DEFI, NFT, WEB3, DAO, etc.
- **Profit scoring**: 0-10 scale based on Web3 relevance

## Config

Edit `.env` file for settings.