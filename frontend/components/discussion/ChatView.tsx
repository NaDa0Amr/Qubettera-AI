"use client";

import { useEffect, useRef, useCallback } from "react";
import { ChatMessage } from "./ChatMessage";
import { StreamingMessage } from "./StreamingMessage";
import { RoundHeader } from "./RoundHeader";
import type { DiscussionMessage, StreamingDraft } from "@/types";

interface ChatViewProps {
  messages: DiscussionMessage[];
  agentNames: Record<string, string>;
  streaming: boolean;
  /** Partial messages from all concurrently generating agents. */
  streamingMessages?: Record<string, StreamingDraft>;
}

interface RoundGroup {
  key: string;
  roundNumber: number;
  phase: "initial" | "discussion";
  messages: DiscussionMessage[];
  drafts: Array<{ agentId: string; text: string }>;
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
        drafts: [],
      });
    }
    groups.get(key)!.messages.push(msg);
  }

  return Array.from(groups.values()).sort(
    (a, b) => a.roundNumber - b.roundNumber,
  );
}

export function ChatView({
  messages,
  agentNames,
  streaming,
  streamingMessages = {},
}: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);

  // Scroll scheduling state.
  const lastScrollTimeRef = useRef(0);
  const prevMessageCountRef = useRef(0);

  const groups = groupByRound(messages);
  const byKey = new Map(groups.map((group) => [group.key, group]));
  for (const [agentId, draft] of Object.entries(streamingMessages)) {
    const roundNumber = draft.round ?? messages.at(-1)?.round_number ?? 0;
    const phase = roundNumber === 0 ? "initial" : "discussion";
    const key = `${phase}-${roundNumber}`;
    let group = byKey.get(key);
    if (!group) {
      group = { key, phase, roundNumber, messages: [], drafts: [] };
      groups.push(group);
      byKey.set(key, group);
    }
    group.drafts.push({ agentId, text: draft.text });
  }
  groups.sort((a, b) => a.roundNumber - b.roundNumber);

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
  }, [messages, streaming, streamingMessages]);

  if (groups.length === 0) {
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
      {groups.map((group) => (
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

            {group.drafts.map(({ agentId, text }) => (
              <StreamingMessage
                key={agentId}
                agentId={agentId}
                agentName={agentNames[agentId] ?? agentId}
                text={text}
              />
            ))}
          </div>
        </div>
      ))}

      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}
