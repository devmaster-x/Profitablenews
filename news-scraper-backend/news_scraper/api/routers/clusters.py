"""Article-cluster endpoints (multi-source corroboration, Phase 2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from news_scraper.api.deps import get_db

router = APIRouter()


@router.get("/clusters")
async def get_article_clusters(
    min_corroboration: int = Query(2, ge=1, description="Minimum number of sources reporting the same event"),
    limit: int = Query(20, ge=1, le=100, description="Number of clusters to return"),
    db=Depends(get_db),
):
    """Get article clusters with multi-source corroboration."""
    try:
        clusters = db.get_clusters(min_corroboration=min_corroboration, limit=limit)
        return {"clusters": clusters, "count": len(clusters), "min_corroboration": min_corroboration}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get clusters: {str(e)}")


@router.get("/clusters/{cluster_id}")
async def get_cluster_details(cluster_id: str, db=Depends(get_db)):
    """Get all articles in a specific cluster."""
    try:
        articles = db.get_cluster_articles(cluster_id)
        if not articles:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return {"cluster_id": cluster_id, "articles": articles, "corroboration_count": len(articles)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cluster details: {str(e)}")
