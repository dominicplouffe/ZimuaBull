import json
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone
from openai import OpenAI, OpenAIError

from .tools import ChatToolset, ToolExecutionError, aggregate_tool_results

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are ZimuaBull AI, a professional investment assistant.

Capabilities:
- Explain market activity, company fundamentals, and technical indicators using the data supplied via tools.
- Analyse user portfolios, holdings, risk, and performance.
- Run scenario analyses when asked (e.g., hypothetical price moves).
- Backtest trading strategies using the provided backtester tool before giving conclusions.
- For ambiguous questions, ask clarifying questions before proceeding.
- Always cite the data source (e.g., "Based on ZimuaBull daily prices") when summarising results.
- Return concise, actionable insights; highlight risks and next steps.

Guidelines:
- If a tool call fails, apologise and suggest alternative actions.
- Respect the numbers returned by tools; do not invent unseen data.
- Preserve conversation context and reference previous user goals when helpful.
- Format every assistant reply in valid Markdown. Use headings, bullet lists, and tables where they improve readability. Inline data with backticks when referencing symbols, indicators, or numeric metrics. Do not return plain text outside Markdown formatting.
"""


class ChatOrchestrator:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL

    def run(
        self,
        user,
        conversation,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        toolset = ChatToolset(user=user)
        tool_results: List[Dict[str, Any]] = []
        status_updates: List[str] = []

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        for msg in conversation.messages.order_by("created_at"):
            messages.append({"role": msg.role, "content": msg.content})

        if context:
            messages.append({"role": "system", "content": f"Context hints: {json.dumps(context)}"})

        messages.append({"role": "user", "content": user_message})

        openai_tools = toolset.tool_specs()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
            )
        except OpenAIError as exc:
            logger.exception("OpenAI initial completion failed")
            return {
                "reply": "I ran into an issue reaching the analysis engine. Please try again shortly.",
                "analysis": {"symbols": [], "comparisons": [], "portfolios": [], "scenarios": [], "backtests": [], "simulations": [], "warnings": [str(exc)]},
                "messages": [],
                "status_updates": status_updates,
                "tool_results": [],
            }

        while True:
            choice = response.choices[0]
            message = choice.message

            if message and getattr(message, "tool_calls", None):
                # Log assistant tool request
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": tool_call.type,
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in message.tool_calls
                        ],
                    }
                )

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        arguments = {}

                    try:
                        result = toolset.execute(tool_name, arguments)
                        status_updates.append(f"Executed tool {tool_name}")
                        if status_callback:
                            try:
                                status_callback(f"Executed tool {tool_name}")
                            except Exception:  # pylint: disable=broad-except
                                logger.exception("Status callback failed for tool %s", tool_name)
                        tool_results.append({"tool": tool_name, "arguments": arguments, "result": result})
                        tool_content = json.dumps(result)
                    except ToolExecutionError as exec_err:
                        logger.warning("Tool %s failed: %s", tool_name, exec_err)
                        error_payload = {"error": str(exec_err), "tool": tool_name}
                        tool_content = json.dumps(error_payload)
                        tool_results.append({"tool": tool_name, "arguments": arguments, "result": error_payload})
                        status_updates.append(f"Tool {tool_name} failed: {exec_err}")
                        if status_callback:
                            try:
                                status_callback(f"Tool {tool_name} failed: {exec_err}")
                            except Exception:  # pylint: disable=broad-except
                                logger.exception("Status callback failed during tool error for %s", tool_name)

                    messages.append(
                        {
                            "role": "tool",
                            "content": tool_content,
                            "tool_call_id": tool_call.id,
                        }
                    )

                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=openai_tools,
                    )
                    continue
                except OpenAIError as exc:
                    logger.exception("OpenAI completion failed after tool call")
                    return {
                        "reply": "I encountered a problem while processing the analysis. Please try again.",
                        "analysis": {"symbols": [], "comparisons": [], "portfolios": [], "scenarios": [], "backtests": [], "simulations": [], "warnings": [str(exc)]},
                        "messages": [],
                        "status_updates": status_updates,
                        "tool_results": tool_results,
                    }

            assistant_reply = message.content if message else ""
            analysis = aggregate_tool_results([tr["result"] for tr in tool_results if isinstance(tr.get("result"), dict)])

            return {
                "reply": assistant_reply,
                "analysis": analysis,
                "status_updates": status_updates,
                "tool_results": tool_results,
            }
