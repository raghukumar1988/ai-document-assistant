from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Azure OpenAI Settings
    azure_openai_api_key: str = Field(..., env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = Field(..., env="AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment_name: str = Field(..., env="AZURE_OPENAI_DEPLOYMENT_NAME")
    azure_openai_api_version: str = Field(
        default="2024-02-15-preview",
        env="AZURE_OPENAI_API_VERSION"
    )
    
    # Model Configuration
    azure_openai_model_name: str = Field(default="gpt-4", env="AZURE_OPENAI_MODEL_NAME")
    temperature: float = Field(default=0.7, env="TEMPERATURE")
    max_tokens: int = Field(default=1000, env="MAX_TOKENS")
    
    # Application Settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()

def validate_azure_config():
    """Validate that all required Azure OpenAI settings are present"""
    required_settings = [
        ("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
        ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
        ("AZURE_OPENAI_DEPLOYMENT_NAME", settings.azure_openai_deployment_name),
    ]
    
    missing = []
    for name, value in required_settings:
        if not value or value == "your_api_key_here" or value.startswith("your_"):
            missing.append(name)
    
    if missing:
        raise ValueError(
            f"Missing or invalid Azure OpenAI configuration: {', '.join(missing)}. "
            f"Please set these in your .env file."
        )
    
    return True