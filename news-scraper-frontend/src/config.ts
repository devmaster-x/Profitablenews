// Frontend Configuration
export const config = {
  // API Configuration
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  
  // App Configuration
  appName: 'News Scraper Dashboard',
  appVersion: '1.0.0',
  
  // Default Settings
  defaultPageSize: 12,
  maxPageSize: 100,
  
  // Profit Analysis Settings
  defaultMinProfitScore: 7.0,
  defaultAlertThreshold: 8.0,
  
  // UI Settings
  refreshInterval: 30000, // 30 seconds
  maxRetries: 3,
  
  // Feature Flags
  enableRealTimeUpdates: true,
  enableProfitAnalysis: true,
  enableMarketTrends: true,
}

// Environment helpers
export const isDevelopment = import.meta.env.DEV
export const isProduction = import.meta.env.PROD

// API endpoints
export const apiEndpoints = {
  health: `${config.apiBaseUrl}/healthz`,
  articles: `${config.apiBaseUrl}/articles`,
  stats: `${config.apiBaseUrl}/stats`,
  scrape: `${config.apiBaseUrl}/scrape`,
  opportunities: `${config.apiBaseUrl}/opportunities`,
  alerts: `${config.apiBaseUrl}/alerts`,
  trends: `${config.apiBaseUrl}/trends`,
  companies: `${config.apiBaseUrl}/companies`,
  scheduler: {
    start: `${config.apiBaseUrl}/scheduler/start`,
    stop: `${config.apiBaseUrl}/scheduler/stop`,
    status: `${config.apiBaseUrl}/scheduler/status`,
    runNow: `${config.apiBaseUrl}/scheduler/run-now`,
  }
} 