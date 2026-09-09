# Demo econômica do AVA

Verificado em 09/09/2026, perfil AWS `default` (root), região `us-east-1`.
A API Free Tier retornou plano PAID ativo e US$ 200 de créditos. A atualização
do saldo não necessariamente reflete imediatamente as chamadas de inferência.

## Modelos e alterações

- Nova Lite é o padrão em 10 templates, incluindo os configs Strands/LangGraph,
  os parâmetros do catálogo e os exemplos/Terraform correspondentes.
- GLM 4.7 Flash é o padrão compartilhado de FSI Foundry e de seu runtime Terraform.
  `BEDROCK_MODEL_ID` pode substituir esse padrão; casos com modelos explicitamente
  fixados ainda precisam de revisão individual.
- O gateway local e seu catálogo padrão oferecem Nova Lite e GLM Flash;
  não há fallback automático para Claude/GPT nem necessidade de chave Mantle.
- Corrigidos dois erros de inicialização: retorno inválido no gerador assíncrono
  de conversa e colisão dos nomes das ferramentas do supervisor.

Preços Bedrock Standard em us-east-1, USD por milhão de tokens:

| Modelo | Entrada | Saída | Uso proposto |
|---|---:|---:|---|
| Nova Lite | 0,06 | 0,24 | Conversa e ferramentas |
| GLM 4.7 Flash | 0,07 | 0,40 | Código e agentes econômicos |
| GLM 4.7 | 0,60 | 2,20 | Opção manual para tarefas mais exigentes |

Fonte: https://aws.amazon.com/bedrock/pricing/
Preços variam por região/tier. Os preços de catálogo não são um limite de gasto.

## Execuções comprovadas

| Teste | Resultado |
|---|---|
| GLM Flash: código Python pela API Converse | Sucesso; função de soma; 53 tokens; latência reportada 225 ms |
| Nova Lite, GLM Flash e GLM 4.7: solicitação de ferramenta | Os três retornaram `calculator` com expressão válida |
| Template Conversational Assistant, Nova Lite e GLM Flash | Ferramenta executada: 42 × 17 = 714; contexto preservado: +6 = 720 |
| Template Workflow Pipeline, GLM Flash | Classificação, extração, validação e resumo de fatura fictícia; quatro etapas em 7,36 s |
| Template Supervisor Specialists, GLM Flash | Delegou ao `analyst`; 3 × USD 20 = USD 60 |
| Classe base StrandsAgent do FSI Foundry, GLM Flash | Inferência real respondeu OK com a configuração compartilhada padrão |

Os testes dos templates rodaram o código Python local e inferência real no
Bedrock, incluindo streaming do SDK. Não constituem benchmark de qualidade,
teste HTTP do servidor, validação de isolamento entre usuários ou deploy AgentCore.

## Outras funcionalidades: investigação da conta

19 consultas AWS passaram. As consultas regionais foram em us-east-1.
Listar recursos comprova acesso à API de consulta, não permissão de criação,
capacidade de quotas ou funcionamento de uma aplicação implantada.

| Funcionalidade | Evidência e dependência restante |
|---|---|
| S3 e DynamoDB | APIs acessíveis; inventário inicial vazio. Tabela de Guardrails criada posteriormente; faltam outros dados e persistência |
| ECS, ECR, CodeBuild, Step Functions, CloudFormation | APIs acessíveis; nenhuma infraestrutura AVA encontrada; deploy pela UI ainda depende de provisionamento |
| Cognito | API acessível; nenhum user pool; login real ainda não configurado |
| Guardrails e Knowledge Bases | APIs acessíveis; nenhuma configuração encontrada; aplicação de filtros/RAG ainda não testada |
| AgentCore Runtime, Memory, Gateway e Policy | APIs acessíveis; listas vazias; execução hospedada, memória persistente e políticas ainda não testadas |
| Agent Registry | Consulta acessível; primeira página vazia com token de continuação; não foi feito inventário completo |
| CloudWatch e VPC | Consulta de logs vazia; uma VPC encontrada; observabilidade ainda precisa de agentes implantados |
| App Factory | Adaptado para Bedrock Converse com GLM 4.7/Flash; 20 testes e smoke real de geração/delegação passaram. Geração completa de app FSI e deploy ainda não validados |
| Govern/FinOps/compliance | O README do repo identifica algumas superfícies como dados de demonstração; não confundir UI preenchida com integração real |
| LiteLLM local | Compose ativo; Nova Lite e GLM Flash responderam via gateway. Login administrativo e listagem de modelos passaram no navegador; chaves virtuais ainda não testadas |
| Langfuse | Ainda não iniciado nem validado |

### Validação da interface local — 09/09/2026

- Fonte Geist corrigida; página inicial sem erros de rede ou JavaScript.
- Gateway reconhecido com `LLM_GATEWAY_ADMIN_URL=http://localhost:4000/ui/`.
  Administrador abre em nova aba, pois o LiteLLM bloqueia iframes.
  Login local e Models + Endpoints validados no Chromium, sem erros.
