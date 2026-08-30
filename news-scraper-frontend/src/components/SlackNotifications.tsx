import { useState, useEffect } from 'react'
import { Bell, Send, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { apiEndpoints } from '@/config'

interface NotificationStatus {
  total_unsent: number
  min_score: number
  articles: Array<{
    id: number
    title: string
    url: string
    profit_score: number
    source: string
    category: string
  }>
}

interface NotificationResponse {
  success: boolean
  message: string
  sent_count: number
}

interface SendProgress {
  currentBatch: number
  totalBatches: number
  totalSent: number
}

export function SlackNotifications() {
  const [status, setStatus] = useState<NotificationStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [lastResult, setLastResult] = useState<NotificationResponse | null>(null)
  const [batchSize, setBatchSize] = useState(10)
  const [progress, setProgress] = useState<SendProgress | null>(null)
  const minScore = 5.0

  const fetchStatus = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${apiEndpoints.notifications.status}?min_score=${minScore}`)
      const data = await response.json()
      setStatus(data)
    } catch (error) {
      console.error('Error fetching notification status:', error)
    } finally {
      setLoading(false)
    }
  }

  const sendNotifications = async (limit?: number) => {
    try {
      setSending(true)
      setLastResult(null)
      
      const limitParam = limit || batchSize
      const response = await fetch(
        `${apiEndpoints.notifications.send}?min_score=${minScore}&limit=${limitParam}`,
        { method: 'POST' }
      )
      const data = await response.json()
      setLastResult(data)
      
      // Refresh status after sending
      if (data.success) {
        setTimeout(() => {
          fetchStatus()
        }, 1000)
      }
    } catch (error) {
      console.error('Error sending notifications:', error)
      setLastResult({
        success: false,
        message: 'Failed to send notifications',
        sent_count: 0,
      })
    } finally {
      setSending(false)
    }
  }

  const sendAllNotifications = async () => {
    if (!status || status.total_unsent === 0) return
    
    try {
      setSending(true)
      setLastResult(null)
      setProgress(null)
      
      let totalSent = 0
      let batchCount = 0
      const batchesToSend = Math.ceil(status.total_unsent / 10)
      
      // Send in batches of 10
      for (let i = 0; i < batchesToSend; i++) {
        batchCount++
        
        // Update progress
        setProgress({
          currentBatch: batchCount,
          totalBatches: batchesToSend,
          totalSent: totalSent,
        })
        
        const response = await fetch(
          `${apiEndpoints.notifications.send}?min_score=${minScore}&limit=10`,
          { method: 'POST' }
        )
        const data = await response.json()
        
        if (!data.success) {
          setLastResult({
            success: false,
            message: `Failed at batch ${batchCount}: ${data.message}. Sent ${totalSent} articles before error.`,
            sent_count: totalSent,
          })
          setProgress(null)
          return
        }
        
        totalSent += data.sent_count
        
        // Stop if no more articles to send
        if (data.sent_count === 0) {
          break
        }
        
        // Small delay between batches to avoid rate limiting
        if (i < batchesToSend - 1) {
          await new Promise(resolve => setTimeout(resolve, 1000))
        }
      }
      
      setProgress(null)
      setLastResult({
        success: true,
        message: `Successfully sent all articles in ${batchCount} batch(es)`,
        sent_count: totalSent,
      })
      
      // Refresh status after all batches
      setTimeout(() => {
        fetchStatus()
      }, 1000)
      
    } catch (error) {
      console.error('Error sending all notifications:', error)
      setProgress(null)
      setLastResult({
        success: false,
        message: 'Failed to send all notifications',
        sent_count: 0,
      })
    } finally {
      setSending(false)
    }
  }

  const testNotification = async () => {
    try {
      setSending(true)
      setLastResult(null)
      
      const response = await fetch(apiEndpoints.notifications.test, {
        method: 'POST',
      })
      const data = await response.json()
      setLastResult({
        success: data.success,
        message: `${data.message} (Test)`,
        sent_count: 1,
      })
    } catch (error) {
      console.error('Error sending test notification:', error)
      setLastResult({
        success: false,
        message: 'Failed to send test notification',
        sent_count: 0,
      })
    } finally {
      setSending(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bell className="h-5 w-5 text-blue-600" />
            <CardTitle>Slack Notifications</CardTitle>
          </div>
          {status && status.total_unsent > 0 && (
            <Badge variant="destructive" className="animate-pulse">
              {status.total_unsent} pending
            </Badge>
          )}
        </div>
        <CardDescription>
          Send high-profit news alerts (score ≥ {minScore}) to your Slack channel
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Status Display */}
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
        ) : status ? (
          <div className="space-y-4">
            {/* Pending Count */}
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-700">
                  Unsent High-Profit Articles
                </p>
                <p className="text-2xl font-bold text-gray-900">
                  {status.total_unsent}
                </p>
                {status.total_unsent > 10 && (
                  <p className="text-xs text-amber-600 mt-1">
                    ⚠️ Will send in batches of 10
                  </p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Button
                  onClick={() => sendNotifications()}
                  disabled={sending || status.total_unsent === 0}
                  className="flex items-center space-x-2"
                  size="sm"
                >
                  {sending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Sending...</span>
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4" />
                      <span>
                        Send Next 10
                      </span>
                    </>
                  )}
                </Button>
                {status.total_unsent > 10 && (
                  <Button
                    onClick={sendAllNotifications}
                    disabled={sending}
                    variant="default"
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {sending ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        <span>Sending All...</span>
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4 mr-2" />
                        <span>Send All ({status.total_unsent})</span>
                      </>
                    )}
                  </Button>
                )}
                <Button
                  onClick={testNotification}
                  disabled={sending}
                  variant="outline"
                  size="sm"
                >
                  Test Notification
                </Button>
              </div>
            </div>

            {/* Recent Result Alert */}
            {lastResult && (
              <Alert variant={lastResult.success ? 'default' : 'destructive'}>
                {lastResult.success ? (
                  <CheckCircle2 className="h-4 w-4" />
                ) : (
                  <AlertCircle className="h-4 w-4" />
                )}
                <AlertTitle>
                  {lastResult.success ? 'Success' : 'Error'}
                </AlertTitle>
                <AlertDescription>{lastResult.message}</AlertDescription>
              </Alert>
            )}

            {/* Progress Indicator */}
            {progress && (
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-blue-900">
                    Sending batch {progress.currentBatch} of {progress.totalBatches}
                  </p>
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                </div>
                <div className="w-full bg-blue-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${(progress.currentBatch / progress.totalBatches) * 100}%`,
                    }}
                  />
                </div>
                <p className="text-xs text-blue-700">
                  {progress.totalSent} articles sent so far...
                </p>
              </div>
            )}

            {/* Pending Articles List */}
            {status.total_unsent > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">
                  Pending Articles:
                </p>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {status.articles.slice(0, 10).map((article) => (
                    <div
                      key={article.id}
                      className="flex items-start justify-between p-3 bg-white border rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 line-clamp-1">
                          {article.title}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge variant="outline" className="text-xs">
                            {article.category}
                          </Badge>
                          <span className="text-xs text-gray-500">
                            {article.source}
                          </span>
                        </div>
                      </div>
                      <Badge
                        className="ml-2 flex-shrink-0"
                        variant={
                          article.profit_score >= 8
                            ? 'default'
                            : article.profit_score >= 6
                            ? 'secondary'
                            : 'outline'
                        }
                      >
                        {article.profit_score.toFixed(1)}
                      </Badge>
                    </div>
                  ))}
                  {status.articles.length > 10 && (
                    <p className="text-xs text-gray-500 text-center py-2">
                      and {status.articles.length - 10} more...
                    </p>
                  )}
                </div>
              </div>
            )}

            {status.total_unsent === 0 && (
              <div className="text-center py-8">
                <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-2" />
                <p className="text-sm text-gray-600">
                  All high-profit articles have been sent!
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  New alerts will appear here when articles are scraped
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            Failed to load notification status
          </div>
        )}
      </CardContent>
    </Card>
  )
}
