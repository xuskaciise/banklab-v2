import { useLayoutEffect, useState, type RefObject } from "react";

const PANEL_H = 380;

export type Pos = {
  left: number;
  width: number;
  top?: number;
  bottom?: number;
  maxH: number;
};

/** Fixed-position coords for a popover anchored to a trigger; flips upward when cramped. */
export function usePanelPosition(
  open: boolean,
  trigger: RefObject<HTMLElement | null>,
): Pos | null {
  const [pos, setPos] = useState<Pos | null>(null);
  useLayoutEffect(() => {
    if (!open) return;
    function place() {
      const r = trigger.current?.getBoundingClientRect();
      if (!r) return;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const mobile = vw < 640;
      const width = mobile ? vw - 16 : Math.min(Math.max(r.width, 320), vw - 16);
      const left = mobile ? 8 : Math.min(Math.max(8, r.left), vw - width - 8);
      const below = vh - r.bottom - 8;
      const above = r.top - 8;
      const up = below < Math.min(PANEL_H, 300) && above > below;
      setPos(
        up
          ? { left, width, bottom: vh - r.top + 4, maxH: Math.min(PANEL_H, above - 4) }
          : { left, width, top: r.bottom + 4, maxH: Math.min(PANEL_H, below - 4) },
      );
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, trigger]);
  return pos;
}
