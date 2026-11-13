"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const STEP_MS = 300;

/**
 * Re-run = refetch, then reveal results row by row (spinner per row).
 * `isRunning(i)` is true while row i has not been revealed yet.
 */
export function useRerun(refetch: () => Promise<unknown>, total: number) {
  const [phase, setPhase] = useState<"idle" | "fetching" | "revealing">("idle");
  const [shown, setShown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
    },
    [],
  );

  const rerun = useCallback(async () => {
    if (timer.current) clearInterval(timer.current);
    setShown(0);
    setPhase("fetching");
    await refetch();
    setPhase("revealing");
    let n = 0;
    timer.current = setInterval(() => {
      n += 1;
      setShown(n);
      if (n >= total && timer.current) {
        clearInterval(timer.current);
        setPhase("idle");
      }
    }, STEP_MS);
  }, [refetch, total]);

  return {
    rerun,
    busy: phase !== "idle",
    isRunning: (i: number) => phase === "fetching" || (phase === "revealing" && i >= shown),
  };
}
