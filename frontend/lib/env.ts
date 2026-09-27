// Environment variable access helpers.
// serverEnv must only be used in server-side code (route handlers, server components).
// publicEnv is safe in client components.

export const serverEnv = {
  fastapiUrl: process.env.FASTAPI_INTERNAL_URL ?? "http://localhost:8000",
  mockBackend: process.env.MOCK_BACKEND === "true",
};

export const publicEnv = {
  appName:
    process.env.NEXT_PUBLIC_APP_NAME ?? "Multi-Agent Opinion Simulator",
};
