Backend: cd news-scraper-backend && poetry install && poetry run fastapi dev app/main.py
py -3.13 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


Frontend: cd news-scraper-frontend && npm install && npm run dev