- Formulário inicial do App Factory abre; geração completa pela interface ainda pendente.
- Tabela `fsi-control-plane-guardrails` criada em `us-east-1`, modo
  `PAY_PER_REQUEST`, chaves string `pk`/`sk`, tag `Project=ava-demo`.
  Listagem voltou a HTTP 200. Erro 500 simulado no navegador mostra alerta;
  botão Try again recupera a listagem real.
- Memory abre sem erros; criação e persistência ainda não testadas.
- Knowledge: tabela `fsi-control-plane-knowledge` criada com as mesmas chaves,
  modo de cobrança e tag da tabela de Guardrails. API HTTP 200; alerta de erro
  e recuperação pelo botão Try again validados no navegador.
- Guardrail real `ava-demo-word-filter` criado pela API do app: status active.
  ApplyGuardrail com versão DRAFT bloqueou `AVA_DEMO_BLOCKED`
  (`GUARDRAIL_INTERVENED`) e liberou uma frase comum (`NONE`).
  Isso valida filtro de palavras; PII, filtros de conteúdo e integração no gateway
  ainda não foram testados.
- App Factory: tabela `fsi-control-plane-app-factory` criada em modo
  `PAY_PER_REQUEST`, chaves string `pk`/`sk`, tag `Project=ava-demo`.
  Submissão fictícia `demo-support-triage` salva pela API (HTTP 201), catálogo
  `AS01`; consultas de detalhe e lista passaram com todos os campos preservados.
- Pipeline mínimo provisionado em `demo/pipeline`: 23 recursos Terraform,
  incluindo CodeBuild, Step Functions, IAM, duas tabelas e dois buckets.
  Backend conectado via `STATE_MACHINE_ARN`; deploy de `AS01` retornou HTTP 201.
  Primeira execução chegou ao gerador GLM 4.7 e começou a ler referências.
  Build interrompido durante a geração, antes de validar o app completo:
  a API mostrava `pending` apesar do estado MarkBuilding ter concluído.
  Causa identificada: após iniciar Step Functions, a rota fazia `put_item` do
  objeto antigo para salvar `execution_arn`, sobrescrevendo o status atualizado.
  Corrigido para atualizar somente o ARN; teste de concorrência passou.
  Segunda execução preservou status/build ID, mas revelou erro no pipeline mínimo:
  ele gravava `building`, ausente do enum DeploymentStatus, causando HTTP 500.
  Corrigido para `deploying`; todos os valores do pipeline conferidos contra o
  enum. Terceira execução: API e tela de deployment funcionaram sem erros.
  A geração terminou ao atingir o limite conservador de 150.000 tokens:
  153.902 tokens de entrada + 9.373 de saída, 11 chamadas GLM 4.7, 98 segundos
  de geração. O limite é verificado entre chamadas, permitindo ultrapassagem
  pela última resposta. Agent-builder escreveu arquivos, mas UI/dados/validação
  e deploy não foram concluídos. CodeBuild e workflow encerraram FAILED.
  Não há build ativo; próxima decisão é ajustar o limite de geração.
  CodeBuild terminou STOPPED e o workflow registrou a execução como FAILED.
  Geração completa, deploy AgentCore e UI gerada ainda não foram validados.
- Modelo do runtime corrigido: `BEDROCK_MODEL_ID` com padrão
  `zai.glm-4.7-flash` substitui a variável indefinida `ANTHROPIC_MODEL`.
- Build frontend e 22 testes offline (App Factory + templates) passaram.

Também foi identificado que as políticas IAM de alguns templates constroem
`foundation-model/${var.model_id}` mesmo para IDs `us.*` de inference profiles.
Antes de deploy com Nova cross-region, ajustar essas políticas para o profile
e os modelos de destino. As execuções locais com root não validam a role do runtime.
Recursos AWS criados até esta etapa: tabelas DynamoDB de Guardrails, Knowledge
e App Factory, o Bedrock Guardrail `ava-demo-word-filter`, os recursos do
pipeline descritos em `pipeline/README.md` e um bucket de arquivos do primeiro
deploy, todos em `us-east-1`.

## Reproduzir

Na raiz do repo, com a sessão AWS padrão ativa:

```bash
uv venv /tmp/ava-demo-venv
uv pip install --python /tmp/ava-demo-venv/bin/python \
  'boto3>=1.43.0' 'botocore[crt]' 'strands-agents>=1.38.0,<2' \
  'bedrock-agentcore>=1.9.0,<2' pydantic-settings pyyaml structlog pytest

# Consultas e três chamadas pequenas de ferramentas (há cobrança de tokens).
/tmp/ava-demo-venv/bin/python demo/check_aws.py

# Exemplos reais, com dados fictícios.
/tmp/ava-demo-venv/bin/python demo/run_agent.py
/tmp/ava-demo-venv/bin/python demo/run_agent.py --model zai.glm-4.7-flash
/tmp/ava-demo-venv/bin/python demo/run_agent.py --template workflow-pipeline --model zai.glm-4.7-flash
/tmp/ava-demo-venv/bin/python demo/run_agent.py --template supervisor-specialists --model zai.glm-4.7-flash

# Regressões offline.
/tmp/ava-demo-venv/bin/python -m pytest demo/test_templates.py -q
```

O runner limita cada resposta a 768 tokens. Esse limite é por chamada, não por
execução inteira. Começar pela demo local evita o custo fixo de toda a plataforma.
