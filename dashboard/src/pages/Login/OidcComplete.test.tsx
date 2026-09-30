import { describe, expect, it } from "vitest";
import { readOidcCompleteParams, safeRedirect } from "./OidcComplete";

describe("safeRedirect", () => {
  it.each([
    ["//identity.example.com", "/chat"],
    ["http://identity.example.com", "/chat"],
    ["/chat://identity.example.com", "/chat"],
    ["/chat\\identity.example.com", "/chat"],
    ["chat", "/chat"],
    ["/agents", "/agents"],
  ])("allows only internal paths: %s", (redirect, expected) => {
    expect(safeRedirect(redirect)).toBe(expected);
  });
});

describe("readOidcCompleteParams", () => {
  it("prefers hash over query", () => {
    expect(
      readOidcCompleteParams(
        "#code=from-hash&redirect=%2Fsettings",
        "?code=from-query",
      ),
    ).toEqual({
      code: "from-hash",
      redirect: "/settings",
      bind: false,
      embedded: false,
    });
  });

  it("falls back to query for legacy links", () => {
    expect(readOidcCompleteParams("", "?code=legacy&redirect=%2Fchat")).toEqual(
      {
        code: "legacy",
        redirect: "/chat",
        bind: false,
        embedded: false,
      },
    );
  });

  it("reads embedded mode from the query string", () => {
    expect(readOidcCompleteParams("", "?code=one&embedded=1").embedded).toBe(
      true,
    );
  });
});
