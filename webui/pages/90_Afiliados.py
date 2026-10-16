"""Offline affiliate workflow. API credentials and paid generation intentionally absent."""
import hashlib
import json
import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.afiliados.core import AffiliateBrief, CTA, prepare_draft  # noqa: E402
from app.afiliados.plans import get_plan_policy  # noqa: E402
from app.afiliados.subscriptions import SubscriptionStore, AuthorizedProjects  # noqa: E402
from app.afiliados.ads import ads_enabled, validated_adsense_config  # noqa: E402
from app.afiliados.sponsor import sponsor_destination  # noqa: E402

# Fail closed: subscription verification is not connected yet.
# Never read a premium plan from session_state, query params or uploaded JSON.
ACTIVE_PLAN = "gratis"
ACTIVE_POLICY = get_plan_policy(ACTIVE_PLAN)

st.set_page_config(page_title="Afiliados Creator", page_icon="🔷", layout="wide")

# Branded prototype header; watermark styling remains separate from UI colors.
st.markdown("""
<style>
.ac-hero { background:linear-gradient(115deg,#101a38,#21144c 70%,#132b5b);border-radius:18px;padding:22px 26px;margin-bottom:18px;color:#fff; }
.ac-brand {display:flex;align-items:center;gap:16px}
.ac-mark {width:62px;height:62px;flex-shrink:0}
.ac-name {font-family:Manrope,Arial,sans-serif;font-size:30px;font-weight:800;line-height:1.08;letter-spacing:-.6px}
.ac-name span {background:linear-gradient(90deg,#ae51ff,#21c6ff);-webkit-background-clip:text;background-clip:text;color:transparent}
.ac-tagline {color:#d8def5;font-size:14px;margin-top:9px}
@media(max-width:600px){.ac-name{font-size:23px}.ac-hero{padding:16px}.ac-mark{width:48px;height:48px}}
</style>
<div class="ac-hero"><div class="ac-brand">
<svg class="ac-mark" viewBox="0 0 100 100" role="img" aria-label="Símbolo AC">
<defs><linearGradient id="acgrad" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#ba3cff"/><stop offset=".52" stop-color="#493cff"/><stop offset="1" stop-color="#00c9ef"/></linearGradient></defs>
<path d="M77 20 A39 39 0 1 0 77 80" fill="none" stroke="url(#acgrad)" stroke-width="16" stroke-linecap="round"/>
<path d="M31 71 L50 28 L69 71 M39 57 H61" fill="none" stroke="#fff" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>
<path d="M81 40 L96 50 L81 60Z" fill="#00c9ef"/>
</svg><div><div class="ac-name">Afiliados <span>Creator</span></div>
<div class="ac-tagline">Crie anúncios com fotos reais, vídeos e capas em poucos passos.</div></div></div></div>
""", unsafe_allow_html=True)
# Explicit local-only opt-in; public deployments must use a hardened identity provider.
from app.afiliados.showcase import public_demo_videos, public_plan_comparison  # noqa: E402


def show_public_studio():
    """Read-only public view; no rendering, downloads or private project access."""
    st.markdown("### Conheça o estúdio antes de criar sua conta")
    st.caption("Explore o funcionamento gratuitamente. Para gerar, baixar ou gerenciar anúncios, entre ou cadastre-se.")
    preview_tab, examples_tab, pricing_tab = st.tabs(("Prévia do editor", "Vídeos de exemplo", "Planos"))
    with preview_tab:
        st.markdown("#### Criar anúncio")
        st.text_input("Link do produto", value="https://shopee.com.br/...", disabled=True, key="public_preview_url")
        st.text_input("Nome do produto", value="Exemplo: Aspirador portátil", disabled=True, key="public_preview_name")
        st.text_area("Roteiro do vídeo", value="Aqui você revisa o roteiro antes de gerar seu anúncio.", disabled=True, key="public_preview_script")
        st.button("Gerar vídeo — entre para desbloquear", disabled=True, key="public_preview_generate")
        st.caption("Editor ilustrativo. Nenhum vídeo é gerado sem autenticação.")
    with examples_tab:
        st.markdown("#### Demonstrações")
        demos = public_demo_videos(ROOT)
        if demos:
            for demo in demos:
                st.video(str(demo))
        else:
            st.info("Vídeos demonstrativos serão publicados aqui. Nenhum exemplo fictício foi apresentado como vídeo real.")
    with pricing_tab:
        st.table(public_plan_comparison())
    st.divider()

