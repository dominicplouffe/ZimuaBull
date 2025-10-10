import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from django.http import StreamingHttpResponse

from asgiref.sync import sync_to_async

from zimuabull.models import ConversationMessage


async def sse_event_stream(orchestrator, user, conversation, message: str, context: dict[str, Any]) -> AsyncGenerator[str]:
    """Async generator yielding SSE-formatted chunks with live updates."""

    loop = asyncio.get_running_loop()
    status_queue: asyncio.Queue[str] = asyncio.Queue()

    def status_callback(msg: str) -> None:
        try:
            asyncio.run_coroutine_threadsafe(status_queue.put(msg), loop)
        except RuntimeError:
            # Loop may be closed; ignore since stream is ending
            pass

    yield 'data: {"status": "started"}\n\n'

    async def run_orchestrator():
        result = await sync_to_async(orchestrator.run)(user, conversation, message, context, status_callback=status_callback)
        await sync_to_async(ConversationMessage.objects.create)(
            conversation=conversation,
            role="assistant",
            content=result.get("reply", ""),
            context_data={
                "analysis": result.get("analysis", {}),
                "status_updates": result.get("status_updates", []),
                "tool_results": result.get("tool_results", []),
            },
        )
        await status_queue.put(json.dumps({
            "type": "final",
            "reply": result.get("reply"),
            "analysis": result.get("analysis", {}),
            "status_updates": result.get("status_updates", []),
            "tool_results": result.get("tool_results", []),
        }))
        await status_queue.put("__end__")

    task = asyncio.create_task(run_orchestrator())

    while True:
        update = await status_queue.get()
        if update == "__end__":
            break
        try:
            payload = json.loads(update)
            if payload.get("type") == "final":
                yield f"data: {json.dumps(payload)}\n\n"
            else:
                yield f"data: {json.dumps({'status': payload})}\n\n"
        except json.JSONDecodeError:
            yield f"data: {json.dumps({'status': update})}\n\n"

    await task
    yield "event: end\ndata: {}\n\n"


def sse_response(orchestrator, user, conversation, message: str, context: dict[str, Any]) -> StreamingHttpResponse:
    async def async_stream():
        async for chunk in sse_event_stream(orchestrator, user, conversation, message, context):
            yield chunk

    response = StreamingHttpResponse(async_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
