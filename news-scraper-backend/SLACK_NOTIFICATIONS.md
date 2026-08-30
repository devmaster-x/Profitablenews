# Slack Notifications Feature

## Overview

The Slack Notifications feature allows you to automatically send high-profit news alerts to your Slack channel. Articles with a profit score of 5.0 or higher can be sent to Slack, and the system tracks which articles have been sent to prevent duplicates.

## Features

- 🔔 **Automatic Duplicate Prevention**: Articles are marked as sent to avoid duplicate notifications
- 📊 **Score-Based Filtering**: Only high-profit articles (score ≥ 5.0) are sent
- 🎨 **Rich Formatting**: Messages use Slack Block Kit for beautiful, structured notifications
- 🔄 **Real-Time Status**: Check how many unsent articles are pending
- 🧪 **Test Mode**: Send test notifications to verify your webhook configuration
- 📈 **Batch Sending**: Automatically handles large volumes with 10-article batches
- ⚡ **Smart Limiting**: Respects Slack's 50-block limit per message

## Setup

### 1. Configure Slack Webhook

1. Go to your Slack workspace settings
2. Navigate to **Apps** → **Manage** → **Custom Integrations** → **Incoming Webhooks**
3. Create a new webhook for your desired channel
4. Copy the webhook URL (format: `https://hooks.slack.com/services/...`)

### 2. Add Webhook to Environment Variables

Edit your `.env` file in the backend directory:

```env
SLACK_NOTIFICATION_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 3. Restart the Backend

```bash
# Using uvicorn directly
uvicorn news_scraper.main:app --reload

# Or using Python module
python -m uvicorn news_scraper.main:app --reload
```

## API Endpoints

### Send Notifications

**POST** `/notifications/send`

Send all unsent high-profit articles to Slack.

**Query Parameters:**
- `min_score` (optional, default: 5.0): Minimum profit score to filter articles
- `limit` (optional, default: 10, max: 50): Maximum articles per notification

**Important**: Slack has a 50-block limit per message. Each article uses ~3 blocks, so the default limit is 10 articles per request. To send more articles, make multiple requests.

**Response:**
```json
{
  "success": true,
  "message": "Successfully sent 10 article(s) to Slack",
  "sent_count": 10,
  "article_ids": [1, 5, 8, 12, 15, 18, 22, 25, 28, 31]
}
```

**Examples:**
```bash
# Send up to 10 articles (default)
curl -X POST "http://localhost:8000/notifications/send?min_score=5.0"

# Send up to 5 articles
curl -X POST "http://localhost:8000/notifications/send?min_score=5.0&limit=5"

