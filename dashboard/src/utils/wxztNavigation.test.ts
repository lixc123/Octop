import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  OCTOP_EMBED_GO_HOME,
  OCTOP_EMBED_LOGOUT,
  clearWxztNavigation,
  getWxztLogoutUrl,
  getWxztReturnUrl,
  notifyWxztEmbed,
  rememberWxztNavigation,
} from "./wxztNavigation";

describe("wxztNavigation", () => {
  const parent = { postMessage: vi.fn() };

  beforeEach(() => {
    sessionStorage.clear();
    Object.defineProperty(window, "parent", {
      configurable: true,
      value: parent,
    });
    parent.postMessage.mockReset();
  });

  afterEach(() => {
    clearWxztNavigation();
    Object.defineProperty(window, "parent", {
      configurable: true,
      value: window,
    });
  });

  it("keeps only canonical wxzt navigation URLs", () => {
    rememberWxztNavigation(
      "https://wxzt.example/ai_hub_layout?site=octop",
      "https://wxzt.example/logout?next=/ai_hub_layout",
    );

    expect(getWxztReturnUrl()).toBeNull();
    expect(getWxztLogoutUrl()).toBeNull();

    rememberWxztNavigation(
      "https://wxzt.example/ai_hub_layout",
      "https://wxzt.example/logout",
    );
    expect(getWxztReturnUrl()).toBe("https://wxzt.example/ai_hub_layout");
    expect(getWxztLogoutUrl()).toBe("https://wxzt.example/logout");
  });

  it("sends fixed navigation messages without URLs or tokens", () => {
    rememberWxztNavigation(
      "https://wxzt.example/ai_hub_layout",
      "https://wxzt.example/logout",
    );

    expect(notifyWxztEmbed(OCTOP_EMBED_GO_HOME)).toBe(true);
    expect(parent.postMessage).toHaveBeenCalledWith(
      { type: OCTOP_EMBED_GO_HOME },
      "https://wxzt.example",
    );

    expect(notifyWxztEmbed(OCTOP_EMBED_LOGOUT)).toBe(true);
    expect(parent.postMessage).toHaveBeenLastCalledWith(
      { type: OCTOP_EMBED_LOGOUT },
      "https://wxzt.example",
    );
  });

  it("uses the actual embedding origin when config still has a loopback URL", () => {
    Object.defineProperty(document, "referrer", {
      configurable: true,
      value: "http://192.168.0.47:5202/ai_hub_layout?site=octop",
    });
    rememberWxztNavigation(
      "http://127.0.0.1:5202/ai_hub_layout",
      "http://127.0.0.1:5202/logout",
    );

    expect(notifyWxztEmbed(OCTOP_EMBED_GO_HOME)).toBe(true);
    expect(parent.postMessage).toHaveBeenCalledWith(
      { type: OCTOP_EMBED_GO_HOME },
      "http://192.168.0.47:5202",
    );
  });
});
