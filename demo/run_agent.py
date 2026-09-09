"""Run an existing AVA template against real Bedrock with a small output budget."""
import argparse
import asyncio
import importlib
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--template", choices=["conversational-assistant", "workflow-pipeline", "supervisor-specialists"], default="conversational-assistant")
parser.add_argument("--model", choices=["us.amazon.nova-lite-v1:0", "zai.glm-4.7-flash", "zai.glm-4.7"], default="us.amazon.nova-lite-v1:0")
args = parser.parse_args()
os.environ.update(AWS_PROFILE="default", AWS_REGION="us-east-1", MODEL_ID=args.model,
                  MAX_TOKENS="768", TEMPERATURE="0", ENABLE_TRACING="false")
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "platform/control_plane/templates" / args.template))
module = importlib.import_module("src.strands.main")

if args.template == "conversational-assistant":
    agent = module.create_agent()
    first = agent("Use the calculator to compute 42 * 17. Give a short answer.")
    second = agent("Add 6 to your previous result using the calculator. Give a short answer.")
    used_tools = [b["toolUse"]["name"] for m in agent.messages for b in m["content"] if "toolUse" in b]
    report = {"model": args.model, "first": str(first), "followup": str(second), "tools": used_tools}
    assert "714" in str(first) and "720" in str(second) and "calculator" in used_tools, report
else:
    payload = ({"document": "INVOICE INV-001. Seller: Demo Ltd. Buyer: Example Ltd. Date: 2026-09-09. Due: 2026-09-30. Consulting: 2 hours at USD 50/hour. Tax: USD 0. Total: USD 100. Payment: bank transfer."}
               if args.template == "workflow-pipeline" else
               {"prompt": "Ask the analyst to calculate revenue for 3 units sold at USD 20 each. Answer briefly."})
    report = asyncio.run(module.handler(payload))
    if args.template == "workflow-pipeline":
        assert report.get("success") and len(report["steps_completed"]) == 4, report
    else:
        used_tools = [b["toolUse"]["name"] for m in module.supervisor.messages for b in m["content"] if "toolUse" in b]
        assert "analyst" in used_tools and "60" in str(report), report

print("\nDEMO_RESULT=" + json.dumps(report, default=str))
