// Wait for the app container to be serving before any test runs. In the
// docker-compose test topology `depends_on` only orders start, not readiness,
// so we poll /api/health until the FastAPI process answers.
const baseURL = process.env.BASE_URL || 'http://localhost:8000';

export default async function globalSetup() {
  const deadline = Date.now() + 90_000;
  let lastErr: unknown;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${baseURL}/api/health`);
      if (res.ok) {
        // Also wait until the price cache has warmed so watchlist rows have prices.
        const wl = await fetch(`${baseURL}/api/watchlist`);
        if (wl.ok) {
          const rows = (await wl.json()) as unknown[];
          if (Array.isArray(rows) && rows.length >= 10) return;
        }
      }
    } catch (e) {
      lastErr = e;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`App at ${baseURL} did not become ready in time: ${lastErr}`);
}
