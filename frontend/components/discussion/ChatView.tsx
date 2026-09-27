"use client";

import { useEffect, useRef, useCallback } from "react";
import { ChatMessage } from "./ChatMessage";
import { StreamingMessage } from "./StreamingMessage";
import { RoundHeader } from "./RoundHeader";
import type { DiscussionMessage } from "@/types";

interface ChatViewProps {
  messages: DiscussionMessage[];
  agentNames: Record<string, string>;
  streaming: boolean;
  /** ID of the agent currently generating tokens (null between turns). */
  streamingAgentId?: string | null;
  /** Accumulated token buffer for the currently-speaking agent. */
  streamingText?: string;
  /**
   * Number of participating agents. Used to decide whether the current
   * round is fully populated, which determines whether the streaming message
   * belongs to the last group or starts a new one.
   * Defaults to the number of keys in `agentNames`.
   */
  numAgents?: number;
}

interface RoundGroup {
  key: string;
  roundNumber: number;
  phase: "initial" | "discussion";
  messages: DiscussionMessage[];
}

// Minimum gap between scroll calls during token streaming. Without this,
// every rAF flush (up to 60x per second) queues a new smooth-scroll animation
// that competes with the previous one, producing visible jitter. 100ms keeps
// the view anchored without ever queueing more than one animation.
const SCROLL_THROTTLE_MS = 100;

function groupByRound(messages: DiscussionMessage[]): RoundGroup[] {
  const groups = new Map<string, RoundGroup>();

  for (const msg of messages) {
    const key = `${msg.phase}-${msg.round_number}`;
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        roundNumber: msg.round_number,
        phase: msg.phase,
        messages: [],
      });
    }
    groups.get(key)!.messages.push(msg);
  }

  return Array.from(groups.values()).sort(
    (a, b) => a.roundNumber - b.roundNumber,
  );
}

/**
 * Determine which round the currently-streaming message belongs to.
 *
 * Logic:
 *   - No messages yet → streaming turn is the very first of the discussion,
 *     which always lives in the initial phase, round 0.
 *   - Some messages exist → count how many messages the last round contains.
 *     If it has fewer than `numAgents`, the streaming turn is the next agent
 *     in the *same* round. Otherwise, the round is full and the streaming
 *     turn starts a new one.
 */
function computeStreamingRound(
  messages: DiscussionMessage[],
  numAgents: number,
): { roundNumber: number; phase: "initial" | "discussion" } | null {
  if (messages.length === 0) {
    return { roundNumber: 0, phase: "initial" };
  }

  const last = messages[messages.length - 1];
  const messagesInLastRound = messages.filter(
    (m) => m.round_number === last.round_number && m.phase === last.phase,
  ).length;

  if (messagesInLastRound < numAgents) {
    return { roundNumber: last.round_number, phase: last.phase };
  }

  // Round is full — the streaming turn opens the next one.
  if (last.phase === "initial") {
    return { roundNumber: 1, phase: "discussion" };
  }
  return { roundNumber: last.round_number + 1, phase: "discussion" };
}

export function ChatView({
  messages,
  agentNames,
  streaming,
  streamingAgentId = null,
  streamingText = "",
  numAgents,
}: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);

  // Scroll scheduling state.
  const lastScrollTimeRef = useRef(0);
  const prevMessageCountRef = useRef(0);

  const groups = groupByRound(messages);
  const effectiveNumAgents = numAgents ?? Object.keys(agentNames).length;

  const streamingRound =
    streamingAgentId !== null
      ? computeStreamingRound(messages, effectiveNumAgents)
      : null;

  const streamingAgentName = streamingAgentId
    ? agentNames[streamingAgentId] ?? streamingAgentId
    : null;

  // Does a group already exist for the round the streaming message belongs to?
  const streamingRoundHasGroup =
    streamingRound !== null &&
    groups.some(
      (g) =>
        g.roundNumber === streamingRound.roundNumber &&
        g.phase === streamingRound.phase,
    );

  // Detect manual scroll: pause auto-scroll when the user scrolls more than
  // 100px from the bottom.
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight;
    userScrolledRef.current = distanceFromBottom > 100;
  }, []);

  // Auto-scroll behaviour.
  //
  // Design:
  //   - On a *new message*, scroll smoothly and skip the throttle. The user
  //     should see a completed turn slide into view.
  //   - During *token streaming*, scroll instantaneously (`behavior: "auto"`)
  //     and throttle to SCROLL_THROTTLE_MS. Smooth scroll during streaming
  //     queues a new animation on every flush and produces jitter.
  //   - If the user has scrolled up, do nothing until they return to the
  //     bottom or the discussion completes.
  useEffect(() => {
    const isNewMessage = messages.length !== prevMessageCountRef.current;
    prevMessageCountRef.current = messages.length;

    // When streaming ends, reset the "user scrolled" flag so the next run
    // starts from a clean state.
    if (!streaming) {
      userScrolledRef.current = false;
    }

    if (userScrolledRef.current) return;

    const now = Date.now();

    // During streaming (not a new message), throttle to SCROLL_THROTTLE_MS.
    // On a new message, bypass the throttle so the completed turn is visible
    // immediately.
    if (!isNewMessage && now - lastScrollTimeRef.current < SCROLL_THROTTLE_MS) {
      return;
    }
    lastScrollTimeRef.current = now;

    bottomRef.current?.scrollIntoView({
      behavior: isNewMessage ? "smooth" : "auto",
    });
  }, [messages, streaming, streamingText]);

  if (messages.length === 0 && !streamingAgentId) {
    return (
      <div className="flex flex-1 items-center justify-center py-16 text-sm text-slate-400 dark:text-slate-500">
        Waiting for first turn…
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      className="flex flex-col gap-6 overflow-y-auto px-4 py-4"
      aria-live={streaming ? "polite" : undefined}
      aria-label="Discussion messages"
    >
      {groups.map((group) => {
        const isStreamingGroup =
          streamingRound !== null &&
          streamingRound.roundNumber === group.roundNumber &&
          streamingRound.phase === group.phase;

        return (
          <div key={group.key}>
            <RoundHeader
              roundNumber={group.roundNumber}
              phase={group.phase}
            />
            <div className="mt-4 space-y-6">
              {group.messages.map((msg) => (
                <ChatMessage
                  key={msg.message_id}
                  message={msg}
                  agentName={agentNames[msg.sender_id] ?? msg.sender_id}
                />
              ))}

              {/*
                If the streaming turn belongs to this round, render the
                StreamingMessage at the end of this group instead of floating
                it after all groups. This keeps the streaming text visually
                anchored to the correct round header.
              */}
              {isStreamingGroup && streamingAgentId && streamingAgentName && (
                <StreamingMessage
                  agentId={streamingAgentId}
                  agentName={streamingAgentName}
                  text={streamingText}
                />
              )}
            </div>
          </div>
        );
      })}

      {/*
        If the streaming turn is the first speaker of a new round that has no
        completed messages yet, render it as its own group with a RoundHeader.
        Without this, a streaming message arriving at the start of Round 1
        would have no header above it until the first turn of that round
        completed.
      */}
      {streamingAgentId &&
        streamingAgentName &&
        streamingRound &&
        !streamingRoundHasGroup && (
          <div
            key={`streaming-${streamingRound.phase}-${streamingRound.roundNumber}`}
          >
            <RoundHeader
              roundNumber={streamingRound.roundNumber}
              phase={streamingRound.phase}
            />
            <div className="mt-4 space-y-6">
              <StreamingMessage
                agentId={streamingAgentId}
                agentName={streamingAgentName}
                text={streamingText}
              />
            </div>
          </div>
        )}

      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}