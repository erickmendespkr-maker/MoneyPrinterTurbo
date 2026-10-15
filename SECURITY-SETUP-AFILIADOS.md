# Secure setup (Afiliados branch)

This branch contains initial hardening only, **not** a completed security certification.

1. Create a local `config.toml` from `config.example.toml`. Set `[app].api_key` to a long, random secret. Never commit it.
2. Run only on your own computer or an isolated test VM; do not expose ports publicly.
3. Local API binds to 127.0.0.1 by default. Docker publishes 8080 and 8501 only on the host's 127.0.0.1.
4. API startup refuses empty authentication keys; requests to /api/v1 and /tasks require `x-api-key`.
5. The Streamlit WebUI is **not authenticated** by this API key. Never expose port 8501 to an untrusted network.
6. Docker now uses a non-root user and drops Linux capabilities. The compose bind mount still exposes the project directory: only use with trusted local files.
7. Run the GitHub Actions security workflow and investigate any alerts before using real credentials.
8. Review transitive dependencies, downloads, workflow supply-chain, SSRF, file uploads, logging, and outbound requests. Dynamic sandbox testing remains necessary.
9. Do not connect OpenAI, Kling, Instagram or Shopee accounts until those reviews pass. Apply provider spending limits and use least-privilege credentials.

**Compatibility note:** old clients relying on unauthenticated API access will stop working. Docker volume permissions may require adjustments on some hosts. Do not use a real API key for troubleshooting.
