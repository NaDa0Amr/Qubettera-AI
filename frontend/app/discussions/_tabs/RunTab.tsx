"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { usePersonas } from "@/hooks/usePersonas";
import { useDiscussion } from "@/contexts/DiscussionContext";
import { PersonaCard } from "@/components/personas/PersonaCard";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { InlineError } from "@/components/ui/ErrorState";
import { toast } from "@/components/ui/Toast";
import { ChevronDown, ChevronUp, Lightbulb } from "lucide-react";
import type { DiscussRequest } from "@/types";

const MAX_TOPIC_LEN = 4000;
const MIN_TOPIC_LEN = 20;

const SUGGESTED_BRIEFS: Array<{ label: string; topic: string }> = [
  {
    label: "MoE vs Dense",
    topic:
      "Objective: Decide whether to use Mixture-of-Experts (MoE) layers or traditional Dense feed-forward layers as the default in our next 1B parameter transformer.\n\nConstraints: Single A100 GPU (40GB), 3-month training timeline.\n\nTopics to discuss:\n- Routing stability and load-balancing auxiliary losses\n- Training convergence behavior under constrained hardware\n- Inference cost at deployment vs. training cost\n\nStrict Notes: Cite all evidence with exact source URLs.",
  },
  {
    label: "SSM vs Attention",
    topic:
      "Objective: Evaluate whether State-Space Models (SSMs, e.g. Mamba) should replace or supplement self-attention in our architecture.\n\nConstraints: Long-context workloads (up to 32k tokens), latency-sensitive deployment.\n\nTopics to discuss:\n- Linear vs quadratic scaling with sequence length\n- Expressive power for in-context learning\n- Hardware utilization on A100 GPUs\n\nStrict Notes: Cite all evidence with exact source URLs.",
  },
  {
    label: "Sliding Window vs Global Attention",
    topic:
      "Objective: Decide between sliding window attention (Longformer-style) and full global attention for handling long documents.\n\nConstraints: Maximum context of 128k tokens, single-pass inference required.\n\nTopics to discuss:\n- Memory footprint of global vs. local attention patterns\n- Task performance on long-document benchmarks\n- Implementation complexity in production\n\nStrict Notes: Cite all evidence with exact source URLs.",
  },
];

const TEMPLATE = `Objective: <one sentence describing the architecture decision>

Constraints: <hardware, budget, timeline>

Topics to discuss:
- <sub-topic 1>
- <sub-topic 2>
- <sub-topic 3>

Strict Notes: Cite all evidence with exact source URLs.`;

