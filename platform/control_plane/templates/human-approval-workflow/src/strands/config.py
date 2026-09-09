"""Configuration loaded from environment variables."""

import os

MODEL_ID = os.getenv("MODEL_ID", "us.amazon.nova-lite-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PORT = int(os.getenv("PORT", "8000"))
