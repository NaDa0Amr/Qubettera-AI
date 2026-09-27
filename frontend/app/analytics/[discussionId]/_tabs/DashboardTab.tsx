"use client";

import { MetricCard } from "@/components/analytics/MetricCard";
import { OpinionChangeCard } from "../_metrics/OpinionChangeCard";
import { AgreementCard } from "../_metrics/AgreementCard";
import { InfluenceCard } from "../_metrics/InfluenceCard";
import { SentimentCard } from "../_metrics/SentimentCard";
import { InteractionGraphCard } from "../_metrics/InteractionGraphCard";
import type { AnalyticsState, MetricName } from "@/types";

interface DashboardTabProps {
  discussionId: string;
  state: AnalyticsState;
  retryMetric: (metric: MetricName) => void;
}

export function DashboardTab({ discussionId, state, retryMetric }: DashboardTabProps) {
  const { metrics } = state;

  return (
    <div className="space-y-6">
      {/* Top row: 2 columns */}
      <div className="grid gap-6 lg:grid-cols-2">
        <MetricCard
          title="Opinion Change"
          description="Agent stance across rounds (−1 = against, +1 = in favor)"
          status={metrics.opinion_change}
          onRetry={() => retryMetric("opinion_change")}
          minHeight="min-h-96"
          staggerIndex={0}
        >
          {(data) => <OpinionChangeCard data={data} />}
        </MetricCard>

        <MetricCard
          title="Agreement"
          description="Round-by-round group alignment (0 = divergent, 1 = unanimous)"
          status={metrics.agreement}
          onRetry={() => retryMetric("agreement")}
          minHeight="min-h-96"
          staggerIndex={1}
        >
          {(data) => <AgreementCard data={data} />}
        </MetricCard>
      </div>

      {/* Second row: 2 columns */}
      <div className="grid gap-6 lg:grid-cols-2">
        <MetricCard
          title="Influence"
          description="DeGroot-model influence weight per agent"
          status={metrics.influence}
          onRetry={() => retryMetric("influence")}
          minHeight="min-h-80"
          staggerIndex={2}
        >
          {(data) => <InfluenceCard data={data} />}
        </MetricCard>

        <MetricCard
          title="Sentiment"
          description="Per-message sentiment score (−1 negative, +1 positive)"
          status={metrics.sentiment}
          onRetry={() => retryMetric("sentiment")}
          minHeight="min-h-80"
          staggerIndex={3}
        >
          {(data) => <SentimentCard data={data} />}
        </MetricCard>
      </div>

      {/* Full-width: Interaction Graph */}
      <MetricCard
        title="Interaction Graph"
        description="Edge width proportional to influence magnitude"
        status={metrics.visuals}
        onRetry={() => retryMetric("visuals")}
        minHeight="min-h-64"
        staggerIndex={4}
      >
        {(data) => (
          <InteractionGraphCard
            discussionId={discussionId}
            visualsData={data}
            analyticsState={state}
          />
        )}
      </MetricCard>
    </div>
  );
}
