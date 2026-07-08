---
name: cerebras
description: Use this to write code to call an LLM using LiteLLM and OpenRouter, using a free-tier model (no paid inference provider).
---

# Calling an LLM via OpenRouter (free-tier model)

These instructions allow you to write code to call an LLM via OpenRouter, using LiteLLM. This project uses a **free** OpenRouter model, the same choice made in the earlier PM project, instead of paying for the Cerebras inference provider that the course lecture used for low-latency responses. If low latency ever becomes a priority, this can be switched to a paid model with `extra_body={"provider": {"order": ["cerebras"]}}` — but free-tier requests do not reliably support forcing a specific inference provider, so that routing is left out here.

## Setup

- The model is `nvidia/nemotron-3-super-120b-a12b:free`, accessed through OpenRouter (same free model already used in the PM project's `backend/app/ai.py`).
- The OpenRouter API key is read from the `OPENROUTER_API_KEY` environment variable (see `.env` in the project root).
- Free models require the Privacy/Guardrails toggles to be enabled on the OpenRouter account (see the settings used for the PM project).
- Install dependencies with `uv add litellm`.

## Imports and constants

```python
import os
import litellm

OPENROUTER_MODEL = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
```

## Basic call

```python
def call_llm(prompt: str) -> str:
    response = litellm.completion(
        model=OPENROUTER_MODEL,
        api_base=OPENROUTER_API_BASE,
        api_key=OPENROUTER_API_KEY,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content
```

## Structured outputs

Use this when you need to populate specific fields (e.g. legal document fields) from the model's response, instead of parsing free text.

```python
from pydantic import BaseModel

class DocumentFields(BaseModel):
    party_a_name: str
    party_b_name: str
    effective_date: str
    governing_law: str

def call_llm_structured(prompt: str) -> DocumentFields:
    response = litellm.completion(
        model=OPENROUTER_MODEL,
        api_base=OPENROUTER_API_BASE,
        api_key=OPENROUTER_API_KEY,
        messages=[{"role": "user", "content": prompt}],
        response_format=DocumentFields,
    )
    return DocumentFields.model_validate_json(response.choices[0].message.content)
```

Adjust the `DocumentFields` schema to match whichever legal document template's fields you are populating.
