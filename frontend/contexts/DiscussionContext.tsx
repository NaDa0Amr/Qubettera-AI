"use client";

/**
 * DiscussionContext
 *
 * Lifts `useStreamingDiscussion` state out of RunTab so that when the router
 * navigates to /discussions/[id] the live stream survives the component unmount.
 *
 * Provider is mounted in the /discussions layout so both /discussions (RunTab)
 * and /discussions/[id] (DiscussionPage) share the same hook instance.
 */

import { createContext, useContext, ReactNode } from "react";
import { useStreamingDiscussion } from "@/hooks/useStreamingDiscussion";
import type { DiscussionStreamState, DiscussRequest } from "@/types";

interface DiscussionContextValue {
  state: DiscussionStreamState;
  startDiscussion: (request: DiscussRequest) => void;
  stopDiscussion: () => void;
  reset: () => void;
}

const DiscussionContext = createContext<DiscussionContextValue | null>(null);

export function DiscussionProvider({ children }: { children: ReactNode }) {
  const hook = useStreamingDiscussion();
  return (
    <DiscussionContext.Provider value={hook}>
      {children}
    </DiscussionContext.Provider>
  );
}

export function useDiscussion(): DiscussionContextValue {
  const ctx = useContext(DiscussionContext);
  if (!ctx) {
    throw new Error("useDiscussion must be used inside <DiscussionProvider>");
  }
  return ctx;
}
