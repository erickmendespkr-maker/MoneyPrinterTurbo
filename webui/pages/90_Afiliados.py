"""Offline affiliate workflow. API credentials and paid generation intentionally absent."""
import json
import sys
from pathlib import Path
from uuid import uuid4

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.afiliados.core import AffiliateBrief, CTA, make_openai_prompt, prepare_draft

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
    st.caption("Aprovação, narração, Kling e exportação MP4 serão habilitados após os testes e a configuração final.")
    st.download_button(
        "Baixar projeto do anúncio (JSON)",
        data=json.dumps(draft, ensure_ascii=False, indent=2),
        file_name="anuncio-afiliado.json",
        mime="application/json",
    )
    with st.expander("Prompt preparado para ChatGPT"):
        st.code(draft["prompt"]["system"] + "\n\n" + draft["prompt"]["user"], language="text")
