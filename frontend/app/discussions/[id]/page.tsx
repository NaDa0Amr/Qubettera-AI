"use client";

import { use } from "react";
import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { useDiscussion } from "@/contexts/DiscussionContext";
import { ChatView } from "@/components/discussion/ChatView";
import { ParticipantList } from "@/components/discussion/ParticipantList";
import { EvidencePanel } from "@/components/discussion/EvidencePanel";
import { BriefPanel } from "@/components/discussion/BriefPanel";
import { StatusPill } from "@/components/layout/StatusPill";
import { Button } from "@/components/ui/Button";
import { InlineError } from "@/components/ui/ErrorState";
import { toast } from "@/components/ui/Toast";
import { BarChart2, ArrowLeft } from "lucide-react";
import type { DiscussionDetail, EvidenceItem } from "@/types";
import { truncate } from "@/lib/format";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default function DiscussionPage({ params }: PageProps) {
  const { id } = use(params);
  const { state, startDiscussion } = useDiscussion();
  const [replayData, setReplayData] = useState<DiscussionDetail | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);
  const [replayError, setReplayError] = useState<string | null>(null);

  // A discussion is "live" when the React context has an active SSE stream:
  //   a) Context ID matches URL and stream isn't idle, OR
  //   b) Stream is active but discussionId not yet confirmed (race window
  //      between router.push() and the first stream_started event).
  const isLive =
    (state.discussionId === id && state.status !== "idle") ||
    (state.status === "streaming" && state.discussionId === null);

  // ── Replay (no live SSE context) ─────────────────────────────────────────
  // When the user reaches this page via page-refresh, History-tab link, or
  // direct URL the context starts idle, so isLive is false. We fetch the
  // transcript from the REST API and poll every 3 s while status is "running"
  // so that an ongoing discussion still updates without needing an SSE
  // re-attachment mechanism on the backend.

  // Number of consecutive polls that returned the same message count.
  const staleCountRef = useRef(0);
  // Message count from the previous poll — used to detect stability.
  const prevMsgCountRef = useRef(-1);

  const fetchReplay = useCallback(() => {
    return fetch(`/api/discussions/${id}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<DiscussionDetail>;
      });
  }, [id]);

  // Initial fetch — fires whenever id, isLive, or stream status changes.
  useEffect(() => {
    if (isLive || state.status === "streaming") return;
    setReplayLoading(true);
    setReplayError(null);
    staleCountRef.current = 0;
    prevMsgCountRef.current = -1;
    fetchReplay()
      .then((data) => {
        prevMsgCountRef.current = data.messages.length;
        setReplayData(data);
        setReplayLoading(false);
      })
      .catch((err: unknown) => {
        setReplayError(err instanceof Error ? err.message : "Failed to load discussion.");
        setReplayLoading(false);
      });
  }, [id, isLive, state.status, fetchReplay]);

  // Polling — starts after initial load when the discussion is still running.
  useEffect(() => {
    // Only poll in replay mode and after the initial load has finished.
    if (isLive || state.status === "streaming") return;
    if (replayLoading || !replayData) return;
    // Stop polling immediately if the transcript is already in a terminal state.
    if (replayData.status === "completed" || replayData.status === "failed") return;
    // staleCountRef is incremented inside the interval without triggering a
    // re-render, so we must also check it here on every effect re-run.
    if (staleCountRef.current >= 3) return;

    const interval = setInterval(() => {
      fetchReplay()
        .then((data) => {
          const newCount = data.messages.length;
          const isTerminal =
            data.status === "completed" || data.status === "failed";

          if (newCount > prevMsgCountRef.current) {
            // New messages arrived — update UI and reset stale counter.
            staleCountRef.current = 0;
            prevMsgCountRef.current = newCount;
            setReplayData(data); // triggers effect re-run for next interval
          } else {
            // No new messages this poll.
            staleCountRef.current += 1;
          }

          if (isTerminal) {
            // Discussion finished — show final state and stop polling.
            setReplayData(data);
            clearInterval(interval); // self-terminate immediately
          } else if (staleCountRef.current >= 3) {
            // 9 s of no new messages — assume the discussion has ended
            // without a proper completion event (e.g. backend crashed).
            clearInterval(interval); // self-terminate immediately
          }
        })
        .catch(() => {
          staleCountRef.current += 1;
          if (staleCountRef.current >= 3) {
            clearInterval(interval);
          }
        });
    }, 3_000);

    return () => clearInterval(interval);
  }, [id, isLive, state.status, replayLoading, replayData, fetchReplay]);

  // Toast on discussion completion.
  useEffect(() => {
    if (state.status === "done") {
      toast("success", "Discussion complete. Preparing analytics…");
      // Prefetch analytics in the background so it is cached when the user navigates.
      void fetch(`/api/week4/analytics/${state.discussionId}`, { keepalive: true });
    }
  }, [state.status, state.discussionId]);

  // Determine what data to display.
  const messages = isLive ? state.messages : (replayData?.messages ?? []);
  const participants = isLive
    ? state.participants
    : Object.fromEntries(
        (replayData?.config.participant_ids ?? []).map((pid) => [
          pid,
          { id: pid, status: "spoke" as const },
        ]),
      );

  // Build agent name map from messages (since we may not have /api/personas loaded here).
  const agentNames: Record<string, string> = {};
  for (const msg of messages) {
    if (!agentNames[msg.sender_id]) {
      // Derive a human-readable name from the ID: dr_aris -> Dr Aris.
      agentNames[msg.sender_id] = msg.sender_id
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");
    }
  }

  // Latest turn evidence for sidebar.
  const lastMessage = messages[messages.length - 1];
  const latestEvidence: EvidenceItem[] = lastMessage?.evidence ?? [];

  // Status derived from live or replay context.
  // replayRunning = discussion is ongoing but this tab has no SSE connection
  // (page-refresh / History-tab link); we are polling REST for updates.
  const replayRunning = !isLive && replayData?.status === "running";
  const streamStatus = isLive ? state.status : "done";
  const topicLabel = isLive
    ? (state.config?.brief.objective ?? "Discussion")
    : (replayData?.topic ?? id);

  return (
    <div className="flex h-[calc(100dvh-4rem)] flex-col overflow-hidden">
      {/* Page header */}
      <div className="flex shrink-0 items-center justify-between border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/discussions"
            className="shrink-0 rounded-md p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Back to discussions"
          >
            <ArrowLeft className="h-5 w-5" aria-hidden="true" />
          </Link>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-slate-900 dark:text-slate-100 truncate">
              {truncate(topicLabel, 80)}
            </h1>
            <p className="text-xs font-mono text-slate-400 mt-0.5">{id.slice(0, 8)}…</p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <StatusPill
            status={
              streamStatus === "streaming" || replayRunning
                ? "streaming"
                : streamStatus === "done" && !replayRunning
                  ? "complete"
                  : streamStatus === "error"
                    ? "error"
                    : "idle"
            }
            label={
              streamStatus === "streaming"
                ? `Streaming · R${Math.max(...messages.map((m) => m.round_number), 0)}/${state.config?.num_rounds ?? "?"}`
                : replayRunning
                  ? `Updating… · ${messages.length} turns`
                  : streamStatus === "done"
                    ? "Complete"
                    : streamStatus === "error"
                      ? "Failed"
                      : "Replay"
            }
          />

          {(streamStatus === "done" || replayData) && (
            <Link href={`/analytics/${id}`}>
              <Button size="sm" variant="primary" id={`view-analytics-${id}`}>
                <BarChart2 className="h-4 w-4" aria-hidden="true" />
                View Analytics
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Brief panel */}
      {(state.brief || replayData?.config.brief) && (
        <div className="shrink-0 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
          <BriefPanel
            brief={(state.brief ?? replayData!.config.brief)!}
            participantIds={state.config?.participant_ids ?? replayData?.config.participant_ids ?? []}
            agentNames={agentNames}
            numRounds={state.config?.num_rounds ?? replayData?.config.num_rounds ?? 0}
            discussionId={id}
            createdAt={replayData?.created_at ?? new Date().toISOString()}
          />
        </div>
      )}

      {/* Error banner */}
      {state.status === "error" && (
        <div className="shrink-0 px-4 pt-3">
          <InlineError
            message={state.error ?? "Stream failed."}
            onRetry={() => {
              if (state.config) {
                startDiscussion({
                  topic: state.config.brief.objective,
                  participant_ids: state.config.participant_ids,
                  num_rounds: state.config.num_rounds,
                  mode: "live",
                });
              }
            }}
          />
        </div>
      )}

      {/* Main layout — chat + sidebar */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat column */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {replayLoading ? (
            <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
              Loading transcript…
            </div>
          ) : replayError && !isLive ? (
            <div className="p-6">
              <InlineError message={replayError} />
            </div>
          ) : (
            <ChatView
              messages={messages}
              agentNames={agentNames}
              streaming={streamStatus === "streaming"}
              streamingAgentId={isLive ? state.streamingAgentId : null}
              streamingText={isLive ? state.streamingText : ""}
            />
          )}
        </div>

        {/* Sidebar */}
        <aside
          className="hidden md:flex w-64 shrink-0 flex-col border-l border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 overflow-y-auto"
          aria-label="Discussion sidebar"
        >
          <div className="p-4 space-y-6">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-3">
                Participants
              </h2>
              <ParticipantList
                participants={participants}
                agentNames={agentNames}
              />
            </div>

            <hr className="border-slate-200 dark:border-slate-700" />

            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-3">
                Evidence — Last Turn
              </h2>
              <EvidencePanel evidence={latestEvidence} />
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
