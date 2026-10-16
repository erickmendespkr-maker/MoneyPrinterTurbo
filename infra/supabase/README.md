# Afiliados Creator — migração para autenticação/cotas públicas

**Status: preparação de infraestrutura, ainda NÃO implantada.** Esta pasta
não provisiona serviços, não cria contas, não envia e-mails e não ativa APIs
pagas. O login experimental SQLite/Streamlit não deve ser exposto na internet.

## Componentes já preparados

- `app/afiliados/production_auth.py`: cliente do Supabase Auth para cadastro,
  login, renovação de sessão, recuperação e verificação online em
  `GET /auth/v1/user`. O servidor só reconhece contas com **e-mail
  confirmado**. Não confia no `user_metadata` para determinar plano.
- `infra/supabase/001_affiliate_quota.sql`: migração PostgreSQL, com tabela
  de planos protegida, histórico centralizado e RPCs autorizadas
  por `auth.uid()`.
- `app/afiliados/production_quota.py`: comunicação autenticada com as RPCs.
  A identidade é validada no Supabase Auth em cada operação.
- `app/afiliados/production_generation.py`: barreira do backend que reserva
  cotas, determina marca-d'água e recursos pelo plano consultado no servidor,
  conclui a reserva após sucesso e tenta liberar em caso de falha.
- `app/afiliados/turnstile.py`: verificação do desafio anti-bot no servidor.
  O cadastro público exige Turnstile configurado, não aceita bypass.

## Políticas de vídeo implementadas na migração

| Plano | Regra | Thumbnails | Marca d'água |
| --- | --- | --- | --- |
| Grátis | 1 vídeo concluído a cada 24 horas corridas | Não | Sim |
| Pro | 3 vídeos por dia, calendário de Brasília | Não | Sim |
| Premium | 5 vídeos por dia, calendário de Brasília | Sim | Não |
| Creator | 10 vídeos por dia, calendário de Brasília | Sim | Não |

O Creator pode pedir pacote com 3 vídeos e 9 capas, consumindo 3 cotas. Na
migração inicial, todas as contas começam **Grátis**. Nenhuma tela ou parâmetro
de URL altera o plano: mudanças dependem de processo administrativo confiável
ou, futuramente, de cobrança verificada no servidor.

O orçamento para usuários gratuitos é compartilhado entre todas as contas:
no máximo **12 tentativas em 1 hora** e **40 tentativas em 24 horas**, além de
até **5 tentativas por usuário em 1 hora**. Tentativas fracassadas não iniciam
o cooldown individual de 24 horas, mas contam para os limites de custo. Estes
tetos são iniciais e precisarão de calibragem conforme custo e demanda.

## Ativação futura (somente após testes de implantação)

1. Criar um projeto Supabase na região apropriada e ativar **confirmação
   obrigatória de e-mail** no Auth. Configurar SMTP remetente e URLs
   permitidas. Essa etapa requer ação explícita do responsável.
2. Registrar o domínio HTTPS no Cloudflare Turnstile, obter chave pública
   e segredo do widget, sem publicá-los no GitHub.
3. Revisar e aplicar `001_affiliate_quota.sql` manualmente no **SQL Editor**
   de um projeto de testes. Verificar grants, RLS/isolamento e lock em duas
   sessões concorrentes. **O arquivo ainda não foi executado em Postgres
   real.** A tabela `affiliate_private.subscriptions` nunca deve ser
   acessível à função `authenticated` para alterações diretas.
4. Fornecer, em *variáveis de ambiente* do servidor, sem valores no código:

   - `AFILIADOS_SUPABASE_URL=https://<ref>.supabase.co`
   - `AFILIADOS_SUPABASE_PUBLISHABLE_KEY=<chave publicável>`
   - `AFILIADOS_TURNSTILE_SITE_KEY=<chave pública>`
   - `AFILIADOS_TURNSTILE_SECRET_KEY=<segredo>`
   - `AFILIADOS_TURNSTILE_HOSTNAME=<domínio público>`

5. Implementar o fluxo de sessão e backend assíncrono com **fila de
   processamento e armazenamento durável**. Os adaptadores não estão
   conectados ao Streamlit público nem a endpoints de geração neste commit.
   Não levar a interface local/SQLite para o servidor público.
6. Executar testes end-to-end: cadastro sem e-mail confirmado, CAPTCHA
   inválido/reutilizado, múltiplos cadastros, geração simultânea, mudança de
   dia em Brasília, upgrade/downgrade e revogação de token.
7. Somente então ativar cadastro público. Nenhuma cobrança recorrente está
   implementada e nenhuma API comercial está habilitada.

## Segurança e limites

- O cliente usa a **chave publicável** (`sb_publishable_...` ou JWT legada
  com papel `anon`); chaves `service_role`/`sb_secret_` são recusadas.
- Todo token de acesso é confirmado pelo **Supabase Auth** antes de qualquer
  consulta de cotas. O cliente não aceita identidade ou plano fornecidos
  por campos do navegador.
- As tabelas de controle ficam em `affiliate_private`, sem grant de
  leitura/escrita a `anon`/`authenticated`. As funções RPC em `public`
  usam `SECURITY DEFINER` com `search_path` vazio e derivam o usuário
  de `auth.uid()`.
- **Atenção:** Supabase PostgREST permite a chamada de funções concedidas à
  role `authenticated` diretamente por usuários verificados. Os limites
  de tentativas reduzem custos, mas usuários maliciosos ainda podem ocupar
  a capacidade gratuita com reservas válidas. Antes do lançamento é
  recomendável mover a autorização de início de tarefas para um backend
  com verificação de origem, WAF, rate limits e filas com leases.
- As reservas pendentes expiram após 6 horas na versão beta; workers
  produtivos devem ter timeouts/reconciliação para não descartar processos
  ainda ativos. Armazenamento de vídeos, renovação de pagamentos,
  cancelamentos, tributos, LGPD e backups ainda são pendentes.
- A verificação anti-bot não garante identidade única; múltiplos e-mails
  permanecem possíveis. Limitar o plano Grátis pelo custo global e pelo
  cooldown individual evita promessas de bloqueio absoluto.