# Opt-in public-account integration preview. The production rendering worker
# and billing are NOT connected: no generation actions are exposed in this mode.
PUBLIC_AUTH_BETA = os.environ.get("AFILIADOS_PUBLIC_AUTH_BETA") == "1"
LOCAL_ACCOUNTS = os.environ.get("AFILIADOS_LOCAL_ACCOUNTS") == "1"
if PUBLIC_AUTH_BETA:
    if LOCAL_ACCOUNTS:
        st.error("Escolha apenas um provedor de autenticação.")
        st.stop()
    try:
        from app.afiliados.production_auth import SupabaseAuth, AuthDenied, AuthServiceUnavailable
        from app.afiliados.production_quota import SupabaseVideoQuota
        from app.afiliados.turnstile import load_turnstile_config
        public_auth = SupabaseAuth.from_env()
        public_captcha = load_turnstile_config(required=True)
    except (ValueError, RuntimeError):
        st.error("Modo beta indisponível: autenticação e CAPTCHA ainda não configurados.")
        st.stop()
    st.warning("Beta de autenticação: a geração pública de vídeos ainda não está disponível.")
    beta_session = st.session_state.get("affiliate_public_session")
    beta_identity = None
    if isinstance(beta_session, dict):
        try:
            beta_identity = public_auth.require_verified_user(beta_session["access_token"])
        except (KeyError, ValueError, AuthDenied, AuthServiceUnavailable):
            try:
                new_session = public_auth.refresh(beta_session["refresh_token"])
                st.session_state["affiliate_public_session"] = new_session
                beta_session = new_session
                beta_identity = public_auth.require_verified_user(new_session["access_token"])
            except (KeyError, ValueError, AuthDenied, AuthServiceUnavailable):
                st.session_state.pop("affiliate_public_session", None)
                beta_session = None

    if beta_identity is None:
        show_public_studio()
        st.markdown("### Minha conta — acesso beta")
        login_tab, signup_tab, recover_tab = st.tabs(
            ("Entrar", "Criar conta", "Recuperar senha")
        )
        with login_tab:
            with st.form("affiliate_public_login"):
                email = st.text_input("E-mail", key="ac_beta_login_email")
                password = st.text_input("Senha", type="password", key="ac_beta_login_password")
                if st.form_submit_button("Entrar"):
                    try:
                        st.session_state["affiliate_public_session"] = public_auth.login(email, password)
                        st.rerun()
                    except (ValueError, AuthDenied, AuthServiceUnavailable):
                        st.error("Não foi possível entrar. Verifique suas credenciais e confirmação de e-mail.")
        with signup_tab:
            from app.afiliados.turnstile_widget import registration_challenge
            nonce = st.session_state.get("affiliate_public_captcha_nonce", 0)
            challenge = registration_challenge(public_captcha.site_key, nonce)
            with st.form("affiliate_public_signup"):
                email = st.text_input("E-mail", key="ac_beta_signup_email")
                password = st.text_input("Senha (12 caracteres ou mais)", type="password")
                confirmation = st.text_input("Confirme sua senha", type="password")
                if st.form_submit_button("Criar conta"):
                    try:
                        if password != confirmation:
                            raise ValueError("Confirmação de senha inválida")
                        public_auth.register(email, password, captcha_token=challenge)
                        st.success("Confira seu e-mail e confirme sua conta antes de entrar.")
                    except (ValueError, PermissionError, RuntimeError):
                        st.error("Não foi possível criar a conta. Confira os dados e refaça o CAPTCHA.")
                    finally:
                        st.session_state["affiliate_public_captcha_nonce"] = nonce + 1
        with recover_tab:
            with st.form("affiliate_public_recover"):
                email = st.text_input("E-mail da conta", key="ac_beta_recover_email")
                if st.form_submit_button("Enviar recuperação"):
                    try:
                        public_auth.recover(email)
                        st.success("Se o e-mail estiver cadastrado, você receberá as instruções.")
                    except (ValueError, AuthDenied, AuthServiceUnavailable):
                        st.info("A solicitação não pôde ser concluída agora. Tente mais tarde.")
        st.stop()

    st.markdown("### Minha conta")
    st.caption("Identidade verificada pelo Supabase Auth.")
    st.write(f"E-mail: {beta_identity.email}")
    try:
        quota = SupabaseVideoQuota(public_auth)
        current_plan = quota.plan(beta_session["access_token"])
        st.write(f"Plano ativo: **{current_plan.title()}**")
        if current_plan == "gratis":
            status = quota.free_status(beta_session["access_token"])
            if status.in_progress:
                st.info("Geração em andamento.")
            elif status.remaining_seconds:
                hrs, rem = divmod(status.remaining_seconds, 3600)
                mins, secs = divmod(rem, 60)
                st.info(f"Próximo vídeo grátis em {hrs:02d}:{mins:02d}:{secs:02d}.")
            elif not status.can_generate:
                st.info("Limite temporário de tentativas ou capacidade atingido.")
            else:
                st.success("Cota de vídeo gratuita disponível.")
            st.caption("Atualize a página para consultar novamente o tempo restante.")
        st.markdown("#### Minhas gerações")
        st.caption("Acompanhamento da fila de teste. Nenhum vídeo é iniciado nesta tela beta.")
        if st.button("Atualizar andamento", key="ac_beta_refresh_jobs"):
            st.rerun()
        items = quota.list_jobs(beta_session["access_token"])
        if items:
            labels = {"queued": "Na fila", "running": "Processando",
                      "completed": "Concluído", "failed": "Falhou"}
            st.table([{
                "Trabalho": job.id[:8] + "…",
                "Tipo": "Campanha (3 vídeos)" if job.kind == "campaign" else "Vídeo",
                "Situação": labels[job.status],
                "Solicitado em": job.created_at[:19].replace("T", " ") if job.created_at else "—",
            } for job in items])
            st.caption("Para baixar arquivos concluídos, será necessário habilitar o backend de downloads seguros.")
        else:
            st.info("Você ainda não tem vídeos na fila.")
        st.info("A geração pública será ativada somente após a validação dos servidores e da fila de processamento.")
    except (AuthDenied, AuthServiceUnavailable, ValueError):
        st.error("Não foi possível consultar seu plano ou cota. Verifique a configuração do Supabase.")
    if st.button("Sair da conta", key="affiliate_public_logout"):
        try:
            public_auth.logout(beta_session["access_token"])
        except (AuthDenied, AuthServiceUnavailable):
            st.warning("Sessão local encerrada; não foi possível confirmar o logout remoto.")
        st.session_state.pop("affiliate_public_session", None)
        st.rerun()
    st.stop()

