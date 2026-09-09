"""Read-only AWS checks plus tiny, billable model/tool-use probes.

Run with the default profile; no cloud resources are created.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config

REGION = "us-east-1"
SESSION = boto3.Session(profile_name="default", region_name=REGION)
CONFIG = Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 0})

CHECKS = [
    ("sts", "get_caller_identity", {}),
    ("freetier", "get_account_plan_state", {}),
    ("s3", "list_buckets", {}),
    ("dynamodb", "list_tables", {}),
    ("ecs", "list_clusters", {}),
    ("ecr", "describe_repositories", {}),
    ("codebuild", "list_projects", {}),
    ("stepfunctions", "list_state_machines", {}),
    ("cloudformation", "describe_stacks", {}),
    ("cognito-idp", "list_user_pools", {"MaxResults": 10}),
    ("bedrock", "list_guardrails", {}),
    ("bedrock-agent", "list_knowledge_bases", {}),
    ("bedrock-agentcore-control", "list_agent_runtimes", {}),
    ("bedrock-agentcore-control", "list_memories", {}),
    ("bedrock-agentcore-control", "list_gateways", {}),
    ("bedrock-agentcore-control", "list_policy_engines", {}),
    ("agent-registry-control", "list_registries", {}),
    ("logs", "describe_log_groups", {"limit": 10}),
    ("ec2", "describe_vpcs", {}),
]


def check(spec):
    service, operation, params = spec
    try:
        client = SESSION.client(service, config=CONFIG)
        response = getattr(client, operation)(**params)
        response.pop("ResponseMetadata", None)
        # Keep account inventories compact; these checks do not read file contents.
        result = {k: len(v) if isinstance(v, list) else v for k, v in response.items()
                  if k not in ("Owner", "nextToken", "NextToken")}
        result["has_more_pages"] = bool(response.get("nextToken") or response.get("NextToken"))
        return {"service": service, "operation": operation, "ok": True, "result": result}
    except Exception as exc:
        return {"service": service, "operation": operation, "ok": False, "error": str(exc)}


def model_check(model):
    try:
        client = SESSION.client("bedrock-runtime", config=CONFIG)
        result = client.converse(
            modelId=model,
            messages=[{"role": "user", "content": [{"text": "Use the calculator tool to calculate 42 * 17."}]}],
            inferenceConfig={"maxTokens": 256, "temperature": 0},
            toolConfig={"tools": [{"toolSpec": {
                "name": "calculator", "description": "Calculate arithmetic expressions",
                "inputSchema": {"json": {"type": "object", "properties": {
                    "expression": {"type": "string"}}, "required": ["expression"]}},
            }}]},
        )
        result.pop("ResponseMetadata", None)
        uses = [b["toolUse"] for b in result["output"]["message"]["content"] if "toolUse" in b]
        ok = bool(uses) and all(t["name"] == "calculator" and isinstance(t["input"].get("expression"), str) for t in uses)
        return {"model": model, "tool_use_ok": ok, "result": result}
    except Exception as exc:
        return {"model": model, "tool_use_ok": False, "error": str(exc)}


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as pool:
        checks = list(pool.map(check, CHECKS))
    models = [model_check(m) for m in ("us.amazon.nova-lite-v1:0", "zai.glm-4.7-flash", "zai.glm-4.7")]
    report = {"time": datetime.now(timezone.utc).isoformat(), "region": REGION,
              "note": "Successful list calls do not prove create/deploy permissions.",
              "checks": checks, "models": models}
    Path(__file__).with_name("aws-check-results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
