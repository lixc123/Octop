const RETURN_URL_KEY = "octop:wxzt:return-url";
const LOGOUT_URL_KEY = "octop:wxzt:logout-url";

export const OCTOP_EMBED_GO_HOME = "OCTOP_EMBED_GO_HOME";
export const OCTOP_EMBED_LOGOUT = "OCTOP_EMBED_LOGOUT";
export const OCTOP_EMBED_READY = "OCTOP_EMBED_READY";
export const OCTOP_EMBED_ERROR = "OCTOP_EMBED_ERROR";

function allowedWxztUrl(value: string | null, path: string): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value, window.location.origin);
    if (!/^https?:$/.test(parsed.protocol)) return null;
    if (parsed.pathname !== path || parsed.search || parsed.hash) return null;
    return parsed.toString();
  } catch {
    return null;
  }
}

export function rememberWxztNavigation(
  returnUrl?: string,
  logoutUrl?: string,
): void {
  const safeReturn = allowedWxztUrl(returnUrl ?? null, "/ai_hub_layout");
  const safeLogout = allowedWxztUrl(logoutUrl ?? null, "/logout");
  if (safeReturn) sessionStorage.setItem(RETURN_URL_KEY, safeReturn);
  if (safeLogout) sessionStorage.setItem(LOGOUT_URL_KEY, safeLogout);
}

export function getWxztReturnUrl(): string | null {
  return allowedWxztUrl(
    sessionStorage.getItem(RETURN_URL_KEY),
    "/ai_hub_layout",
  );
}

export function getWxztLogoutUrl(): string | null {
  return allowedWxztUrl(sessionStorage.getItem(LOGOUT_URL_KEY), "/logout");
}

function postToWxztParent(
  type: string,
  targetUrl: string | null,
  data: Record<string, unknown> = {},
): boolean {
  if (window.parent === window) return false;
  try {
    // The configured return URL can be a loopback address while a browser
    // opens wxzt through its LAN/reverse-proxy origin. In an iframe, the
    // browser-provided referrer is the actual embedding parent, so prefer it
    // for delivery. wxzt still validates event.source and event.origin.
    const referrerOrigin = document.referrer
      ? new URL(document.referrer).origin
      : null;
    const ancestorOrigin = window.location.ancestorOrigins?.[0] || null;
    const configuredOrigin = targetUrl ? new URL(targetUrl).origin : null;
    const targetOrigin = referrerOrigin || ancestorOrigin || configuredOrigin;
    if (!targetOrigin) return false;
    window.parent.postMessage({ type, ...data }, targetOrigin);
    return true;
  } catch {
    return false;
  }
}

export function notifyWxztEmbed(
  type:
    | typeof OCTOP_EMBED_GO_HOME
    | typeof OCTOP_EMBED_LOGOUT
    | "OCTOP_EMBED_READY"
    | "OCTOP_EMBED_ERROR",
  data: Record<string, unknown> = {},
): boolean {
  const targetUrl =
    type === OCTOP_EMBED_LOGOUT ? getWxztLogoutUrl() : getWxztReturnUrl();
  return postToWxztParent(type, targetUrl, data);
}

/** Navigate to wxzt, or ask the embedding wxzt page to handle top-level navigation. */
export function navigateToWxzt(
  url: string | null,
  messageType:
    | typeof OCTOP_EMBED_GO_HOME
    | typeof OCTOP_EMBED_LOGOUT = OCTOP_EMBED_GO_HOME,
): boolean {
  const targetUrl =
    messageType === OCTOP_EMBED_LOGOUT
      ? getWxztLogoutUrl()
      : getWxztReturnUrl();
  if (postToWxztParent(messageType, targetUrl)) return true;
  if (url) window.location.assign(url);
  return false;
}

export function clearWxztNavigation(): void {
  sessionStorage.removeItem(RETURN_URL_KEY);
  sessionStorage.removeItem(LOGOUT_URL_KEY);
}
