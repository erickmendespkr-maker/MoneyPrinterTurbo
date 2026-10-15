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

## Interface com identidade AC

A página Streamlit usa um cabeçalho azul/roxo com monograma A dentro de C e tipografia Manrope com fallback Arial. O desenho é implementado em SVG inline como aproximação visual do conceito aprovado. Ainda não há arquivo de logotipo final verificado, nem a interface completa do mockup de dashboard; a página permanece um protótipo funcional.

## Dashboard inicial

A interface Streamlit ganhou navegação lateral com Criar anúncio, Meus projetos, Biblioteca, Templates e Planos, além de um resumo do estúdio de criação. Somente a seção Criar anúncio executa o fluxo de geração existente. Meus projetos exibe o rascunho da sessão; Biblioteca e Templates descrevem recursos atuais; Planos informa políticas propostas, sem cobrar nem impor quotas. Não há persistência de histórico nem autenticação neste estágio. O layout não é ainda uma reprodução integral do mockup aprovado.

## Retomada de projetos exportados

A aba **Meus projetos** aceita importar um JSON do Afiliados Creator (versão de esquema 1, até 16 KB). A importação valida URL, campos e roteiro, reconstrói as instruções internas e mantém integrações pagas desabilitadas, mesmo que o arquivo contenha configurações alteradas. Ao importar, volta à tela Criar anúncio e exige nova aprovação antes de renderizar. As fotos, áudios e MP4 não fazem parte do JSON e precisam ser enviados novamente. Não há armazenamento persistente por usuário.

## Persistencia de projetos (backend experimental)

O modulo app/afiliados/storage.py oferece SQLite para salvar, listar, abrir, atualizar e excluir projetos por proprietario. A interface nao usa esse armazenamento porque ainda falta autenticacao confiavel. O identificador do proprietario deve vir da sessao validada pelo servidor. O banco e local, nao nuvem; fotos, audios e videos nao sao persistidos nesta etapa.

## Autenticacao local experimental

O modulo app/afiliados/auth.py implementa cadastro e login local, hashing scrypt com salt aleatorio, tokens de sessao opacos armazenados como hash e logout. Ainda nao esta conectado a interface Streamlit. Antes de habilitar acesso publico sao necessarios HTTPS, limitacao de tentativas, verificacao de e-mail, recuperacao de senha, protecao CSRF, revisao de sessao e testes integrados. Nao confundir este prototipo com autenticacao pronta para producao.

## Teste local com login e projetos

A interface Streamlit agora integra o login experimental e o ProjectStore apenas quando a variavel de ambiente AFILIADOS_LOCAL_ACCOUNTS=1. Por padrao, o login permanece desabilitado. Com a opcao habilitada, o usuario pode cadastrar uma conta local, entrar, salvar o rascunho editado, listar, reabrir e excluir projetos. Os arquivos de imagem, audio e video nao sao persistidos; ao reabrir, envie novamente as midias e revise o roteiro. O banco fica em data/afiliados-auth.sqlite e data/afiliados-projects.sqlite. Uso exclusivamente local, sem exposicao publica. Nao usar este login como autenticacao de producao: faltam rate limiting, verificacao de e-mail, recuperacao de senha e endurecimento das sessoes.

## Testes integrados de contas e projetos

O arquivo test/test_afiliados_auth_storage_integration.py verifica login, ciclo de vida de projetos, isolamento entre contas e expiracao de sessao. A suite deve passar no CI antes de disponibilizar o recurso. Testes automatizados nao substituem a revisao de seguranca para uso publico.

## Biblioteca local de midias

Com AFILIADOS_LOCAL_ACCOUNTS=1, contas de teste podem salvar capas PNG e MP4 gerados, listar, visualizar, baixar e excluir os arquivos na aba Biblioteca. O banco SQLite fica em data/afiliados-media.sqlite e as consultas filtram o proprietario da sessao. O backend limita arquivos a 12 MB (PNG) ou 100 MB (MP4) e 100 arquivos por conta. A verificacao MP4 checa apenas a assinatura do container e nao valida codecs nem conteudo integral. Nao e armazenamento em nuvem nem recurso pronto para acesso publico; faltam isolamento de processamento, backup, limites totais de disco e testes de interface.

## Cotas e deduplicacao de midias

A biblioteca SQLite local limita cada conta a 100 arquivos e 512 MB totais, com limite individual de 12 MB por PNG e 100 MB por MP4. Gravar bytes identicos do mesmo tipo na mesma conta retorna o ID ja existente, sem duplicar armazenamento. A checagem de cota usa transacao SQLite IMMEDIATE para serializar gravacoes. O dashboard exibe uso de espaco e quantidade de arquivos. Esses limites nao substituem cotas de planos comerciais nem backup e monitoramento de disco.

## Variacoes de video locais

O renderizador aceita impacto, beneficio e curiosidade, com posicoes de legenda diferentes e ordem alternativa das fotos quando ha mais de uma. O dashboard permite escolher e gerar uma variacao de cada vez, sem APIs pagas. Ainda nao existe geracao automatica em lote de tres MP4 nem nove capas agrupadas por video; os tres estilos de capa atuais continuam disponiveis separadamente. Todos os videos usam o roteiro revisado e as imagens reais fornecidas.
