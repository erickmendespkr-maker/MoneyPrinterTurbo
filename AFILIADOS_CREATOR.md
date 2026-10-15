# Afiliados Creator

**Afiliados Creator** é o nome da experiência de produção de vídeos de afiliados desenvolvida neste fork do MoneyPrinterTurbo.

## Objetivo atual

Concluir primeiro uma ferramenta segura para uso próprio: anúncios verticais a partir de fotos reais, roteiros revisados, narração e legendas, com baixo custo por vídeo. Avaliar a viabilidade de comercialização apenas depois de testes de qualidade, estabilidade e custos.

## Estado da implementação

- Fluxo local para dados do produto, roteiro automático básico com edição e aprovação, upload de fotos e áudio, renderização MP4 e exportação JSON.
- Narração automática opcional em português brasileiro por Edge TTS. Requer internet, transmite o texto do roteiro ao serviço de voz e não usa créditos de API paga. É acionada somente por escolha do usuário.
- A montagem de vídeo utiliza fotos fornecidas pelo usuário, sem inventar características ou preços.
- Integrações externas (ChatGPT, Kling e demais APIs) ainda não habilitadas neste fluxo; credenciais ficam para a etapa final.
- Recursos comerciais, assinaturas e cobrança não estão implementados.
- Nome comercial e domínios ainda dependem de verificação formal antes de lançamento público.

## Créditos e licença

Esta implementação deriva do projeto de código aberto [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo). O novo nome não remove a autoria, os avisos de copyright ou as obrigações da licença original. Consulte o arquivo `LICENSE` e a documentação upstream.

## Execução e privacidade

Abra a página **Afiliados** na interface Streamlit. O roteiro e a montagem de fotos funcionam localmente; a opção de narração Edge TTS é uma operação **online** e transmite o texto do roteiro ao serviço da Microsoft. O projeto não baixa automaticamente imagens nem acessa URLs de produtos fornecidas pelo usuário.

O fluxo exige revisão manual das informações comerciais antes de renderizar. Alterar o roteiro ou os dados do produto invalida a aprovação anterior, e modificar as entradas invalida a prévia MP4 anterior.

## Critérios antes de distribuição

- Obter resultados verdes nos testes isolados (Windows/Linux, Python 3.11/3.13) e no teste real de codificação MP4.
- Eliminar os alertas de vulnerabilidades da auditoria de dependências resolvidas pelo `uv.lock`.
- Verificar instalação limpa no computador de destino, incluindo suporte do FFmpeg e narração opcional.
- Conferir manualmente a legibilidade das legendas, enquadramento das fotos, qualidade de voz e chamada para ação.

**Importante:** MoviePy 2.2.1 declara uma restrição de Pillow anterior à versão 12. A resolução `uv` aplica uma substituição explícita para usar Pillow corrigido; instalar as dependências com `pip install -r requirements.txt` não equivale a reproduzir o ambiente `uv.lock`. Não distribuir sem confirmar a compatibilidade em teste real.
