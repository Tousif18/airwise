export async function fetchWithTimeout(url, options = {}, timeoutMs = 30_000, fetchImpl = fetch) {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    return await fetchImpl(url, {
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (timedOut) {
      const timeoutError = new Error(
        `AirWise assistant request timed out after ${Math.ceil(timeoutMs / 1000)} seconds. Please try again.`
      );
      timeoutError.name = "TimeoutError";
      timeoutError.isTimeoutError = true;
      throw timeoutError;
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}
