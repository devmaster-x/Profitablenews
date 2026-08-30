import { Badge } from '@/components/ui/badge'
import {
  formatCategory,
  formatDate,
  getProfitScoreColor,
  getSentimentColor,
  type NewsArticle,
} from '@/lib/article-utils'

interface ArticleListViewProps {
  articles: NewsArticle[]
}

const gridColumns = 'md:grid-cols-[minmax(0,1fr)_8rem_5rem_9rem_7rem]'

export function ArticleListView({ articles }: ArticleListViewProps) {
  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
      <div
        className={`hidden bg-zinc-50 px-4 py-2.5 text-xs font-medium uppercase tracking-wide text-zinc-500 md:grid md:gap-4 dark:bg-zinc-900 dark:text-zinc-400 ${gridColumns}`}
      >
        <span>Article</span>
        <span>Category</span>
        <span className="text-right">Score</span>
        <span>Source</span>
        <span>Date</span>
      </div>

      <ul role="list" className="divide-y divide-zinc-200 dark:divide-zinc-800">
        {articles.map((article) => (
          <li key={article.id}>
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block px-4 py-3 transition-colors hover:bg-zinc-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-zinc-950 dark:hover:bg-zinc-900/50 dark:focus-visible:ring-zinc-300"
            >
              <div
                className={`flex flex-col gap-3 md:grid md:items-center md:gap-4 ${gridColumns}`}
              >
                <div className="min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="line-clamp-2 text-sm font-medium leading-snug text-zinc-900 dark:text-zinc-50">
                      {article.title}
                    </h3>
                    <span
                      className={`shrink-0 text-sm md:hidden ${getProfitScoreColor(article.profit_score)}`}
                    >
                      {article.profit_score.toFixed(1)}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 md:hidden">
                    <Badge variant="outline" className="text-[11px]">
                      {formatCategory(article.category)}
                    </Badge>
                    <span className="inline-flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                      <span
                        className={`h-2 w-2 shrink-0 rounded-full ${getSentimentColor(article.sentiment)}`}
                      />
                      {article.source}
                    </span>
                    <span className="text-xs text-zinc-500 dark:text-zinc-400">
                      {formatDate(article.created_at)}
                    </span>
                  </div>
                </div>

                <div className="hidden md:block">
                  <Badge variant="outline">{formatCategory(article.category)}</Badge>
                </div>
                <div className="hidden md:block">
                  <span
                    className={`text-sm ${getProfitScoreColor(article.profit_score)}`}
                  >
                    {article.profit_score.toFixed(1)}
                  </span>
                </div>
                <div className="hidden min-w-0 md:block">
                  <span className="inline-flex items-center gap-1.5 text-sm text-zinc-500 dark:text-zinc-400">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${getSentimentColor(article.sentiment)}`}
                    />
                    <span className="truncate">{article.source}</span>
                  </span>
                </div>
                <div className="hidden text-sm text-zinc-500 md:block dark:text-zinc-400">
                  {formatDate(article.created_at)}
                </div>
              </div>
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}
