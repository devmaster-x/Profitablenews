# Slack Notifications - Quick Reference Card

## 🚀 Quick Commands

### Send Notifications
```bash
# Default: Send 10 articles
curl -X POST "http://localhost:8000/notifications/send"

# Custom batch size
curl -X POST "http://localhost:8000/notifications/send?limit=5"

# High priority only (score >= 8)
curl -X POST "http://localhost:8000/notifications/send?min_score=8.0"
```

### Check Status
```bash
# See pending articles
curl "http://localhost:8000/notifications/status"
```

### Test Setup
```bash
# Verify webhook works
curl -X POST "http://localhost:8000/notifications/test"
```

## 📊 Key Limits

| Limit | Value | Reason |
|-------|-------|--------|
| Articles per message | **10** | Slack's 50-block limit |
| Min score default | **5.0** | Configurable |
| Max batch size | **50** | API protection |
| Blocks per message | **50** | Slack constraint |

## ⚡ Common Scenarios

### Scenario 1: Send Daily Digest
```bash
# Run every morning at 9 AM
0 9 * * * curl -X POST "http://localhost:8000/notifications/send?limit=10"
```

### Scenario 2: Real-Time High-Priority Alerts
```bash
# Every 15 minutes, ultra-high scores only
*/15 * * * * curl -X POST "http://localhost:8000/notifications/send?min_score=9.0&limit=5"
```

### Scenario 3: Clear Large Backlog
```bash
# Send 10 every 5 minutes until cleared
*/5 * * * * curl -X POST "http://localhost:8000/notifications/send?limit=10"
```

### Scenario 4: Category-Specific Alerts
```bash
# Frontend: Filter by category in articles view first
# Then send from Slack Notifications tab
```

## 🎯 Frontend UI

### Location
Dashboard → **Slack Notifications** tab

### Actions
- **Send [N]**: Send next batch (up to 10)
- **Send All**: Send all pending articles in batches
- **Test Notification**: Verify webhook setup

### Indicators
- 🔴 **Red badge**: Articles pending
- ⚠️ **Warning**: More than 10 pending
- ✅ **Green check**: All sent

## 🔧 Troubleshooting

### Problem: 400 Bad Request
**Cause**: Too many articles  
**Fix**: Automatically limited to 10

### Problem: No articles sent
**Check**: 
1. Webhook configured?
2. Articles have score >= 5.0?
3. Already sent? (slack_notified=1)

### Problem: Articles already sent
**Fix**: 
```bash
# Reset specific articles (via API)
curl -X POST "http://localhost:8000/notifications/reset" \
  -H "Content-Type: application/json" \
  -d '{"article_ids": [1, 2, 3]}'
```

## 📝 Article Status

```sql
-- Check pending
SELECT COUNT(*) FROM articles 
WHERE profit_score >= 5.0 AND slack_notified = 0;

-- Check sent
SELECT COUNT(*) FROM articles 
WHERE slack_notified = 1;

-- View top pending
SELECT id, title, profit_score 
FROM articles 
WHERE profit_score >= 5.0 AND slack_notified = 0 
ORDER BY profit_score DESC 
LIMIT 10;
```

## 🎨 Message Format

Each notification includes:
- 🚀 Header: "High-Profit News Alerts"
- 📊 Count: Number of articles
- Per article:
  - 📰 Title (clickable link)
  - ⭐ Score with emoji (🔥≥9, ⭐≥8, 📈≥7, 💡≥6, 📊≥5)
  - 🏢 Source
  - 🗂️ Category
  - 😊 Sentiment (if available)
- 🕒 Timestamp footer

## 🔐 Security

### Protect Your Webhook
```bash
# ✅ DO: Store in .env
SLACK_NOTIFICATION_WEBHOOK=https://hooks.slack.com/services/...

# ❌ DON'T: Commit to git
# .env should be in .gitignore

# ❌ DON'T: Share publicly
# Rotate if exposed
```

### Verify Webhook
```bash
# Test directly
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"text":"Test message"}'
```

## 📱 Integration Examples

### Python Script
```python
import requests

def send_notifications(min_score=5.0, limit=10):
    response = requests.post(
        f"http://localhost:8000/notifications/send",
        params={"min_score": min_score, "limit": limit}
    )
    return response.json()

# Usage
result = send_notifications(min_score=7.0, limit=5)
print(f"Sent {result['sent_count']} articles")
```

### JavaScript/Node
```javascript
async function sendNotifications(minScore = 5.0, limit = 10) {
  const response = await fetch(
    `http://localhost:8000/notifications/send?min_score=${minScore}&limit=${limit}`,
    { method: 'POST' }
  );
  return await response.json();
}

// Usage
const result = await sendNotifications(7.0, 5);
console.log(`Sent ${result.sent_count} articles`);
```

### Bash Loop (Send All)
```bash
#!/bin/bash
# send_all_notifications.sh

while true; do
  result=$(curl -s -X POST "http://localhost:8000/notifications/send?limit=10")
  count=$(echo $result | jq -r '.sent_count')
  
  echo "Sent $count articles"
  
  if [ "$count" -eq 0 ]; then
    echo "All articles sent!"
    break
  fi
  
  sleep 2  # Rate limit
done
```

## 🎯 Best Practices

1. **Start Small**: Test with 1-2 articles first
2. **Use Test Endpoint**: Verify setup before real sends
3. **Monitor Pending**: Check status regularly
4. **Batch Wisely**: 10 articles is optimal
5. **Set Thresholds**: Use min_score to filter
6. **Rate Limit**: Wait between batches
7. **Check Slack**: Verify messages look good
8. **Track Sent**: Monitor slack_notified in DB

## 📚 Additional Resources

- **Full Documentation**: `SLACK_NOTIFICATIONS.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
- **Fix Details**: `FIX_SUMMARY.md`
- **Architecture**: `ARCHITECTURE_DIAGRAM.txt`

## 🆘 Support

### Check Logs
```bash
# Backend logs
uvicorn news_scraper.main:app --log-level debug

# Database check
sqlite3 news_scraper.db "SELECT * FROM articles WHERE slack_notified = 0 LIMIT 5;"
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Webhook 404 | Verify URL in .env |
| No pending articles | Lower min_score or scrape news |
| Already sent | Normal - duplicates prevented |
| 400 error | Fixed automatically (10-article limit) |
| Timeout | Check network/webhook URL |

---

## 🎉 That's It!

**Remember**: The system automatically limits to 10 articles per message to respect Slack's constraints. For large volumes, send multiple batches!

**Happy alerting! 🚀**
