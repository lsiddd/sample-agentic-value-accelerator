# Pedidos de demonstração enviados pelo App Factory

## Proposal Review — 09/09/2026

`proposal-review.json` registra os campos preenchidos na interface local, pelas
cinco etapas do formulário, seguido de Submit & Review e Generate & Deploy.
A submissão e o início do deployment ocorreram sem erros de JavaScript.

- Catálogo: `AO01`
- Submissão: `54e46bdb-c77a-48dd-862c-694e22c390e1`
- Deployment: `051dccbc-00cf-4b54-9ed2-bf57e08581a1`
- CodeBuild: `51862e06-c1da-48f8-945b-51f314023570`

Resultado: não concluiu autonomamente. Gerou código dos agentes e três arquivos
`RFQ001/profile.json`, `RFQ002/profile.json` e `RFQ003/profile.json`, mas passou a
repetir o mesmo comando de importação. Foram observadas 59 checagens de import
entre 18:08:31 e 18:11:40 UTC, sem avanço para a UI. O build foi interrompido
manualmente (`STOPPED`) para encerrar o ciclo de consumo. Nenhum arquivo da
execução foi corrigido manualmente. Não houve nova execução nesta tentativa.

A fase de empacotamento dos fontes gerados e o Terraform do novo app não foram
alcançados. O app de tickets previamente validado continua disponível. Esse teste
mostra que o fluxo pela interface inicia corretamente, mas a conclusão autônoma
do gerador GLM ainda não é confiável para todo pedido.
