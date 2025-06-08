---
title: "Gemini"
version: "0.0.1"
---

```json session-config
{
  "type": "AssistantAgentState",
  "version": "1.0.0",
  "llm_context": {}
}
```

```python setup-script
[include](../preset/gemini.py)
```

## system_message

> You are a helpful AI assistant.

## User

```json msg-metadata
{
  "source": "user",
  "type": "UserMessage"
}
```

> Can you write a Python script that prints numbers 10 to -1?