# Public deployment cannot expose experimental SQLite authentication.
if LOCAL_ACCOUNTS and os.environ.get("AFILIADOS_PUBLIC_DEPLOYMENT") == "1":
    st.error("Autenticação local experimental indisponível em implantação pública.")
    st.stop()
owner_id = None
store = None
if LOCAL_ACCOUNTS:
    from app.afiliados.auth import LocalAuth
    from app.afiliados.storage import ProjectStore

    auth = LocalAuth(ROOT / "data" / "afiliados-auth.sqlite")
    from app.afiliados.turnstile import load_turnstile_config
    try:
        turnstile_config = load_turnstile_config(
            required=os.environ.get("AFILIADOS_TURNSTILE_REQUIRED") == "1"
        )
    except RuntimeError:
        # Fail closed: a partially configured challenge must never silently turn off.
        turnstile_config = False
    verify_token = st.query_params.get("verify_token")
    if verify_token:
        try:
            auth.verify_email(verify_token)
            st.success("E-mail confirmado! Agora você pode gerar seus vídeos.")
        except ValueError as exc:
            st.error(str(exc))
        finally:
            del st.query_params["verify_token"]
    token = st.session_state.get("affiliate_session_token")
    owner_id = auth.resolve(token) if token else None
    if owner_id is None:
        st.session_state.pop("affiliate_session_token", None)
        show_public_studio()
        st.subheader("Acessar Afiliados Creator")
        st.warning("Login experimental para uso local. Não publique esta opção na internet.")
        reset_token = st.query_params.get("reset_token")
        if reset_token:
            st.subheader("Definir nova senha")
            with st.form("affiliate_reset_password"):
                new_password = st.text_input("Nova senha (mínimo 12 caracteres)", type="password")
                confirm_new = st.text_input("Confirmar nova senha", type="password")
                if st.form_submit_button("Redefinir senha"):
                    if new_password != confirm_new:
                        st.error("As senhas não coincidem.")
                    else:
                        try:
                            auth.reset_password(reset_token, new_password)
                            del st.query_params["reset_token"]
                            st.success("Senha alterada. Entre com sua nova senha.")
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
            st.stop()
        login_tab, register_tab, forgot_tab = st.tabs(("Entrar", "Criar conta", "Esqueci minha senha"))
        with login_tab:
            with st.form("affiliate_login"):
                email = st.text_input("E-mail", key="affiliate_login_email")
                password = st.text_input("Senha", type="password", key="affiliate_login_password")
                if st.form_submit_button("Entrar"):
                    try:
                        st.session_state["affiliate_session_token"] = auth.login(email, password)
                        st.rerun()
                    except ValueError as exc:
                        if "Muitas tentativas" in str(exc):
                            st.warning("Muitas tentativas. Aguarde 15 minutos antes de tentar novamente.")
                        else:
                            st.error("Não foi possível entrar com essas credenciais.")
        with register_tab:
            captcha_token = None
            if turnstile_config is False:
                st.error("Cadastro temporariamente indisponível: proteção anti-bot incompleta.")
            elif turnstile_config is not None:
                from app.afiliados.turnstile_widget import registration_challenge
                captcha_nonce = st.session_state.get("affiliate_turnstile_nonce", 0)
                captcha_token = registration_challenge(turnstile_config.site_key, captcha_nonce)
            else:
                st.caption("Cadastro sem CAPTCHA: permitido apenas para testes locais.")
            with st.form("affiliate_register"):
                email = st.text_input("E-mail", key="affiliate_register_email")
                password = st.text_input("Senha (mínimo 12 caracteres)", type="password", key="affiliate_register_password")
                confirm = st.text_input("Confirmar senha", type="password")
                if st.form_submit_button("Criar conta", disabled=turnstile_config is False):
                    if password != confirm:
                        st.error("As senhas não coincidem.")
                    else:
                        try:
                            if turnstile_config is not None:
                                from app.afiliados.turnstile import verify_registration_token
                                verify_registration_token(captcha_token, turnstile_config)
                                # Challenge proof is consumed even if creating the account fails.
                                st.session_state["affiliate_turnstile_nonce"] = (
                                    st.session_state.get("affiliate_turnstile_nonce", 0) + 1
                                )
                            auth.register(email, password)
                            from app.afiliados.verification_email import send_verification_email
                            confirmation = auth.create_verification_token(email)
                            if confirmation:
                                send_verification_email(email.strip().casefold(), confirmation)
                            st.success("Conta criada. Confira seu e-mail e confirme antes de gerar vídeos.")
                        except PermissionError:
                            st.error("Falha na verificação anti-bot. Refaça a verificação antes de tentar novamente.")
                            st.session_state["affiliate_turnstile_nonce"] = (
                                st.session_state.get("affiliate_turnstile_nonce", 0) + 1
                            )
                        except ValueError as exc:
                            st.error(str(exc))
                        except (RuntimeError, OSError):
                            st.warning("Conta criada, mas o e-mail não pôde ser enviado. Configure o SMTP e solicite um novo link.")
        with forgot_tab:
            st.caption("Enviaremos um link de recuperação válido por 30 minutos.")
            with st.form("affiliate_forgot_password"):
                recovery_email = st.text_input("E-mail cadastrado", key="affiliate_recovery_email")
                if st.form_submit_button("Enviar link de recuperação"):
                    try:
                        from app.afiliados.recovery_email import send_reset_email
                        reset = auth.create_reset_token(recovery_email)
                        if reset is not None:
                            send_reset_email(recovery_email.strip().casefold(), reset)
                        st.success("Se o e-mail estiver cadastrado, enviaremos as instruções de recuperação.")
                    except ValueError as exc:
                        if "Muitas tentativas" in str(exc):
                            st.warning("Limite de solicitações atingido. Tente novamente mais tarde.")
                        else:
                            st.error("Informe um endereço de e-mail válido.")
                    except (RuntimeError, OSError):
                        st.error("O serviço de recuperação por e-mail está indisponível no momento.")
        st.markdown("#### Reenviar verificação")
        with st.form("affiliate_verify_email_again"):
            verify_email = st.text_input("E-mail da conta", key="affiliate_verify_email_again_input")
            if st.form_submit_button("Enviar novo link de confirmação"):
                try:
                    from app.afiliados.verification_email import send_verification_email
                    confirmation = auth.create_verification_token(verify_email)
                    if confirmation:
                        send_verification_email(verify_email.strip().casefold(), confirmation)
                    st.success("Se a conta precisar de verificação, enviaremos um novo link.")
                except ValueError as exc:
                    if "Muitas tentativas" in str(exc):
                        st.warning("Limite de envios atingido. Aguarde antes de solicitar novamente.")
                    else:
                        st.error("Informe um e-mail válido.")
                except (RuntimeError, OSError):
                    st.error("O serviço de confirmação de e-mail está indisponível.")
        st.stop()
    email_verified = auth.is_verified(owner_id)
    subscriptions = SubscriptionStore(ROOT / "data" / "afiliados-subscriptions.sqlite")
    ACTIVE_PLAN = subscriptions.get_plan(owner_id)
    ACTIVE_POLICY = get_plan_policy(ACTIVE_PLAN)
    store = AuthorizedProjects(ProjectStore(ROOT / "data" / "afiliados-projects.sqlite"), subscriptions)
    from app.afiliados.video_quota import VideoQuota
    video_quota = VideoQuota(ROOT / "data" / "afiliados-video-quota.sqlite")
    from app.afiliados.media_store import MediaStore
    media_store = MediaStore(ROOT / "data" / "afiliados-media.sqlite")

