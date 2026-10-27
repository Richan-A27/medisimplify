"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

type State = "checking" | "ready" | "limited" | "offline";

const LABELS: Record<State, { text: string; dot: string }> = {
  checking: { text: "Connecting…", dot: "bg-muted animate-pulse" },
  ready: { text: "System ready", dot: "bg-success" },
  limited: { text: "Limited mode", dot: "bg-warning-border" },
  offline: { text: "Backend offline", dot: "bg-danger" },
};

/** Compact status pill for the header; details live in the System status section. */
export function HeaderStatus() {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((health) =>
        setState(health.llm.api_key_configured && health.knowledge_base.index_ready ? "ready" : "limited"),
      )
      .catch(() => {
        if (!controller.signal.aborted) setState("offline");
      });
    return () => controller.abort();
  }, []);

  const label = LABELS[state];
  return (
    <a
      href="#status"
      className="flex items-center gap-2 rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-medium text-muted hover:text-foreground"
    >
      <span aria-hidden="true" className={`size-2 rounded-full ${label.dot}`} />
      {label.text}
    </a>
  );
}
