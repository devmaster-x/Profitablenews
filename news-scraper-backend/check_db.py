#!/usr/bin/env python3
"""
Database Inspection Script
Run this to check what's in the in-memory database
"""

from app.database import db
from app.models import NewsCategory, SentimentScore

def check_database():
    """Check the current state of the database"""
    print("🔍 Database Inspection Report")
    print("=" * 50)
    
    # Get basic stats
    stats = db.get_stats()
    
    print(f"📊 Total Articles: {stats['total_articles']}")
    print(f"📈 Average Profit Score: {stats.get('avg_profit_score', 'N/A')}")
    print(f"🎯 High Profit Opportunities: {stats.get('high_profit_opportunities', 0)}")
    
    # Get all articles
    articles, total = db.get_articles(limit=1000)
    
    if total == 0:
        print("\n❌ No articles found in database")
        print("💡 Try running the scraper first: POST /scrape")
        return
    
    print(f"\n📰 Articles in Database: {total}")
    print("-" * 50)
    
    # Show articles by category
    categories = {}
    sentiments = {}
    profit_scores = []
    
    for article in articles:
        # Count by category
        cat = article.category.value
        categories[cat] = categories.get(cat, 0) + 1
        
        # Count by sentiment
        if article.sentiment:
            sent = article.sentiment.value
            sentiments[sent] = sentiments.get(sent, 0) + 1
        
        # Collect profit scores
        if article.profit_score:
            profit_scores.append(article.profit_score)
    
    print("\n📂 Articles by Category:")
    for category, count in categories.items():
        print(f"   {category}: {count}")
    
    print("\n😊 Articles by Sentiment:")
    for sentiment, count in sentiments.items():
        print(f"   {sentiment}: {count}")
    
    if profit_scores:
        print(f"\n💰 Profit Score Analysis:")
        print(f"   Average: {sum(profit_scores) / len(profit_scores):.2f}")
        print(f"   Highest: {max(profit_scores):.2f}")
        print(f"   Lowest: {min(profit_scores):.2f}")
        print(f"   Articles with score ≥ 7.0: {len([s for s in profit_scores if s >= 7.0])}")
        print(f"   Articles with score ≥ 8.0: {len([s for s in profit_scores if s >= 8.0])}")
    
    # Show recent articles
    print(f"\n🕒 Recent Articles (last 5):")
    recent_articles = sorted(articles, key=lambda x: x.created_at, reverse=True)[:5]
    for i, article in enumerate(recent_articles, 1):
        print(f"   {i}. {article.title[:60]}...")
        print(f"      Category: {article.category.value}, Score: {article.profit_score:.1f}, Source: {article.source}")
    
    # Show high-profit opportunities
    opportunities = db.get_profit_opportunities(min_score=7.0, limit=5)
    if opportunities:
        print(f"\n🎯 High-Profit Opportunities (Score ≥ 7.0):")
        for i, opp in enumerate(opportunities, 1):
            print(f"   {i}. {opp['title'][:60]}...")
            print(f"      Score: {opp['profit_score']:.1f}, Category: {opp['category']}, Source: {opp['source']}")

if __name__ == "__main__":
    check_database() 