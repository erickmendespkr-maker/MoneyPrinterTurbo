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
from app.afiliados.ads import ads_enabled, ad_placement, validated_adsense_config  # noqa: E402
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
LOCAL_ACCOUNTS = os.environ.get("AFILIADOS_LOCAL_ACCOUNTS") == "1"
owner_id = None
store = None
if LOCAL_ACCOUNTS:
    from app.afiliados.auth import LocalAuth
    from app.afiliados.storage import ProjectStore

    auth = LocalAuth(ROOT / "data" / "afiliados-auth.sqlite")
    token = st.session_state.get("affiliate_session_token")
    owner_id = auth.resolve(token) if token else None
    if owner_id is None:
        st.session_state.pop("affiliate_session_token", None)
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
            demo_dir = ROOT / "assets" / "afiliados" / "demos"
            demos = sorted(demo_dir.glob("*.mp4"))[:6] if demo_dir.is_dir() else []
            if demos:
                for demo in demos:
                    st.video(str(demo))
            else:
                st.info("Vídeos demonstrativos serão publicados aqui. Nenhum exemplo fictício foi apresentado como vídeo real.")
        with pricing_tab:
            st.table({
                "Plano": ["Grátis", "Pro", "Creator"],
                "Vídeos por dia": ["1", "5", "Ilimitados (uso justo)"],
                "Vídeos por anúncio": [1, 1, 3],
                "Capas por anúncio": [0, 0, 9],
                "Salvar projetos": ["Não", "Sim", "Sim"],
                "Publicidade": ["Sim", "Não", "Não"],
            })
        st.divider()
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
                    except ValueError:
                        st.error("Não foi possível entrar com essas credenciais.")
        with register_tab:
            with st.form("affiliate_register"):
                email = st.text_input("E-mail", key="affiliate_register_email")
                password = st.text_input("Senha (mínimo 12 caracteres)", type="password", key="affiliate_register_password")
                confirm = st.text_input("Confirmar senha", type="password")
                if st.form_submit_button("Criar conta"):
                    if password != confirm:
                        st.error("As senhas não coincidem.")
                    else:
                        try:
                            auth.register(email, password)
                            st.success("Conta local criada. Entre na aba Entrar.")
                        except ValueError as exc:
                            st.error(str(exc))
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
                    except ValueError:
                        st.error("Informe um endereço de e-mail válido.")
                    except (RuntimeError, OSError):
                        st.error("O serviço de recuperação por e-mail está indisponível no momento.")
        st.stop()
    subscriptions = SubscriptionStore(ROOT / "data" / "afiliados-subscriptions.sqlite")
    ACTIVE_PLAN = subscriptions.get_plan(owner_id)
    ACTIVE_POLICY = get_plan_policy(ACTIVE_PLAN)
    store = AuthorizedProjects(ProjectStore(ROOT / "data" / "afiliados-projects.sqlite"), subscriptions)
    from app.afiliados.video_quota import VideoQuota
    video_quota = VideoQuota(ROOT / "data" / "afiliados-video-quota.sqlite")
    from app.afiliados.media_store import MediaStore
    media_store = MediaStore(ROOT / "data" / "afiliados-media.sqlite")

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
    st.info("Salvar e reabrir projetos é exclusivo dos planos Pro e Creator.")
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
    st.caption("Os indicadores acima descrevem recursos do protótipo, não produções realizadas. Capas e campanhas em lote são exclusivas do Creator.")
    if LOCAL_ACCOUNTS:
        used_today = video_quota.usage(owner_id)
        daily_limit = ACTIVE_POLICY.daily_video_limit
        st.caption(f"Vídeos concluídos hoje (São Paulo): {used_today} / {daily_limit if daily_limit is not None else chr(8734)}")
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
        if st.button("Gerar narração em português brasileiro", disabled=not edited_script.strip()):
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
                covers = generate_thumbnails(photos[0].getvalue(), draft["product"]["product_name"])
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
            st.info("Capas automáticas são exclusivas do plano Creator.")
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
        if st.button("Gerar MP4 local (sem usar APIs)", disabled=not approved or not photos or len(photos) > 8 or not edited_script.strip()):
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
