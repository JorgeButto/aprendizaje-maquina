"""API FastAPI para el chatbot de orientacion sanitaria COVID-19."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .chatbot_service import OLLAMA_MODEL, ChatbotService
from .dataset_loader import DEFAULT_OUTPUT_PATH, process_dataset
from .schemas import ChatRequest, ChatResponse, HealthResponse


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="Chatbot COVID-19 - Fase 2",
    description="Orientacion sanitaria preliminar sobre COVID-19 usando Ollama local.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chatbot = ChatbotService()

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=OLLAMA_MODEL,
        knowledge_loaded=bool(chatbot.knowledge),
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        answer = chatbot.answer(request.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(response=answer, model=OLLAMA_MODEL)


@app.post("/knowledge/rebuild")
def rebuild_knowledge() -> dict[str, object]:
    try:
        knowledge = process_dataset(output_path=DEFAULT_OUTPUT_PATH)
        chatbot.reload_knowledge()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "rebuilt",
        "output": str(DEFAULT_OUTPUT_PATH),
        "covid_related_rows": knowledge["metadata"]["covid_related_rows"],
    }
