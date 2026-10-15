"""Offline affiliate workflow. API credentials and paid generation intentionally absent."""
import hashlib
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.afiliados.core import AffiliateBrief, CTA, prepare_draft  # noqa: E402

st.set_page_config(page_title="Afiliados Creator", page_icon="🎬", layout="centered")
st.title("🎬 Afiliados Creator")
st.caption("Roteiros e montagem de vídeo locais. Narração online opcional por Edge TTS, acionada somente por você.")
st.info("Preencha os dados reais do produto. Um roteiro básico será criado localmente para sua revisão; o ChatGPT será conectado na etapa final.")
with st.form("affiliate_brief"):
    product_name = st.text_input("Nome do produto", max_chars=140)
    product_url = st.text_input("Link HTTPS do produto (Shopee, Mercado Livre ou Amazon)")
    features = st.text_area("Características verificadas do produto", max_chars=3000)
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
    if photos:
        try:
            from app.afiliados.thumbnails import generate_thumbnails
            covers = generate_thumbnails(photos[0].getvalue(), draft["product"]["product_name"])
            columns = st.columns(3)
            for column, (style, cover) in zip(columns, covers.items()):
                with column:
                    st.image(cover, caption=style.title(), use_container_width=True)
                    st.download_button(
                        f"Baixar {style}", cover,
                        file_name=f"afiliados-{style}.png", mime="image/png",
                        key=f"cover-{current_render_key}-{style}",
                    )
        except ValueError as exc:
            st.error(f"Não foi possível criar as capas: {exc}")
    # An approval belongs to one specific script/product, never to a previous draft.
    approval_payload = json.dumps(reviewed_draft, sort_keys=True, ensure_ascii=False)
    approval_key = hashlib.sha256(approval_payload.encode("utf-8")).hexdigest()
    if st.session_state.get("affiliate_approval_key") != approval_key:
        st.session_state["affiliate_approved"] = False
        st.session_state["affiliate_approval_key"] = approval_key
    approved = st.checkbox("Revisei o roteiro e confirmo que as informações do produto são verdadeiras.", key="affiliate_approved")
    if len(photos or []) > 8:
        st.error("Envie no máximo 8 fotos do produto.")
    if st.button("Gerar MP4 local (sem usar APIs)", disabled=not approved or not photos or len(photos) > 8 or not edited_script.strip()):
        try:
            from app.afiliados.render import render_mp4
            with st.spinner("Montando vídeo vertical com os arquivos enviados..."):
                mp4 = render_mp4(
                    [photo.getvalue() for photo in photos],
                    draft["product"]["duration"],
                    edited_script.strip(),
                    selected_audio,
                    selected_extension,
                )
            st.session_state["affiliate_mp4"] = mp4
            st.session_state["affiliate_render_key"] = current_render_key
            st.success("Vídeo montado localmente. Nenhuma API paga foi utilizada.")
        except Exception as exc:
            st.error(f"Não foi possível montar o vídeo: {type(exc).__name__}: {exc}")
    if st.session_state.get("affiliate_mp4") and st.session_state.get("affiliate_render_key") != current_render_key:
        st.session_state.pop("affiliate_mp4", None)
    if st.session_state.get("affiliate_mp4"):
        st.video(st.session_state["affiliate_mp4"])
        st.download_button(
            "Baixar MP4",
            st.session_state["affiliate_mp4"],
            file_name="afiliados-creator.mp4",
            mime="video/mp4",
        )
    st.download_button(
        "Baixar projeto do anúncio (JSON)",
        data=json.dumps(reviewed_draft, ensure_ascii=False, indent=2),
        file_name="afiliados-creator-projeto.json",
        mime="application/json",
    )
    with st.expander("Prompt preparado para ChatGPT"):
        st.code(draft["prompt"]["system"] + "\n\n" + draft["prompt"]["user"], language="text")
