# Demo econômica do AVA

Verificado em 09/09/2026, perfil AWS `default` (root), região `us-east-1`.
A API Free Tier retornou plano PAID ativo e US$ 200 de créditos. A atualização
do saldo não necessariamente reflete imediatamente as chamadas de inferência.

## App Factory funcionando — 09/09/2026

- App: https://d276q5tp5ptm8q.cloudfront.net/console
- Deployment: `bbe7b3ed-6c40-41d7-a68d-bea5b839347b`, status `deployed`.
- CodeBuild: `f4363597-4d74-4509-8a88-9b953f9440d8`, `SUCCEEDED`.
- AgentCore `READY`, modelo efetivo `zai.glm-4.7-flash`.
- Teste real pela interface: `TICKET001`, modo `full`, retornou `account_access`,
  urgência `high`, justificativa e rascunho. Nenhum erro HTTP/JavaScript no teste.
- My Apps lista o app com Open App e View details.
- Aprovação é uma ação demonstrativa local; não envia mensagens nem grava uma
  aprovação durável. O modo completo foi testado; os modos parciais não foram validados.
- Código e UI gerados estão em `applications/fsi_foundry/{use_cases,ui}/demo_support_triage`.
  Os oito exemplos fictícios estão em `data/samples/demo_support_triage`.
- A geração completa levou 352 segundos e usou 1.474.065 tokens de entrada,
  28.385 de saída, em 110 chamadas GLM 4.7/Flash. Esses números são desta
  execução, não o consumo acumulado da conta.
- Correções: diretório de trabalho explícito no Bash; validação de amostras sem
  exigir CUST001; parser JSON no executor; confiança e edição de resposta na UI.
  O gerador produziu `ticket.json`, mas chamou o retriever compartilhado `profile`.
  Copiamos os mesmos dados para `profile.json` no S3 e no repo para alinhar o runtime.
- Os limites artificiais do gerador seguem desativados conforme solicitado.
  Não foi adicionado mecanismo de checkpoints. O pacote gerado foi salvo pelo
  estágio normal de empacotamento do pipeline.
- Validação offline: 29 testes App Factory; compilação Vite e TypeScript da UI.

As seções abaixo preservam o histórico dos testes e das tentativas anteriores.

## Credenciais locais com renovação automática

Execute `python3 demo/start_local.py` em uma sessão Linux com systemd de usuário.
O launcher instala/ativa `ava-aws-credentials.service` e usa o override
`demo/compose.credentials.yaml`. Backend e gateway usam `credential_process`,
com `Expiration`, para renovar credenciais no mesmo cliente AWS. Não são mais
injetadas chaves temporárias fixas nas variáveis de ambiente dos containers.

O serviço executa o AWS CLI do host, valida a conta e fornece credenciais por
um socket Unix privado (diretório 0700, socket 0600). O cache de login fica no
host; os containers recebem somente credenciais temporárias, mantidas em memória.
O serviço inicia com a sessão de usuário e reinicia automaticamente em caso de falha.

- Verificar: `systemctl --user status ava-aws-credentials.service`
- Parar a renovação: `systemctl --user disable --now ava-aws-credentials.service`
- Ao expirar a sessão completa: `aws login --profile default` no host. Os
  containers passam a usar a nova sessão sem precisar reiniciar.
- O AWS login renova credenciais de 15 minutos por até 12 horas; a renovação
  automática não remove o prazo máximo de autenticação imposto pela AWS.
  Fonte: https://docs.aws.amazon.com/sdkref/latest/guide/feature-login-credentials.html
- Usar o launcher para subir/recriar o stack; executar Compose sem o override
  de credenciais volta à configuração genérica do repositório.
- Testes: `python -m pytest demo/test_credentials.py -q`. A renovação também
  foi exercitada em um cliente STS real dentro do backend, forçando a expiração
  dos metadados do SDK; backend e gateway resolveram `RefreshableCredentials`.

