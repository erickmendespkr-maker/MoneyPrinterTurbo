# Afiliados Creator — validação e auditoria técnica

Data: 2026-10-15. Escopo: branch `feature/afiliados`, sem publicação nem credenciais de serviços pagos.

## Resultados verificáveis

- **GitHub Actions:** os jobs `CI` (Python 3.11, Python 3.13 e Windows) e `Afiliados security checks` estavam **queued**, não aprovados, na última consulta. Não considerar a suíte validada até obter resultados de execução.
- **Conflito de dependências confirmado por metadados instalados:** `moviepy==2.2.1` declara `pillow>=9.2.0,<12.0`. A instalação local de `Pillow==12.3.0` causa erro em `pip check`. Portanto, forçar Pillow 12 com MoviePy 2.2.1 **não** é uma correção segura.
- **Risco de vulnerabilidades:** versões anteriores do Pillow foram sinalizadas na auditoria anterior. O inventário completo de CVEs e a versão corrigida precisam ser confirmados por um scanner executado com as dependências resolvidas; não declarar 35 vulnerabilidades como achado atual sem relatório reproduzível.
- **Custos externos:** criação de roteiro básico e montagem de MP4 são locais. Edge TTS é opcional e envia texto a um serviço online; ChatGPT e Kling não estão habilitados no fluxo.
- **Proteções de entrada:** links HTTPS em domínios permitidos, sem credenciais nem portas alternativas; limite de tamanho de imagem e áudio; tipos de voz e duração validados. Links não são baixados pelo backend deste módulo.
- **Limitação funcional:** legendas são divididas entre fotos, não sincronizadas com a narração; textos extensos podem ser visualmente truncados.

## Bloqueios para lançamento

1. Resolver o par MoviePy/Pillow com versões oficialmente compatíveis e auditadas, **ou** isolar/substituir o renderizador para evitar a dependência vulnerável, sem quebrar o restante do MoneyPrinterTurbo.
2. Executar e aprovar testes Python 3.11, Python 3.13 e Windows em ambiente reproduzível.
3. Executar auditoria de dependências e varredura de segredos; analisar os relatórios reais.
4. Fazer um teste end-to-end de MP4 9:16 com imagem real e outro com narração, inspecionando áudio, legibilidade e duração.
5. Antes de comercializar, adicionar isolamento entre usuários, limites de uso, política de privacidade e gestão segura de credenciais.

**Conclusão:** ainda **não aprovado** para produção. Este documento registra evidências e pendências, não substitui relatórios automatizados.
