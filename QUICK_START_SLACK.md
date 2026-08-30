# Quick Start: Slack Notifications

## 🚀 Get Started in 3 Steps

### Step 1: Verify Configuration ✅

Your Slack webhook is already configured in the backend `.env` file:
```env
SLACK_NOTIFICATION_WEBHOOK=https://hooks.slack.com/services/XXXXXXXXX/XXXXXXXXX/XXXXXXXXXXXXXXXX
```

### Step 2: Restart the Backend 🔄

```bash
cd news-scraper-backend
uvicorn news_scraper.main:app --reload
```

Or with Python:
```bash
cd news-scraper-backend
python -m uvicorn news_scraper.main:app --reload
```

### Step 3: Use the Feature 🎉

#### Option A: Using the Web UI (Recommended)

1. Open your browser to the frontend (usually `http://localhost:5173`)
2. Click on the **"Slack Notifications"** tab
3. Click **"Test Notification"** to verify setup
4. Click **"Send to Slack"** to send real high-profit articles

#### Option B: Using the API

**Test the connection:**
```bash
curl -X POST http://localhost:8000/notifications/test
```

**Check what's pending:**
```bash
curl http://localhost:8000/notifications/status?min_score=5.0
```

**Send notifications:**
```bash
curl -X POST http://localhost:8000/notifications/send?min_score=5.0
```

## 📋 What Gets Sent?

- Articles with **profit_score ≥ 5.0**
- Only **unsent** articles (duplicates prevented automatically)
- **Rich formatting** with emojis, links, and metadata
- **Batch messages** (multiple articles in one notification)

## 🎨 Message Format

Each notification includes:
- 🚀 Header with article count
- 📰 Article titles (clickable links)
- ⭐ Profit scores with emoji indicators
- 🏢 Source and category
- 😊 Sentiment (if available)
- 🕒 Timestamp

## 🔧 Troubleshooting

### Backend won't start?
```bash
# Check Python syntax
cd news-scraper-backend
python -m py_compile news_scraper/slack_notifier.py

# Check dependencies
pip install fastapi uvicorn pydantic pydantic-settings
```

### Frontend won't compile?
```bash
cd news-scraper-frontend
npm install
npm run dev
```

### Slack not receiving messages?
1. Test the webhook directly:
```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"text":"Test"}' \
  https://hooks.slack.com/services/XXXXXXXXX/XXXXXXXXX/XXXXXXXXXXXXXXXX
```

2. Check if webhook is still active in Slack settings
3. Verify the webhook URL has no extra spaces or line breaks

### No pending articles?
- Scrape some news first (click "Refresh Data" in the UI)
- Check if articles have high enough scores:
```bash
sqlite3 news_scraper.db "SELECT COUNT(*) FROM articles WHERE profit_score >= 5.0;"
```

## 📊 Database Changes

The system automatically adds a `slack_notified` column to track sent articles. No manual SQL needed!

**Check what's been sent:**
```bash
sqlite3 news_scraper.db "SELECT id, title, slack_notified FROM articles WHERE profit_score >= 5.0 LIMIT 10;"
```

## 🎯 Use Cases

### Daily Morning Digest
1. Scrape news overnight (use scheduler)
2. Morning: Open "Slack Notifications" tab
3. Review pending high-profit articles
4. Send to team Slack channel

### Real-Time Alerts
Set up a cron job or hook to automatically send:
```bash
# Every hour, send unsent articles with score >= 7.0
0 * * * * curl -X POST "http://localhost:8000/notifications/send?min_score=7.0"
```

### Custom Threshold
```bash
# Only ultra-high profit articles (score >= 8.0)
curl -X POST "http://localhost:8000/notifications/send?min_score=8.0"
```

## 📚 Full Documentation

For complete details, see:
- `SLACK_NOTIFICATIONS.md` - Complete API reference and features
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details

## ✨ Features Summary

- ✅ Duplicate prevention (tracked in database)
- ✅ Score-based filtering (configurable threshold)
- ✅ Rich Slack formatting (Block Kit)
- ✅ Batch sending (multiple articles per message)
- ✅ Test mode (verify configuration)
- ✅ Real-time status (auto-refresh UI)
- ✅ Error handling (network, API errors)
- ✅ Preview mode (see before sending)

## 🎉 That's It!

You're all set! Just restart the backend and start sending notifications to Slack.

**Happy alerting! 🚀**
