import sqlite3

conn = sqlite3.connect('news_scraper.db')
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM articles')
total = cursor.fetchone()[0]
print(f'Total articles: {total}')

if total > 0:
    cursor.execute('SELECT id, title, profit_score, category FROM articles LIMIT 5')
    print('\nSample articles:')
    for row in cursor.fetchall():
        print(f'  ID: {row[0]}, Title: {row[1][:50]}, Score: {row[2]}, Category: {row[3]}')
else:
    print('No articles found in database!')

conn.close()
