"""Slack notification utility for high-profit news alerts."""

from __future__ import annotations

import json
from typing import Dict, List, Any, Optional
import urllib.request
import urllib.error
from datetime import datetime

from news_scraper.config import settings


class SlackNotifier:
    """Send formatted news notifications to Slack."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.slack_notification_webhook

    def send_notification(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send a batch of high-profit articles to Slack.

        Args:
            articles: List of article dicts with keys: id, title, url, profit_score, etc.
                     Limited to max 10 articles per message due to Slack block limits.

        Returns:
            Dict with success status and message
        """
        if not self.webhook_url:
            return {
                "success": False,
                "message": "Slack webhook URL not configured",
                "sent_count": 0
            }

        if not articles:
            return {
                "success": False,
                "message": "No articles to send",
                "sent_count": 0
            }

        # Slack has a limit of 50 blocks per message
        # Each article takes ~3 blocks, so limit to 10 articles to be safe
        MAX_ARTICLES_PER_MESSAGE = 10
        if len(articles) > MAX_ARTICLES_PER_MESSAGE:
            articles = articles[:MAX_ARTICLES_PER_MESSAGE]

        try:
            # Build Slack message payload
            blocks = self._build_message_blocks(articles)
            payload = {
                "blocks": blocks,
                "text": f"🔔 {len(articles)} High-Profit News Alert(s)"
            }

            # Send to Slack
            data = json.dumps(payload).encode('utf-8')
            request = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    return {
                        "success": True,
                        "message": f"Successfully sent {len(articles)} article(s) to Slack",
                        "sent_count": len(articles)
                    }
                else:
                    response_body = response.read().decode('utf-8')
                    return {
                        "success": False,
                        "message": f"Slack API returned status {response.status}: {response_body}",
                        "sent_count": 0
                    }

        except urllib.error.HTTPError as e:
            # HTTP errors (400, 500, etc.)
            error_body = ""
            try:
                error_body = e.read().decode('utf-8')
            except (OSError, UnicodeDecodeError):
                pass
            return {
                "success": False,
                "message": f"HTTP Error {e.code}: {e.reason}. Details: {error_body}",
                "sent_count": 0
            }
        except urllib.error.URLError as e:
            return {
                "success": False,
                "message": f"Network error: {str(e)}",
                "sent_count": 0
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to send notification: {str(e)}",
                "sent_count": 0
            }

    def _build_message_blocks(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build Slack Block Kit message blocks for the articles."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 High-Profit News Alerts",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{len(articles)}* high-scoring news article(s) detected (Score ≥ 5.0)"
                }
            },
            {
                "type": "divider"
            }
        ]

        # Add each article
        for idx, article in enumerate(articles, 1):
            article_blocks = self._build_article_block(article, idx)
            blocks.extend(article_blocks)

            # Add divider between articles (but not after the last one)
            if idx < len(articles):
                blocks.append({"type": "divider"})

        # Add footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC_"
                }
            ]
        })

        return blocks

    def _build_article_block(self, article: Dict[str, Any], index: int) -> List[Dict[str, Any]]:
        """Build blocks for a single article."""
        title = article.get("title", "Untitled")
        url = article.get("url")
        profit_score = article.get("profit_score", 0.0)
        source = article.get("source", "Unknown")
        category = article.get("category", "general")
        sentiment = article.get("sentiment")

        # Sanitize text for Slack
        title = self._sanitize_text(title, max_length=150)
        source = self._sanitize_text(source, max_length=50)
        
        # Sanitize and validate URL
        if url:
            url = self._sanitize_url(url)

        # Score emoji based on value
        score_emoji = self._get_score_emoji(profit_score)

        # Build title with link - use simpler format to avoid escaping issues
        if url:
            title_text = f"*{index}. {title}*\n🔗 {url}"
        else:
            title_text = f"*{index}. {title}*"

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": title_text
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Profit Score:* {score_emoji} {profit_score:.1f}/10"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Source:* {source}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:* {category.title()}"
                    }
                ]
            }
        ]

        # Add sentiment if available
        if sentiment:
            blocks[1]["fields"].append({
                "type": "mrkdwn",
                "text": f"*Sentiment:* {self._format_sentiment(sentiment)}"
            })

        return blocks

    @staticmethod
    def _get_score_emoji(score: float) -> str:
        """Get emoji based on profit score."""
        if score >= 9.0:
            return "🔥"
        elif score >= 8.0:
            return "⭐"
        elif score >= 7.0:
            return "📈"
        elif score >= 6.0:
            return "💡"
        else:
            return "📊"

    @staticmethod
    def _format_sentiment(sentiment: str) -> str:
        """Format sentiment with emoji."""
        sentiment_map = {
            "very_positive": "😄 Very Positive",
            "positive": "🙂 Positive",
            "neutral": "😐 Neutral",
            "negative": "😟 Negative",
            "very_negative": "😞 Very Negative"
        }
        return sentiment_map.get(sentiment, sentiment.title())

    @staticmethod
    def _sanitize_text(text: str, max_length: int = 3000) -> str:
        """Sanitize text for Slack by escaping special characters and limiting length.
        
        Slack markdown has special meanings for: & < >
        """
        if not text:
            return ""
        
        # Convert to string and strip whitespace
        text = str(text).strip()
        
        # Escape special Slack characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        
        # Limit length
        if len(text) > max_length:
            text = text[:max_length - 3] + "..."
        
        return text

    @staticmethod
    def _sanitize_url(url: str) -> str:
        """Sanitize URL for Slack.
        
        Remove any whitespace and ensure it's a valid URL.
        """
        if not url:
            return ""
        
        # Strip whitespace
        url = str(url).strip()
        
        # Basic validation - must start with http:// or https://
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        return url


# Singleton instance
_notifier: Optional[SlackNotifier] = None


def get_slack_notifier() -> SlackNotifier:
    """Get or create the Slack notifier singleton."""
    global _notifier
    if _notifier is None:
        _notifier = SlackNotifier()
    return _notifier
