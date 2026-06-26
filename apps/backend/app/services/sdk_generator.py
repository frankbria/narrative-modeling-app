"""
SDK Generator Service (issue #86 — P5.6).

Generates **per-deployment** client SDKs (Python / TypeScript / JavaScript / cURL),
a Postman collection, framework integration samples, and per-SDK README docs for a
trained model. Unlike the generic ``APIDocumentationService`` (which hardcodes a fake
host and the wrong predict route), these target the **real** production serving
contract:

    POST {serving_endpoint}/predict
    Header: X-API-Key: sk_live_...
    Body:   {"data": [{<feature>: <value>}, ...], "include_probabilities": true}

where ``serving_endpoint`` is the deployment URL
``{host}/api/v1/production/v1/models/{model_id}`` (issue #84). Pure and stateless —
every generator is a string/dict builder driven by the model's real ``feature_names``;
nothing here performs IO or raises on bad model metadata.
"""
from __future__ import annotations

import json
import re
from typing import Any

SUPPORTED_LANGUAGES = ("python", "typescript", "javascript", "curl")


def _class_name(model_name: str) -> str:
    """Build a PascalCase client class name from a free-text model name."""
    words = re.findall(r"[A-Za-z0-9]+", model_name or "")
    pascal = "".join(w[:1].upper() + w[1:] for w in words)
    if not pascal or not pascal[0].isalpha():
        pascal = "Model" + pascal
    return f"{pascal}Client"


