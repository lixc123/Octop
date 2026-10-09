const CONTEXT_KEY = "octop:wxzt:navigation";

export const OCTOP_EMBED_GO_HOME = "OCTOP_EMBED_GO_HOME";
export const OCTOP_EMBED_LOGOUT = "OCTOP_EMBED_LOGOUT";
export const OCTOP_EMBED_READY = "OCTOP_EMBED_READY";
export const OCTOP_EMBED_ERROR = "OCTOP_EMBED_ERROR";

interface NavigationContext {
  returnUrl: string;
  logoutUrl: string;
  requestId: string;
  state: string;
  mode: "embedded" | "standalone";
}

function canonicalUrl(value: string | undefined, path: string): URL | null {
  try {
    if (!value || value.includes("\\")) return null;
    const parsed = new URL(value);
    if (
      !/^https?:$/.test(parsed.protocol) ||
      parsed.username ||
      parsed.password ||
      parsed.pathname !== path ||
      parsed.search ||
      parsed.hash
    )
      return null;
    return parsed;
  } catch {
    return null;
  }
}

export function rememberWxztNavigation(
  returnUrl?: string,
  logoutUrl?: string,
  context?: {
    requestId: string;
    state: string;
    mode: "embedded" | "standalone";
  },
): void {
  clearWxztNavigation();
  const home = canonicalUrl(returnUrl, "/ai_hub_layout");
  const logout = canonicalUrl(logoutUrl, "/logout");
  if (home && logout && home.origin === logout.origin && context) {
    sessionStorage.setItem(
      CONTEXT_KEY,
      JSON.stringify({
        returnUrl: home.href,
        logoutUrl: logout.href,
        ...context,
      }),
    );
  }
}

function navigation(): NavigationContext | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(CONTEXT_KEY) || "null");
    const home = canonicalUrl(value?.returnUrl, "/ai_hub_layout");
    const logout = canonicalUrl(value?.logoutUrl, "/logout");
    if (
      !home ||
      !logout ||
      home.origin !== logout.origin ||
      !value.requestId ||
      !value.state ||
      !["embedded", "standalone"].includes(value.mode)
    )
      return null;
    return value as NavigationContext;
  } catch {
    return null;
  }
}

export function getWxztReturnUrl(): string | null {
  return navigation()?.returnUrl || null;
}
export function getWxztLogoutUrl(): string | null {
  return navigation()?.logoutUrl || null;
}

export function notifyWxztEmbed(
  type: string,
  data: Record<string, unknown> = {},
): boolean {
  const context = navigation();
  if (!context || context.mode !== "embedded" || window.parent === window)
    return false;
  window.parent.postMessage(
    { ...data, type, request_id: context.requestId, state: context.state },
    new URL(context.returnUrl).origin,
  );
  return true;
}

export function navigateToWxzt(
  url: string | null,
  messageType: string = OCTOP_EMBED_GO_HOME,
): boolean {
  if (notifyWxztEmbed(messageType)) return true;
  const context = navigation();
  const trusted =
    messageType === OCTOP_EMBED_LOGOUT
      ? context?.logoutUrl
      : context?.returnUrl;
  if (trusted && trusted === url) window.location.assign(trusted);
  return false;
}

export function clearWxztNavigation(): void {
  sessionStorage.removeItem(CONTEXT_KEY);
  sessionStorage.removeItem("octop:wxzt:return-url");
  sessionStorage.removeItem("octop:wxzt:logout-url");
}
