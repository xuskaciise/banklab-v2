"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import SignaturePad from "signature_pad";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Draw a signature with mouse, touch or stylus; returns a PNG File. */
export function SignaturePadDialog({
  open,
  onOpenChange,
  pending,
  onSave,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  pending: boolean;
  onSave: (file: File) => void;
}) {
  const [node, setNode] = useState<HTMLCanvasElement | null>(null);
  const padRef = useRef<SignaturePad | null>(null);
  const [empty, setEmpty] = useState(true);

  const resize = useCallback((canvas: HTMLCanvasElement) => {
    const pad = padRef.current;
    const data = pad?.toData();
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    if (!w || !h) return;
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    canvas.getContext("2d")?.scale(ratio, ratio);
    pad?.clear();
    if (data && data.length) pad?.fromData(data);
  }, []);

  useEffect(() => {
    if (!node) return;
    // Pen and background come from theme tokens, read at runtime
    // (a canvas cannot use Tailwind classes).
    const pad = new SignaturePad(node, {
      penColor: cssVar("--color-text-strong"),
      backgroundColor: cssVar("--color-card"),
    });
    padRef.current = pad;
    const onEnd = () => setEmpty(pad.isEmpty());
    pad.addEventListener("endStroke", onEnd);
    resize(node);
    const ro = new ResizeObserver(() => resize(node));
    ro.observe(node);
    return () => {
      ro.disconnect();
      pad.off();
      padRef.current = null;
    };
  }, [node, resize]);

  function save() {
    const pad = padRef.current;
    if (!pad || pad.isEmpty() || !node) return;
    node.toBlob((blob) => {
      if (!blob) return;
      onSave(new File([blob], "signature.png", { type: "image/png" }));
    }, "image/png");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) setEmpty(true);
        onOpenChange(v);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Draw signature</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-2">
          <canvas
            ref={setNode}
            aria-label="Signature drawing area"
            className="h-48 w-full touch-none rounded-lg border border-border bg-card"
          />
          <p className="text-xs text-text-muted">
            Sign inside the box using a mouse, finger or stylus.
          </p>
        </DialogBody>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={pending}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={pending || empty}
            onClick={() => {
              padRef.current?.clear();
              setEmpty(true);
            }}
          >
            Clear
          </Button>
          <Button type="button" disabled={pending || empty} onClick={save}>
            {pending ? "Saving…" : "Save signature"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
