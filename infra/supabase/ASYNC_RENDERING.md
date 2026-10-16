# Afiliados Creator — fila e arquivos privados (beta técnico)

**Status:** código e migrações preparados na branch de desenvolvimento.
**Nenhuma migração foi aplicada, nenhuma API paga foi ativada, nenhum
servidor de vídeo foi iniciado.** Esta documentação não autoriza um
lançamento público.

## Como funciona

```text
Usuário autenticado (e-mail confirmado)
         |
         v
API confiável: valida fotos/roteiro e consulta plano/cota
         |
         +--> Upload privado: {user_uuid}/{job_uuid}/input.zip
         |
         +--> RPC affiliate_enqueue_job (transação de cota + fila)
                      |
                      v
                Fila PostgreSQL
                      |
                 Worker autorizado
                      |
          Claim + lease de 20min + heartbeat
                      |
           Download privado + render local
                      |
       Upload privado: output.mp4 ou output.zip
                      |
              Worker_finish atômico
                      |
             Status "completed" + cota
                      |
          Link assinado com expiração de 60s
```

O usuário não possui autorização para usar as RPCs de conclusão ou
liberação de cotas. Só o trabalhador com credenciais `service_role` as
executa. Um trabalho com falha **não inicia** o cooldown do plano Grátis.
Um trabalho concluído inicia as **24 horas corridas** a partir da
conclusão do arquivo.

## Arquivos preparados

- `infra/supabase/001_affiliate_quota.sql`: cotas, preços/entitlements
  e proteção da identidade (etapa anterior).
- `infra/supabase/002_affiliate_jobs.sql`: fila e RPCs de trabalho;
  revoga as RPCs antigas de conclusão e de reserva da role
  `authenticated`, vinculando execução ao trabalhador com lease.
- `infra/supabase/003_affiliate_private_storage.sql`: bucket privado
  `afiliados-private`, sem políticas de acesso direto para navegador.
- `app/afiliados/render_inputs.py`: pacote ZIP limitado, com arquivos
  esperados, tamanhos, roteiro e imagens; não inclui plano nem dados
  de permissão do usuário.
- `app/afiliados/production_jobs.py`: recebe solicitação já autenticada,
  faz preflight da cota, envia arquivo ao armazenamento e coloca na fila.
- `app/afiliados/private_object_storage.py`: acesso ao bucket privado,
  URLs assinadas de curta duração e caminhos isolados por usuário.
- `app/afiliados/worker_queue.py`: claim, heartbeat, sucesso e falha
  autorizados exclusivamente para trabalhadores.
- `app/afiliados/render_worker.py`: processa **um trabalho de cada vez**,
  usa a marca-d'água determinada pelo servidor e efetiva cota somente
  após a gravação da saída.

## Cotas e segurança

| Plano | Cota | Marca-d'água | Pacote Creator |
| --- | --- | --- | --- |
| Grátis | 1 vídeo a cada 24 horas corridas | Sim | Não |
| Pro | 3 vídeos/dia (Brasília) | Sim | Não |
| Premium | 5 vídeos/dia (Brasília) | Não | Não |
| Creator | 10 vídeos/dia (Brasília) | Não | 3 vídeos + 9 capas |

Um pacote Creator consome 3 unidades. Um trabalho individual só
consome 1 após arquivo válido e upload concluído. As filas impedem
solicitações simultâneas de burlarem o limite transacional. O servidor
permite no máximo 2 trabalhos pendentes por conta e 100 globalmente
na migração inicial. O plano Grátis mantém tetos de 5 tentativas por
conta/hora, 12 globais/hora e 40 globais em 24 horas.

**Isolamento:** o acesso de leitura ao job é checado com `auth.uid()`
e o link de download é assinado pelo backend somente após confirmação
de status do trabalho e identidade. Credenciais `service_role` ficam
exclusivamente no backend/worker, nunca no navegador, na configuração
pública do Streamlit ou nos repositórios. Auditar as políticas globais
de `storage.objects` antes de utilizar um projeto Supabase compartilhado.

## Configuração futura — somente em projeto de testes

1. Configurar Supabase Auth e Turnstile conforme `README.md` deste
   diretório. Exigir confirmação de e-mail e URLs permitidas.
2. Revisar e aplicar **na ordem** 001, 002 e 003 no SQL Editor.
   Conceder EXECUTE somente aos papéis definidos. Testar que um usuário
   normal **não consegue** chamar `affiliate_complete_videos`,
   `affiliate_release_videos` nem as RPCs de trabalhador.
