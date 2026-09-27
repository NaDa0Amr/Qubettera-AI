// Structured JSON logger for the Next.js service.
// Outputs to stdout as newline-delimited JSON so container log aggregators
// (e.g. Docker, Loki) can parse fields without regex.

type LogLevel = "INFO" | "WARN" | "ERROR";
type Meta = Record<string, unknown>;

function write(level: LogLevel, event: string, message: string, meta?: Meta) {
  const entry = JSON.stringify({
    timestamp: new Date().toISOString(),
    level,
    service: "nextjs",
    event,
    message,
    ...meta,
  });

  if (level === "ERROR") {
    console.error(entry);
  } else if (level === "WARN") {
    console.warn(entry);
  } else {
    console.log(entry);
  }
}

export const log = {
  info: (event: string, message: string, meta?: Meta) =>
    write("INFO", event, message, meta),
  warn: (event: string, message: string, meta?: Meta) =>
    write("WARN", event, message, meta),
  error: (event: string, message: string, meta?: Meta) =>
    write("ERROR", event, message, meta),
};
