"""Accessible Turnstile widget for Streamlit 1.59 component v2.

The visible widget is only a challenge UI. The server must still validate its
token with Cloudflare before allowing account creation.
"""
from __future__ import annotations

import streamlit as st

WIDGET_JS = r"""
export default function(component) {
  const { data, parentElement, setStateValue } = component;
  const mount = parentElement.querySelector(".ac-register-turnstile");
  if (!mount) return;
  if (data.completed) {
    mount.textContent = "Verificação de segurança concluída.";
    return;
  }
  let cancelled = false;
  let widgetId = null;
  let polls = 0;
  if (!document.querySelector('script[data-ac-turnstile="true"]')) {
    const script = document.createElement("script");
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    script.async = true;
    script.defer = true;
    script.dataset.acTurnstile = "true";
    document.head.appendChild(script);
  }
  const interval = window.setInterval(() => {
    if (cancelled) { window.clearInterval(interval); return; }
    if (!window.turnstile) {
      polls++;
      if (polls > 160) {
        window.clearInterval(interval);
        mount.textContent = "Não foi possível carregar a verificação de segurança.";
      }
      return;
    }
    window.clearInterval(interval);
    widgetId = window.turnstile.render(mount, {
      sitekey: data.site_key,
      action: "register",
      callback: token => { if (!cancelled) setStateValue("token", token); },
      "expired-callback": () => { if (!cancelled) setStateValue("token", ""); },
      "error-callback": () => { if (!cancelled) setStateValue("token", ""); }
    });
  }, 100);
  return () => {
    cancelled = true;
    window.clearInterval(interval);
    if (widgetId !== null && window.turnstile) {
      try { window.turnstile.remove(widgetId); } catch (_) {}
    }
  };
}
"""


def registration_challenge(site_key: str, nonce: int) -> str | None:
    key = f"affiliate_turnstile_{nonce}"
    previous = st.session_state.get(key)
    completed = bool(previous and previous.get("token"))
    renderer = st.components.v2.component(
        name="afiliados_register_turnstile",
        html='<div class="ac-register-turnstile" aria-label="Verificação anti-bot"></div>',
        js=WIDGET_JS,
        isolate_styles=False,
    )
    result = renderer(
        key=key, data={"site_key": site_key, "completed": completed},
        default={"token": ""},
        on_token_change=lambda: None,
    )
    token = result.get("token") if result else None
    return token if isinstance(token, str) and token else None
