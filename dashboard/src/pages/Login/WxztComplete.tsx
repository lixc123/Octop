import { useEffect, useRef, useState } from "react";
import { Button, Result, Spin } from "antd";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getRememberLoginPreference, setAuthToken } from "../../api";
import { refreshServerLabels } from "../../i18n";
import { apiErrorMessage } from "../../utils/apiError";
import { applyUserLocale } from "../../utils/locale";
import {
  clearWxztNavigation,
  rememberWxztNavigation,
} from "../../utils/wxztNavigation";
import { readWxztWindowContext, signInWxzt } from "../../utils/wxztSso";

export default function WxztComplete() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const [context] = useState(readWxztWindowContext);
  const translation = useRef(t);
  translation.current = t;
  useEffect(() => {
    if (!context) {
      navigate("/login", { replace: true });
      return;
    }
    const controller = new AbortController();
    clearWxztNavigation();
    void signInWxzt(context, controller.signal)
      .then(async ({ response, state }) => {
        if (controller.signal.aborted) return;
        rememberWxztNavigation(response.return_url, response.logout_url, {
          requestId: context.requestId,
          state,
          mode: context.mode,
        });
        setAuthToken(response.access_token, getRememberLoginPreference());
        await applyUserLocale(response.user.locale);
        if (controller.signal.aborted) return;
        void refreshServerLabels(response.user.locale);
        context.target.postMessage(
          { type: "OCTOP_EMBED_READY", request_id: context.requestId, state },
          context.origin,
        );
        navigate("/chat", { replace: true });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const text = apiErrorMessage(
          err,
          translation.current("login.oidcComplete.failed"),
          translation.current,
        );
        context.target.postMessage(
          {
            type: "OCTOP_EMBED_ERROR",
            request_id: context.requestId,
            error: text,
          },
          context.origin,
        );
        setError(text);
      });
    return () => controller.abort();
  }, [context, navigate]);
  if (error)
    return (
      <Result
        status="error"
        title={t("login.oidcComplete.title")}
        subTitle={error}
        extra={
          <Button onClick={() => navigate("/login", { replace: true })}>
            {t("login.oidcComplete.backToLogin")}
          </Button>
        }
      />
    );
  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Spin size="large" tip={t("login.oidcComplete.loading")} />
    </div>
  );
}
