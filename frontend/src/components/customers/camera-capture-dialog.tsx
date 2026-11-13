"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const SIZE = 600;

function cameraError(e: unknown): string {
  const name = e instanceof DOMException ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError")
    return "Camera access was blocked. Allow the camera in your browser, or use Upload instead.";
  if (name === "NotFoundError" || name === "OverconstrainedError")
    return "No camera was found. Plug one in, or use Upload instead.";
  if (name === "NotReadableError")
    return "The camera is in use by another application.";
  return "Could not start the camera.";
}

/** Take a photo from a webcam / USB camera; returns a square JPEG File. */
export function CameraCaptureDialog({
  open,
  onOpenChange,
  pending,
  onUse,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  pending: boolean;
  onUse: (file: File) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);
  const [shot, setShot] = useState<{ blob: Blob; url: string } | null>(null);

  const supported =
    typeof window !== "undefined" &&
    window.isSecureContext &&
    !!navigator.mediaDevices?.getUserMedia;

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setLive(false);
  }, []);

  const start = useCallback(
    async (id: string) => {
      stop();
      setError(null);
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: id ? { deviceId: { exact: id } } : true,
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
        setLive(true);
        const list = (await navigator.mediaDevices.enumerateDevices()).filter(
          (d) => d.kind === "videoinput",
        );
        setDevices(list);
        const active = stream.getVideoTracks()[0]?.getSettings().deviceId;
        if (active) setDeviceId(active);
      } catch (e) {
        setError(cameraError(e));
      }
    },
    [stop],
  );

  const streaming = open && !shot && supported;
  useEffect(() => {
    if (!streaming) return;
    // Starting the camera is an external-system sync; state is set after the await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void start("");
    return stop;
  }, [streaming, start, stop]);

  useEffect(
    () => () => {
      if (shot) URL.revokeObjectURL(shot.url);
    },
    [shot],
  );

  function capture() {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const side = Math.min(v.videoWidth, v.videoHeight);
    const canvas = document.createElement("canvas");
    canvas.width = SIZE;
    canvas.height = SIZE;
    canvas
      .getContext("2d")
      ?.drawImage(
        v,
        (v.videoWidth - side) / 2,
        (v.videoHeight - side) / 2,
        side,
        side,
        0,
        0,
        SIZE,
        SIZE,
      );
    canvas.toBlob(
      (blob) => {
        if (blob) setShot({ blob, url: URL.createObjectURL(blob) });
      },
      "image/jpeg",
      0.9,
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) {
          stop();
          setShot(null);
          setError(null);
        }
        onOpenChange(v);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Take photo</DialogTitle>
        </DialogHeader>
        <DialogBody className="space-y-3">
          {!supported ? (
            <p className="text-sm text-text-body">
              Camera needs localhost or HTTPS. Use Upload to add a photo instead.
            </p>
          ) : (
            <>
              {!shot && devices.length > 1 && (
                <select
                  aria-label="Camera"
                  className="h-9 w-full rounded-lg border border-border bg-card px-2 text-sm"
                  value={deviceId}
                  onChange={(e) => {
                    setDeviceId(e.target.value);
                    void start(e.target.value);
                  }}
                >
                  {devices.map((d, i) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || `Camera ${i + 1}`}
                    </option>
                  ))}
                </select>
              )}
              <div className="mx-auto aspect-square w-full max-w-sm overflow-hidden rounded-lg border border-border bg-surface">
                {shot ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={shot.url}
                    alt="Captured photo"
                    className="size-full object-cover"
                  />
                ) : (
                  <video
                    ref={videoRef}
                    muted
                    playsInline
                    className="size-full object-cover"
                  />
                )}
              </div>
              {error && (
                <p role="alert" className="text-sm text-fin-danger">
                  {error}
                </p>
              )}
            </>
          )}
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
          {supported && shot ? (
            <>
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => setShot(null)}
              >
                Retake
              </Button>
              <Button
                type="button"
                disabled={pending}
                onClick={() =>
                  onUse(new File([shot.blob], "photo.jpg", { type: "image/jpeg" }))
                }
              >
                {pending ? "Saving…" : "Use photo"}
              </Button>
            </>
          ) : (
            supported && (
              <Button type="button" disabled={!live} onClick={capture}>
                Capture
              </Button>
            )
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
