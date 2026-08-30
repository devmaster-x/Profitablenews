import { useState, useEffect } from 'react'
import { TrendingUp, Newspaper, DollarSign, BarChart3, Filter, Search, RefreshCw, LayoutGrid, List } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts'
import { ProfitAnalysis } from './components/ProfitAnalysis'
import { ArticleListView } from './components/ArticleListView'
import { SlackNotifications } from './components/SlackNotifications'
import { getSentimentColor, getProfitScoreColor, type NewsArticle } from './lib/article-utils'
import { apiEndpoints } from './config'
import './App.css'

type ArticleViewMode = 'card' | 'list'
type ArticleSort = 'date_desc' | 'date_asc' | 'score_desc' | 'score_asc'

interface NewsStats {
  total_articles: number
  categories: Record<string, number>
  sentiments: Record<string, number>
  average_profit_score: number
}

function App() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [stats, setStats] = useState<NewsStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedSentiment, setSelectedSentiment] = useState<string>('all')
  const [minProfitScore, setMinProfitScore] = useState<number>(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [viewMode, setViewMode] = useState<ArticleViewMode>(() => {
    return localStorage.getItem('articleViewMode') === 'list' ? 'list' : 'card'
  })
  const [sort, setSort] = useState<ArticleSort>('date_desc')

  useEffect(() => {
    localStorage.setItem('articleViewMode', viewMode)
  }, [viewMode])

  const fetchArticles = async () => {
    try {
      setLoading(true)
      const [sortBy, order] = sort.split('_')
      const params = new URLSearchParams({
        page: currentPage.toString(),
        per_page: '12',
        ...(selectedCategory !== 'all' && { category: selectedCategory }),
        ...(selectedSentiment !== 'all' && { sentiment: selectedSentiment }),
        ...(minProfitScore > 0 && { min_profit_score: minProfitScore.toString() }),
        ...(searchTerm && { search: searchTerm }),
        sort_by: sortBy,
        order,
      })

      const response = await fetch(`${apiEndpoints.articles}?${params}`)
      const data = await response.json()
      
      setArticles(data.articles || [])
      setTotalPages(data.total_pages || 1)
    } catch (error) {
      console.error('Error fetching articles:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const response = await fetch(apiEndpoints.stats)
      const data = await response.json()
      setStats(data)
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
  }

  const triggerScraping = async () => {
    try {
      setLoading(true)
      await fetch(apiEndpoints.scrape, { method: 'POST' })
      await fetchArticles()
      await fetchStats()
    } catch (error) {
      console.error('Error triggering scraping:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchArticles()
    fetchStats()
  }, [currentPage, selectedCategory, selectedSentiment, minProfitScore, searchTerm, sort])

  const chartData = stats ? Object.entries(stats.categories).map(([category, count]) => ({
    category: category.replace('_', ' ').toUpperCase(),
    count
  })) : []

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center space-x-3">
              <TrendingUp className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">News Profit Analyzer</h1>
                <p className="text-sm text-gray-500">Market & Software Development Intelligence</p>
              </div>
            </div>
            <Button onClick={triggerScraping} disabled={loading} className="flex items-center space-x-2">
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh Data</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Overview */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Articles</CardTitle>
                <Newspaper className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total_articles}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Profit Score</CardTitle>
                <DollarSign className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.average_profit_score?.toFixed(1) || '0.0'}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Categories</CardTitle>
                <BarChart3 className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{Object.keys(stats.categories).length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">High Profit (8+)</CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {articles.filter(a => a.profit_score >= 8).length}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs defaultValue="articles" className="space-y-6">
          <TabsList>
            <TabsTrigger value="articles">Articles</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
            <TabsTrigger value="profit-analysis">Profit Analysis</TabsTrigger>
            <TabsTrigger value="notifications">Slack Notifications</TabsTrigger>
          </TabsList>

          <TabsContent value="articles" className="space-y-6">
            {/* Filters */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Filter className="h-5 w-5" />
                  <span>Filters</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="relative">
                    <Search className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="Search articles..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                    <SelectTrigger>
                      <SelectValue placeholder="Category" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Categories</SelectItem>
                      <SelectItem value="market">Market</SelectItem>
                      <SelectItem value="software">Software</SelectItem>
                      <SelectItem value="crypto">Crypto</SelectItem>
                      <SelectItem value="startup">Startup</SelectItem>
                      <SelectItem value="tech_earnings">Tech Earnings</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={selectedSentiment} onValueChange={setSelectedSentiment}>
                    <SelectTrigger>
                      <SelectValue placeholder="Sentiment" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Sentiments</SelectItem>
                      <SelectItem value="very_positive">Very Positive</SelectItem>
                      <SelectItem value="positive">Positive</SelectItem>
                      <SelectItem value="neutral">Neutral</SelectItem>
                      <SelectItem value="negative">Negative</SelectItem>
                      <SelectItem value="very_negative">Very Negative</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={minProfitScore.toString()} onValueChange={(value) => setMinProfitScore(Number(value))}>
                    <SelectTrigger>
                      <SelectValue placeholder="Min Profit Score" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">Any Score</SelectItem>
                      <SelectItem value="5">5+ Score</SelectItem>
                      <SelectItem value="6">6+ Score</SelectItem>
                      <SelectItem value="7">7+ Score</SelectItem>
                      <SelectItem value="8">8+ Score</SelectItem>
                      <SelectItem value="9">9+ Score</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Articles Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-500">
                {articles.length} article{articles.length === 1 ? '' : 's'}
              </p>
              <div className="flex items-center gap-3">
                <Select value={sort} onValueChange={(value) => setSort(value as ArticleSort)}>
                  <SelectTrigger className="w-[170px]">
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="date_desc">Newest first</SelectItem>
                    <SelectItem value="date_asc">Oldest first</SelectItem>
                    <SelectItem value="score_desc">Highest score</SelectItem>
                    <SelectItem value="score_asc">Lowest score</SelectItem>
                  </SelectContent>
                </Select>
                <ToggleGroup
                  type="single"
                  variant="outline"
                  size="sm"
                  value={viewMode}
                  onValueChange={(value) => {
                    if (value) setViewMode(value as ArticleViewMode)
                  }}
                >
                  <ToggleGroupItem value="card" aria-label="Card view" title="Card view">
                    <LayoutGrid className="h-4 w-4" />
                  </ToggleGroupItem>
                  <ToggleGroupItem value="list" aria-label="List view" title="List view">
                    <List className="h-4 w-4" />
                  </ToggleGroupItem>
                </ToggleGroup>
              </div>
            </div>

            {/* Articles Grid */}
            {loading ? (
              <div className="flex justify-center items-center py-12">
                <RefreshCw className="h-8 w-8 animate-spin text-blue-600" />
              </div>
            ) : articles.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-zinc-300 py-16 text-center">
                <Newspaper className="mb-2 h-8 w-8 text-zinc-400" />
                <p className="text-sm text-zinc-500">
                  No articles match the current filters.
                </p>
                <p className="mt-1 text-xs text-zinc-400">
                  Adjust your filters or click &quot;Refresh Data&quot; to scrape new articles.
                </p>
              </div>
            ) : viewMode === 'list' ? (
              <ArticleListView articles={articles} />
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {articles.map((article) => (
                  <Card key={article.id} className="hover:shadow-lg transition-shadow">
                    <CardHeader>
                      <div className="flex justify-between items-start space-x-2">
                        <CardTitle className="text-lg line-clamp-2">{article.title}</CardTitle>
                        <div className="flex flex-col items-end space-y-1">
                          <Badge className={getProfitScoreColor(article.profit_score)}>
                            {article.profit_score.toFixed(1)}
                          </Badge>
                          <div className={`w-3 h-3 rounded-full ${getSentimentColor(article.sentiment)}`} />
                        </div>
                      </div>
                      <CardDescription className="flex items-center space-x-2">
                        <Badge variant="outline">{article.category.replace('_', ' ')}</Badge>
                        <span className="text-sm text-gray-500">{article.source}</span>
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-gray-600 line-clamp-3 mb-4">
                        {article.content}
                      </p>
                      {article.keywords.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-3">
                          {article.keywords.slice(0, 3).map((keyword, idx) => (
                            <Badge key={idx} variant="secondary" className="text-xs">
                              {keyword}
                            </Badge>
                          ))}
                        </div>
                      )}
                      <div className="flex justify-between items-center text-xs text-gray-500">
                        <span>{new Date(article.created_at).toLocaleDateString()}</span>
                        {article.url && (
                          <a
                            href={article.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:underline"
                          >
                            Read More
                          </a>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center space-x-2">
                <Button
                  variant="outline"
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                >
                  Previous
                </Button>
                <span className="flex items-center px-4 py-2 text-sm">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                </Button>
              </div>
            )}
          </TabsContent>

          <TabsContent value="analytics" className="space-y-6">
            {stats && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>Articles by Category</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="category" />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="count" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Sentiment Distribution</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {Object.entries(stats.sentiments).map(([sentiment, count]) => (
                        <div key={sentiment} className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <div className={`w-4 h-4 rounded-full ${getSentimentColor(sentiment)}`} />
                            <span className="capitalize">{sentiment.replace('_', ' ')}</span>
                          </div>
                          <Badge variant="outline">{count}</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          <TabsContent value="profit-analysis" className="space-y-6">
            <ProfitAnalysis />
          </TabsContent>

          <TabsContent value="notifications" className="space-y-6">
            <SlackNotifications />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

export default App
