"""Servicio de chatbot: prepara el prompt y consulta un modelo local en Ollama."""

from __future__ import annotations

import os
import re
from typing import Any

import requests

from .dataset_loader import compact_knowledge_for_prompt, load_knowledge
from .prompt_template import SYSTEM_PROMPT, build_user_prompt


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))

EMPTY_MESSAGE_ERROR = "El mensaje no puede estar vacio."

EMERGENCY_PATTERNS = [
    r"dificultad (para )?respirar",
    r"me cuesta respirar",
    r"falta de aire",
    r"ahogo",
    r"dolor.*pecho",
    r"presion.*pecho",
    r"confusi[oó]n",
    r"labios.*(azul|morad|gris|palid)",
    r"no.*despierta",
    r"somnolencia extrema",
]


class ChatbotService:
    """Encapsula el conocimiento local y la llamada HTTP a Ollama."""

    def __init__(self) -> None:
        self.knowledge: dict[str, Any] = load_knowledge()
        self.knowledge_context = compact_knowledge_for_prompt(self.knowledge)

    def reload_knowledge(self) -> None:
        self.knowledge = load_knowledge()
        self.knowledge_context = compact_knowledge_for_prompt(self.knowledge)

    def answer(self, user_message: str) -> str:
        clean_message = user_message.strip()
        if not clean_message:
            raise ValueError(EMPTY_MESSAGE_ERROR)

        # Refuerzo local: si el usuario describe signos de alarma, la respuesta debe priorizar urgencias.
        emergency_hint = self._detect_emergency(clean_message)
        user_prompt = build_user_prompt(clean_message, self.knowledge_context)
        if emergency_hint:
            user_prompt += (
                "\n\nNota de seguridad detectada por reglas locales: el mensaje puede contener una senal "
                "de alarma. Prioriza recomendar urgencias sin diagnosticar."
            )

        payload = {
            "model": OLLAMA_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
            },
        }

        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                "No se pudo conectar con Ollama. Verifica que Ollama este instalado y ejecutandose."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise RuntimeError("Ollama no respondio dentro del tiempo esperado.") from exc
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(f"Ollama devolvio un error HTTP: {response.status_code}") from exc

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("Ollama respondio sin contenido util.")

        return self._add_safety_footer(content)

    @staticmethod
    def _detect_emergency(message: str) -> bool:
        lower = message.lower()
        return any(re.search(pattern, lower) for pattern in EMERGENCY_PATTERNS)

    @staticmethod
    def _add_safety_footer(content: str) -> str:
        reminder = "Recuerda: esta es orientacion preliminar y no reemplaza una evaluacion medica."
        if reminder.lower() in content.lower():
            return content
        return f"{content}\n\n{reminder}"