if not LOCAL_ACCOUNTS:
    show_public_studio()
    st.info("Para criar anúncios é necessário entrar ou criar uma conta. O login está indisponível nesta instalação.")
    st.stop()

if st.session_state.pop("affiliate_open_imported", False):
    st.session_state["affiliate_section"] = "Criar anúncio"

with st.sidebar:
    st.markdown("### Afiliados Creator")
    st.caption("Painel de criação • protótipo")
    selected_section = st.radio(
        "Navegação",
        ("Criar anúncio", "Meus projetos", "Biblioteca", "Templates", "Planos"),
        label_visibility="collapsed",
        key="affiliate_section",
    )
    st.divider()
    st.caption("Marca-d'água: AC monocromático, 80% transparente.")
    st.caption(f"Plano ativo: {ACTIVE_PLAN.title()} · Sem serviços pagos ativados.")
    if LOCAL_ACCOUNTS:
        st.caption("Sessão de testes local autenticada")
        if st.button("Sair da conta"):
            auth.logout(st.session_state.pop("affiliate_session_token", ""))
            for key in list(st.session_state):
                if key.startswith("affiliate_"):
                    st.session_state.pop(key, None)
            st.rerun()

if selected_section == "Meus projetos":
    st.subheader("Meus projetos")
    st.info("Salvar e reabrir projetos está disponível nos planos Pro, Premium e Creator.")
    imported_json = (st.file_uploader("Importar projeto Afiliados Creator (JSON, até 16 KB)", type=["json"], key="affiliate_project_upload")
                     if ACTIVE_POLICY.project_saving_allowed else None)
    if ACTIVE_POLICY.project_saving_allowed and st.button("Abrir projeto", disabled=imported_json is None):
        try:
            from app.afiliados.projects import import_project
            imported_draft = import_project(imported_json.getvalue())
            product = imported_draft["product"]
            st.session_state.pop("affiliate_loaded_project_id", None)
            st.session_state["affiliate_draft"] = imported_draft
            st.session_state["affiliate_product_name"] = product["product_name"]
            st.session_state["affiliate_product_url"] = product["product_url"]
            st.session_state["affiliate_product_features"] = product["features"]
            for key in ("affiliate_review_script", "affiliate_mp4", "affiliate_render_key", "affiliate_generated_audio", "affiliate_approval_key"):
                st.session_state.pop(key, None)
            st.session_state["affiliate_approved"] = False
            st.session_state["affiliate_open_imported"] = True
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    if store is not None and ACTIVE_POLICY.project_saving_allowed:
        st.markdown("#### Projetos salvos na conta local")
        saved_projects = store.list(owner_id)
        if saved_projects:
            options = {p["id"]: p["title"] + " · " + p["updated_at"][:16] for p in saved_projects}
            selected_id = st.selectbox("Selecionar projeto", list(options), format_func=lambda pid: options[pid])
            if st.button("Abrir projeto salvo"):
                saved_draft = store.load(owner_id, selected_id)
                product = saved_draft["product"]
                st.session_state["affiliate_draft"] = saved_draft
                st.session_state["affiliate_product_name"] = product["product_name"]
                st.session_state["affiliate_product_url"] = product["product_url"]
                st.session_state["affiliate_product_features"] = product["features"]
                st.session_state["affiliate_loaded_project_id"] = selected_id
                for key in ("affiliate_review_script", "affiliate_mp4", "affiliate_render_key", "affiliate_generated_audio", "affiliate_approval_key"):
                    st.session_state.pop(key, None)
                st.session_state["affiliate_approved"] = False
                st.session_state["affiliate_open_imported"] = True
                st.rerun()
            if st.button("Excluir projeto selecionado"):
                store.delete(owner_id, selected_id)
                if st.session_state.get("affiliate_loaded_project_id") == selected_id:
                    st.session_state.pop("affiliate_loaded_project_id", None)
                st.rerun()
        else:
            st.caption("Nenhum projeto salvo nesta conta.")
    if ACTIVE_POLICY.project_saving_allowed and st.session_state.get("affiliate_draft"):
        st.markdown("#### Projeto da sessão")
        st.json(st.session_state["affiliate_draft"]["product"])
