import { wsUrl } from "./api";
import { useReviewStore } from "../store/reviewStore";
import type { ReviewEvent } from "../types/domain";

let socket: WebSocket | null = null;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let currentReviewId: string | null = null;

function scheduleReconnect() {
  if (!currentReviewId) return;
  const delay = Math.min(1000 * 2 ** reconnectAttempt, 10000);
  reconnectAttempt += 1;
  reconnectTimer = setTimeout(() => connectReviewSocket(currentReviewId!), delay);
}

export function connectReviewSocket(reviewId: string): void {
  disconnectReviewSocket();
  currentReviewId = reviewId;
  reconnectAttempt = 0;

  const store = useReviewStore.getState();
  store.setReviewId(reviewId);
  store.reset();
  store.setConnectionStatus("connecting");

  const ws = new WebSocket(wsUrl(reviewId));
  socket = ws;

  ws.onopen = () => {
    useReviewStore.getState().setConnectionStatus("open");
  };

  ws.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data) as ReviewEvent;
      useReviewStore.getState().applyEvent(event);
    } catch (err) {
      console.error("Failed to parse WS event", err);
    }
  };

  ws.onclose = () => {
    useReviewStore.getState().setConnectionStatus("closed");
    if (currentReviewId) scheduleReconnect();
  };

  ws.onerror = () => {
    ws.close();
  };
}

export function disconnectReviewSocket(): void {
  currentReviewId = null;
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (socket) {
    socket.onclose = null;
    socket.close();
    socket = null;
  }
}
