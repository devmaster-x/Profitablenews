export interface NewsArticle {
  id: number
  title: string
  content: string
  source: string
  url?: string
  category: string
  sentiment: string
  profit_score: number
  keywords: string[]
  created_at: string
  updated_at: string
}

export function getSentimentColor(sentiment: string): string {
  switch (sentiment) {
    case 'very_positive': return 'bg-green-500'
    case 'positive': return 'bg-green-300'
    case 'neutral': return 'bg-gray-300'
    case 'negative': return 'bg-red-300'
    case 'very_negative': return 'bg-red-500'
    default: return 'bg-gray-300'
  }
}

export function getProfitScoreColor(score: number): string {
  if (score >= 8) return 'text-green-600 font-bold'
  if (score >= 6) return 'text-green-500'
  if (score >= 4) return 'text-yellow-500'
  return 'text-red-500'
}

export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString()
}

export function formatCategory(category: string): string {
  return category.replace('_', ' ')
}
