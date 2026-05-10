#!/usr/bin/env python3
"""
Interactive Database Browser
A simple command-line tool to browse the database manually
"""

from app.database import db
from app.models import NewsCategory, SentimentScore
import os

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def show_menu():
    """Show the main menu"""
    print("\n" + "="*60)
    print("🗄️  NEWS SCRAPER DATABASE BROWSER")
    print("="*60)
    print("1. 📊 Show Database Statistics")
    print("2. 📰 List All Articles")
    print("3. 🎯 Show High-Profit Opportunities")
    print("4. 📂 Filter by Category")
    print("5. 😊 Filter by Sentiment")
    print("6. 💰 Filter by Profit Score")
    print("7. 🔍 Search Articles")
    print("8. 🏢 Show Company Mentions")
    print("9. 📈 Show Market Trends")
    print("0. ❌ Exit")
    print("="*60)

def show_stats():
    """Show database statistics"""
    clear_screen()
    print("📊 DATABASE STATISTICS")
    print("-" * 40)
    
    stats = db.get_stats()
    print(f"Total Articles: {stats['total_articles']}")
    print(f"Average Profit Score: {stats.get('avg_profit_score', 'N/A')}")
    print(f"High Profit Opportunities: {stats.get('high_profit_opportunities', 0)}")
    
    if stats['categories']:
        print("\n📂 Articles by Category:")
        for category, count in stats['categories'].items():
            print(f"  {category}: {count}")
    
    if stats['sentiments']:
        print("\n😊 Articles by Sentiment:")
        for sentiment, count in stats['sentiments'].items():
            print(f"  {sentiment}: {count}")
    
    input("\nPress Enter to continue...")

def list_articles():
    """List all articles with pagination"""
    clear_screen()
    print("📰 ALL ARTICLES")
    print("-" * 40)
    
    page = 1
    per_page = 10
    
    while True:
        articles, total = db.get_articles(skip=(page-1)*per_page, limit=per_page)
        
        if not articles:
            print("No articles found!")
            break
        
        print(f"\nPage {page} of {(total + per_page - 1) // per_page}")
        print(f"Showing {len(articles)} of {total} articles")
        print("-" * 40)
        
        for i, article in enumerate(articles, 1):
            print(f"{i}. {article.title[:60]}...")
            print(f"   Category: {article.category.value}")
            print(f"   Score: {article.profit_score:.1f}")
            print(f"   Source: {article.source}")
            print(f"   Date: {article.created_at.strftime('%Y-%m-%d %H:%M')}")
            print()
        
        if total <= page * per_page:
            break
            
        choice = input("Enter 'n' for next page, 'p' for previous, or 'q' to quit: ").lower()
        if choice == 'q':
            break
        elif choice == 'n':
            page += 1
        elif choice == 'p' and page > 1:
            page -= 1

def show_opportunities():
    """Show high-profit opportunities"""
    clear_screen()
    print("🎯 HIGH-PROFIT OPPORTUNITIES")
    print("-" * 40)
    
    min_score = input("Enter minimum profit score (default 7.0): ").strip()
    min_score = float(min_score) if min_score else 7.0
    
    opportunities = db.get_profit_opportunities(min_score=min_score, limit=20)
    
    if not opportunities:
        print(f"No opportunities found with score >= {min_score}")
        input("\nPress Enter to continue...")
        return
    
    print(f"\nFound {len(opportunities)} opportunities with score >= {min_score}")
    print("-" * 40)
    
    for i, opp in enumerate(opportunities, 1):
        print(f"{i}. {opp['title'][:60]}...")
        print(f"   Score: {opp['profit_score']:.1f}")
        print(f"   Category: {opp['category']}")
        print(f"   Source: {opp['source']}")
        print()
    
    input("Press Enter to continue...")

def filter_by_category():
    """Filter articles by category"""
    clear_screen()
    print("📂 FILTER BY CATEGORY")
    print("-" * 40)
    
    print("Available categories:")
    for i, category in enumerate(NewsCategory, 1):
        print(f"{i}. {category.value}")
    
    try:
        choice = int(input("\nEnter category number: ")) - 1
        if 0 <= choice < len(NewsCategory):
            category = list(NewsCategory)[choice]
            articles, total = db.get_articles(category=category, limit=20)
            
            print(f"\nFound {total} articles in {category.value}")
            print("-" * 40)
            
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article.title[:60]}...")
                print(f"   Score: {article.profit_score:.1f}")
                print(f"   Source: {article.source}")
                print()
        else:
            print("Invalid choice!")
    except ValueError:
        print("Invalid input!")
    
    input("Press Enter to continue...")

