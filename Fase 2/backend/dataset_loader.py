"""Carga y procesamiento del dataset clinico para extraer conocimiento COVID-19."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_DATASET_PATH = PROJECT_ROOT / "Fase 1" / "dataset_elpino.csv"
DEFAULT_OUTPUT_PATH = BASE_DIR / "data" / "covid_knowledge.json"

STRICT_COVID_CODES = {"U07.1", "U07.2"}
STRICT_COVID_TERMS = ("covid", "sars", "coronavirus")
EPIDEMIOLOGICAL_CODES = {"Z20.8", "Z29.0", "Z01.7"}
EPIDEMIOLOGICAL_TERMS = ("aislamiento", "contacto", "exposicion", "examen de laboratorio")

SYMPTOM_CODES = {
    "R05",  # tos
    "R06.0",  # disnea
    "R50.9",  # fiebre
    "R53",  # malestar y fatiga
    "M79.19",  # mialgia
    "R51",  # cefalea
    "R11",  # nausea y vomito
    "A09.9",  # diarrea/gastroenteritis
}
RISK_CODES_PREFIXES = ("E11", "I10", "I25", "I50", "J44", "N18", "E66", "O98.5", "O24", "D84", "B20")
ALARM_CODES_PREFIXES = ("J96", "J80", "R57", "A41")


def _ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _normalize(value: str) -> str:
    return " ".join(value.strip().split())


def _code_of(value: str) -> str:
    return value.split(" - ", 1)[0].strip()


def _is_diag_column(name: str) -> bool:
    return _ascii_fold(name).startswith("diag")


def _is_proc_column(name: str) -> bool:
    return _ascii_fold(name).startswith("proced")


def _find_column(fieldnames: list[str], *needles: str) -> str | None:
    folded_needles = [_ascii_fold(needle) for needle in needles]
    for name in fieldnames:
        folded_name = _ascii_fold(name)
        if all(needle in folded_name for needle in folded_needles):
            return name
    return None


def _safe_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _has_strict_covid(diagnoses: list[str]) -> bool:
    for diagnosis in diagnoses:
        code = _code_of(diagnosis)
        text = _ascii_fold(diagnosis)
        if code in STRICT_COVID_CODES:
            return True
        if any(term in text for term in STRICT_COVID_TERMS) and "historia personal" not in text:
            return True
    return False


def _has_epidemiological_context(diagnoses: list[str], procedures: list[str]) -> bool:
    for item in diagnoses + procedures:
        code = _code_of(item)
        text = _ascii_fold(item)
        if code in EPIDEMIOLOGICAL_CODES or any(term in text for term in EPIDEMIOLOGICAL_TERMS):
            return True
    return False


def _row_predictive_score(diagnoses: list[str], procedures: list[str], age: int | None) -> int:
    """Puntaje simple para priorizar filas con mas informacion util para orientacion."""

    score = 0
    diagnosis_codes = {_code_of(item) for item in diagnoses}

    if diagnosis_codes & STRICT_COVID_CODES:
        score += 5
    if any(_code_of(item) in SYMPTOM_CODES for item in diagnoses):
        score += 2
    if any(_code_of(item).startswith(RISK_CODES_PREFIXES) for item in diagnoses):
        score += 2
    if any(_code_of(item).startswith(ALARM_CODES_PREFIXES) for item in diagnoses):
        score += 3
    if _has_epidemiological_context(diagnoses, procedures):
        score += 1
    if age is not None and age >= 60:
        score += 1

    return score


def _counter_with_rates(counter: Counter[str], denominator: int, limit: int) -> list[dict[str, Any]]:
    if denominator <= 0:
        return []
    return [
        {"item": item, "count": count, "rate": round(count / denominator, 4)}
        for item, count in counter.most_common(limit)
    ]


def process_dataset(
    dataset_path: Path = DEFAULT_DATASET_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, Any]:
    """Filtra filas con COVID explicito y guarda un JSON de conocimiento mas preciso."""

    if not dataset_path.exists():
        raise FileNotFoundError(f"No se encontro el dataset en: {dataset_path}")

    diagnosis_counter: Counter[str] = Counter()
    procedure_counter: Counter[str] = Counter()
    symptom_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    alarm_counter: Counter[str] = Counter()
    epidemiological_counter: Counter[str] = Counter()
    ages: list[int] = []
    sex_counter: Counter[str] = Counter()
    sample_records: list[dict[str, Any]] = []
    total_rows = 0
    strict_covid_rows = 0
    epidemiological_context_rows = 0
    high_signal_rows = 0

    with dataset_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        if reader.fieldnames is None:
            raise ValueError("El CSV no contiene encabezados validos.")

        diag_columns = [name for name in reader.fieldnames if _is_diag_column(name)]
        proc_columns = [name for name in reader.fieldnames if _is_proc_column(name)]
        age_column = _find_column(reader.fieldnames, "edad")
        sex_column = _find_column(reader.fieldnames, "sexo")

        for row in reader:
            total_rows += 1
            diagnoses = [_normalize(row.get(col, "")) for col in diag_columns]
            procedures = [_normalize(row.get(col, "")) for col in proc_columns]
            diagnoses = [item for item in diagnoses if item and item != "-"]
            procedures = [item for item in procedures if item and item != "-"]

            # Filtro principal: solo filas con COVID explicito, no sintomas respiratorios aislados.
            if not _has_strict_covid(diagnoses):
                continue

            strict_covid_rows += 1
            age = _safe_int(row.get(age_column, "")) if age_column else None
            sex = _normalize(row.get(sex_column, "")) if sex_column else ""
            predictive_score = _row_predictive_score(diagnoses, procedures, age)

            if predictive_score >= 8:
                high_signal_rows += 1
            if _has_epidemiological_context(diagnoses, procedures):
                epidemiological_context_rows += 1

            diagnosis_counter.update(diagnoses)
            procedure_counter.update(procedures)

            for diagnosis in diagnoses:
                code = _code_of(diagnosis)
                text = _ascii_fold(diagnosis)
                if code in SYMPTOM_CODES:
                    symptom_counter[diagnosis] += 1
                if code.startswith(RISK_CODES_PREFIXES):
                    risk_counter[diagnosis] += 1
                if code.startswith(ALARM_CODES_PREFIXES):
                    alarm_counter[diagnosis] += 1
                if code in EPIDEMIOLOGICAL_CODES or any(term in text for term in EPIDEMIOLOGICAL_TERMS):
                    epidemiological_counter[diagnosis] += 1

            if age is not None:
                ages.append(age)
            if sex:
                sex_counter[sex] += 1

            if len(sample_records) < 10 and predictive_score >= 7:
                sample_records.append(
                    {
                        "edad": age,
                        "sexo": sex,
                        "puntaje_predictivo": predictive_score,
                        "diagnosticos_covid_sintomas_riesgo": [
                            item
                            for item in diagnoses
                            if _code_of(item) in STRICT_COVID_CODES
                            or _code_of(item) in SYMPTOM_CODES
                            or _code_of(item).startswith(RISK_CODES_PREFIXES)
                            or _code_of(item).startswith(ALARM_CODES_PREFIXES)
                            or _code_of(item) in EPIDEMIOLOGICAL_CODES
                        ][:14],
                    }
                )

    age_summary = {
        "min": min(ages) if ages else None,
        "max": max(ages) if ages else None,
        "promedio": round(sum(ages) / len(ages), 1) if ages else None,
        "mayores_60": sum(1 for age in ages if age >= 60),
        "mayores_60_rate": round(sum(1 for age in ages if age >= 60) / len(ages), 4) if ages else None,
    }

    knowledge = {
        "metadata": {
            "source_dataset": str(dataset_path),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total_rows": total_rows,
            "strict_covid_rows": strict_covid_rows,
            "covid_related_rows": strict_covid_rows,
            "epidemiological_context_rows": epidemiological_context_rows,
            "high_signal_rows": high_signal_rows,
            "filter_strategy": (
                "Se incluyen solo filas con COVID explicito en diagnosticos: U07.1, U07.2 "
                "o texto COVID/SARS/coronavirus que no corresponda a historia personal. "
                "Los sintomas respiratorios aislados no activan el filtro."
            ),
            "strict_covid_codes": sorted(STRICT_COVID_CODES),
            "epidemiological_codes": sorted(EPIDEMIOLOGICAL_CODES),
        },
        "dataset_signals": {
            "common_covid_diagnoses": _counter_with_rates(diagnosis_counter, strict_covid_rows, 30),
            "common_covid_procedures": _counter_with_rates(procedure_counter, strict_covid_rows, 20),
            "observed_symptoms": _counter_with_rates(symptom_counter, strict_covid_rows, 20),
            "observed_risk_factors": _counter_with_rates(risk_counter, strict_covid_rows, 20),
            "observed_alarm_conditions": _counter_with_rates(alarm_counter, strict_covid_rows, 20),
            "observed_epidemiological_context": _counter_with_rates(epidemiological_counter, strict_covid_rows, 12),
            "age_summary": age_summary,
            "sex_distribution": sex_counter.most_common(),
            "sample_high_signal_records": sample_records,
        },
        "orientation_knowledge": {
            "scope": (
                "Orientacion sanitaria preliminar sobre COVID-19. No entrega diagnosticos, "
                "tratamientos farmacologicos ni reemplaza atencion profesional."
            ),
            "frequent_symptoms": [
                "fiebre o escalofrios",
                "tos",
                "dolor de garganta",
                "congestion o secrecion nasal",
                "fatiga o malestar",
                "dolor muscular",
                "cefalea",
                "perdida o cambio del gusto u olfato",
                "nauseas, vomitos o diarrea",
                "dificultad para respirar",
            ],
            "alarm_signs": [
                "dificultad para respirar",
                "dolor o presion persistente en el pecho",
                "confusion nueva",
                "somnolencia extrema o dificultad para despertar",
                "labios, unas o piel azulada, grisacea o muy palida",
                "fiebre persistente o empeoramiento rapido",
            ],
            "risk_factors": [
                "edad avanzada",
                "embarazo",
                "diabetes",
                "enfermedad cardiovascular o hipertension",
                "enfermedad pulmonar cronica",
                "enfermedad renal cronica",
                "obesidad",
                "cancer o inmunosupresion",
            ],
            "prevention": [
                "quedarse en casa y evitar contacto estrecho si hay sintomas respiratorios",
                "ventilar espacios cerrados",
                "lavado frecuente de manos o alcohol gel",
                "usar mascarilla bien ajustada en contextos de riesgo o si hay sintomas",
                "cubrir tos y estornudos",
                "seguir indicaciones locales de vacunacion y salud publica",
            ],
            "when_to_consult": [
                "si hay factores de riesgo y sintomas compatibles",
                "si la fiebre persiste o los sintomas empeoran",
                "si hubo contacto con un caso confirmado y aparecen sintomas",
                "si se requiere orientacion sobre test, licencia, aislamiento o control medico",
            ],
            "when_to_emergency": [
                "cualquier signo de alarma respiratorio, neurologico o cardiovascular",
                "dificultad respiratoria en adulto mayor, embarazada o persona con comorbilidades",
            ],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(knowledge, ensure_ascii=False, indent=2), encoding="utf-8")
    return knowledge


def load_knowledge(output_path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    """Carga el JSON procesado; si no existe, lo genera desde el dataset original."""

    if not output_path.exists():
        return process_dataset(output_path=output_path)
    return json.loads(output_path.read_text(encoding="utf-8"))


def compact_knowledge_for_prompt(knowledge: dict[str, Any]) -> str:
    """Convierte el conocimiento en texto breve para incluirlo dentro del prompt."""

    signals = knowledge.get("dataset_signals", {})
    metadata = knowledge.get("metadata", {})
    orientation = knowledge.get("orientation_knowledge", {})

    def names(items: list[dict[str, Any]], limit: int = 10) -> str:
        values = []
        for item in items[:limit]:
            label = item.get("item", "")
            rate = item.get("rate")
            if rate is None:
                values.append(str(label))
            else:
                values.append(f"{label} ({rate:.1%})")
        return "; ".join(values)

    return re.sub(
        r"\n{3,}",
        "\n\n",
        f"""
