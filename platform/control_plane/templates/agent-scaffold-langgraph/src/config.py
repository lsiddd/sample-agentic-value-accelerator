"""Application configuration from environment variables."""

import os


class _Config:
    MODEL_ID = os.getenv("MODEL_ID", "us.amazon.nova-lite-v1:0")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


config = _Config()