export function RunTab() {
  const router = useRouter();
  const { personas, loading: personasLoading } = usePersonas();
  const { state, startDiscussion } = useDiscussion();

  const [topic, setTopic] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [rounds, setRounds] = useState(3);
  const [mode, setMode] = useState<"live" | "fake">("live");
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // When personas load, default to all selected.
  const allSelected = personas.length > 0 && selectedIds.size === 0;
  const effectiveIds = allSelected ? new Set(personas.map((p) => p.id)) : selectedIds;

  function togglePersona(id: string) {
    setSelectedIds((prev) => {
      // If we are in "all selected" state (empty set = all), first materialize all IDs.
      const current = prev.size === 0 ? new Set(personas.map((p) => p.id)) : new Set(prev);
      if (current.has(id)) {
        current.delete(id);
      } else {
        current.add(id);
      }
      return current;
    });
  }

  const topicLen = topic.length;
  const isTopicValid = topicLen >= MIN_TOPIC_LEN && topicLen <= MAX_TOPIC_LEN;
  const isParticipantsValid = effectiveIds.size >= 2;
  const canStart = isTopicValid && isParticipantsValid && rounds >= 3 && state.status === "idle";

  function handleStart() {
    if (!canStart) return;

    const allPersonaIds = new Set(personas.map((p) => p.id));
    const isAllSelected =
      effectiveIds.size === allPersonaIds.size &&
      [...effectiveIds].every((id) => allPersonaIds.has(id));

    const request: DiscussRequest = {
      topic,
      participant_ids: isAllSelected ? null : [...effectiveIds],
      num_rounds: rounds,
      mode,
    };

    startDiscussion(request);
  }

  // Navigate to the discussion page once we have an ID.
  // Must be in useEffect — calling router.push() during render is forbidden.
  useEffect(() => {
    if (state.discussionId && state.status !== "idle") {
      router.push(`/discussions/${state.discussionId}`);
    }
  }, [state.discussionId, state.status, router]);

  // Show error toast — also a side effect, must not run during render.
  useEffect(() => {
    if (state.status === "error" && state.error) {
      toast("error", `Failed to start: ${state.error}`);
    }
  }, [state.status, state.error]);

  return (
    <div className="max-w-3xl space-y-8">
      {/* Discussion Brief */}
      <section aria-labelledby="brief-heading">
        <div className="flex items-start justify-between mb-2">
          <label
            id="brief-heading"
            htmlFor="topic-input"
            className="block text-sm font-semibold text-slate-900 dark:text-slate-100"
          >
            Discussion Brief
          </label>
          <button
            type="button"
            onClick={() => setTopic(TEMPLATE)}
            className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 transition-colors"
          >
            <Lightbulb className="h-3.5 w-3.5" aria-hidden="true" />
            Insert template
          </button>
        </div>

        <textarea
          id="topic-input"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          rows={10}
          maxLength={MAX_TOPIC_LEN}
          placeholder="Describe the architecture decision to debate. Include the objective, constraints, topics, and any strict notes..."
          className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-4 py-3 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 resize-y focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 transition-shadow"
          aria-describedby="topic-counter topic-hint"
        />
        <div className="flex items-center justify-between mt-1.5">
          <p id="topic-hint" className="text-xs text-slate-400 dark:text-slate-500">
            {topicLen < MIN_TOPIC_LEN
              ? `Minimum ${MIN_TOPIC_LEN} characters required`
              : ""}
          </p>
          <p
            id="topic-counter"
            className={`text-xs font-mono tabular-nums ${topicLen > MAX_TOPIC_LEN * 0.9 ? "text-amber-600" : "text-slate-400"}`}
            aria-live="polite"
          >
            {topicLen.toLocaleString()} / {MAX_TOPIC_LEN.toLocaleString()}
          </p>
        </div>

        {/* Suggested briefs */}
        <div className="flex flex-wrap gap-2 mt-3">
          {SUGGESTED_BRIEFS.map(({ label, topic: preset }) => (
            <button
              key={label}
              type="button"
              onClick={() => setTopic(preset)}
              className="rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-1 text-xs font-medium text-slate-600 dark:text-slate-300 hover:border-indigo-300 hover:text-indigo-600 dark:hover:border-indigo-600 dark:hover:text-indigo-400 transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <hr className="border-slate-200 dark:border-slate-700" />

      {/* Participants */}
      <section aria-labelledby="participants-heading">
        <div className="flex items-center justify-between mb-4">
          <h2 id="participants-heading" className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Participants
          </h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {effectiveIds.size} of {personas.length} selected
            {!isParticipantsValid && (
              <span className="text-red-500 ml-2">(minimum 2)</span>
            )}
          </span>
        </div>

        {personasLoading ? (
          <div className="grid gap-3 sm:grid-cols-2" aria-busy="true">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 rounded-lg border border-slate-200 dark:border-slate-700">
                <Skeleton height="h-full" className="w-full" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {personas.map((persona) => (
              <PersonaCard
                key={persona.id}
                persona={persona}
                selectable
                selected={effectiveIds.has(persona.id)}
                onToggle={togglePersona}
              />
            ))}
          </div>
        )}
      </section>

      <hr className="border-slate-200 dark:border-slate-700" />

      {/* Rounds */}
      <section aria-labelledby="rounds-heading">
        <div className="flex items-center gap-6">
          <div>
            <label
              id="rounds-heading"
              htmlFor="rounds-select"
              className="block text-sm font-semibold text-slate-900 dark:text-slate-100 mb-1"
            >
              Rounds
            </label>
            <select
              id="rounds-select"
              value={rounds}
              onChange={(e) => setRounds(Number(e.target.value))}
              className="rounded-md border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value={3}>3</option>
              <option value={4}>4</option>
              <option value={5}>5</option>
            </select>
          </div>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-5">
            Total turns = {effectiveIds.size} agents × ({rounds} + 1) ={" "}
            {effectiveIds.size * (rounds + 1)}
          </p>
        </div>
      </section>

      {/* Advanced */}
      <section>
        <button
          type="button"
          onClick={() => setAdvancedOpen((o) => !o)}
          aria-expanded={advancedOpen}
          aria-controls="advanced-panel"
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
        >
          {advancedOpen ? (
            <ChevronUp className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          )}
          Advanced
        </button>

        {advancedOpen && (
          <div
            id="advanced-panel"
            className="mt-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 p-4 space-y-3"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
              Mode
            </p>
            {(["live", "fake"] as const).map((m) => (
              <label key={m} className="flex items-start gap-3 cursor-pointer">
                <input
                  type="radio"
                  name="mode"
                  value={m}
                  checked={mode === m}
                  onChange={() => setMode(m)}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-100 capitalize">
                    {m === "live" ? "Live" : "Fake (no LLM)"}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {m === "live"
                      ? "Real LLM calls with evidence retrieval. May take several minutes."
                      : "Deterministic stubs — runs instantly. No evidence. Analytics unavailable."}
                  </p>
                </div>
              </label>
            ))}
          </div>
        )}
      </section>

      {/* Error */}
      {state.error && state.status !== "streaming" && (
        <InlineError message={state.error} />
      )}

      {/* Start button */}
      <div className="flex justify-end pt-2">
        <Button
          id="start-discussion-btn"
          onClick={handleStart}
          disabled={!canStart}
          loading={state.status === "streaming"}
          size="lg"
          title={
            !isTopicValid
              ? "Brief must be at least 20 characters"
              : !isParticipantsValid
                ? "Select at least 2 participants"
                : undefined
          }
        >
          {state.status === "streaming" ? "Connecting…" : "Start Discussion"}
        </Button>
      </div>
    </div>
  );
}