class SDKGenerator:
    """Builds deployment-specific SDKs for one model.

    Args:
        model_id: The model's id (path segment in the serving URL).
        model_name: Human-readable model name (drives the client class name).
        feature_names: Raw input feature names (drives the sample record).
        problem_type: ``classification`` / ``regression`` / ... (for doc copy).
        serving_endpoint: The deployment URL ``{host}/api/v1/production/v1/models/{id}``.
            ``/predict`` and ``/info`` are appended by the generated code.
    """

    def __init__(
        self,
        *,
        model_id: str,
        model_name: str,
        feature_names: list[str] | None,
        problem_type: str,
        serving_endpoint: str,
    ) -> None:
        self.model_id = model_id
        self.model_name = model_name or model_id
        self.feature_names = list(feature_names or [])
        self.problem_type = problem_type or "classification"
        self.serving_endpoint = serving_endpoint.rstrip("/")
        self.class_name = _class_name(self.model_name)

    # -- shared helpers -------------------------------------------------------

    def sample_record(self) -> dict[str, Any]:
        """A single example input record (every feature defaulted to 0)."""
        return {name: 0 for name in self.feature_names}

    def languages(self) -> dict[str, str]:
        """All source SDKs keyed by language."""
        return {
            "python": self.python_sdk(),
            "typescript": self.typescript_sdk(),
            "javascript": self.javascript_sdk(),
            "curl": self.curl_examples(),
        }

    def get(self, language: str) -> str | None:
        """Return one SDK by language, or ``None`` if unsupported."""
        builders = {
            "python": self.python_sdk,
            "typescript": self.typescript_sdk,
            "javascript": self.javascript_sdk,
            "curl": self.curl_examples,
        }
        builder = builders.get(language.lower())
        return builder() if builder else None

    def info(self) -> dict[str, Any]:
        """Discovery payload: languages, model metadata, sample record, install hints."""
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "problem_type": self.problem_type,
            "serving_endpoint": self.serving_endpoint,
            "predict_url": f"{self.serving_endpoint}/predict",
            "feature_names": self.feature_names,
            "sample_record": self.sample_record(),
            "languages": list(SUPPORTED_LANGUAGES),
            "install": {
                "python": "pip install requests",
                "typescript": "npm install (uses built-in fetch; Node 18+)",
                "javascript": "uses built-in fetch; Node 18+ or browser",
                "curl": "no install required",
            },
            "auth": "Send your API key in the 'X-API-Key' header (sk_live_...).",
        }

    # -- Python ---------------------------------------------------------------

    def python_sdk(self) -> str:
        sample = json.dumps(self.sample_record(), indent=8).replace("\n", "\n    ")
        return f'''"""
{self.model_name} — Python client (auto-generated, issue #86).

Install:
    pip install requests

Usage:
    client = {self.class_name}(api_key="sk_live_...")
    result = client.predict([{{"feature": 0}}])
"""
import requests


class {self.class_name}:
    """Client for the deployed model '{self.model_name}' ({self.problem_type})."""

    def __init__(self, api_key: str, endpoint: str = "{self.serving_endpoint}"):
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({{"X-API-Key": api_key}})

    def predict(self, records, include_probabilities: bool = True) -> dict:
        """Run a prediction. ``records`` is a list of feature dicts."""
        response = self.session.post(
            f"{{self.endpoint}}/predict",
            json={{"data": records, "include_probabilities": include_probabilities}},
        )
        response.raise_for_status()
        return response.json()

    def info(self) -> dict:
        """Return model metadata (problem type, features, performance)."""
        response = self.session.get(f"{{self.endpoint}}/info")
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = {self.class_name}(api_key="sk_live_your_key_here")
    sample = {sample}
    print(client.predict([sample]))
'''

    # -- TypeScript -----------------------------------------------------------

    def typescript_sdk(self) -> str:
        sample = json.dumps(self.sample_record())
        return f'''/**
 * {self.model_name} — TypeScript client (auto-generated, issue #86).
 *
 * Requires Node 18+ (built-in fetch) or a modern browser.
 *
 * Usage:
 *   const client = new {self.class_name}("sk_live_...");
 *   const result = await client.predict([{{ feature: 0 }}]);
 */

export type PredictionRecord = Record<string, unknown>;

export interface PredictResponse {{
  predictions: unknown[];
  probabilities?: number[][] | null;
  model_version: string;
  prediction_id: string;
  timestamp: string;
  confidence?: number[] | null;
}}

export class {self.class_name} {{
  private readonly endpoint: string;

  constructor(
    private readonly apiKey: string,
    endpoint: string = "{self.serving_endpoint}",
  ) {{
    this.endpoint = endpoint.replace(/\\/$/, "");
  }}

  /** Run a prediction. `records` is a list of feature objects. */
  async predict(
    records: PredictionRecord[],
    includeProbabilities = true,
  ): Promise<PredictResponse> {{
    const response = await fetch(`${{this.endpoint}}/predict`, {{
      method: "POST",
      headers: {{ "X-API-Key": this.apiKey, "Content-Type": "application/json" }},
      body: JSON.stringify({{ data: records, include_probabilities: includeProbabilities }}),
    }});
    if (!response.ok) {{
      throw new Error(`HTTP ${{response.status}}: ${{await response.text()}}`);
    }}
    return response.json() as Promise<PredictResponse>;
  }}

  /** Return model metadata. */
  async info(): Promise<Record<string, unknown>> {{
    const response = await fetch(`${{this.endpoint}}/info`, {{
      headers: {{ "X-API-Key": this.apiKey }},
    }});
    if (!response.ok) {{
      throw new Error(`HTTP ${{response.status}}: ${{await response.text()}}`);
    }}
    return response.json();
  }}
}}

// Example:
// const client = new {self.class_name}("sk_live_your_key_here");
// client.predict([{sample}]).then(console.log);
'''

    # -- JavaScript -----------------------------------------------------------

    def javascript_sdk(self) -> str:
        sample = json.dumps(self.sample_record())
        return f'''/**
 * {self.model_name} — JavaScript client (auto-generated, issue #86).
 *
 * Requires Node 18+ (built-in fetch) or a modern browser.
 *
 * Usage:
 *   const client = new {self.class_name}("sk_live_...");
 *   const result = await client.predict([{{ feature: 0 }}]);
 */

class {self.class_name} {{
  constructor(apiKey, endpoint = "{self.serving_endpoint}") {{
    this.apiKey = apiKey;
    this.endpoint = endpoint.replace(/\\/$/, "");
  }}

  async predict(records, includeProbabilities = true) {{
    const response = await fetch(`${{this.endpoint}}/predict`, {{
      method: "POST",
      headers: {{ "X-API-Key": this.apiKey, "Content-Type": "application/json" }},
      body: JSON.stringify({{ data: records, include_probabilities: includeProbabilities }}),
    }});
    if (!response.ok) {{
      throw new Error(`HTTP ${{response.status}}: ${{await response.text()}}`);
    }}
    return response.json();
  }}

  async info() {{
    const response = await fetch(`${{this.endpoint}}/info`, {{
      headers: {{ "X-API-Key": this.apiKey }},
    }});
    if (!response.ok) {{
      throw new Error(`HTTP ${{response.status}}: ${{await response.text()}}`);
    }}
    return response.json();
  }}
}}

// Example:
// const client = new {self.class_name}("sk_live_your_key_here");
// client.predict([{sample}]).then(console.log);

module.exports = {self.class_name};
'''

    # -- cURL -----------------------------------------------------------------

    def curl_examples(self) -> str:
        body = json.dumps({"data": [self.sample_record()], "include_probabilities": True})
        return f'''# {self.model_name} — cURL examples (auto-generated, issue #86)

export API_KEY="sk_live_your_key_here"
export ENDPOINT="{self.serving_endpoint}"

# 1. Make a prediction
curl -X POST "$ENDPOINT/predict" \\
  -H "X-API-Key: $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{body}'

# 2. Get model info
curl -X GET "$ENDPOINT/info" \\
  -H "X-API-Key: $API_KEY"
'''

    # -- Postman --------------------------------------------------------------

    def postman_collection(self) -> dict[str, Any]:
        predict_body = json.dumps(
            {"data": [self.sample_record()], "include_probabilities": True}, indent=2
        )
        return {
            "info": {
                "name": f"{self.model_name} API",
                "description": (
                    f"Per-deployment collection for model {self.model_id} "
                    f"({self.problem_type})."
                ),
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "variable": [
                {"key": "endpoint", "value": self.serving_endpoint, "type": "string"},
                {"key": "api_key", "value": "sk_live_your_key_here", "type": "string"},
            ],
            "item": [
                {
                    "name": "Predict",
                    "request": {
                        "method": "POST",
                        "header": [
                            {"key": "X-API-Key", "value": "{{api_key}}"},
                            {"key": "Content-Type", "value": "application/json"},
                        ],
                        "url": "{{endpoint}}/predict",
                        "body": {"mode": "raw", "raw": predict_body},
                    },
                },
                {
                    "name": "Model Info",
                    "request": {
                        "method": "GET",
                        "header": [{"key": "X-API-Key", "value": "{{api_key}}"}],
                        "url": "{{endpoint}}/info",
                    },
                },
            ],
        }

    # -- Framework samples ----------------------------------------------------

    def framework_samples(self) -> dict[str, str]:
        ep = self.serving_endpoint
        return {
            "flask": f'''# Flask app proxying predictions to {self.model_name}
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
ENDPOINT = "{ep}"
API_KEY = "sk_live_your_key_here"


@app.route("/predict", methods=["POST"])
def predict():
    resp = requests.post(
        f"{{ENDPOINT}}/predict",
        json={{"data": request.json["data"]}},
        headers={{"X-API-Key": API_KEY}},
    )
    return jsonify(resp.json()), resp.status_code
''',
            "fastapi": f'''# FastAPI app proxying predictions to {self.model_name}
import httpx
from fastapi import FastAPI

app = FastAPI()
ENDPOINT = "{ep}"
API_KEY = "sk_live_your_key_here"


@app.post("/predict")
async def predict(payload: dict):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{{ENDPOINT}}/predict",
            json={{"data": payload["data"]}},
            headers={{"X-API-Key": API_KEY}},
        )
    return resp.json()
''',
            "express": f'''// Express route proxying predictions to {self.model_name}
const express = require("express");
const app = express();
app.use(express.json());

const ENDPOINT = "{ep}";
const API_KEY = "sk_live_your_key_here";

app.post("/predict", async (req, res) => {{
  const resp = await fetch(`${{ENDPOINT}}/predict`, {{
    method: "POST",
    headers: {{ "X-API-Key": API_KEY, "Content-Type": "application/json" }},
    body: JSON.stringify({{ data: req.body.data }}),
  }});
  res.status(resp.status).json(await resp.json());
}});

app.listen(3000);
''',
            "nextjs": f'''// Next.js API route (app/api/predict/route.ts) for {self.model_name}
const ENDPOINT = "{ep}";
const API_KEY = process.env.MODEL_API_KEY!; // sk_live_...

export async function POST(request: Request) {{
  const {{ data }} = await request.json();
  const resp = await fetch(`${{ENDPOINT}}/predict`, {{
    method: "POST",
    headers: {{ "X-API-Key": API_KEY, "Content-Type": "application/json" }},
    body: JSON.stringify({{ data }}),
  }});
  return new Response(await resp.text(), {{ status: resp.status }});
}}
''',
            "webhook_receiver": self.webhook_receiver_sample(),
        }

    def webhook_receiver_sample(self) -> str:
        """Flask receiver that verifies the HMAC signature of a batch-completion webhook."""
        return f'''# Webhook receiver for async (batch) predictions from {self.model_name}.
# Batch jobs accept an optional webhook_url + webhook_secret; on completion the
# server POSTs the job summary with an 'X-Signature' HMAC-SHA256 header (issue #86).
import hashlib
import hmac
from flask import Flask, request, abort

app = Flask(__name__)
WEBHOOK_SECRET = b"your-webhook-secret"


@app.route("/webhook", methods=["POST"])
def webhook():
    signature = request.headers.get("X-Signature", "")
    expected = hmac.new(WEBHOOK_SECRET, request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        abort(401)
    payload = request.get_json()
    print("Batch job completed:", payload["job_id"], payload["status"])
    return "", 204
'''

    # -- README / docs (AC5) --------------------------------------------------

    def readme(self, language: str = "python") -> str:
        install = {
            "python": "pip install requests",
            "typescript": "Node 18+ (built-in fetch); no install needed",
            "javascript": "Node 18+ (built-in fetch); no install needed",
            "curl": "no install required",
        }.get(language.lower(), "see SDK header")
        return f'''# {self.model_name} — {language.title()} SDK

Auto-generated client for the deployed model `{self.model_id}` ({self.problem_type}).

## Install
{install}

## Authentication
All requests authenticate with your API key in the `X-API-Key` header
(format `sk_live_...`). Create keys via `POST /api/v1/production/api-keys`.

## Quickstart
1. Download the `{language}` SDK from the deploy page (or
   `GET /api/v1/ml/{self.model_id}/sdk/{language}`).
2. Instantiate the client with your API key.
3. Call `predict([record])` where each record has the model's input features:
   `{", ".join(self.feature_names) or "(no features)"}`.

## Endpoint
`POST {self.serving_endpoint}/predict`

Body: `{{"data": [{{...features...}}], "include_probabilities": true}}`

## Async / webhooks
For large inputs, create a batch prediction job and pass an optional
`webhook_url` + `webhook_secret`; the server POSTs the signed job summary on
completion (see the `webhook_receiver` framework sample).

## Troubleshooting
- **401** — missing/invalid API key, or the key lacks access to this model.
- **422** — a required feature is missing from a record.
- **429** — rate limit exceeded; honor the `Retry-After` header.
'''