## Custo ocioso observado

Inventário em 09/09/2026, us-east-1: nenhum EC2, NAT Gateway ou RDS ativo e
nenhum CodeBuild em execução. Imagem ECR de 187.726.500 bytes (~188 MB);
AgentCore com idle timeout de 900 segundos. A imagem custa aproximadamente
US$ 0,019/mês a US$ 0,10/GB-mês, antes de franquias/créditos.

Estimativa conservadora para esta demo sem chamadas nem novos builds:
US$ 0,01–0,05/dia (US$ 0,30–1,50/mês), incluindo pequena margem para dados/logs.
É uma estimativa de infraestrutura ociosa, não medição da fatura da conta,
nem teto para uso da API pública. Geração de apps, inferências, sessões ativas
(memória inclusive enquanto aguardam) e tráfego são cobrados à parte.

Fontes: https://aws.amazon.com/ecr/pricing/ e
https://aws.amazon.com/bedrock/agentcore/pricing/.

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
  Limite aprovado e atualizado para 1.000.000 tokens, mantendo 80 chamadas
  e 900 segundos de geração. A tentativa seguinte falhou antes de iniciar
  CodeBuild: `ExpiredTokenException` ao ler a submissão no backend local.
  O perfil AWS CLI `default` continua válido; os containers precisam receber
  credenciais renovadas via `python3 demo/start_local.py`. Nenhum novo build
  foi iniciado nessa tentativa.
  CodeBuild terminou STOPPED e o workflow registrou a execução como FAILED.
  Geração completa, deploy AgentCore e UI gerada ainda não foram validados.
- Modelo do runtime corrigido: `BEDROCK_MODEL_ID` com padrão
  `zai.glm-4.7-flash` substitui a variável indefinida `ANTHROPIC_MODEL`.
- Credenciais renovadas e quarta execução iniciada com HTTP 201, já usando
  limite de 1.000.000 tokens. GLM gerou arquivos do agente, mas o teste de
  importação do agent-builder reportou ausência de `pydantic` no CodeBuild.
  O deploy.sh instala boto3 e bibliotecas de documentos, sem instalar o ambiente
  de runtime necessário para validar os imports (Pydantic, settings, Strands,
  entre outros). Build interrompido antes de gastar com etapas posteriores.
  Dependências corrigidas em requirements.txt e preflight.py. Instalação em
  Python 3.11 limpo, pip check, importação da referência e 20 testes passaram.
  Quinta execução confirmou `Reference import OK` no CodeBuild; agent-builder
  concluiu a etapa, mas repetiu muitas leituras/validações. O limite de 1 milhão
  de tokens foi atingido antes da UI: 997.736 de entrada, 17.106 de saída,
  44 chamadas GLM 4.7, 232 segundos. Build e workflow terminaram FAILED.
  Próximo ajuste proposto: reduzir releituras/contexto e verificações redundantes
  antes de repetir, mantendo o limite aprovado. UI, dados e deploy continuam
  pendentes. Nenhum build está ativo.
- Sexta execução com teto de tokens desativado explicitamente (`0`): geração
  passou por código/UI/dados, mas terminou no limite de 80 chamadas. Consumo:
  1.350.794 tokens de entrada + 30.907 de saída, 330 segundos. GLM 4.7 usou
  1.243.929/24.372; Flash usou 106.865/6.535 (entrada/saída). Cinco delegações;
  houve repetição após os limites individuais de etapas. Validação final e
  deploy não concluídos. Build/workflow FAILED; nenhum build ativo. Restauração do teto
  cancelada pelo usuário antes de aplicar. Nova autorização: remover todos os
  limites artificiais do gerador e concluir a demo, corrigindo os bloqueios.
- My Apps filtra apenas deployments App Factory com status `deployed`.
  Por isso permanece vazio; tentativas em andamento/falhas estão em Deployments.
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
