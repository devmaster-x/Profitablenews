import { useState, useEffect } from 'react'
import { TrendingUp, AlertTriangle, DollarSign, BarChart3, Target, TrendingDown } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { apiEndpoints } from '../config'

interface ProfitOpportunity {
  id: number
  title: string
  profit_score: number
  category: string
  sentiment: string
  created_at: string
  source: string
  url?: string
}

interface ProfitAlert {
  id: number
  title: string
  profit_score: number
  category: string
  sentiment: string
  created_at: string
  source: string
  urgency: string
}

interface MarketTrend {
  category: string
  trend_direction: string
  confidence_score: number
  avg_profit_score: number
  recent_avg_score: number
  article_count: number
}

interface CompanyMention {
  name: string
  mention_count: number
  avg_profit_score: number
  articles: Array<{
    id: number
    title: string
    profit_score: number
    created_at: string
  }>
}

export function ProfitAnalysis() {
  const [opportunities, setOpportunities] = useState<ProfitOpportunity[]>([])
  const [alerts, setAlerts] = useState<ProfitAlert[]>([])
  const [trends, setTrends] = useState<MarketTrend[]>([])
  const [companies, setCompanies] = useState<CompanyMention[]>([])
  const [loading, setLoading] = useState(true)
  const [minScore, setMinScore] = useState(7.0)
  const [alertThreshold, setAlertThreshold] = useState(8.0)

  const fetchOpportunities = async () => {
    try {
      const response = await fetch(`${apiEndpoints.opportunities}?min_score=${minScore}`)
      const data = await response.json()
      setOpportunities(data.opportunities || [])
    } catch (error) {
      console.error('Error fetching opportunities:', error)
    }
  }

  const fetchAlerts = async () => {
    try {
      const response = await fetch(`${apiEndpoints.alerts}?threshold=${alertThreshold}`)
      const data = await response.json()
      setAlerts(data.alerts || [])
    } catch (error) {
      console.error('Error fetching alerts:', error)
    }
  }

  const fetchTrends = async () => {
    try {
      const response = await fetch(apiEndpoints.trends)
      const data = await response.json()
      setTrends(data.trends || [])
    } catch (error) {
      console.error('Error fetching trends:', error)
    }
  }

  const fetchCompanies = async () => {
    try {
      const response = await fetch(apiEndpoints.companies)
      const data = await response.json()
      setCompanies(data.companies || [])
    } catch (error) {
      console.error('Error fetching companies:', error)
    }
  }

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      await Promise.all([
        fetchOpportunities(),
        fetchAlerts(),
        fetchTrends(),
        fetchCompanies()
      ])
      setLoading(false)
    }
    loadData()
  }, [minScore, alertThreshold])

  const getTrendIcon = (direction: string) => {
    switch (direction) {
      case 'up': return <TrendingUp className="h-4 w-4 text-green-500" />
      case 'down': return <TrendingDown className="h-4 w-4 text-red-500" />
      default: return <BarChart3 className="h-4 w-4 text-gray-500" />
    }
  }

  const getUrgencyColor = (urgency: string) => {
    switch (urgency) {
      case 'high': return 'bg-red-500'
      case 'medium': return 'bg-yellow-500'
      default: return 'bg-blue-500'
    }
  }

  const getProfitScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600'
    if (score >= 6) return 'text-yellow-600'
    return 'text-red-600'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">High-Profit Opportunities</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{opportunities.length}</div>
            <p className="text-xs text-muted-foreground">
              Score ≥ {minScore}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Profit Alerts</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{alerts.length}</div>
            <p className="text-xs text-muted-foreground">
              Threshold ≥ {alertThreshold}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Trends</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{trends.filter(t => t.trend_direction !== 'stable').length}</div>
            <p className="text-xs text-muted-foreground">
              Market movements
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Companies Tracked</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{companies.length}</div>
            <p className="text-xs text-muted-foreground">
              Major mentions
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="opportunities" className="space-y-4">
        <TabsList>
          <TabsTrigger value="opportunities">Profit Opportunities</TabsTrigger>
          <TabsTrigger value="alerts">Alerts</TabsTrigger>
          <TabsTrigger value="trends">Market Trends</TabsTrigger>
          <TabsTrigger value="companies">Company Mentions</TabsTrigger>
        </TabsList>

        <TabsContent value="opportunities" className="space-y-4">
          <div className="flex items-center space-x-4">
            <label className="text-sm font-medium">Minimum Score:</label>
            <input
              type="range"
              min="5"
              max="10"
              step="0.5"
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              className="w-32"
            />
            <span className="text-sm font-bold">{minScore}</span>
          </div>

          <div className="grid gap-4">
            {opportunities.map((opportunity) => (
              <Card key={opportunity.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{opportunity.title}</CardTitle>
                    <div className="flex items-center space-x-2">
                      <Badge variant="outline">{opportunity.category}</Badge>
                      <Badge variant="outline">{opportunity.sentiment}</Badge>
                      <span className={`text-lg font-bold ${getProfitScoreColor(opportunity.profit_score)}`}>
                        {opportunity.profit_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <CardDescription>
                    Source: {opportunity.source} • {new Date(opportunity.created_at).toLocaleDateString()}
                  </CardDescription>
                </CardHeader>
                {opportunity.url && (
                  <CardContent>
                    <Button variant="outline" size="sm" asChild>
                      <a href={opportunity.url} target="_blank" rel="noopener noreferrer">
                        Read Article
                      </a>
                    </Button>
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="alerts" className="space-y-4">
          <div className="flex items-center space-x-4">
            <label className="text-sm font-medium">Alert Threshold:</label>
            <input
              type="range"
              min="6"
              max="10"
              step="0.5"
              value={alertThreshold}
              onChange={(e) => setAlertThreshold(parseFloat(e.target.value))}
              className="w-32"
            />
            <span className="text-sm font-bold">{alertThreshold}</span>
          </div>

          <div className="grid gap-4">
            {alerts.map((alert) => (
              <Card key={alert.id} className="border-l-4 border-l-red-500">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{alert.title}</CardTitle>
                    <div className="flex items-center space-x-2">
                      <Badge className={getUrgencyColor(alert.urgency)}>
                        {alert.urgency.toUpperCase()}
                      </Badge>
                      <span className={`text-lg font-bold ${getProfitScoreColor(alert.profit_score)}`}>
                        {alert.profit_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <CardDescription>
                    {alert.category} • {alert.sentiment} • {alert.source} • {new Date(alert.created_at).toLocaleDateString()}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <div className="grid gap-4">
            {trends.map((trend) => (
              <Card key={trend.category}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{trend.category.replace('_', ' ').toUpperCase()}</CardTitle>
                    <div className="flex items-center space-x-2">
                      {getTrendIcon(trend.trend_direction)}
                      <Badge variant={trend.trend_direction === 'up' ? 'default' : 'secondary'}>
                        {trend.trend_direction.toUpperCase()}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Average Score</p>
                      <p className="text-2xl font-bold">{trend.avg_profit_score.toFixed(1)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Recent Average</p>
                      <p className="text-2xl font-bold">{trend.recent_avg_score.toFixed(1)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Confidence</p>
                      <Progress value={trend.confidence_score * 100} className="w-full" />
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Articles</p>
                      <p className="text-2xl font-bold">{trend.article_count}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="companies" className="space-y-4">
          <div className="grid gap-4">
            {companies.slice(0, 20).map((company) => (
              <Card key={company.name}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{company.name}</CardTitle>
                    <div className="flex items-center space-x-2">
                      <Badge variant="outline">{company.mention_count} mentions</Badge>
                      <span className={`text-lg font-bold ${getProfitScoreColor(company.avg_profit_score)}`}>
                        {company.avg_profit_score.toFixed(1)}
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      Average profit score: {company.avg_profit_score.toFixed(1)}
                    </p>
                    <div className="text-sm">
                      <strong>Recent articles:</strong>
                      <ul className="mt-2 space-y-1">
                        {company.articles.slice(0, 3).map((article) => (
                          <li key={article.id} className="text-xs">
                            {article.title} (Score: {article.profit_score?.toFixed(1) || 'N/A'})
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
} 