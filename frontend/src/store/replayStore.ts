import { create } from "zustand";

import type { ReviewEvent } from "../types/domain";
import { applyEventToState, emptyReducerState, type ReducerState } from "./eventReducer";

interface ReplayStoreState extends ReducerState {
  reviewId: string | null;
  timeline: ReviewEvent[];
  cursor: number; // number of events applied so far (0..timeline.length)
  playing: boolean;
  speed: number; // events per second

  load: (reviewId: string, timeline: ReviewEvent[]) => void;
  play: () => void;
  pause: () => void;
  setSpeed: (speed: number) => void;
  stepForward: () => void;
  stepBackward: () => void;
  seek: (index: number) => void;
  clear: () => void;
}

function replayTo(timeline: ReviewEvent[], index: number): ReducerState {
  let state = emptyReducerState();
  for (let i = 0; i < index; i++) {
    state = applyEventToState(state, timeline[i]);
  }
  return state;
}

export const useReplayStore = create<ReplayStoreState>((set, get) => ({
  reviewId: null,
  timeline: [],
  cursor: 0,
  playing: false,
  speed: 2,
  ...emptyReducerState(),

  load: (reviewId, timeline) => {
    set({ reviewId, timeline, cursor: 0, playing: false, ...emptyReducerState() });
  },

  play: () => {
    if (get().cursor >= get().timeline.length) set({ cursor: 0, ...emptyReducerState() });
    set({ playing: true });
  },
  pause: () => set({ playing: false }),
  setSpeed: (speed) => set({ speed }),

  stepForward: () => {
    const { timeline, cursor } = get();
    if (cursor >= timeline.length) {
      set({ playing: false });
      return;
    }
    const patch = applyEventToState(get(), timeline[cursor]);
    set({ ...patch, cursor: cursor + 1 });
    if (cursor + 1 >= timeline.length) set({ playing: false });
  },

  stepBackward: () => {
    const { cursor } = get();
    if (cursor <= 0) return;
    get().seek(cursor - 1);
  },

  seek: (index) => {
    const { timeline } = get();
    const clamped = Math.max(0, Math.min(index, timeline.length));
    set({ ...replayTo(timeline, clamped), cursor: clamped });
  },

  clear: () => set({ reviewId: null, timeline: [], cursor: 0, playing: false, ...emptyReducerState() }),
}));