def filter_by_sentiment():
    """Filter articles by sentiment"""
    clear_screen()
    print("😊 FILTER BY SENTIMENT")
    print("-" * 40)
    
    print("Available sentiments:")
    for i, sentiment in enumerate(SentimentScore, 1):
        print(f"{i}. {sentiment.value}")
    
    try:
        choice = int(input("\nEnter sentiment number: ")) - 1
        if 0 <= choice < len(SentimentScore):
            sentiment = list(SentimentScore)[choice]
            articles, total = db.get_articles(sentiment=sentiment, limit=20)
            
            print(f"\nFound {total} articles with {sentiment.value} sentiment")
            print("-" * 40)
            
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article.title[:60]}...")
                print(f"   Score: {article.profit_score:.1f}")
                print(f"   Category: {article.category.value}")
                print()
        else:
            print("Invalid choice!")
    except ValueError:
        print("Invalid input!")
    
    input("Press Enter to continue...")

def filter_by_profit_score():
    """Filter articles by profit score"""
    clear_screen()
    print("💰 FILTER BY PROFIT SCORE")
    print("-" * 40)
    
    try:
        min_score = float(input("Enter minimum profit score: "))
        articles, total = db.get_articles(min_profit_score=min_score, limit=20)
        
        print(f"\nFound {total} articles with score >= {min_score}")
        print("-" * 40)
        
        for i, article in enumerate(articles, 1):
            print(f"{i}. {article.title[:60]}...")
            print(f"   Score: {article.profit_score:.1f}")
            print(f"   Category: {article.category.value}")
            print()
    except ValueError:
        print("Invalid input!")
    
    input("Press Enter to continue...")

def search_articles():
    """Search articles"""
    clear_screen()
    print("🔍 SEARCH ARTICLES")
    print("-" * 40)
    
    search_term = input("Enter search term: ").strip()
    if not search_term:
        print("No search term entered!")
        input("Press Enter to continue...")
        return
    
    articles, total = db.get_articles(search=search_term, limit=20)
    
    print(f"\nFound {total} articles matching '{search_term}'")
    print("-" * 40)
    
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article.title[:60]}...")
        print(f"   Score: {article.profit_score:.1f}")
        print(f"   Category: {article.category.value}")
        print()

def show_companies():
    """Show company mentions"""
    clear_screen()
    print("🏢 COMPANY MENTIONS")
    print("-" * 40)
    
    companies = db.get_company_mentions()
    
    if not companies:
        print("No company mentions found!")
        input("Press Enter to continue...")
        return
    
    print(f"Found {len(companies)} companies mentioned")
    print("-" * 40)
    
    for i, company in enumerate(companies[:10], 1):
        print(f"{i}. {company['name']}")
        print(f"   Mentions: {company['mention_count']}")
        print(f"   Avg Score: {company['avg_profit_score']:.1f}")
        print()

def show_trends():
    """Show market trends"""
    clear_screen()
    print("📈 MARKET TRENDS")
    print("-" * 40)
    
    trends = db.get_market_trends()
    
    if not trends:
        print("No trends data available!")
        input("Press Enter to continue...")
        return
    
    for trend in trends:
        print(f"Category: {trend['category']}")
        print(f"Trend: {trend['trend_direction']}")
        print(f"Confidence: {trend['confidence_score']:.2f}")
        print(f"Avg Score: {trend['avg_profit_score']:.1f}")
        print(f"Articles: {trend['article_count']}")
        print("-" * 20)

def main():
    """Main function"""
    while True:
        clear_screen()
        show_menu()
        
        try:
            choice = input("\nEnter your choice (0-9): ").strip()
            
            if choice == '0':
                print("Goodbye! 👋")
                break
            elif choice == '1':
                show_stats()
            elif choice == '2':
                list_articles()
            elif choice == '3':
                show_opportunities()
            elif choice == '4':
                filter_by_category()
            elif choice == '5':
                filter_by_sentiment()
            elif choice == '6':
                filter_by_profit_score()
            elif choice == '7':
                search_articles()
            elif choice == '8':
                show_companies()
            elif choice == '9':
                show_trends()
            else:
                print("Invalid choice! Please try again.")
                input("Press Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"Error: {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main() 