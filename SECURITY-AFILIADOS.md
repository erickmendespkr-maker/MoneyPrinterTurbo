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
