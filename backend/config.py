"""
config.py — Application configuration using Pydantic Settings.
Loads values from .env file automatically.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
import os


class Settings(BaseSettings):
    # ── LLM ──────────────────────────────────────────────────
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model: str = Field("openai/gpt-oss-20b", env="GROQ_MODEL")

    # ── Web Search ───────────────────────────────────────────
    tavily_api_key: str = Field(..., env="TAVILY_API_KEY")

    # ── Vector DB ────────────────────────────────────────────
    chroma_persist_dir: str = Field("./chroma_db", env="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field("enterprise_knowledge", env="CHROMA_COLLECTION_NAME")

    # ── Embeddings ───────────────────────────────────────────
    embedding_model: str = Field("all-MiniLM-L6-v2", env="EMBEDDING_MODEL")

    # ── File Storage ─────────────────────────────────────────
    upload_dir: str = Field("./uploads", env="UPLOAD_DIR")
    generated_dir: str = Field("./generated", env="GENERATED_DIR")
    versions_dir: str = Field("./versions", env="VERSIONS_DIR")

    # ── App ───────────────────────────────────────────────────
    app_env: str = Field("development", env="APP_ENV")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    max_file_size_mb: int = Field(50, env="MAX_FILE_SIZE_MB")
    allowed_extensions: str = Field("pdf,docx,pptx,png,jpg,jpeg,tiff", env="ALLOWED_EXTENSIONS")

    # ── CORS ─────────────────────────────────────────────────
    frontend_url: str = Field("http://localhost:5173", env="FRONTEND_URL")

    class Config:
        env_file = ".env" if os.path.exists(".env") else "../.env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def allowed_ext_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",")]

    def ensure_dirs(self):
        """Create required storage directories if they don't exist."""
        for d in [self.upload_dir, self.generated_dir, self.versions_dir, self.chroma_persist_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
settings.ensure_dirs()
