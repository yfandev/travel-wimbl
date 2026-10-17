"""Crusoe Managed Inference client for NVIDIA Nemotron models (setup spec §1, §4–6).

Retries 429/5xx with backoff and jitter, caps concurrency, times out each call, and writes a run record for every call.
Structured output and tool calls fall back to prompt-instructed JSON when the endpoint does not support them.
"""
import asyncio
import json
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any
import httpx
from openai import APIStatusError, APITimeoutError, AsyncOpenAI, BadRequestError, InternalServerError, RateLimitError
from pydantic import BaseModel, ValidationError
from wimbl.config import settings
from wimbl.integrations.models import model_for
from wimbl.runlog import RunLog, estimate_cost

MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 1.0  # 1s, 2s, 4s between the four attempts

class LLMError(RuntimeError): pass
class LLMUnavailable(LLMError): pass
class LLMTimeout(LLMError): pass
class StructuredOutputError(LLMError): pass

@dataclass
class LLMResult:
    text: str
    model: str | None
    tool_calls: list[dict] = field(default_factory=list)  # [{"name": str, "arguments": dict}]
    parsed: Any = None
    demo: bool = False
    record: dict = field(default_factory=dict)

def strip_reasoning(text: str) -> str:
    """Drop <think>…</think> blocks some reasoning models emit before the answer."""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()

def extract_json(text: str) -> Any:
    """Parse the first JSON object or array in a model reply, tolerating code fences and reasoning blocks."""
    text = strip_reasoning(text)
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    if fenced: text = fenced.group(1).strip()
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
    if not starts: raise ValueError("No JSON found in model output.")
    return json.JSONDecoder().raw_decode(text[min(starts):])[0]

def _schema_prompt(schema: type[BaseModel]) -> str:
    return ("Respond with only a JSON object, no prose, matching this JSON Schema:\n"
            + json.dumps(schema.model_json_schema(), separators=(",", ":")))

def _action_prompt(tools: list[dict]) -> str:
    specs = [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
              "parameters": t["function"].get("parameters", {})} for t in tools]
    return ('To use a tool, respond with only a JSON object {"tool": <name>, "args": {...}} and nothing else. '
            "Available tools:\n" + json.dumps(specs, separators=(",", ":")))

def validate_tool_call(name: str, arguments: Any, tools: list[dict]) -> dict:
    spec = next((t["function"] for t in tools if t["function"]["name"] == name), None)
    if spec is None: raise ValueError(f"Model called unknown tool {name!r}.")
    if isinstance(arguments, str): arguments = json.loads(arguments or "{}")
    if not isinstance(arguments, dict): raise ValueError("Tool arguments must be a JSON object.")
    missing = [k for k in spec.get("parameters", {}).get("required", []) if k not in arguments]
    if missing: raise ValueError(f"Tool {name!r} is missing required arguments: {missing}.")
    return {"name": name, "arguments": arguments}

