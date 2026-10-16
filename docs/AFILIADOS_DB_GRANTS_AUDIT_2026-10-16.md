# Marco de segurança — permissões SQL do Supabase (16/10/2026)

Projeto real: `ytyqojcvzaquccaolwyw`.

## Auditoria
As seis tabelas públicas tinham privilégios SQL de INSERT/UPDATE/DELETE/TRUNCATE/TRIGGER/REFERENCES para `anon` e `authenticated`, embora suas políticas RLS existentes fossem apenas de SELECT. RLS já bloqueava as escritas comuns; revogar privilégios torna a defesa mais explícita e reduz risco em alterações futuras de políticas.

## Migrações aplicadas
1. `afiliados_restrict_generation_table_dml_to_worker`: remove escrita de clientes em `video_generations`.
2. `afiliados_restrict_all_business_tables_to_read_only_clients`: remove escrita de clientes em `generation_limits`, `plans`, `profiles`, `subscriptions`, `usage_ledger`.

## Verificação
Consulta a `information_schema.role_table_grants` confirmou que `anon` e `authenticated` possuem somente `SELECT` nas seis tabelas. Políticas RLS de SELECT continuam específicas a usuários autenticados e à propriedade do registro (com catálogo de planos acessível a autenticados).

## Cautelas
- Funções `SECURITY DEFINER` e triggers devem continuar testadas após essa restrição.
- Caso o produto venha a permitir atualização de perfil, criar uma RPC de atualização limitada aos campos editáveis ou políticas/GRANTs por coluna, nunca conceder UPDATE irrestrito em assinatura/cotas.
- Esta auditoria não substitui testes com JWT real e duas contas. Não há teste fim-a-fim de renderização.
