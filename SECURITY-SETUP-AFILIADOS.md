# Secure setup (Afiliados branch)

This branch contains initial hardening only, **not** a completed security certification.

1. Create a local `config.toml` from `config.example.toml`. Set `[app].api_key` to a long, random secret. Never commit it.
2. Run only on your own computer or an isolated test VM; do not expose ports publicly.
3. Local API binds to 127.0.0.1 by default. Docker publishes 8080 and 8501 only on the host's 127.0.0.1.
4. API startup refuses empty authentication keys; requests to /api/v1 and /tasks require `x-api-key`.
5. The Streamlit WebUI is **not authenticated** by this API key. Never expose port 8501 to an untrusted network.
6. Docker uses a non-root user, drops Linux capabilities, and mounts only a local config file plus an isolated named storage volume. Create `config.toml` as a real file before running Docker Compose; never commit it. Docker bind-mount permissions must allow the configured container user to read it.
7. Run the GitHub Actions security workflow and investigate any alerts before using real credentials.
8. Review transitive dependencies, downloads, workflow supply-chain, SSRF, file uploads, logging, and outbound requests. Dynamic sandbox testing remains necessary.
9. Do not connect OpenAI, Kling, Instagram or Shopee accounts until those reviews pass. Apply provider spending limits and use least-privilege credentials.

**Compatibility note:** old clients relying on unauthenticated API access will stop working. Docker volume permissions may require adjustments on some hosts. Do not use a real API key for troubleshooting.

## Affiliate mode implemented before API integration
- `webui/pages/90_Afiliados.py`: product briefing, real-product facts, CTA and narration preferences, prompt preview and JSON download.
- `app/afiliados/core.py`: validates supported HTTPS merchant links without fetching them, builds a factual OpenAI prompt and an approval-pending draft.
- `app/afiliados/render.py`: locally renders a vertical photo slideshow (720×1280) with optional uploaded narration and MP4 export. This is a preliminary editor, not AI video generation.
- `test/test_afiliados_core.py` and `test/test_afiliados_render.py`: input and media handling tests.
- **Neither OpenAI nor Kling is called**; no API key is required for affiliate draft preparation.
- This mode currently accepts Shopee, Mercado Livre and Amazon Brazil product links. Product information is entered manually; automatic product scraping is intentionally disabled.
- The MP4 renderer does not yet burn subtitles or automatically narrate the script. It uses real uploaded images and optional uploaded audio.
- PR #1 is a draft and must remain unmerged until CI, dependency review, and runtime testing pass.

## Security scan findings (15 October 2026)
The initial dependency audit flagged python-multipart 0.0.27, litellm 1.86.2 and transitive Pillow 11.3.0. Requirements and pyproject pins were updated to python-multipart 0.0.31 and litellm 1.96.2. A proposed Pillow 12.3.0 pin was reverted after CI found a dependency conflict with MoviePy 2.2.1. **Pillow remediation remains blocked** until a compatible MoviePy/image stack is selected and tested. The dependency lockfile and CI must be regenerated and verified before approval.
