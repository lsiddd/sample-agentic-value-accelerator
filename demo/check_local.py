"""Check local startup and tiny Bedrock calls; stop on the first failure."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

checks = [
    ("frontend", "http://127.0.0.1:3000/", None, False),
    ("backend health", "http://127.0.0.1:8000/health", None, False),
    ("frontend proxy", "http://127.0.0.1:3000/health", None, False),
    ("gateway models", "http://127.0.0.1:4000/v1/models", None, True),
]
checks += [(model, "http://127.0.0.1:4000/v1/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": "Reply only OK"}],
             "max_tokens": 16, "temperature": 0}, True)
           for model in ("Amazon Nova Lite", "GLM 4.7 Flash")]
for name, url, payload, auth in checks:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = "Bearer sk-local-dev-key"
    request = Request(url, data=json.dumps(payload).encode() if payload else None, headers=headers)
    try:
        with urlopen(request, timeout=60) as response:
            body = response.read().decode()
            if name == "frontend":
                result = "HTML served" if "<html" in body.lower() else body[:100]
            else:
                result = json.loads(body)
            print(json.dumps({"check": name, "status": response.status, "result": result}), flush=True)
    except HTTPError as exc:
        print(json.dumps({"check": name, "status": exc.code, "error": exc.read().decode()[:2500]}), flush=True)
        raise SystemExit(1)
    except Exception as exc:
        print(json.dumps({"check": name, "error": str(exc)}), flush=True)
        raise SystemExit(1)
