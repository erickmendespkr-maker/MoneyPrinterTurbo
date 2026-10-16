# MoneyPrinterTurbo Afiliados — segurança antes das integrações

Este fork ainda não foi aprovado para uso com credenciais reais.

## Regras de liberação
- Não adicionar chaves da OpenAI, Kling, Shopee ou Instagram ao repositório.
- Executar localmente e restringir acesso à API e à interface.
- Exigir autenticação nas rotas que criam tarefas ou leem arquivos.
- Remover permissões excessivas no Docker e revisar volumes.
- Auditar dependências, workflows, downloads e chamadas externas.
- Testar em ambiente isolado, sem credenciais nem pagamentos.
- Solicitar aprovação explícita antes de usar APIs pagas.

## Achados iniciais (revisão estática parcial)
- `config.example.toml` permite `api_key = ""` e define `listen_host = "0.0.0.0"`.
- `Dockerfile` contém `chmod 777 /MoneyPrinterTurbo`.
- `docker-compose.yml` monta todo o repositório no contêiner.
- `.gitignore` exclui `config.toml` e `.env`, mas isso não impede o vazamento de arquivos já versionados.
- Existem controles de caminhos e verificação TLS em partes do código.

Estes achados não comprovam malware nem substituem análise dinâmica ou varredura completa de dependências.

## Correções publicadas nesta branch
- API exige chave não vazia e falha ao iniciar sem ela; validação de requisições falha fechada.
- Exemplo de configuração limita o host da API a 127.0.0.1; Docker mantém escuta interna compatível com publicação local.
- Docker executa como usuário não privilegiado, com no-new-privileges e capacidades removidas.
- GitHub Actions ganhou análise de segredos, sintaxe Python e auditoria de dependências.
- Foram adicionados testes básicos de autenticação.

## Pendências antes de conectar contas reais
- Confirmar que os checks do GitHub Actions foram executados e passaram (nenhuma execução foi confirmada nesta revisão).
- Executar testes funcionais da API, WebUI, uploads, Docker e geração de vídeo.
- Inspecionar todos os downloads e comunicações externas; revisar dependências transitivas e ações de terceiros.
- A WebUI Streamlit não utiliza a autenticação da API; deve continuar restrita ao loopback.
- O Docker Compose ainda monta o diretório do projeto; reduzir a montagem após testar compatibilidade.
- Revisar possíveis problemas de SSRF, vazamento em logs e upload de arquivos.
- Não há certificação de ausência de malware: a análise continua parcial.
