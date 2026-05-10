import requests

try:
    # Test health endpoint
    response = requests.get('http://localhost:8000/healthz')
    print(f'Health check: {response.status_code}')
    print(f'Response: {response.json()}')
    
    # Test stats endpoint
    response = requests.get('http://localhost:8000/stats')
    print(f'\nStats: {response.status_code}')
    print(f'Response: {response.json()}')
    
    # Test articles endpoint
    response = requests.get('http://localhost:8000/articles?page=1&per_page=5')
    print(f'\nArticles: {response.status_code}')
    data = response.json()
    print(f'Total articles: {data.get("total")}')
    print(f'Articles returned: {len(data.get("articles", []))}')
    
except Exception as e:
    print(f'Error: {e}')
