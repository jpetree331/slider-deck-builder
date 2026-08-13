"""Chalk routes — /api/chalk/*. Projects/conversations CRUD (soft deletes)
and the SSE chat stream. Persistence order per the Chalk brief: the user
message lands BEFORE the stream starts; on abort, whatever accumulated is
persisted. No message content in log lines (divergence rule 6).
"""
import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from starlette.responses import StreamingResponse

from . import chalk_chat, chalk_db, config

logger = logging.getLogger("lantern.chalk.api")

chalk_router = APIRouter(prefix="/chalk")


@chalk_router.get("/health")
def chalk_health():
    return {"ok": True, "default_model": config.CHALK_DEFAULT_MODEL,
            "db_path": str(config.CHALK_DB_PATH)}


# ── projects ────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project name must be non-empty")
        return v.strip()


class PatchProjectRequest(BaseModel):
    name: str | None = None
    instructions: str | None = None
    context: str | None = None


@chalk_router.get("/projects")
def list_projects():
    return {"projects": chalk_db.list_projects()}


@chalk_router.post("/projects")
def create_project(req: CreateProjectRequest):
    return chalk_db.create_project(req.name)


@chalk_router.patch("/projects/{project_id}")
def patch_project(project_id: str, req: PatchProjectRequest):
    project = chalk_db.update_project(
        project_id, name=req.name, instructions=req.instructions,
        context=req.context)
    if project is None:
        raise HTTPException(404, f"project {project_id} not found")
    return project


@chalk_router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    if chalk_db.get_project(project_id) is None:
        raise HTTPException(404, f"project {project_id} not found")
    chalk_db.delete_project(project_id)
    return {"ok": True}


# ── conversations ───────────────────────────────────────────────────────────

class CreateConversationRequest(BaseModel):
    project_id: str
    model: str | None = None


class PatchConversationRequest(BaseModel):
    title: str | None = None
    model: str | None = None

    @field_validator("model")
    @classmethod
    def model_allowed(cls, v):
        if v is not None:
            try:
                chalk_chat.resolve_provider(v)
            except chalk_chat.ChatError as e:
                raise ValueError(str(e))  # Pydantic-shaped → clean 422
        return v


@chalk_router.get("/projects/{project_id}/conversations")
def list_conversations(project_id: str):
    if chalk_db.get_project(project_id) is None:
        raise HTTPException(404, f"project {project_id} not found")
    return {"conversations": chalk_db.list_conversations(project_id)}


@chalk_router.post("/conversations")
def create_conversation(req: CreateConversationRequest):
    if chalk_db.get_project(req.project_id) is None:
        raise HTTPException(404, f"project {req.project_id} not found")
    if req.model is not None:
        try:
            chalk_chat.resolve_provider(req.model)
        except chalk_chat.ChatError as e:
            raise HTTPException(400, str(e))
    return chalk_db.create_conversation(req.project_id, req.model)


@chalk_router.patch("/conversations/{conversation_id}")
def patch_conversation(conversation_id: str, req: PatchConversationRequest):
    conversation = chalk_db.update_conversation(
        conversation_id, title=req.title, model=req.model)
    if conversation is None:
        raise HTTPException(404, f"conversation {conversation_id} not found")
    return conversation


@chalk_router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    if chalk_db.get_conversation(conversation_id) is None:
        raise HTTPException(404, f"conversation {conversation_id} not found")
    chalk_db.delete_conversation(conversation_id)
    return {"ok": True}


@chalk_router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str):
    if chalk_db.get_conversation(conversation_id) is None:
        raise HTTPException(404, f"conversation {conversation_id} not found")
    return {"messages": chalk_db.list_messages(conversation_id)}


# ── chat (SSE over POST) ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: str
    content: str
    model: str | None = None

    @field_validator("content")
    @classmethod
    def content_nonempty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must be non-empty")
        return v


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@chalk_router.post("/chat")
def chat(req: ChatRequest):
    conversation = chalk_db.get_conversation(req.conversation_id)
    if conversation is None:
        raise HTTPException(404, f"conversation {req.conversation_id} not found")
    project = chalk_db.get_project(conversation["project_id"])
    if project is None:
        raise HTTPException(404, "conversation's project is gone")
    model = req.model or conversation["model"] or config.CHALK_DEFAULT_MODEL
    try:
        chalk_chat.resolve_provider(model)
    except chalk_chat.ChatError as e:
        raise HTTPException(e.status, str(e))

    history = chalk_db.list_messages(req.conversation_id)
    system, messages = chalk_chat.build_request(
        project["instructions"], project["context"], history, req.content)

    # persist the user message BEFORE streaming — it must survive any failure
    chalk_db.add_message(req.conversation_id, "user", req.content)

    def event_stream():
        accumulated: list[str] = []
        persisted = False

        def persist_partial():
            nonlocal persisted
            if accumulated and not persisted:
                persisted = True
                return chalk_db.add_message(req.conversation_id, "assistant",
                                            "".join(accumulated))
            return None

        try:
            usage = {"input_tokens": 0, "output_tokens": 0}
            for kind, payload in chalk_chat.stream_chat(model, system, messages):
                if kind == "delta":
                    accumulated.append(payload)
                    yield _sse("delta", {"text": payload})
                else:
                    usage = payload
            message = persist_partial()
            yield _sse("done", {
                "message_id": message["id"] if message else None,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            })
            logger.info("chat turn ok: conversation %s model %s in=%d out=%d",
                        req.conversation_id, model,
                        usage["input_tokens"], usage["output_tokens"])
        except chalk_chat.ChatError as e:
            persist_partial()
            logger.warning("chat turn failed (%d) on conversation %s",
                           e.status, req.conversation_id)
            yield _sse("error", {"status": e.status, "message": str(e)})
        except GeneratorExit:
            # client aborted mid-stream — keep what arrived
            persist_partial()
            logger.info("chat aborted by client: conversation %s (%d chars kept)",
                        req.conversation_id, sum(len(t) for t in accumulated))
            raise
        except Exception:
            persist_partial()
            logger.exception("chat turn crashed on conversation %s",
                             req.conversation_id)
            yield _sse("error", {"status": 500,
                                 "message": "unexpected server error — see api.log"})

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
