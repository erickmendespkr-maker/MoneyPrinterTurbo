"""Offline affiliate workflow. API credentials and paid generation intentionally absent."""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.afiliados.core import AffiliateBrief, CTA, prepare_draft

st.set_page_config(page_title="Afiliados | MoneyPrinterTurbo", page_icon="🎬", layout="centered")
st.title("🎬 MoneyPrinterTurbo Afiliados")
st.caption("Modo de preparação offline. Nenhuma API externa é acionada e nenhum crédito é consumido.")
st.info("Preencha os dados reais do produto. O roteiro do ChatGPT será conectado na etapa final; por enquanto, você pode revisar um texto manualmente.")
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
        st.session_state["affiliate_draft"] = draft

draft = st.session_state.get("affiliate_draft")
if draft:
    st.subheader("Revisão do anúncio")
    st.write(draft["script"] or "Roteiro ainda não fornecido — aguardando integração com ChatGPT.")
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
    approved = st.checkbox("Revisei o roteiro e confirmo que as informações do produto são verdadeiras.")
    if st.button("Gerar MP4 local (sem usar APIs)", disabled=not approved or not photos):
        try:
            from app.afiliados.render import render_mp4
            with st.spinner("Montando vídeo vertical com os arquivos enviados..."):
                mp4 = render_mp4(
                    [photo.getvalue() for photo in photos],
                    draft["product"]["duration"],
                    draft["script"],
                    narration.getvalue() if narration else None,
                    "." + narration.name.rsplit(".", 1)[-1].lower() if narration else ".mp3",
                )
            st.session_state["affiliate_mp4"] = mp4
            st.success("Vídeo montado localmente. Nenhuma API paga foi utilizada.")
        except Exception as exc:
            st.error(f"Não foi possível montar o vídeo: {type(exc).__name__}: {exc}")
    if st.session_state.get("affiliate_mp4"):
        st.video(st.session_state["affiliate_mp4"])
        st.download_button(
            "Baixar MP4",
            st.session_state["affiliate_mp4"],
            file_name="reels-afiliados.mp4",
            mime="video/mp4",
        )
    st.download_button(
        "Baixar projeto do anúncio (JSON)",
        data=json.dumps(draft, ensure_ascii=False, indent=2),
        file_name="anuncio-afiliado.json",
        mime="application/json",
    )
    with st.expander("Prompt preparado para ChatGPT"):
        st.code(draft["prompt"]["system"] + "\n\n" + draft["prompt"]["user"], language="text")
