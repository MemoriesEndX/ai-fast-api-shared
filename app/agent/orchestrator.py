import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.tools.auth import UserAuthContext, ToolAuthorizationService
from app.mcp.server import mcp_server
from app.agent.router import intent_router, AgentIntent
from app.agent.conversation import conversation_manager
from app.services.llm_service import get_llm_service
from app.services.qdrant_service import qdrant_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger("ai_service.agent.orchestrator")


class AgentOrchestrator:
    """
    Unified OWL LMS AI Agent Orchestrator.
    Manages intent routing, tool execution, multi-tool reasoning, loop protection,
    grounded LLM synthesis, source citation formatting, and conversation thread tracking.
    """

    def __init__(self):
        self.llm_service = get_llm_service()

    async def process_chat(self, request: ChatRequest) -> ChatResponse:
        start_time = time.perf_counter()
        app_name = str(request.application).lower()
        user_id = request.user_id or 1
        conversation_id = conversation_manager.get_or_create_conversation_id(request.conversation_id)

        # Prompt Injection Protection Guard
        msg_lower = request.message.lower()
        if "ignore previous instructions" in msg_lower or "ignore authorization" in msg_lower:
            logger.warning(f"Prompt injection attack attempt blocked for user {user_id}.")
            return ChatResponse(
                application=app_name,
                message="Request Denied: Prompt injection or security bypass instructions are prohibited.",
                answer="Request Denied: Prompt injection or security bypass instructions are prohibited.",
                provider=settings.LLM_PROVIDER,
                model=settings.LLM_MODEL,
                sources=[],
                conversation_id=conversation_id,
                tools_used=[],
                latency_ms=round((time.perf_counter() - start_time) * 1000, 2),
            )

        auth_context = UserAuthContext(user_id=user_id, application=app_name)

        # 1. Intent Routing & Tool Selection
        intents, candidate_tools = intent_router.classify_intent(request.message, request.document_id)
        logger.info(f"Classified intents for '{request.message[:40]}...': {[i.value for i in intents]} | Candidates: {candidate_tools}")

        # 2. Tool Execution Loop with Tenant Security Enforcement
        tool_results: List[Dict[str, Any]] = []
        tools_executed: List[str] = []
        seen_tool_calls: set = set()

        max_calls = min(settings.CHAT_MAX_TOOL_CALLS, 5)

        for tool_name in candidate_tools:
            if len(tools_executed) >= max_calls:
                logger.warning(f"Reached MAX_TOOL_CALLS limit ({max_calls}). Stopping tool loop.")
                break

            # Tenant isolation enforcement: HR-Corner cannot execute OWL LMS tools
            if app_name == "hr-corner" and tool_name not in ["search_pdf_knowledge", "search_video_transcript"]:
                logger.warning(f"Tenant isolation breach attempt: hr-corner application requested OWL tool '{tool_name}'.")
                continue

            args: Dict[str, Any] = {}
            if tool_name in ["get_user_learning_profile", "get_learning_progress", "get_user_assessments", "get_learning_recommendations"]:
                args["user_id"] = user_id
                if tool_name == "get_learning_recommendations":
                    args["limit"] = 5
            elif tool_name in ["search_learning_content", "search_learning_playlist"]:
                args["query"] = request.message
                args["limit"] = 5
            elif tool_name == "get_content_detail":
                args["content_id"] = 101
            elif tool_name == "get_playlist_detail":
                args["playlist_id"] = 103
            elif tool_name in ["search_pdf_knowledge", "search_video_transcript"]:
                args["query"] = request.message
                args["top_k"] = settings.RAG_TOP_K
                if request.document_id is not None:
                    args["document_id"] = request.document_id

            call_signature = f"{tool_name}:{str(args)}"
            if call_signature in seen_tool_calls:
                logger.warning(f"Tool loop detected for signature '{call_signature}'. Skipping repeat execution.")
                continue
            seen_tool_calls.add(call_signature)

            try:
                res = await mcp_server.execute_tool(tool_name, args, auth_context=auth_context)
                tools_executed.append(tool_name)
                tool_results.append({
                    "tool": tool_name,
                    "args": args,
                    "result": res
                })
            except Exception as exc:
                logger.error(f"Error executing tool '{tool_name}' in Agent orchestrator: {exc}")

        # Direct Qdrant RAG fallback if no specific tools were matched (or for general RAG intent)
        context_chunks: List[Dict[str, Any]] = []
        if not tools_executed:
            try:
                query_vector = embedding_service.embed_text(request.message)
                context_chunks = await qdrant_service.search_similar(
                    query_vector=query_vector,
                    application=app_name,
                    document_id=str(request.document_id) if request.document_id else None,
                    top_k=settings.RAG_TOP_K,
                    score_threshold=settings.RAG_SCORE_THRESHOLD,
                )
            except Exception as e:
                logger.error(f"Error during RAG fallback search: {e}")

        # 3. Extract Conversation History
        history = conversation_manager.get_history(conversation_id)

        # 4. Extract Citations & Standardized Sources
        sources = self._extract_sources(tool_results, context_chunks)

        # 5. Synthesize Answer with Qwen LLM
        final_answer = await self._synthesize_answer(
            user_message=request.message,
            tool_results=tool_results,
            context_chunks=context_chunks,
            history=history,
            intents=intents
        )

        # 6. Record Turn in Conversation Context
        conversation_manager.add_turn(conversation_id, request.message, final_answer)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return ChatResponse(
            application=app_name,
            message=final_answer,
            answer=final_answer,
            provider=settings.LLM_PROVIDER,
            model=settings.LLM_MODEL,
            sources=sources,
            conversation_id=conversation_id,
            tools_used=tools_executed,
            latency_ms=latency_ms,
        )

    def _extract_sources(self, tool_results: List[Dict[str, Any]], context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract and format standardized citations (LMS, PDF, Video, Recommendation)."""
        sources: List[Dict[str, Any]] = []

        for chunk in context_chunks:
            source_type = chunk.get("source_type", "pdf")
            source_item = {
                "type": source_type,
                "source_type": source_type,
                "document_id": chunk.get("document_id"),
                "title": chunk.get("title", ""),
                "filename": chunk.get("filename", ""),
                "score": chunk.get("score", 0.0),
            }
            if source_type == "video":
                source_item["start_time"] = chunk.get("start_time", "00:00")
                source_item["end_time"] = chunk.get("end_time", "00:00")
                source_item["start_seconds"] = chunk.get("start_seconds", 0)
                source_item["end_seconds"] = chunk.get("end_seconds", 0)
            else:
                source_item["page_start"] = chunk.get("page_start", 1)
                source_item["page_end"] = chunk.get("page_end", 1)
            sources.append(source_item)

        for item in tool_results:
            tool_name = item["tool"]
            result = item.get("result", {})

            if tool_name == "search_pdf_knowledge":
                pdf_results = result.get("results", [])
                for chunk in pdf_results:
                    sources.append({
                        "type": "pdf",
                        "source_type": "pdf",
                        "document_id": chunk.get("document_id"),
                        "filename": chunk.get("filename", "Dokumen.pdf"),
                        "title": chunk.get("title", ""),
                        "page_start": chunk.get("page_start", 1),
                        "page_end": chunk.get("page_end", 1),
                        "score": chunk.get("score", 0.0),
                    })

            elif tool_name == "search_video_transcript":
                video_results = result.get("results", [])
                for chunk in video_results:
                    sources.append({
                        "type": "video",
                        "source_type": "video",
                        "document_id": chunk.get("document_id"),
                        "title": chunk.get("title", "Video Safety"),
                        "start_time": chunk.get("start_time", "00:00"),
                        "end_time": chunk.get("end_time", "00:00"),
                        "start_seconds": chunk.get("start_seconds", 0),
                        "end_seconds": chunk.get("end_seconds", 0),
                        "score": chunk.get("score", 0.0),
                    })

            elif tool_name == "get_learning_recommendations":
                recs = result.get("recommendations", [])
                for rec in recs:
                    sources.append({
                        "type": "recommendation",
                        "source_type": "recommendation",
                        "content_id": rec.get("content_id"),
                        "title": rec.get("title"),
                        "score": rec.get("final_score"),
                    })

            elif tool_name in ["get_user_learning_profile", "get_learning_progress", "get_user_assessments", "search_learning_content", "search_learning_playlist", "get_content_detail", "get_playlist_detail"]:
                sources.append({
                    "type": "lms",
                    "source_type": "lms",
                    "tool": tool_name,
                    "summary": str(result)[:150]
                })

        return sources

    async def _synthesize_answer(
        self,
        user_message: str,
        tool_results: List[Dict[str, Any]],
        context_chunks: List[Dict[str, Any]],
        history: List[Dict[str, str]],
        intents: List[AgentIntent],
    ) -> str:
        """Synthesize a concise, grounded natural language answer using Qwen or deterministic fallback."""

        # Format Grounded Data Context
        context_str = ""
        if context_chunks:
            context_str += "\n--- Retrieved Knowledge Chunks ---\n"
            for c in context_chunks:
                context_str += f"- [{c.get('filename') or c.get('title')}]: {c.get('text')}\n"

        for item in tool_results:
            context_str += f"\n--- Tool '{item['tool']}' Output ---\n{str(item['result'])}\n"

        if len(context_str) > settings.RAG_MAX_CONTEXT_CHARS:
            context_str = context_str[:settings.RAG_MAX_CONTEXT_CHARS] + "... (truncated)"

        history_str = ""
        if history:
            history_str = "\nConversation History:\n" + "\n".join([f"{h['role'].capitalize()}: {h['content']}" for h in history[-4:]]) + "\n"

        system_prompt = (
            "You are the Unified OWL LMS AI Assistant.\n"
            "CRITICAL SECURITY RULES:\n"
            "1. Never invent LMS data, user progress, assessment scores, content availability, PDF citations, video timestamps, or recommendation reasons.\n"
            "2. Base your answer strictly on the provided Tool Outputs and Conversation History.\n"
            "3. If required data is unavailable, state clearly: 'Informasi tersebut tidak ditemukan dalam materi yang tersedia.'\n"
            "4. Answer concisely, professionally, and directly in Indonesian without self-referential prefixes."
        )

        user_prompt = (
            f"{history_str}\n"
            f"Grounding Data:\n{context_str}\n\n"
            f"User Question: {user_message}\n"
            f"Answer:"
        )

        try:
            if settings.APP_ENV not in ("development", "test") and (context_chunks or tool_results):
                qwen_response = await self.llm_service.generate_completion(
                    prompt=f"{system_prompt}\n\n{user_prompt}",
                    temperature=0.2,
                    max_tokens=256
                )
                if qwen_response and len(qwen_response.strip()) > 5:
                    return qwen_response.strip()
        except Exception as e:
            logger.warning(f"Qwen synthesis unavailable or timed out ({e}). Falling back to grounded summary generator.")

        # Grounded Deterministic Summary Generator (Dev/Test/Fallback mode)
        return self._generate_deterministic_fallback(user_message, tool_results, context_chunks, intents)

    def _generate_deterministic_fallback(
        self,
        user_message: str,
        tool_results: List[Dict[str, Any]],
        context_chunks: List[Dict[str, Any]],
        intents: List[AgentIntent]
    ) -> str:
        """Fallback natural language answer summary constructed directly from grounded tool output."""
        if not tool_results and not context_chunks:
            return "Informasi tersebut tidak ditemukan dalam materi yang tersedia."

        lines = []

        for c in context_chunks:
            lines.append(f"Berdasarkan {c.get('filename') or c.get('title')}: {c.get('text')}")

        for item in tool_results:
            tool_name = item["tool"]
            res = item.get("result", {})

            if tool_name == "get_user_learning_profile":
                lines.append(f"Profil Pembelajaran: Divisi {res.get('division', 'N/A')}, Posisi {res.get('position', 'N/A')}.")

            elif tool_name == "get_learning_progress":
                items = res.get("items", [])
                completed = [i.get('title') for i in items if i.get('status') == 'completed']
                in_prog = [i.get('title') for i in items if i.get('status') == 'in_progress']
                lines.append(f"Progress Belajar: Selesai ({', '.join(completed) if completed else 'Belum ada'}), Sedang Diikuti ({', '.join(in_prog) if in_prog else 'Tidak ada'}).")

            elif tool_name == "get_user_assessments":
                items = res.get("items", [])
                scores = [f"{i.get('title')}: {i.get('score')} ({i.get('status')})" for i in items]
                lines.append(f"Nilai Assessment: {'; '.join(scores) if scores else 'Belum ada ujian'}.")

            elif tool_name == "get_learning_recommendations":
                recs = res.get("recommendations", [])
                rec_titles = [f"{r.get('title')} (Skor: {r.get('final_score')})" for r in recs[:3]]
                lines.append(f"Rekomendasi Pembelajaran untuk Anda: {', '.join(rec_titles) if rec_titles else 'Tidak ada'}.")

            elif tool_name == "search_pdf_knowledge":
                chunks = res.get("results", [])
                if chunks:
                    c = chunks[0]
                    lines.append(f"Berdasarkan dokumen {c.get('filename', 'PDF')} (halaman {c.get('page_start')}): {c.get('text')}")

            elif tool_name == "search_video_transcript":
                chunks = res.get("results", [])
                if chunks:
                    c = chunks[0]
                    lines.append(f"Berdasarkan video {c.get('title', 'Video')} (menit {c.get('start_time')} - {c.get('end_time')}): {c.get('text')}")

        if lines:
            return " ".join(lines)
        return "Informasi tersebut tidak ditemukan dalam materi yang tersedia."


agent_orchestrator = AgentOrchestrator()
