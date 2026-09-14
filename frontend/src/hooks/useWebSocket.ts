import { useEffect, useRef } from "react";

import type { WsEnvelope } from "../api/types";
import { usePodStore } from "../store/podStore";

const WS_URL = import.meta.env.VITE_WS_URL ?? "ws://localhost:8000/ws";
const MAX_BACKOFF_MS = 10_000;

/**
 * Owns the single WebSocket connection for the whole app and feeds every
 * incoming event into the pod store. Reconnects with capped exponential
 * backoff -- the backend may not be up yet on first load, or a long
 * pipeline run may briefly outlive a dev-server reload.
 */
export function useWebSocket(): void {
  const applyEvent = usePodStore((s) => s.applyEvent);
  const setWsConnected = usePodStore((s) => s.setWsConnected);
  const attemptRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedByUsRef = useRef(false);

  useEffect(() => {
    closedByUsRef.current = false;
    let socket: WebSocket | null = null;

    const connect = () => {
      socket = new WebSocket(WS_URL);

      socket.onopen = () => {
        attemptRef.current = 0;
        setWsConnected(true);
      };

      socket.onmessage = (event) => {
        try {
          const envelope = JSON.parse(event.data) as WsEnvelope;
          if (envelope.kind === "event") {
            applyEvent(envelope.event);
          }
        } catch {
          // ignore malformed frames rather than crashing the whole feed
        }
      };

      socket.onclose = () => {
        setWsConnected(false);
        if (closedByUsRef.current) return;
        const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF_MS);
        attemptRef.current += 1;
        timerRef.current = setTimeout(connect, delay);
      };

      socket.onerror = () => {
        socket?.close();
      };
    };

    connect();

    return () => {
      closedByUsRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      socket?.close();
    };
  }, [applyEvent, setWsConnected]);
}
