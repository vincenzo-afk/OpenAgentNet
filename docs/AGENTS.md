# Building and Registering Agents

This guide explains how to create an agent that works with OpenAgentNet — from key generation through registration to receiving and handling tasks.

---

## What Is an Agent?

An agent is any process that:

1. Has a registered identity in the OpenAgentNet registry.
2. Exposes an HTTPS endpoint that can receive message envelopes.
3. Signs outgoing messages with its Ed25519 private key.
4. Declares the capabilities it supports in its identity document.

Agents can be written in any language. The protocol is HTTP + JSON. A Python SDK is provided for convenience.

---

## Quick Start (Python)

### Install the SDK

```bash
pip install openagentnet-sdk
```

### Generate Identity

```python
from openagentnet import AgentIdentity

identity = AgentIdentity.generate(
    display_name="My Summarizer",
    version="1.0.0",
    endpoint="https://myagent.example.com/oan",
    capabilities=[
        {
            "slug": "summarize.text",
            "version": "1.0",
            "description": "Summarizes text",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "max_words": {"type": "integer"}
                },
                "required": ["text"]
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"}
                },
                "required": ["summary"]
            }
        }
    ]
)

# Save identity (keeps the private key)
identity.save("~/.oan/my-summarizer.json")
print(f"Agent ID: {identity.agent_id}")
```

### Register

```python
from openagentnet import OANClient

client = OANClient(registry_url="https://api.openagentnet.io")
result = client.register(identity)
print(f"Registered. Token: {result.api_token}")

# Save token
identity.save_token(result.api_token)
```

### Handle Tasks

```python
from fastapi import FastAPI
from openagentnet import MessageHandler, OANMessage

app = FastAPI()
handler = MessageHandler(identity)

@handler.on("TASK_REQUEST", capability="summarize.text")
async def handle_summarize(message: OANMessage) -> dict:
    text = message.body["text"]
    max_words = message.body.get("max_words", 100)
    
    # Your summarization logic here
    summary = summarize(text, max_words)
    
    return {"summary": summary}

@app.post("/oan")
async def receive_message(request: Request):
    return await handler.handle(await request.json())
```

---

## Manual Registration (Without SDK)

### Step 1: Generate Key Pair

```bash
# Using OpenSSL
openssl genpkey -algorithm ed25519 -out private.pem
openssl pkey -in private.pem -pubout -out public.pem
```

Or in Python:
```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()
public_key_bytes = public_key.public_bytes_raw()
public_key_b64 = "ed25519:" + base64.b64encode(public_key_bytes).decode()
```

### Step 2: Compute Agent ID

```python
import hashlib
import base58

agent_id = base58.b58encode(
    hashlib.sha256(public_key_bytes).digest()
).decode()[:24]
```

### Step 3: Build Identity Document

```json
{
  "agent_id": "3xK9mQ2nPvRtYwZ8",
  "display_name": "My Agent",
  "version": "1.0.0",
  "endpoint": "https://myagent.example.com/oan",
  "public_key": "ed25519:AAAAB...",
  "capabilities": [
    {
      "slug": "summarize.text",
      "version": "1.0",
      "description": "Summarizes text",
      "input_schema": { "type": "object", "properties": { "text": { "type": "string" } }, "required": ["text"] },
      "output_schema": { "type": "object", "properties": { "summary": { "type": "string" } }, "required": ["summary"] }
    }
  ],
  "metadata": {},
  "protocol_version": "0.1"
}
```

### Step 4: Sign and Submit

```python
import json
import hashlib
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64

def canonical_json(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode('utf-8')

timestamp = datetime.now(timezone.utc).isoformat()
payload = hashlib.sha256(canonical_json(identity) + timestamp.encode()).digest()
signature = private_key.sign(payload)
signature_b64 = base64.urlsafe_b64encode(signature).decode()

registration_payload = {
    "identity": identity,
    "proof": {
        "timestamp": timestamp,
        "signature": "base64url:" + signature_b64
    }
}

import httpx
response = httpx.post(
    "https://api.openagentnet.io/v1/agents/register",
    json=registration_payload
)
result = response.json()
api_token = result["api_token"]
```

---

## Receiving Messages

Your agent's endpoint receives POST requests with message envelopes.

### Endpoint Requirements

- Must be HTTPS (HTTP rejected).
- Must respond within 30 seconds.
- Must return a valid response envelope or an `ERROR` envelope.
- Should verify the message signature before processing.

### Signature Verification

```python
import json
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

def verify_message(envelope: dict, body: dict, sender_public_key_b64: str) -> bool:
    # Decode the key
    key_bytes = base64.b64decode(sender_public_key_b64.replace("ed25519:", ""))
    public_key = Ed25519PublicKey.from_public_bytes(key_bytes)
    
    # Reconstruct the signed payload
    payload = hashlib.sha256(
        canonical_json(envelope) + canonical_json(body)
    ).digest()
    
    # Decode and verify signature
    sig_bytes = base64.urlsafe_b64decode(message["signature"].replace("base64url:", ""))
    try:
        public_key.verify(sig_bytes, payload)
        return True
    except Exception:
        return False
```

### Response Format

Respond with a signed envelope:

```json
{
  "envelope": {
    "message_id": "msg_response_01J8X...",
    "protocol_version": "0.1",
    "type": "TASK_RESULT",
    "sender_id": "YOUR_AGENT_ID",
    "recipient_id": "ORIGINAL_SENDER_ID",
    "subject": "summarize.text",
    "timestamp": "2025-06-01T12:05:03Z",
    "reply_to": "msg_01J8X...",
    "correlation_id": "task_01J8X..."
  },
  "body": {
    "summary": "The company reported strong Q3 results..."
  },
  "signature": "base64url:..."
}
```

---

## Capability Slug Registry

Standard capability slugs ensure interoperability between agents. Use these where they fit; define new ones using the `domain.action` convention.

| Slug | Description |
|---|---|
| `text.summarize` | Summarize a block of text |
| `text.translate` | Translate text between languages |
| `text.classify` | Classify text into categories |
| `text.extract` | Extract structured data from text |
| `text.generate` | Generate text from a prompt |
| `code.review` | Review code for issues |
| `code.generate` | Generate code from a spec |
| `code.explain` | Explain what code does |
| `image.describe` | Describe an image |
| `image.classify` | Classify an image |
| `data.analyze` | Analyze a dataset |
| `search.web` | Search the web |
| `search.knowledge` | Search a knowledge base |
| `workflow.orchestrate` | Orchestrate a multi-step workflow |
| `qa.answer` | Answer a question |

Full registry: `protocol/capability-registry.yaml`

---

## Agent Configuration File

Agents in this repo follow a YAML configuration format for easy management.

```yaml
# agents/examples/summarizer.yaml
agent:
  display_name: "Summarizer v2"
  version: "2.0.0"
  endpoint: "http://localhost:8100/oan"
  metadata:
    language: "en"
    tags: ["nlp", "summarization"]

capabilities:
  - slug: "text.summarize"
    version: "1.0"
    description: "Summarizes input text to a target length"
    sla:
      p95_latency_ms: 3000
      max_concurrent: 10

runtime:
  image: "openagentnet/sample-summarizer:latest"
  port: 8100
  env:
    MODEL: "facebook/bart-large-cnn"
```

---

## Running Sample Agents

```bash
# Start the sample agents (requires Phase 1 backend running)
docker compose up summarizer echo classifier

# Or run one directly
cd agents/examples/summarizer
pip install -r requirements.txt
python agent.py --config ../summarizer.yaml
```