elif selected_section == "Biblioteca":
    st.subheader("Biblioteca")
    if store is None:
        st.info("A biblioteca local exige uma conta de teste. Ative AFILIADOS_LOCAL_ACCOUNTS=1 somente no ambiente local.")
    else:
        st.caption("Arquivos gerados e salvos nesta instalação local. Não é armazenamento em nuvem.")
        files = media_store.list(owner_id)
        from app.afiliados.media_store import MAX_TOTAL_BYTES_PER_OWNER
        used_bytes = sum(item["size"] for item in files)
        st.progress(min(used_bytes / MAX_TOTAL_BYTES_PER_OWNER, 1.0), text=f"Armazenamento local: {used_bytes / 1024 / 1024:.1f} de {MAX_TOTAL_BYTES_PER_OWNER / 1024 / 1024:.0f} MB")
        st.caption(f"{len(files)} de 100 arquivos nesta conta.")
        if not files:
            st.info("Nenhuma mídia salva nesta conta.")
        for item in files:
            with st.expander(("Capa PNG" if item["kind"] == "thumbnail" else "Vídeo MP4") + " · " + item["created_at"][:16]):
                kind, content = media_store.load(owner_id, item["id"])
                st.caption(f"{item['size'] / 1024 / 1024:.2f} MB")
                if kind == "thumbnail":
                    st.image(content, width=240)
                else:
                    st.video(content)
                st.download_button("Baixar arquivo", content, file_name=item["id"] + (".png" if kind == "thumbnail" else ".mp4"), mime="image/png" if kind == "thumbnail" else "video/mp4", key="media-download-" + item["id"])
                if st.button("Excluir arquivo", key="media-delete-" + item["id"]):
                    media_store.delete(owner_id, item["id"])
                    st.rerun()
elif selected_section == "Templates":
    st.subheader("Templates")
    st.write("Capas disponíveis: Impacto, Benefício e Curiosidade. A geração de vídeo ainda usa o modelo de apresentação com fotos.")
elif selected_section == "Planos":
    st.subheader("Planos previstos")
    st.table({"Plano": ["Grátis", "Pro", "Creator"], "Vídeos concluídos por dia": ["1", "5", "Ilimitados (uso justo)"], "Marca-d'água": ["Obrigatória", "Obrigatória", "Opcional / personalizada"]})
    st.warning("Regras informativas: autenticação, cobrança e limites no servidor ainda não estão implementados.")

# No network script is injected until the publisher config and deployment are approved.
# Streamlit embeds ad scripts inconsistently; actual serving needs a production
# integration with consent, CSP and the advertising provider's requirements.
AD_CONFIG = validated_adsense_config(
    os.environ.get("AFILIADOS_ADSENSE_PUBLISHER"),
    {
        "dashboard": os.environ.get("AFILIADOS_ADSENSE_DASHBOARD_SLOT"),
        "render_complete": os.environ.get("AFILIADOS_ADSENSE_COMPLETE_SLOT"),
    },
)
SPONSOR_URL = sponsor_destination(ACTIVE_PLAN, os.environ.get("AFILIADOS_SPONSOR_URL"))
if SPONSOR_URL and selected_section == "Criar anúncio":
    st.markdown("#### Patrocinador")
    st.caption("Link publicitário opcional. Abrirá uma nova guia; não é necessário acessar para gerar vídeos.")
    st.link_button("Conhecer patrocinador ↗", SPONSOR_URL)

if ads_enabled(ACTIVE_PLAN) and selected_section == "Criar anúncio":
    st.caption("Publicidade · Plano Grátis")
    st.container(border=True).info(
        "Espaço reservado para anúncio patrocinado. "
        + ("Integração publicitária aguardando aprovação do site." if AD_CONFIG else
           "Publicidade ainda não ativada.")
    )

