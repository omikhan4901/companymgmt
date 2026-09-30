/** Reads the device's position for clock-in, with errors a person can act on. */

export interface Position {
  latitude: number;
  longitude: number;
  accuracy_m: number;
}

export type LocationProblem = "denied" | "unavailable" | "timeout" | "unsupported" | "insecure";

export class LocationError extends Error {
  constructor(readonly problem: LocationProblem) {
    super(problem);
  }
}

export function currentPosition(options: { timeoutMs?: number } = {}): Promise<Position> {
  if (typeof window !== "undefined" && !window.isSecureContext) return Promise.reject(new LocationError("insecure"));
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.reject(new LocationError("unsupported"));
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy_m: pos.coords.accuracy }),
      (err) => {
        const problem: LocationProblem = err.code === err.PERMISSION_DENIED ? "denied" : err.code === err.TIMEOUT ? "timeout" : "unavailable";
        reject(new LocationError(problem));
      },
      // Always a fresh, precise fix: a cached one could be from before the person arrived.
      { enableHighAccuracy: true, timeout: options.timeoutMs ?? 15_000, maximumAge: 0 },
    );
  });
}

/** "80 m", "1.2 km" (or "৮০ মি", "১.২ কিমি") in the current language. */
export function formatDistance(metres: number, locale: string): string {
  const bangla = locale.startsWith("bn");
  const n = (v: number, digits = 0) => new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(v);
  if (metres < 1000) return `${n(Math.round(metres / 10) * 10 || Math.round(metres))} ${bangla ? "মি" : "m"}`;
  return `${n(metres / 1000, metres < 10_000 ? 1 : 0)} ${bangla ? "কিমি" : "km"}`;
}