Resumen del dataset local:
- Registros totales: {metadata.get('total_rows')}
- Registros con COVID explicito usados como base: {metadata.get('strict_covid_rows')}
- Estrategia de filtro: {metadata.get('filter_strategy')}
- Diagnosticos frecuentes en filas COVID: {names(signals.get('common_covid_diagnoses', []))}
- Sintomas observados en filas COVID: {names(signals.get('observed_symptoms', []))}
- Factores de riesgo observados en filas COVID: {names(signals.get('observed_risk_factors', []))}
- Condiciones graves observadas en filas COVID: {names(signals.get('observed_alarm_conditions', []))}
- Contexto epidemiologico observado: {names(signals.get('observed_epidemiological_context', []))}

Conocimiento de orientacion:
- Sintomas frecuentes: {', '.join(orientation.get('frequent_symptoms', []))}
- Senales de alarma: {', '.join(orientation.get('alarm_signs', []))}
- Factores de riesgo: {', '.join(orientation.get('risk_factors', []))}
- Prevencion: {', '.join(orientation.get('prevention', []))}
- Consulta medica: {', '.join(orientation.get('when_to_consult', []))}
- Urgencias: {', '.join(orientation.get('when_to_emergency', []))}
""".strip(),
    )


if __name__ == "__main__":
    result = process_dataset()
    print(
        "Conocimiento COVID-19 generado en "
        f"{DEFAULT_OUTPUT_PATH} con {result['metadata']['strict_covid_rows']} registros COVID explicitos."
    )
