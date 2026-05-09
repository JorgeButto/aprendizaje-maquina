"""Esquemas de entrada y salida para la API."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Mensaje escrito por el usuario.")


class ChatResponse(BaseModel):
    response: str
    model: str


class HealthResponse(BaseModel):
    status: str
    model: str
    knowledge_loaded: bool
