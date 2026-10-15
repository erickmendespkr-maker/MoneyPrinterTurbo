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

1. **Em validação:** o uv usa override de Pillow >=12.3.0 apesar da restrição de metadados de MoviePy 2.2.1. Esse override não altera os metadados de MoviePy e não torna o `pip install -r requirements.txt` compatível com Pillow 12. É obrigatório verificar o lock e executar integração real; o bloqueio só pode ser encerrado depois desses resultados.
2. Executar e aprovar testes Python 3.11, Python 3.13 e Windows em ambiente reproduzível.
3. Executar auditoria de dependências e varredura de segredos; analisar os relatórios reais.
4. Fazer um teste end-to-end de MP4 9:16 com imagem real e outro com narração, inspecionando áudio, legibilidade e duração.
5. Antes de comercializar, adicionar isolamento entre usuários, limites de uso, política de privacidade e gestão segura de credenciais.

**Conclusão:** ainda **não aprovado** para produção. Este documento registra evidências e pendências, não substitui relatórios automatizados.

## Mitigação em andamento (2026-10-15)

- `pyproject.toml` inclui `[tool.uv].override-dependencies = ["pillow>=12.3.0,<13"]`. Isso contorna apenas a restrição de resolução do MoviePy; **não comprova compatibilidade de execução**.
- A matriz isolada instala Pillow 12.3.0 e executa os testes do módulo; a auditoria deve verificar a instalação final.
- O arquivo legado `requirements.txt` e o `uv.lock` devem ser revisados antes de distribuição. Não anunciar vulnerabilidades resolvidas sem resultado da auditoria e verificação de versões instaladas.

## Evidência do lock (2026-10-15)

- Inspeção direta de `uv.lock` na branch `feature/afiliados`: entrada `pillow` com versão **12.3.0** e manifesto de override `>=12.3.0,<13` presentes.
- O bloqueio de **lock não atualizado** está encerrado. Permanecem pendentes auditoria de dependências com resultado verde e testes de renderização de MP4 com a combinação MoviePy/Pillow, inclusive no Windows.
- A execução de CI não deve ser presumida como aprovada enquanto os jobs estiverem em fila.

## Teste de execução local independente (2026-10-15)

- Em ambiente Linux de validação, `moviepy 2.2.1` com `Pillow 12.3.0` gerou um MP4 real H.264, 720x1280, a partir de três imagens e legendas desenhadas via Pillow; arquivo de saída de 19.401 bytes. Também passou um teste simples com uma imagem.
- **Limites:** não foi execução da suíte do repositório, nem teste com narração/Windows, nem auditoria de todas as dependências. O clone do GitHub falhou por ausência de DNS no ambiente de validação. Os metadados do MoviePy continuam declarando `pillow<12.0`, portanto o instalador pip legado continua inconsistente.