class CrusoeClient:
    """One client per process. `capabilities[model]` caches what the endpoint supports once a call has shown it."""
    def __init__(self, *, http_client: httpx.AsyncClient | None = None, runlog: RunLog | None = None,
                 sleep=asyncio.sleep, max_concurrency: int | None = None):
        self.enabled = bool(settings.crusoe_api_key)
        self.client = AsyncOpenAI(api_key=settings.crusoe_api_key or "missing", base_url=settings.crusoe_base_url,
                                  max_retries=0, http_client=http_client) if self.enabled else None
        self.runlog = runlog or RunLog()
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(max_concurrency or settings.crusoe_max_concurrency)
        self.capabilities: dict[str, dict[str, bool]] = {}

    async def chat(self, role: str, messages: list[dict], *, run_id: str, prompt_version: str = "v0",
                   tools: list[dict] | None = None, response_format: dict | None = None,
                   temperature: float = 0.2, max_tokens: int | None = None, model: str | None = None,
                   timeout: float | None = None) -> LLMResult:
        """One logged model call. `model` overrides routing only for benchmarks and smoke tests; `timeout` overrides the
        per-call default for slow, rare calls (e.g. a long reasoning call on Super)."""
        model = model or model_for(role)
        record = dict(run_id=run_id, agent_role=role, model_id_requested=model, prompt_version=prompt_version)
        if not self.client:
            if settings.wimbl_demo_mode:
                return LLMResult(text="", model=None, demo=True, record=self.runlog.write(**record, status="demo",
                                 error="CRUSOE_API_KEY not set; no model call made."))
            raise LLMUnavailable("CRUSOE_API_KEY is missing and demo mode is disabled.")
        kwargs = dict(model=model, messages=messages, temperature=temperature, timeout=timeout or settings.crusoe_timeout_s)
        if tools: kwargs["tools"] = tools
        if response_format: kwargs["response_format"] = response_format
        if max_tokens: kwargs["max_tokens"] = max_tokens
        started, attempt = time.monotonic(), 0
        async with self._semaphore:
            while True:
                attempt += 1
                try:
                    response = await self.client.chat.completions.create(**kwargs)
                    break
                except (RateLimitError, InternalServerError) as exc:
                    if attempt >= MAX_ATTEMPTS: self._fail(record, started, attempt, exc, "error"); raise LLMError(_describe(exc)) from exc
                    delay = BACKOFF_BASE_S * 2 ** (attempt - 1)
                    await self._sleep(delay + random.uniform(0, delay / 4))
                except APITimeoutError as exc:
                    self._fail(record, started, attempt, exc, "timeout"); raise LLMTimeout(_describe(exc)) from exc
                except APIStatusError as exc:  # other 4xx: auth, validation, unsupported parameter — never retried
                    self._fail(record, started, attempt, exc, "error"); raise
        message, usage = response.choices[0].message, response.usage
        calls = [{"name": c.function.name, "arguments": c.function.arguments} for c in (message.tool_calls or [])]
        in_t, out_t = (usage.prompt_tokens, usage.completion_tokens) if usage else (None, None)
        row = self.runlog.write(**record, model_id_returned=response.model, input_tokens=in_t, output_tokens=out_t,
            latency_ms=round((time.monotonic() - started) * 1000), cost_estimate_usd=estimate_cost(model, in_t, out_t),
            tool_calls=[c["name"] for c in calls], status="ok", attempts=attempt)
        return LLMResult(text=message.content or "", model=response.model, tool_calls=calls, record=row)

    def _fail(self, record: dict, started: float, attempt: int, exc: Exception, status: str) -> None:
        self.runlog.write(**record, latency_ms=round((time.monotonic() - started) * 1000), status=status,
                          error=_describe(exc), attempts=attempt)

    async def structured(self, role: str, messages: list[dict], schema: type[BaseModel], *, run_id: str,
                         prompt_version: str = "v0", **kwargs) -> LLMResult:
        """JSON matching `schema`. Uses response_format when supported, else prompt-instructed JSON; one repair retry."""
        model = kwargs.get("model") or model_for(role)
        caps = self.capabilities.setdefault(model, {})
        result = None
        if caps.get("response_format", True):
            fmt = {"type": "json_schema", "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}
            try:
                result = await self.chat(role, messages, run_id=run_id, prompt_version=prompt_version, response_format=fmt, **kwargs)
                caps["response_format"] = True
            except BadRequestError:
                caps["response_format"] = False
        if result is None:
            prompted = [{"role": "system", "content": _schema_prompt(schema)}, *messages]
            result = await self.chat(role, prompted, run_id=run_id, prompt_version=prompt_version, **kwargs)
        if result.demo: return result
        try:
            result.parsed = schema.model_validate(extract_json(result.text))
            return result
        except (ValueError, ValidationError) as first_error:
            repair = [{"role": "system", "content": _schema_prompt(schema)}, *messages,
                      {"role": "assistant", "content": result.text[:4000]},
                      {"role": "user", "content": f"That reply was invalid: {str(first_error)[:500]}. Return only the corrected JSON."}]
            fixed = await self.chat(role, repair, run_id=run_id, prompt_version=prompt_version + "+repair", **kwargs)
            try:
                fixed.parsed = schema.model_validate(extract_json(fixed.text))
                return fixed
            except (ValueError, ValidationError) as exc:
                raise StructuredOutputError(f"Output did not match {schema.__name__} after one repair: {str(exc)[:300]}") from exc

    async def act(self, role: str, messages: list[dict], tools: list[dict], *, run_id: str,
                  prompt_version: str = "v0", **kwargs) -> LLMResult:
        """Ask for tool calls. Native tool calling when supported, else the JSON action protocol. Calls are validated."""
        model = kwargs.get("model") or model_for(role)
        caps = self.capabilities.setdefault(model, {})
        if caps.get("tools", True):
            try:
                result = await self.chat(role, messages, run_id=run_id, prompt_version=prompt_version, tools=tools, **kwargs)
                if result.demo: return result
                if result.tool_calls:
                    caps["tools"] = True
                    result.tool_calls = [validate_tool_call(c["name"], c["arguments"], tools) for c in result.tool_calls]
                    return result
            except BadRequestError:
                caps["tools"] = False
        prompted = [{"role": "system", "content": _action_prompt(tools)}, *messages]
        result = await self.chat(role, prompted, run_id=run_id, prompt_version=prompt_version + "+action", **kwargs)
        if result.demo: return result
        try:
            action = extract_json(result.text)
            result.tool_calls = [validate_tool_call(action.get("tool"), action.get("args", {}), tools)] if isinstance(action, dict) and action.get("tool") else []
        except ValueError:
            result.tool_calls = []  # a plain-text answer is a valid "no tool needed" reply
        return result

def _describe(exc: Exception) -> str:
    """Error text for logs: status and type only, never request objects or headers."""
    status = getattr(exc, "status_code", None)
    return f"{type(exc).__name__}" + (f" (HTTP {status})" if status else "") + f": {str(exc)[:200]}"