# Send high-priority articles only (score >= 8.0)
curl -X POST "http://localhost:8000/notifications/send?min_score=8.0&limit=10"
```

### Check Status

**GET** `/notifications/status`

Check how many high-profit articles are pending notification.

**Query Parameters:**
- `min_score` (optional, default: 5.0): Minimum profit score to filter articles

**Response:**
```json
{
  "total_unsent": 3,
  "min_score": 5.0,
  "articles": [
    {
      "id": 1,
      "title": "Major Tech Acquisition Announced",
      "url": "https://example.com/article",
      "profit_score": 8.5,
      "source": "TechCrunch",
      "category": "market",
      "sentiment": "very_positive"
    }
  ]
}
```

### Test Notification

**POST** `/notifications/test`

Send a test notification to verify webhook configuration.

**Response:**
```json
{
  "success": true,
  "message": "Successfully sent 1 article(s) to Slack (Test)",
  "is_test": true
}
```

### Reset Notification Status

**POST** `/notifications/reset`

Reset notification status for specific articles to allow re-sending.

**Request Body:**
```json
{
  "article_ids": [1, 2, 3]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Reset notification status for 3 article(s)",
  "article_ids": [1, 2, 3]
}
```

## Frontend UI

### Slack Notifications Tab

The frontend includes a dedicated "Slack Notifications" tab with:

1. **Pending Counter**: Shows how many unsent high-profit articles are available
2. **Send Button**: Sends all pending articles to Slack
3. **Test Button**: Sends a test notification to verify configuration
4. **Pending Articles List**: Preview of articles that will be sent
5. **Auto-Refresh**: Status updates every 30 seconds

### How to Use

1. Navigate to the **Slack Notifications** tab in the dashboard
2. Review the pending articles list
3. Click **"Send to Slack"** to send all pending notifications
4. Click **"Test Notification"** to verify your Slack webhook is working

## Database Schema

The feature adds a new column to the `articles` table:

```sql
ALTER TABLE articles ADD COLUMN slack_notified INTEGER DEFAULT 0;
```

- `slack_notified = 0`: Article has not been sent
- `slack_notified = 1`: Article has been sent to Slack

The migration runs automatically when the backend starts.

## Slack Message Format

Notifications are sent with the following structure:

### Header
- Title: "🚀 High-Profit News Alerts"
- Summary: Count of articles being sent

### Each Article
- **Title**: Clickable link to the article (if URL available)
- **Profit Score**: Displayed with emoji indicators
  - 🔥 Score ≥ 9.0
  - ⭐ Score ≥ 8.0
  - 📈 Score ≥ 7.0
  - 💡 Score ≥ 6.0
  - 📊 Score ≥ 5.0
- **Source**: News source name
- **Category**: Article category
- **Sentiment**: Formatted with emoji (if available)

### Footer
- Timestamp of when the notification was sent (UTC)

## Error Handling

The system gracefully handles various error scenarios:

- **No Webhook Configured**: Returns error message
- **Network Errors**: Returns descriptive error about connection issues
- **Slack API Errors**: Returns status code from Slack
- **No Articles to Send**: Returns success with 0 sent count

## Best Practices

1. **Test First**: Always use the test endpoint before sending real notifications
2. **Monitor Status**: Regularly check the notifications status to avoid backlogs
3. **Adjust Threshold**: Modify `min_score` parameter to control notification volume
4. **Webhook Security**: Keep your webhook URL secret and never commit it to version control

## Troubleshooting

### Webhook Not Working

1. Verify the webhook URL is correct in `.env`
2. Test the webhook directly using curl:
   ```bash
   curl -X POST -H 'Content-Type: application/json' \
     -d '{"text":"Test from News Scraper"}' \
     YOUR_WEBHOOK_URL
   ```
3. Check if the Slack app is still installed in your workspace

### "invalid_blocks" Error

This occurs when trying to send too many articles at once. Slack has a **50-block limit** per message.

**Solution**: The system automatically limits to 10 articles per request. If you have many pending articles:
- Send in batches using the `limit` parameter
- Or use the frontend "Send All" button which handles batching automatically

```bash
# Send 10 at a time
curl -X POST "http://localhost:8000/notifications/send?limit=10"
curl -X POST "http://localhost:8000/notifications/send?limit=10"  # Send next 10
```

### Articles Not Being Marked as Sent

1. Check database permissions
2. Verify the `slack_notified` column exists:
   ```bash
   sqlite3 news_scraper.db "PRAGMA table_info(articles);"
   ```
3. Check backend logs for errors

### No Articles Showing in Status

1. Ensure articles have `profit_score >= 5.0`
2. Check if articles have already been sent:
   ```bash
   sqlite3 news_scraper.db "SELECT COUNT(*) FROM articles WHERE slack_notified = 1;"
   ```

## Future Enhancements

Potential improvements for this feature:

- [ ] Schedule automatic notifications (e.g., daily digest)
- [ ] Multiple webhook support for different channels
- [ ] Custom message templates
- [ ] Notification history/logs
- [ ] Slack thread replies for article updates
- [ ] @mention support for high-priority alerts
- [ ] Category-specific channels

## API Integration Examples

### Python
```python
import requests

# Send notifications
response = requests.post(
    "http://localhost:8000/notifications/send",
    params={"min_score": 6.0}
)
print(response.json())

# Check status
response = requests.get(
    "http://localhost:8000/notifications/status",
    params={"min_score": 5.0}
)
print(response.json())
```

### JavaScript
```javascript
// Send notifications
const sendNotifications = async () => {
  const response = await fetch(
    'http://localhost:8000/notifications/send?min_score=5.0',
    { method: 'POST' }
  );
  const data = await response.json();
  console.log(data);
};

// Check status
const checkStatus = async () => {
  const response = await fetch(
    'http://localhost:8000/notifications/status?min_score=5.0'
  );
  const data = await response.json();
  console.log(data);
};
```

### cURL
```bash
# Send notifications
curl -X POST "http://localhost:8000/notifications/send?min_score=5.0"

# Check status
curl "http://localhost:8000/notifications/status?min_score=5.0"

# Test notification
curl -X POST "http://localhost:8000/notifications/test"

# Reset articles
curl -X POST "http://localhost:8000/notifications/reset" \
  -H "Content-Type: application/json" \
  -d '{"article_ids": [1, 2, 3]}'
```
