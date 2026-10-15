# Afiliados Creator

**Afiliados Creator** é o nome da experiência de produção de vídeos de afiliados desenvolvida neste fork do MoneyPrinterTurbo.

## Objetivo atual

Concluir primeiro uma ferramenta segura para uso próprio: anúncios verticais a partir de fotos reais, roteiros revisados, narração e legendas, com baixo custo por vídeo. Avaliar a viabilidade de comercialização apenas depois de testes de qualidade, estabilidade e custos.

## Estado da implementação

- Fluxo local para dados do produto, roteiro automático básico com edição e aprovação, upload de fotos e áudio, renderização MP4 e exportação JSON.
- Narração automática opcional em português brasileiro por Edge TTS. Requer internet, transmite o texto do roteiro ao serviço de voz e não usa créditos de API paga. É acionada somente por escolha do usuário.
- A montagem de vídeo utiliza fotos fornecidas pelo usuário, sem inventar características ou preços.
- Integrações externas (ChatGPT, Kling e demais APIs) ainda não habilitadas neste fluxo; credenciais ficam para a etapa final.
- Políticas iniciais dos planos implementadas em `app/afiliados/plans.py`: Grátis (1 vídeo/dia), Pro (5 vídeos/dia), Creator (sem limite diário). A persistência de uso, autenticação, cobrança e aplicação segura de cotas no servidor ainda não foram implementadas.\n- Marca-d'água visual padrão aplicada no MP4: branca, pequena, aproximadamente 80% opaca, canto inferior direito. A função de renderização possui uma opção técnica `watermark=False`, que **não deve ser exposta a usuários** antes da autorização do plano Creator ser validada no servidor.\n- Três thumbnails PNG verticais (impacto, benefício e curiosidade) agora são geradas localmente a partir da primeira foto real do produto, com visualização e download no Streamlit. São composições de texto e foto, **não imagens generativas por IA**.\n- Remoção de marca-d'água com autorização do plano, logotipo personalizado, persistência de projetos por usuário e fluxo automático a partir de link ainda exigem implementação e testes.
- Nome comercial e domínios ainda dependem de verificação formal antes de lançamento público.

## Planos previstos\n\n| Plano | Vídeos finalizados por dia | Marca da plataforma | Marca própria |\n| --- | ---: | --- | --- |\n| Grátis | 1 | Obrigatória | Não |\n| Pro | 5 | Obrigatória | Não |\n| Creator | Ilimitado | Opcional | Sim |\n\nA cota deve ser aplicada com contagem transacional por usuário no fuso de Brasília; falhas de renderização não devem consumir uma geração. O plano Creator não dispensa proteção contra abuso, concorrência excessiva ou custos de infraestrutura. A interface atual ainda é uma ferramenta de teste sem login nem cobrança.\n\n## Créditos e licença

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

## Importação experimental de dados do produto

A interface Streamlit permite enviar um arquivo HTML salvo da página do produto (até 2 MB). O extrator local lê JSON-LD do tipo Product e metadados OpenGraph, preenche nome e descrição para revisão e não faz solicitações de rede. A URL de imagem extraída é apenas informativa: imagens não são baixadas automaticamente. Ainda não há importação automática somente por link; sites podem bloquear acesso ou omitir metadados, e o usuário deve validar todas as informações.

## Sugestão offline a partir do link

A interface agora permite colar um URL HTTPS de loja suportada e sugerir um nome a partir do slug da URL. Isso não faz requisição HTTP nem comprova nome, preço ou atributos do produto. URLs com apenas identificadores podem não gerar sugestão. A importação completa somente por link permanece pendente de integração segura e autorização dos provedores.

## Identidade visual aprovada

Marca: **Afiliados Creator**. Símbolo escolhido: monograma A dentro de C (conceito nº 3). A marca-d'água padrão dos vídeos e capas é **monocromática branca, com 80% de transparência (20% de opacidade, alpha 51/255)**, pequena, no canto inferior direito, acompanhada do nome Afiliados Creator. O código atual desenha uma aproximação vetorial desse conceito com Pillow; ainda será necessário produzir e revisar o ativo vetorial definitivo antes de afirmar correspondência pixel a pixel com a arte aprovada. A marca-d'água permanece obrigatória no protótipo para os planos Grátis e Pro; personalização do Creator exige autenticação e validação de plano no servidor antes de disponibilizar.
