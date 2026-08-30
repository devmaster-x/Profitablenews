"""Quick CLI: print backtest accuracy for all windows (dev utility)."""
import sys

from news_scraper.persistent_database import PersistentDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

db = PersistentDatabase("news_scraper.db")
for w in ("1h", "24h", "7d"):
    a = db.get_backtest_accuracy(w, 10)
    slim = {
        k: (round(v, 4) if isinstance(v, float) else v)
        for k, v in a.items()
        if k in ("correlation", "p_value", "total_samples", "avg_predicted", "avg_actual", "error")
    }
    print(w, slim, flush=True)
