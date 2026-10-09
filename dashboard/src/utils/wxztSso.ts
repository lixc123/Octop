import { authApi } from "../api/modules/auth";

export interface WxztWindowContext {
  target: Window;
  origin: string;
  requestId: string;
  mode: "embedded" | "standalone";
}

export function readWxztWindowContext(): WxztWindowContext | null {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("embedded") === "1" ? "embedded" : "standalone";
  const target = mode === "embedded" ? window.parent : window.opener;
  const requestId = params.get("request_id") || "";
  const rawOrigin = params.get("parent_origin") || "";
  try {
    const url = new URL(rawOrigin);
    if (
      !target ||
      target === window ||
      !/^[A-Za-z0-9_-]{16,128}$/.test(requestId) ||
      !/^https?:$/.test(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash ||
      url.pathname !== "/" ||
      rawOrigin.includes("\\")
    )
      return null;
    return { target, origin: url.origin, requestId, mode };
  } catch {
    return null;
  }
}

export async function signInWxzt(
  context: WxztWindowContext,
  signal: AbortSignal,
) {
  const prepared = await authApi.prepareWxzt(context.origin, context.mode);
  if (signal.aborted) throw new Error("cancelled");
  const code = await new Promise<string>((resolve, reject) => {
    const finish = (value?: string) => {
      clearTimeout(timer);
      window.removeEventListener("message", receive);
      signal.removeEventListener("abort", cancel);
      if (value) resolve(value);
      else reject(new Error("wxzt login timed out or was cancelled"));
    };
    const cancel = () => finish();
    const receive = (event: MessageEvent) => {
      const data = event.data;
      if (
        event.source !== context.target ||
        event.origin !== context.origin ||
        data?.type !== "OCTOP_EMBED_CODE" ||
        data.request_id !== context.requestId ||
        data.state !== prepared.state ||
        typeof data.code !== "string" ||
        !/^[A-Za-z0-9_-]{32,128}$/.test(data.code)
      )
        return;
      finish(data.code);
    };
    const timer = setTimeout(cancel, prepared.expires_in * 1000);
    window.addEventListener("message", receive);
    signal.addEventListener("abort", cancel, { once: true });
    context.target.postMessage(
      {
        type: "OCTOP_EMBED_PREPARED",
        state: prepared.state,
        request_id: context.requestId,
      },
      context.origin,
    );
  });
  if (signal.aborted) throw new Error("cancelled");
  const response = await authApi.exchangeWxztCode(
    prepared.state,
    code,
    prepared.verifier,
  );
  return { response, state: prepared.state };
}
