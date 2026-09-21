import apiClient from './client';

export interface AnalyticsOverview {
  total_conversations: number;
  ai_resolved_conversations: number;
  human_escalations: number;
  ai_resolution_rate: number;
  average_confidence: number;
  average_latency_ms: number;
  top_intents: Array<{ intent: string; count: number }>;
  channels: {
    telegram: number;
    webchat: number;
  };
}

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const resp = await apiClient.get<AnalyticsOverview>('/analytics/overview');
  return resp.data;
}
