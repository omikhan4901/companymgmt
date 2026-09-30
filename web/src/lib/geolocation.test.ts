import { currentPosition, formatDistance, LocationError } from "./geolocation";

describe("formatDistance", () => {
  it("rounds metres and switches to kilometres", () => {
    expect(formatDistance(7, "en-GB")).toBe("10 m");
    expect(formatDistance(423, "en-GB")).toBe("420 m");
    expect(formatDistance(1234, "en-GB")).toBe("1.2 km");
    expect(formatDistance(25_400, "en-GB")).toBe("25 km");
  });
  it("uses Bangla digits and units in Bangla", () => {
    expect(formatDistance(420, "bn-BD")).toBe("৪২০ মি");
    expect(formatDistance(2000, "bn-BD")).toBe("২ কিমি");
  });
});

describe("currentPosition", () => {
  const original = navigator.geolocation;
  afterEach(() => Object.defineProperty(navigator, "geolocation", { value: original, configurable: true }));

  function fake(impl: Geolocation["getCurrentPosition"]) {
    Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
    Object.defineProperty(navigator, "geolocation", { value: { getCurrentPosition: impl }, configurable: true });
  }

  it("returns the position with its accuracy", async () => {
    fake((ok) => ok({ coords: { latitude: 23.7, longitude: 90.4, accuracy: 12 } } as GeolocationPosition));
    await expect(currentPosition()).resolves.toEqual({ latitude: 23.7, longitude: 90.4, accuracy_m: 12 });
  });

  it("explains a blocked permission", async () => {
    fake((_ok, fail) => fail?.({ code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3, message: "" } as GeolocationPositionError));
    await expect(currentPosition()).rejects.toEqual(new LocationError("denied"));
  });

  it("refuses on an insecure page", async () => {
    Object.defineProperty(window, "isSecureContext", { value: false, configurable: true });
    await expect(currentPosition()).rejects.toMatchObject({ problem: "insecure" });
  });
});
