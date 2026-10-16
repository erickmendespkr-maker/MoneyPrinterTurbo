# Afiliados Creator — integração do renderizador

## Estado atual
- Supabase: projeto `ytyqojcvzaquccaolwyw`, bucket privado `generated-videos`.
- A reserva autenticada ocorre pela RPC `reserve_video_generation(duration)`.
- O worker usa a credencial **service_role somente no servidor**, nunca no navegador.
- A RPC `worker_claim_next_generation()` retorna id, usuário e duração; **não retorna ainda o briefing do vídeo**.
- `app/services/task.py:start(task_id, params, stop_at="video")` é a entrada existente para a pipeline; requer `VideoParams` completos.
- `app/services/afiliados_backend.py` contém claim, start, upload, finish e timeout.

## Bloqueio antes de ativar produção
**Não iniciar jobs reais somente com a duração.** É necessário implementar um endpoint autenticado para receber e validar o briefing, fotos/URLs permitidas, texto, voz, estilo e consentimentos; gravar dados vinculados ao job com política de acesso; e entregar ao worker uma configuração validada. Sem isso, não há informações suficientes para produzir o vídeo correto.

## Contrato sugerido
1. Frontend autenticado envia o briefing para uma API de criação controlada pelo servidor.
2. API valida limites, uploads e campos; reserva o job e armazena o briefing de forma transacional.
3. Worker reivindica job atomicamente e recupera o briefing pelo ID usando credencial restrita.
4. Worker constrói `VideoParams` e chama `task.start(..., stop_at="video")`, monitorando estado terminal.
5. Sucesso: envia MP4 para `generated-videos/{user_id}/{generation_id}.mp4` e só então chama `worker_finish_generation(success=True, storage_path=...)`.
6. Falha: registra código seguro sem divulgar segredos; chama `worker_finish_generation(success=False, error_code=...)`.
7. Rotina periódica chama `worker_fail_stale_generations`; exige estratégia para evitar expirar jobs ativos de longa duração.

## Testes necessários
- Requisições paralelas no plano grátis: somente uma reserva em 24 horas.
- Acesso cruzado a arquivos: usuário B não lê arquivo de A.
- Worker duplicado: apenas um reivindica o mesmo job.
- Falha de render, falha de upload e timeout não geram conclusão falsa.
- Definir política explícita de reembolso de créditos e reposição de tentativa gratuita.
- Nunca expor API original do MoneyPrinterTurbo sem autenticação ou sem verificação de cotas.

## Configuração (somente servidor)
`SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` via gerenciador de segredos. Não registrar os valores em Git.