if selected_section == "Criar anúncio":
    st.caption("Roteiros e montagem de vídeo locais. Narração online opcional por Edge TTS, acionada somente por você.")
    st.info("Preencha os dados reais do produto. Um roteiro básico será criado localmente para sua revisão; o ChatGPT será conectado na etapa final.")
    st.markdown("#### Seu estúdio de criação")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Formatos de capa", "3")
    with c2:
        st.metric("Durações disponíveis", "15 / 20 / 30 s")
    with c3:
        st.metric("APIs pagas", "0")
    st.caption("Os indicadores acima descrevem recursos do protótipo. Capas estão disponíveis no Premium e Creator; campanhas em lote são exclusivas do Creator.")
    if LOCAL_ACCOUNTS:
        if not email_verified:
            st.warning("Confirme seu e-mail para desbloquear a geração de vídeos.")
            if st.button("Reenviar e-mail de confirmação", key="affiliate_resend_logged_in"):
                try:
                    from app.afiliados.verification_email import send_verification_email
                    account_email = auth.verified_account_email(owner_id)
                    if not account_email:
                        raise RuntimeError("Conta não encontrada")
                    confirmation = auth.create_verification_token(account_email)
                    if confirmation:
                        send_verification_email(account_email, confirmation)
                    st.success("Verifique a caixa de entrada ou a pasta de spam.")
                except ValueError:
                    st.warning("Limite de reenvios atingido. Aguarde antes de tentar novamente.")
                except (RuntimeError, OSError):
                    st.error("O envio de e-mails está indisponível. Procure o administrador.")
        if ACTIVE_PLAN == "gratis":
            @st.fragment(run_every="1s")
            def free_cooldown_counter():
                state = video_quota.free_status(owner_id)
                if state.in_progress:
                    st.info("Seu vídeo gratuito está sendo processado. Aguarde a conclusão.")
                elif state.remaining_seconds > 0:
                    hours, remainder = divmod(state.remaining_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    st.info(f"Próximo vídeo gratuito em **{hours:02d}:{minutes:02d}:{seconds:02d}** (24 horas após a conclusão).")
                    st.session_state["affiliate_free_was_waiting"] = True
                elif state.attempt_retry_seconds > 0:
                    minutes, seconds = divmod(state.attempt_retry_seconds, 60)
                    st.warning(f"Muitas tentativas de geração. Tente novamente em {minutes:02d}:{seconds:02d}.")
                    st.session_state["affiliate_free_was_waiting"] = True
                elif state.capacity_retry_seconds > 0:
                    minutes, seconds = divmod(state.capacity_retry_seconds, 60)
                    st.warning(f"Capacidade gratuita ocupada. Nova tentativa em {minutes:02d}:{seconds:02d}.")
                    st.session_state["affiliate_free_was_waiting"] = True
                else:
                    st.success("Seu vídeo gratuito está disponível.")
                    if st.session_state.pop("affiliate_free_was_waiting", False):
                        st.rerun()
            free_cooldown_counter()
        else:
            used_today = video_quota.usage(owner_id)
            daily_limit = ACTIVE_POLICY.daily_video_limit
            st.caption(f"Vídeos concluídos hoje (Brasília): {used_today} / {daily_limit}")
    with st.expander("Importar dados de HTML salvo"):
        st.caption("Teste offline: envie o HTML da página para extrair nome e descrição. Nenhum site será acessado.")
        uploaded_html = st.file_uploader("HTML do produto (máximo 2 MB)", type=["html", "htm"])
        if st.button("Ler dados do produto", disabled=uploaded_html is None):
            try:
                from app.afiliados.metadata import extract_product_metadata
                raw = uploaded_html.getvalue()
                if len(raw) > 2_000_000:
                    raise ValueError("Arquivo acima de 2 MB")
                info = extract_product_metadata(raw.decode("utf-8-sig", errors="replace"))
                st.session_state["affiliate_imported"] = info
                if not info.get("name") and not info.get("description"):
                    st.warning("Nenhum dado do produto encontrado neste HTML. Informe manualmente.")
                if info.get("name"):
                    st.session_state["affiliate_product_name"] = info["name"]
                if info.get("description"):
                    st.session_state["affiliate_product_features"] = info["description"]
            except ValueError as exc:
                st.error(str(exc))
        if st.session_state.get("affiliate_imported"):
            st.json(st.session_state["affiliate_imported"])
            st.caption("Confirme os dados extraídos. Fotos continuam sendo enviadas manualmente.")

    with st.expander("Sugerir nome pelo link (sem acessar a loja)"):
        hint_url = st.text_input("Cole o link HTTPS do produto", key="affiliate_hint_url")
        if st.button("Analisar formato do link", disabled=not hint_url.strip()):
            try:
                from app.afiliados.link_hint import suggest_name_from_link
                suggestion = suggest_name_from_link(hint_url)
                st.session_state["affiliate_product_url"] = hint_url.strip()
                if suggestion:
                    st.session_state["affiliate_product_name"] = suggestion
                    st.success("Nome sugerido a partir do endereço. Confirme o nome real do produto.")
                else:
                    st.info("Este link não contém um nome identificável. Informe o nome manualmente.")
            except ValueError as exc:
                st.error(str(exc))
        st.caption("Não consulta preço, descrição ou fotos. O link sozinho ainda não produz um anúncio completo.")

    with st.form("affiliate_brief"):
        product_name = st.text_input("Nome do produto", max_chars=140, key="affiliate_product_name")
        product_url = st.text_input("Link HTTPS do produto (Shopee, Mercado Livre ou Amazon)", key="affiliate_product_url")
        features = st.text_area("Características verificadas do produto", max_chars=3000, key="affiliate_product_features")
        price_note = st.text_input("Preço/observação opcional (não inventar)", max_chars=180)
        duration = st.selectbox("Duração alvo", (15, 20, 30))
        cta = st.selectbox("Chamada para ação", list(CTA), format_func=lambda x: CTA[x])
        voice = st.selectbox("Narração desejada", ("feminina", "masculina"))
        script = st.text_area("Roteiro para aprovação (opcional)", max_chars=1400)
        submitted = st.form_submit_button("Preparar anúncio sem gastar créditos")

    if submitted:
        try:
            brief = AffiliateBrief(product_name, product_url, features, duration, cta, voice, price_note)
            draft = prepare_draft(brief, script)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.pop("affiliate_mp4", None)
            st.session_state.pop("affiliate_review_script", None)
            st.session_state.pop("affiliate_render_key", None)
            st.session_state.pop("affiliate_generated_audio", None)
            st.session_state.pop("affiliate_voice_script", None)
            st.session_state.pop("affiliate_voice_type", None)
            st.session_state.pop("affiliate_approval_key", None)
            # The checkbox widget may have been instantiated in a prior run;
            # clear its value before the widget is created below.
            st.session_state["affiliate_approved"] = False
            st.session_state.pop("affiliate_loaded_project_id", None)
            st.session_state["affiliate_draft"] = draft

    draft = st.session_state.get("affiliate_draft")
    if draft:
        st.subheader("Revisão do anúncio")
        edited_script = st.text_area("Revise o roteiro antes de gerar", value=draft["script"], max_chars=1400, key="affiliate_review_script")
        reviewed_draft = {**draft, "script": edited_script.strip()}
        st.caption("ChatGPT e Kling permanecem desativados até a etapa final. Você já pode montar um vídeo com fotos reais e áudio enviado manualmente.")
        photos = st.file_uploader(
            "Fotos reais do produto (até 8, JPEG/PNG/WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )
        narration = st.file_uploader(
            "Narração opcional já gravada (MP3, WAV ou M4A)",
            type=["mp3", "wav", "m4a"],
        )
        st.caption("As legendas são distribuídas entre as fotos, sem sincronização palavra por palavra.")
        st.caption("Narração automática opcional via Edge TTS: requer internet e envia o roteiro ao serviço externo.")
        if st.button("Gerar narração em português brasileiro", disabled=not email_verified or not edited_script.strip()):
            try:
                from app.afiliados.voice import generate_voice
                with st.spinner("Gerando narração..."):
                    generated = generate_voice(edited_script.strip(), draft["product"]["voice"])
                st.session_state["affiliate_generated_audio"] = generated
                st.session_state["affiliate_voice_script"] = edited_script.strip()
                st.session_state["affiliate_voice_type"] = draft["product"]["voice"]
            except Exception as exc:
                st.error(f"Falha na narração: {type(exc).__name__}: {exc}")
        if (st.session_state.get("affiliate_voice_script") != edited_script.strip()
                or st.session_state.get("affiliate_voice_type") != draft["product"]["voice"]):
            st.session_state.pop("affiliate_generated_audio", None)
        generated_audio = st.session_state.get("affiliate_generated_audio")
        if generated_audio:
            st.audio(generated_audio, format="audio/mp3")
            st.download_button("Baixar narração MP3", generated_audio, file_name="afiliados-creator-narracao.mp3", mime="audio/mpeg")
        selected_audio = narration.getvalue() if narration else generated_audio
        selected_extension = ("." + narration.name.rsplit(".", 1)[-1].lower()) if narration else ".mp3"

        # Fingerprint the full rendering input so an old MP4 is never offered for new assets.
        render_digest = hashlib.sha256()
        render_digest.update(json.dumps(reviewed_draft["product"], sort_keys=True, ensure_ascii=False).encode("utf-8"))
        render_digest.update(edited_script.strip().encode("utf-8"))
        render_digest.update(str(draft["product"]["duration"]).encode("ascii"))
        for photo in photos or []:
            render_digest.update(photo.getvalue())
            render_digest.update(photo.name.encode("utf-8"))
        if selected_audio:
            render_digest.update(selected_audio)
            render_digest.update(selected_extension.encode("ascii"))
        current_render_key = render_digest.hexdigest()
        st.subheader("Capas automáticas")
        st.caption("Três opções de thumbnail PNG feitas localmente com a primeira foto real do produto.")
        if photos and ACTIVE_POLICY.thumbnails_per_ad:
            try:
                from app.afiliados.thumbnails import generate_thumbnails
                covers = generate_thumbnails(photos[0].getvalue(), draft["product"]["product_name"], watermark=ACTIVE_POLICY.platform_watermark_required)
                columns = st.columns(3)
                for column, (style, cover) in zip(columns, covers.items()):
                    with column:
                        st.image(cover, caption=style.title(), use_container_width=True)
                        if store is not None and st.button(f"Salvar capa {style} na biblioteca", key=f"save-cover-{current_render_key}-{style}"):
                            try:
                                media_store.save(owner_id, "thumbnail", cover)
                                st.success("Capa salva na biblioteca local.")
                            except ValueError as exc:
                                st.error(str(exc))
                        st.download_button(
                            f"Baixar {style}", cover,
                            file_name=f"afiliados-{style}.png", mime="image/png",
                            key=f"cover-{current_render_key}-{style}",
                        )
            except ValueError as exc:
                st.error(f"Não foi possível criar as capas: {exc}")
        elif photos:
            st.info("Capas automáticas estão disponíveis nos planos Premium e Creator.")
        # An approval belongs to one specific script/product, never to a previous draft.
        approval_payload = json.dumps(reviewed_draft, sort_keys=True, ensure_ascii=False)
        approval_key = hashlib.sha256(approval_payload.encode("utf-8")).hexdigest()
        if st.session_state.get("affiliate_approval_key") != approval_key:
            st.session_state["affiliate_approved"] = False
            st.session_state["affiliate_approval_key"] = approval_key
        approved = st.checkbox("Revisei o roteiro e confirmo que as informações do produto são verdadeiras.", key="affiliate_approved")
        if len(photos or []) > 8:
            st.error("Envie no máximo 8 fotos do produto.")
        from app.afiliados.render import VIDEO_VARIANTS
        selected_variant = (st.selectbox("Versão do vídeo", VIDEO_VARIANTS, format_func=str.title, key="affiliate_video_variant")
                            if ACTIVE_POLICY.videos_per_ad == 3 else "impacto")
        free_blocked = ACTIVE_PLAN == "gratis" and not video_quota.free_status(owner_id).can_generate
        if st.button("Gerar MP4 local (sem usar APIs)", disabled=not email_verified or free_blocked or not approved or not photos or len(photos) > 8 or not edited_script.strip()):
            try:
                from app.afiliados.render import render_mp4
                reservation = video_quota.reserve(owner_id, ACTIVE_PLAN) if LOCAL_ACCOUNTS else None
                try:
                    with st.spinner("Montando vídeo vertical com os arquivos enviados..."):
                        mp4 = render_mp4(
                        [photo.getvalue() for photo in photos],
                        draft["product"]["duration"],
                        edited_script.strip(),
                        selected_audio,
                        selected_extension,
                        variant=selected_variant,
                        watermark=ACTIVE_POLICY.platform_watermark_required,
                        )
                    if reservation is not None:
                        video_quota.complete(owner_id, reservation)
                except Exception:
                    if reservation is not None:
                        video_quota.release(owner_id, reservation)
                    raise
                st.session_state["affiliate_mp4"] = mp4
                st.session_state["affiliate_render_key"] = current_render_key + ":" + selected_variant
                st.success("Vídeo montado localmente. Nenhuma API paga foi utilizada.")
                if ads_enabled(ACTIVE_PLAN):
                    st.caption("Publicidade · Espaço reservado após a conclusão do vídeo")
            except Exception as exc:
                st.error(f"Não foi possível montar o vídeo: {type(exc).__name__}: {exc}")
        if st.session_state.get("affiliate_mp4") and st.session_state.get("affiliate_render_key") != current_render_key + ":" + selected_variant:
            st.session_state.pop("affiliate_mp4", None)
        if st.session_state.get("affiliate_mp4"):
            st.video(st.session_state["affiliate_mp4"])
            if store is not None and st.button("Salvar MP4 na biblioteca local"):
                try:
                    media_store.save(owner_id, "video", st.session_state["affiliate_mp4"])
                    st.success("Vídeo salvo na biblioteca local.")
                except ValueError as exc:
                    st.error(str(exc))
            st.download_button(
                "Baixar MP4",
                st.session_state["affiliate_mp4"],
                file_name=f"afiliados-creator-{selected_variant}.mp4",
                mime="video/mp4",
            )
        st.markdown("#### Pacote completo: 3 vídeos + 9 capas")
        st.caption("Exclusivo do Creator. Geração local em sequência, com alto uso de CPU e memória.")
        if st.button("Gerar pacote completo ZIP", disabled=ACTIVE_POLICY.videos_per_ad != 3 or not approved or not photos or len(photos) > 8 or not edited_script.strip()):
            try:
                from app.afiliados.campaign import build_campaign
                reservation = video_quota.reserve(owner_id, ACTIVE_PLAN, count=3) if LOCAL_ACCOUNTS else None
                try:
                    with st.spinner("Renderizando as três versões e as nove capas..."):
                        package = build_campaign(
                        [photo.getvalue() for photo in photos],
                        draft["product"]["product_name"],
                        draft["product"]["duration"],
                        edited_script.strip(),
                        selected_audio,
                        selected_extension,
                        plan=ACTIVE_PLAN,
                        watermark=ACTIVE_POLICY.platform_watermark_required,
                        )
                    if reservation is not None:
                        video_quota.complete(owner_id, reservation)
                except Exception:
                    if reservation is not None:
                        video_quota.release(owner_id, reservation)
                    raise
                st.session_state["affiliate_campaign_zip"] = package
                st.session_state["affiliate_campaign_key"] = current_render_key
                st.success("Pacote completo gerado: 3 vídeos e 9 capas.")
            except Exception as exc:
                st.session_state.pop("affiliate_campaign_zip", None)
                st.session_state.pop("affiliate_campaign_key", None)
                st.error(f"Falha na geração do pacote: {type(exc).__name__}: {exc}")
        if st.session_state.get("affiliate_campaign_key") != current_render_key:
            st.session_state.pop("affiliate_campaign_zip", None)
        if st.session_state.get("affiliate_campaign_zip"):
            st.download_button(
                "Baixar pacote completo (ZIP)",
                st.session_state["affiliate_campaign_zip"],
                file_name="afiliados-creator-campanha.zip",
                mime="application/zip",
                key="affiliate_campaign_download",
            )
        if store is not None and ACTIVE_POLICY.project_saving_allowed:
            if st.button("Salvar projeto na minha conta local"):
                try:
                    project_id = store.save(owner_id, reviewed_draft, st.session_state.get("affiliate_loaded_project_id"))
                    st.session_state["affiliate_loaded_project_id"] = project_id
                    st.success("Projeto salvo no banco local desta conta.")
                except ValueError as exc:
                    st.error(str(exc))
        if ACTIVE_POLICY.project_saving_allowed:
            st.download_button(
                "Baixar projeto do anúncio (JSON)",
            data=json.dumps(reviewed_draft, ensure_ascii=False, indent=2),
            file_name="afiliados-creator-projeto.json",
                mime="application/json",
            )
        with st.expander("Prompt preparado para ChatGPT"):
            st.code(draft["prompt"]["system"] + "\n\n" + draft["prompt"]["user"], language="text")
