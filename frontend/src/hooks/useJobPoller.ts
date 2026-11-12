import { useEffect, useRef } from 'react';
import { getJobStatus } from '../services/api';
import { JobStatusResponse } from '../types/pdf';

const TERMINAL_STATES = new Set(['completed', 'failed', 'cancelled']);

export function useJobPoller(
  jobId: string | null,
  isActive: boolean,
  onUpdate: (status: JobStatusResponse) => void,
  onError?: (err: unknown) => void
): void {
  const onUpdateRef = useRef(onUpdate);
  const onErrorRef = useRef(onError);
  onUpdateRef.current = onUpdate;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!jobId || !isActive) return;

    let stopped = false;
    let timerId: number | undefined;

    const pollOnce = async () => {
      try {
        const status = await getJobStatus(jobId);
        if (stopped) return;
        onUpdateRef.current(status);
        if (!TERMINAL_STATES.has(status.state)) {
          timerId = window.setTimeout(pollOnce, 300);
        }
      } catch (err) {
        if (stopped) return;
        if (onErrorRef.current) {
          onErrorRef.current(err);
        }
      }
    };

    pollOnce();

    return () => {
      stopped = true;
      if (timerId !== undefined) {
        window.clearTimeout(timerId);
      }
    };
  }, [jobId, isActive]);
}
