# Errata verificável do dossiê — 16/10/2026

**Este registro complementa o dossiê original, sem apagar decisões históricas.** Inspeção direta do HEAD de `feature/afiliados` e definições SQL do Supabase real. Não representa homologação de produção.

## Erros e divergências confirmados

1. **Cooldown gratuito:** `public.create_video_generation` atualmente escreve `next_free_generation_at = now()+24h` **na reserva**, em vez de iniciar após conclusão. `public.worker_finish_generation` não corrige isso. **Erro confirmado; ainda pendente no banco.**
2. **Planos:** `app/afiliados/plans.py` define `gratis/pro/premium/creator`; o banco possui `free/pro/creator`. Premium não está cadastrado no banco. **Pendente no banco.**
3. **Cotas pagas:** a RPC atual somente faz verificação de cooldown do Grátis; não limita 3/5/10 vídeos por dia para Pro/Premium/Creator. **Falha de autorização/controle de custo confirmada.**
4. **Geração por imagens:** o worker da trilha real usa `build_video_params`, que não recebe imagens de produto; não afirmar que fotos enviadas já são usadas.
5. **Link Shopee:** validar sintaxe HTTPS não prova resolução de URL curta ou obtenção de metadados.
6. **Trilha A x Trilha B:** migrations `infra/supabase/001–003` não equivalem ao esquema real. Não aplicar diretamente.
7. **Interface:** Streamlit em `webui/pages/90_Afiliados.py` existe, mas não comprova fidelidade às imagens originais enviadas.
8. **Preço anual:** `pricing.py` calcula dez mensalidades e entrega doze meses. Valores corretos: Grátis R$0; Pro R$69,90/R$699; Premium R$119,90/R$1.199; Creator R$199,90/R$1.999.
9. **Estado de testes:** testes de contrato/mocks não provam renderização fim-a-fim, cobrança, segurança RLS sob contas reais ou implantação pública.
10. **Proteção antifraude:** limites globais do protótipo não estão demonstrados no Supabase real. Não tratar como ativos.

## Correções de código efetuadas
- `app/afiliados/plans.py`: `normalize_plan_code('free') == 'gratis'` para compatibilidade **sem conceder direitos** pelo cliente.
- `app/afiliados/pricing.py`: usa a mesma normalização; preços permanecem inalterados.
- `tests/test_afiliados_plan_reconciliation.py`: testes de quatro planos, valores, direitos e códigos inválidos.
- Workflow `afiliados-checks.yml`: passa a executar esse teste e acompanhar alterações dos módulos comerciais.

## Restrições para a próxima migração
Não corrigir apenas o texto do dossiê: é preciso migrar RPCs do Supabase em transação, sob testes de concorrência e falha. A reserva deve impedir jobs paralelos; o cooldown só deve ser gravado na conclusão bem-sucedida; uma falha deve liberar a reserva sem consumir 24h. Planos pagos exigem contagem atômica por dia em `America/Sao_Paulo` e verificação server-side de direitos. Não executar migração parcialmente especificada nem lançar pagamentos.

## Estado desta errata
**Código de normalização e testes: alterados no GitHub.** **Banco de dados: não alterado.** **MP4 real: não testado.** **CI do novo HEAD: consultar antes de declarar aprovado.**
