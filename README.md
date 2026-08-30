# Web3 News Scraper

Scrapes Web3 news from 14 sources with intelligent profit scoring.

## Quick Start

**Windows:**
```bash
start.bat        # Start everything
stop-all.bat     # Stop everything
```

**Manual:**
```bash
# Backend
cd news-scraper-backend
poetry install
poetry run fastapi dev app/main.py

# Frontend (new terminal)
cd news-scraper-frontend
pnpm install
pnpm dev --host
```

## Access

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## What It Tracks

**11 Web3 Sources**: CoinDesk, Cointelegraph, Decrypt, The Block, The Defiant, Bitcoin Magazine, Ethereum Foundation, Blockworks, NFT Now, Bankless, and more.

**200+ Keywords**: Bitcoin, Ethereum, Solana, DeFi protocols, Layer 2s, NFTs, DAOs, etc.

**13 Categories**: CRYPTO, BLOCKCHAIN, WEB3, DEFI, NFT, DAO, AI_ML, INVESTMENT, STARTUP, SOFTWARE, MARKET, TECH_EARNINGS, GENERAL

**Profit Scoring**: 0-10 scale based on Web3 keywords, market impact, and time sensitivity.

## API Examples

```bash
# Trigger scrape
curl -X POST http://localhost:8000/scrape

# Get high-profit articles (score > 7.0)
curl http://localhost:8000/articles/high-profit

# Get DeFi articles
curl http://localhost:8000/articles/category/defi
```

## Configuration

Edit `.env` files in backend/frontend folders.

## Troubleshooting

- Port in use? Run `stop-all.bat` first
- Missing dependencies? Run `start.bat` (auto-installs)
- Need Poetry? https://python-poetry.org/docs/#installation
- Need pnpm? Run `npm install -g pnpm`

---

**Version**: 2.0 (Web3 Enhanced)
