# Minimal App Factory demo pipeline

This Terraform root connects the local control plane to AWS CodeBuild through
Step Functions. It reuses the repository's CodeBuild and state backend modules.
It does not provision the full control plane (ECS, RDS, VPC, Cognito or Langfuse).

Resources: deployments table, state lock table, private versioned state/buildspec
buckets, CodeBuild project, log group, Step Functions state machine and IAM roles.
The CodeBuild role retains the repository module's broad IaC provisioning
permissions, needed by generated deployments; this is a dedicated demo pipeline.

Limits: one concurrent build, 30-minute CodeBuild timeout, 40-minute workflow
limit, 80 model calls and 150,000 aggregate tokens for generation. Token limits
are checked between model calls and are not a dollar spending cap.

From the repository root, with the authorized `default` AWS session:

```bash
python3 demo/aws_exec.py terraform -chdir=demo/pipeline init
python3 demo/aws_exec.py terraform -chdir=demo/pipeline plan -out=demo.tfplan
python3 demo/aws_exec.py terraform -chdir=demo/pipeline apply demo.tfplan
python3 demo/start_local.py
```

`aws_exec.py` validates the demo account and resolves AWS CLI login credentials
in memory. Terraform state and plans stay local and are ignored by Git. Preserve
that state for teardown. `start_local.py` reads the state machine output and
passes it to the local backend. The app-generated runtime uses GLM Flash;
code generation uses GLM 4.7, with Flash for data/documentation.

A failed CodeBuild marks the deployment failed. Build IDs are stored for the
existing log viewer; CodeBuild writes generated outputs to the deployment table.
Step Functions execution history records the orchestration details.

Cleanup is separate from deployment: first stop active builds/executions and
remove generated applications using their own Terraform states, then destroy
this root. This root does not own the previously created Guardrails, Knowledge,
App Factory tables, the demo Guardrail, or per-deployment archive buckets. The
versioned state bucket must be emptied only after preserving/removing application
states; Terraform will not silently delete a non-empty state bucket.
