# Marco de implementação — snapshot de plano e segurança (16/10/2026)

Projeto Supabase real `ytyqojcvzaquccaolwyw`.

## Alterações aplicadas
- Migration `afiliados_snapshot_entitlement_at_generation_creation`: coluna `video_generations.effective_plan_code` com check de `free/pro/premium/creator`, trigger BEFORE INSERT e função SECURITY DEFINER que resolve o plano a partir da assinatura ativa no servidor, ignorando dados de plano enviados pelo cliente.
- Migration `afiliados_use_reserved_plan_for_free_cooldown`: `worker_finish_generation` usa `effective_plan_code` capturado na reserva. Cooldown do Grátis só inicia em sucesso; falhas não iniciam a espera.
- Confirmada a existência do trigger `trg_snapshot_video_generation_plan` em `public.video_generations`.
- Auditoria anterior: funções `worker_*` não executáveis por `authenticated` nem `anon`; somente o backend de confiança pode concluir jobs.
- `worker_fail_stale_generations` marca jobs reservados/processando como falhos sem iniciar cooldown. A verificação foi por inspeção do SQL, não por job real.

## Riscos e tarefas ainda abertos
- Zero contas e zero jobs no banco na última leitura; **não há teste fim-a-fim autenticado**.
- Testar corrida entre conclusão de vídeo e reserva concorrente, upgrade/downgrade durante job, timeout, sucesso repetido, e idempotência de upload.
- Conferir se RLS e permissões de colunas impedem cliente de alterar `effective_plan_code` por UPDATE; trigger protege INSERT, mas coluna deve ser protegida contra UPDATE por cliente.
- Garantir que UI, thumbnails, marca-d'água, 3 vídeos/anúncio Creator e importação de fotos usam entitlements server-side.
- Resolver o upload e a renderização de fotos reais; o mapper atual usa Pexels.
- Não ativar cobrança ou infraestrutura paga sem aprovação.
