"use client";

/**
 * Discussions layout — mounts a single DiscussionProvider so the live stream
 * state is shared between /discussions (RunTab) and /discussions/[id] (DiscussionPage).
 *
 * Without this, navigating from RunTab to DiscussionPage creates a new hook
 * instance with empty state, so the live stream is lost and DiscussionPage
 * falls back to polling the REST API.
 */

import { DiscussionProvider } from "@/contexts/DiscussionContext";

export default function DiscussionsLayout({ children }: { children: React.ReactNode }) {
  return <DiscussionProvider>{children}</DiscussionProvider>;
}
