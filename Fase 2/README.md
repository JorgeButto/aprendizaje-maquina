# Fase 2 - Chatbot de orientacion sanitaria preliminar sobre COVID-19

## Objetivo

Este proyecto implementa un chatbot web que entrega orientacion sanitaria preliminar sobre COVID-19 usando Python, FastAPI y un LLM local mediante Ollama.

El chatbot usa como fuente local el dataset `../Fase 1/dataset_elpino.csv`, filtra registros con COVID-19 explicito y extrae desde esas filas sintomas, factores de riesgo, antecedentes epidemiologicos y condiciones clinicas asociadas. El resultado procesado se guarda en:

```text
data/covid_knowledge.json
```

## Dominio elegido

Orientacion preliminar sobre COVID-19 basada en:

- Sintomas reportados por el usuario.
- Factores de riesgo.
- Antecedentes epidemiologicos.
- Medidas generales de prevencion.
- Recomendaciones de consulta medica o urgencias.

El sistema no diagnostica enfermedades, no reemplaza atencion profesional y no entrega tratamientos farmacologicos especificos.

## Estructura

```text
Fase 2/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── chatbot_service.py
│   ├── dataset_loader.py
│   ├── prompt_template.py
│   └── schemas.py
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── script.js
├── data/
│   └── covid_knowledge.json
├── README.md
└── requirements.txt
```

## Requisitos previos

- Python 3.10 o superior.
- Ollama instalado y ejecutandose.
- Un modelo local descargado en Ollama, por ejemplo `llama3`, `mistral` o `deepseek-r1`.

## Instalacion

Desde la raiz del proyecto:

```powershell
cd "Fase 2"
pip install -r requirements.txt
```

## Configurar Ollama

Instalar Ollama desde:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Descargar un modelo:

```powershell
ollama pull llama3
```

Iniciar Ollama si no esta activo:

```powershell
ollama run llama3
```

## Generar conocimiento desde el dataset

El backend genera `data/covid_knowledge.json` automaticamente si no existe. Tambien se puede regenerar manualmente:

```powershell
python -m backend.dataset_loader
```

El extractor lee:

```text
../Fase 1/dataset_elpino.csv
```

y filtra principalmente registros con diagnostico COVID explicito, como `U07.1`, `U07.2` o texto COVID/SARS/coronavirus. Los sintomas respiratorios aislados, como tos, fiebre o disnea, no activan el filtro por si solos; se usan como senales solo cuando aparecen dentro de filas COVID.

## Ejecutar backend y frontend

Desde `Fase 2`:

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Abrir en el navegador:

```text
http://127.0.0.1:8000
```

Endpoint principal:

```text
POST /chat
```

Ejemplo JSON:

```json
{
  "message": "Tengo fiebre y tos desde ayer, ¿podria ser COVID-19?"
}
```

## Manejo de errores incluido

- Mensaje vacio: el frontend y el backend lo rechazan.
- Dataset faltante: el backend informa que no encontro `../Fase 1/dataset_elpino.csv`.
- Ollama apagado: el backend responde error 503 indicando que no pudo conectarse.
- Respuesta vacia o timeout de Ollama: se informa al usuario desde la interfaz.


## Fuentes sanitarias generales usadas para las reglas de orientacion

- CDC, sintomas y signos de emergencia de COVID-19: https://www.cdc.gov/covid/signs-symptoms/index.html
- CDC en espanol, sintomas del COVID-19: https://www.cdc.gov/covid/es/signs-symptoms/sintomas-del-covid-19.html
- OMS, coronavirus disease COVID-19: https://www.who.int/news-room/fact-sheets/detail/coronavirus-disease-%28covid-19%29

## 10 preguntas para probar

1. Tengo fiebre y tos, ¿podria ser COVID-19?
2. ¿Cuando deberia ir a urgencias?
3. Tengo dolor de garganta y contacto con una persona positiva, ¿que hago?
4. ¿Que medidas de prevencion puedo seguir?
5. Soy adulto mayor y tengo dificultad para respirar, ¿que debo hacer?
6. ¿Cuales son los sintomas frecuentes de COVID-19?
7. ¿Debo aislarme si tengo sintomas respiratorios?
8. Tengo diabetes y fiebre, ¿es un factor de riesgo?
9. ¿El chatbot puede diagnosticar COVID-19?
10. ¿Cuando deberia consultar a un medico?
