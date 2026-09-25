import { useCallback, useEffect, useState } from "react";
import { RequestError } from "./api";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const memoFn = useCallback(fn, deps);

  const run = useCallback(() => {
    let active = true;
    setLoading(true);
    setError(null);
    memoFn()
      .then((d) => active && setData(d))
      .catch((e) =>
        active && setError(e instanceof RequestError ? e.message : "Something went wrong."),
      )
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [memoFn]);

  useEffect(() => run(), [run]);

  return { data, loading, error, reload: run };
}