3. Configurar variáveis em ambiente privado:
   `AFILIADOS_SUPABASE_URL`,
   `AFILIADOS_SUPABASE_PUBLISHABLE_KEY`,
   `AFILIADOS_SUPABASE_SERVICE_ROLE_KEY` (JWT legado com
   role `service_role`),
   `AFILIADOS_TURNSTILE_SITE_KEY`,
   `AFILIADOS_TURNSTILE_SECRET_KEY` e
   `AFILIADOS_TURNSTILE_HOSTNAME`.
4. Testar a função de envio do backend (não está publicada como
   endpoint HTTP). Verificar no Storage que o input é privado e
   pertence ao dono autenticado.
5. Depois da aprovação da infraestrutura e dos testes, iniciar um
   único trabalhador opt-in, por exemplo:
   `AFILIADOS_WORKER_ENABLED=1 python -m app.afiliados.render_worker`.
   Sem a variável, o comando recusa iniciar.
6. Usar a API confiável para consultar status e assinar links por
   poucos segundos. O status público nunca devolve a chave privada
   do objeto. Não ativar API paga de imagens/narração nesta fase.

## Pendências para lançamento

- **Teste real do SQL com Postgres/Supabase**, inclusive concorrência
  com várias conexões, leases e permissões de worker.
- **API HTTP pública autenticada** com limites de upload, orçamento
  global, validação de origem/CSRF conforme o modelo de sessão e WAF.
  O código desta etapa é uma biblioteca de backend, não um endpoint.
- **Política de retenção e limpeza** de inputs antigos, outputs
  expirados, jobs abandonados e objetos órfãos. Definir prazos com
  transparência para evitar custo ilimitado de armazenamento.
- Worker dedicado, com RAM suficiente para pacote de até 8 fotos
  (12 MB cada) e áudio de até 25 MB, além de MP4/ZIP de saída.
  Há limite de 100 MB por MP4, 350 MB por pacote, e limite máximo de
  armazenamento também imposto pelo plano do fornecedor; validar
  o limite real da conta antes de disponibilizar o Creator.
- Gerenciar longos jobs: a lease tem 20 minutos, com heartbeat a cada
  120 segundos e expiração total de reserva em 6 horas. Timeout
  de processamento, reinício automático de processos e monitoração
  precisam de testes com FFmpeg real. A migração permite até 3
  tentativas de claim antes de encerrar a tarefa.
- **Cobrança e reconciliação de assinatura** não estão integradas.
  Nenhuma alteração de plano deve partir de parâmetros de navegador.
- Estratégia para evitar que uma pessoa crie várias contas. O CAPTCHA
  reduz automação, não prova identidade única.
- **Teste de recuperação após falha**: execução interrompida antes
  ou depois do upload, link assinado expirado, perda de conectividade,
  cobrança expirada, arquivo incompatível, saída corrompida.

Os testes unitários e estáticos no GitHub não equivalem a um teste
completo de produção. **Não implantar para clientes sem a validação
e o hardening acima.**

## Acompanhamento e custo por geração (preparado)

A função `public.affiliate_my_jobs(p_limit)` lista somente os últimos
trabalhos do usuário autenticado, com limite de 20 resultados e sem expor
chaves de objetos, tokens ou credenciais. A interface beta utiliza essa
listagem para exibir o andamento e atualizar os dados sob demanda.
**A interface ainda não envia solicitações de vídeo em produção.**

Ao concluir um trabalho, o trabalhador armazena `worker_wall_ms`
(duração de execução medida no trabalhador) e `output_bytes` (tamanho
da saída). Esses números são confirmados na mesma transação que atualiza
a cota; não são aceitos do navegador. Os dados são indicadores de
capacidade, não uma fatura de infraestrutura nem medição precisa de CPU.

Um arquivo de consultas somente para administradores,
`ADMIN_METRICS.sql`, calcula média de tempo por trabalho, quantidade de
vídeos efetivamente concluídos, tamanho total dos arquivos e taxa de
falhas. Para estimar o custo por vídeo, será necessário acrescentar
o preço real do servidor, créditos de IA, transferências, retenção,
impostos e tarifas do gateway. O custo operacional final não deve
ser inferido apenas pelos segundos de renderização.

A rota de **leitura do bucket privado** é
`GET /storage/v1/object/authenticated/<bucket>/<arquivo>`, com a
autorização do serviço; uploads continuam na rota
`POST /storage/v1/object/<bucket>/<arquivo>`.

Para testar num ambiente real, precisamos de um projeto Supabase de
desenvolvimento escolhido pelo proprietário e credenciais configuradas
apenas em segredo de servidor. Não reutilizar automaticamente o banco
de outros aplicativos.
