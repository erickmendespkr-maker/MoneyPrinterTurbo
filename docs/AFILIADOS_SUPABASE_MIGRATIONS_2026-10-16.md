# Migrações aplicadas ao Supabase real — 16/10/2026

Projeto: `ytyqojcvzaquccaolwyw` (São Paulo). **Não aplicar novamente manualmente** sem consultar o histórico de migrations do Supabase.

## Aplicadas com sucesso
1. `afiliados_four_plan_catalog_20261016`: inseriu `premium` no catálogo, preservando `free/pro/creator`.
2. `afiliados_enforce_plan_quota_and_completion_cooldown_20261016`:
   - `create_video_generation` mantém validação de brief, serializa reservas por usuário via `generation_limits ... FOR UPDATE`, impede duas gerações gratuitas em andamento, não inicia cooldown na reserva.
   - Pagos: cotas 3/5/10 para Pro/Premium/Creator; contabiliza `reserved/processing/completed` por `created_at` dentro do dia `America/Sao_Paulo`.
   - `worker_finish_generation`: em sucesso, grava cooldown Grátis de 24h após conclusão; em falha, não inicia cooldown.
   - `reserve_video_generation`: desabilitada com exceção e REVOKE para anon/authenticated.

## Conferência pós-migração
- `public.plans` retorna `free/pro/premium/creator`.
- `authenticated` pode executar `create_video_generation`, não pode executar `reserve_video_generation` nem `worker_finish_generation`.

## Limites e próximos testes
- Não houve testes de ponta a ponta com duas contas reais nem simulação de concorrência autenticada.
- O backend usa `created_at` para quota de dia, reservando vagas antecipadamente; falhas/cancelamentos deixam de contar.
- Ainda faltam enforcement de pacote de três vídeos por anúncio Creator, thumbnails, marca-d'água, importador Shopee, upload-to-render e assinatura/cobrança.
- O plano Grátis pode ter registros legados com `next_free_generation_at` iniciado na reserva antes desta migração; requer auditoria específica antes de ajustar dados.
- **Importante:** se assinatura mudar durante a renderização, a regra atual do cooldown consulta o plano na conclusão. Antes do lançamento, persistir o plano efetivo no momento da reserva para evitar troca de plano durante o job.
- Testar que `worker_fail_stale_generations` não bloqueia permanentemente a conta Grátis e que reexecuções do worker não duplicam consumo.
