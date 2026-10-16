# Reconciliação de arquitetura — 2026-10-16

## Fontes de verdade
- Decisões: dossiê de continuidade de 16/10/2026 e imagens originais aprovadas.
- Código: branch `feature/afiliados`; não alterar `main`.
- Banco real: Supabase `ytyqojcvzaquccaolwyw` (São Paulo).
- **Não aplicar** migrations `infra/supabase/001–003` no banco real: pertencem à trilha experimental.

## Inspeção somente leitura efetuada
- `app/afiliados/plans.py` contém quatro planos: `gratis`, `pro`, `premium`, `creator`, com limites 1/3/5/10, respectivamente.
- `app/afiliados/pricing.py` contém mensalidades 0/69,90/119,90/199,90 e preço anual de dez mensalidades.
- Banco real `public.plans` possui `free`, `pro`, `creator`; **falta `premium`**. O banco usa `free` e o protótipo `gratis`.
- O esquema atual de `public.plans` contém `code`, `name`, `daily_free_limit`, `created_at`; não modela ainda todas as permissões e preços.
- `public.create_video_generation` define `next_free_generation_at=now()+interval '24 hours'` **ao reservar**, contrariando a política aprovada de 24 horas **após sucesso**.
- `public.worker_finish_generation` conclui job e registra ledger, mas **não inicia** a janela de 24h.
- `public.reserve_video_generation` (rota antiga) também inicia a janela na reserva; deve permanecer sem permissão de uso por clientes.
- `app/services/afiliados_render_params.py` declara explicitamente que imagens reais do produto ainda não são suportadas.

## Matriz de convergência
| Regra | Trilha A | Trilha B / banco real | Ação |
| --- | --- | --- | --- |
| Planos | 4 níveis, preços corretos | 3 registros, permissões incompletas | Nova migration compatível e enforcement server-side |
| Grátis | 24h após conclusão, falha não consome | 24h na reserva | Corrigir criação/conclusão e testar concorrência |
| Pagos | 3/5/10 vídeos por dia SP | RPC sem limite diário de pagos | Criar cotas atômicas por período SP |
| Entrada | Link, HTML, fotos | Contrato Pydantic, bucket privado | Integrar upload e importador autorizado |
| Renderização | MoviePy com fotos reais | Mapper usa Pexels | Integrar mídia específica com validação |
| Autorização | Protótipo local | Auth/RLS/RPC | Testar com duas contas reais |
| UI | Streamlit aproximada | Sem fidelidade comprovada | Usar mockup original enviado pelo usuário |
| Worker | Worker experimental | RPC claim/heartbeat/finish | Testar MP4 fim-a-fim e falhas |

## Segurança de migração
Não lançar cobrança antes de garantir cotas pagas e direitos por plano no servidor. Não alterar o projeto Supabase antigo. Não iniciar serviço pago. Para evitar dupla fila, usar a Trilha B como base de produção e transplantar apenas capacidades da Trilha A após testes.

## Próxima implementação
1. Migration **não destrutiva** do catálogo de quatro planos e política de cotas.
2. Corrigir cooldown para iniciar exclusivamente após conclusão bem-sucedida, bloqueando jobs simultâneos.
3. Testar falha, conclusão, concorrência, permissões e regressões.
4. Integrar fotos reais ao worker e executar renderização controlada antes de ligar ao dashboard.
