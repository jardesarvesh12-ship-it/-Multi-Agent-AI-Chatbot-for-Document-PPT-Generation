
"""
orchestrator.py — Multi-Agent Supervisor/Orchestrator using LangGraph.

This is the central brain of the system. It:
1. Receives user messages and file context
2. Plans which agents to invoke
3. Executes agents in the right order
4. Aggregates results
5. Maintains full conversation + artifact state

Agent graph:
  START → supervisor → [doc_analyzer | ppt_analyzer | web_researcher | rag_agent |
                         doc_generator | ppt_generator | validator | editor] → END
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Annotated, Sequence, TypedDict, Optional
from operator import add as list_add

from loguru import logger

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

from langgraph.graph import StateGraph, END, START

from backend.config import settings
from backend.agents.document_analyzer import analyze_document
from backend.agents.ppt_analyzer import analyze_pptx
from backend.agents.web_researcher import research_topic, multi_topic_research
from backend.agents.rag_agent import retrieve_knowledge
from backend.agents.doc_generator import generate_document
from backend.agents.ppt_generator import generate_presentation
from backend.agents.validator import validate_artifact
from backend.agents.editor import edit_artifact
from backend.tools.style_extractor import StyleProfile


# ─────────────────────────────────────────────
# State Schema
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    """Shared state across all agents in the LangGraph graph."""
    # Conversation
    messages: list[dict]                    # {role, content, timestamp}
    session_id: str

    # Uploaded files
    uploaded_files: list[str]               # file paths
    doc_style_profile: Optional[dict]       # extracted from DOCX template
    ppt_style_profile: Optional[dict]       # extracted from PPTX template

    # Research & RAG
    research_results: Optional[dict]
    rag_results: Optional[dict]
    citations: list[str]

    # Generated artifacts
    generated_doc_path: Optional[str]
    generated_ppt_path: Optional[str]
    doc_artifact_id: Optional[str]
    ppt_artifact_id: Optional[str]

    # Validation
    validation_results: list[dict]

    # Agent trace (for UI transparency)
    agent_trace: list[dict]                 # [{agent, action, status, timestamp}]

    # Orchestrator decision
    next_agents: list[str]
    task_type: str                          # generate_doc | generate_ppt | generate_both | edit | analyze | chat
    topic: str
    user_instruction: str

    # Status
    error: Optional[str]
    final_response: Optional[str]


def _trace(state: AgentState, agent: str, action: str, status: str, detail: str = "") -> list[dict]:
    """Append a trace entry."""
    entry = {
        "agent": agent,
        "action": action,
        "status": status,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    logger.info(f"[Trace] [{agent}] {action} → {status}")
    return state.get("agent_trace", []) + [entry]


# ─────────────────────────────────────────────
# Supervisor / Router Node
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor: Analyzes user instruction and decides which agents to run.
    Uses Groq LLM to plan the multi-agent workflow.
    """
    user_msg = state.get("user_instruction", "")
    uploaded = state.get("uploaded_files", [])

    logger.info(f"[Supervisor] Planning for: '{user_msg[:80]}'")

    # Use LLM to classify intent and plan agents
    if GROQ_AVAILABLE:
        client = Groq(api_key=settings.groq_api_key)
        plan_prompt = f"""You are the supervisor of a multi-agent AI system for document generation.

User instruction: "{user_msg}"
Uploaded files: {[Path(f).name for f in uploaded]}

Analyze the request and return a JSON plan:
{{
  "task_type": "generate_both" | "generate_doc" | "generate_ppt" | "edit" | "analyze" | "chat",
  "topic": "the main topic/title for generation",
  "need_web_research": true | false,
  "need_rag": true | false,
  "need_doc_analysis": true | false,
  "need_ppt_analysis": true | false,
  "agents": ["list of agents to run in order"],
  "reasoning": "brief explanation"
}}

Available agents: doc_analyzer, ppt_analyzer, web_researcher, rag_agent, doc_generator, ppt_generator, validator, editor

Rules:
- If user mentions "presentation" or "slides" → include ppt_generator
- If user mentions "document" or "proposal" or "report" → include doc_generator
- If user mentions "research" or "latest" or "trends" → include web_researcher
- If user mentions "edit", "modify", "add", "update", "make" an existing artifact → task_type=edit, include editor
- If uploaded files include DOCX → include doc_analyzer
- If uploaded files include PPTX → include ppt_analyzer
- Always include validator after generation"""

        try:
            from backend.tools.llm_utils import safe_groq_completion
            raw = safe_groq_completion(
                client=client,
                messages=[{"role": "user", "content": plan_prompt}],
                temperature=0.1,
                max_tokens=600,
            )
            from backend.tools.json_utils import parse_llm_json
            plan = parse_llm_json(raw, default={})
            if not isinstance(plan, dict):
                plan = {}
        except Exception as e:
            logger.warning(f"[Supervisor] LLM planning failed, using heuristic: {e}")
            plan = {}
    else:
        plan = {}

    # Heuristic fallback / merge
    msg_lower = user_msg.lower()
    if not plan:
        is_greeting = any(w in msg_lower for w in ["hi", "hello", "hey", "who are you", "what can you do", "help", "introduce"]) and not any(w in msg_lower for w in ["generate", "create", "make", "build", "slide", "ppt", "doc", "presentation", "report"])
        if is_greeting:
            plan = {
                "task_type": "chat",
                "topic": "Assistant Introduction",
                "agents": [],
            }
        else:
            plan = {
                "task_type": "generate_both",
                "topic": user_msg[:60],
                "need_web_research": any(w in msg_lower for w in ["research", "latest", "trends", "current"]),
                "need_rag": True,
                "need_doc_analysis": any(f.endswith(".docx") or f.endswith(".pdf") for f in uploaded),
                "need_ppt_analysis": any(f.endswith(".pptx") for f in uploaded),
                "agents": ["web_researcher", "rag_agent", "doc_generator", "ppt_generator", "validator"],
            }

    task_type = plan.get("task_type", "generate_both")
    topic = plan.get("topic", user_msg[:60])
    agents = plan.get("agents", [])

    # Ensure analysis agents are first if files uploaded
    ordered_agents: list[str] = []
    if plan.get("need_doc_analysis") and any(f.endswith((".docx", ".pdf")) for f in uploaded):
        ordered_agents.append("doc_analyzer")
    if plan.get("need_ppt_analysis") and any(f.endswith(".pptx") for f in uploaded):
        ordered_agents.append("ppt_analyzer")
    if plan.get("need_web_research"):
        ordered_agents.append("web_researcher")
    if plan.get("need_rag"):
        ordered_agents.append("rag_agent")

    # Add generation/editing agents
    for agent in agents:
        if agent not in ordered_agents:
            ordered_agents.append(agent)

    # Ensure validator is last
    if "validator" in ordered_agents:
        ordered_agents.remove("validator")
    if task_type in ("generate_both", "generate_doc", "generate_ppt", "edit"):
        ordered_agents.append("validator")

    logger.info(f"[Supervisor] Plan: type={task_type} | agents={ordered_agents}")

    trace = _trace(state, "Supervisor", "Planning", "done",
                   f"type={task_type} agents={ordered_agents}")

    return {
        **state,
        "task_type": task_type,
        "topic": topic,
        "next_agents": ordered_agents,
        "agent_trace": trace,
    }


# ─────────────────────────────────────────────
# Agent Nodes
# ─────────────────────────────────────────────

def doc_analyzer_node(state: AgentState) -> AgentState:
    """Run Document Analyzer on uploaded DOCX/PDF files."""
    trace = _trace(state, "DocumentAnalyzer", "Analyzing documents", "running")
    results = []
    style_profile = None

    for fp in state.get("uploaded_files", []):
        ext = Path(fp).suffix.lower()
        if ext in (".docx", ".pdf", ".png", ".jpg", ".jpeg"):
            result = analyze_document(fp, index_for_rag=True)
            results.append(result)
            if result.get("style_profile") and ext == ".docx":
                style_profile = result["style_profile"]

    trace = _trace({**state, "agent_trace": trace}, "DocumentAnalyzer",
                   f"Analyzed {len(results)} files", "done")
    return {
        **state,
        "doc_style_profile": style_profile,
        "agent_trace": trace,
    }


def ppt_analyzer_node(state: AgentState) -> AgentState:
    """Run PPT Analyzer on uploaded PPTX files."""
    trace = _trace(state, "PPTAnalyzer", "Analyzing PPTX files", "running")
    style_profile = None

    for fp in state.get("uploaded_files", []):
        if Path(fp).suffix.lower() in (".pptx", ".ppt"):
            result = analyze_pptx(fp, index_for_rag=True)
            if result.get("style_profile"):
                style_profile = result["style_profile"]

    trace = _trace({**state, "agent_trace": trace}, "PPTAnalyzer", "PPTX analysis complete", "done")
    return {**state, "ppt_style_profile": style_profile, "agent_trace": trace}


def web_researcher_node(state: AgentState) -> AgentState:
    """Run Web Research on the topic."""
    topic = state.get("topic", state.get("user_instruction", ""))
    trace = _trace(state, "WebResearcher", f"Searching: {topic[:50]}", "running")

    # Generate up to 3 sub-queries for richer, more specific research
    queries = [topic]
    if len(topic.split()) > 3:
        queries.append(f"latest {topic} trends statistics 2024 2025")
        queries.append(f"{topic} market analysis use cases examples")

    research = multi_topic_research(queries[:3], results_per_topic=5)

    citations = research.get("citations", [])
    trace = _trace({**state, "agent_trace": trace}, "WebResearcher",
                   f"Found {len(research.get('results', []))} web results", "done")
    return {
        **state,
        "research_results": research,
        "citations": citations,
        "agent_trace": trace,
    }


def rag_agent_node(state: AgentState) -> AgentState:
    """Run RAG retrieval on the topic."""
    topic = state.get("topic", state.get("user_instruction", ""))
    trace = _trace(state, "RAGAgent", "Retrieving enterprise knowledge", "running")

    rag = retrieve_knowledge(topic, n_results=5)

    existing_citations = state.get("citations", [])
    rag_citations = rag.get("citations", [])
    all_citations = list(dict.fromkeys(existing_citations + rag_citations))

    trace = _trace({**state, "agent_trace": trace}, "RAGAgent",
                   f"Retrieved {len(rag.get('chunks', []))} chunks", "done")
    return {
        **state,
        "rag_results": rag,
        "citations": all_citations,
        "agent_trace": trace,
    }


def doc_generator_node(state: AgentState) -> AgentState:
    """Run Document Generator."""
    topic = state.get("topic", "")
    trace = _trace(state, "DocGenerator", f"Generating document: {topic[:50]}", "running")

    # Build StyleProfile from extracted data
    style_dict = state.get("doc_style_profile") or state.get("ppt_style_profile") or {}
    style = StyleProfile(**{k: v for k, v in style_dict.items()
                            if k in StyleProfile.__dataclass_fields__}) if style_dict else StyleProfile()

    research_context = ""
    if state.get("research_results"):
        research_context = state["research_results"].get("combined_summary", "")
        # Include ALL web results for maximum content richness
        for r in state["research_results"].get("results", []):
            research_context += f"\n\n=== SOURCE: {r.get('title', '')} ===\n{r.get('content', '')}"

    rag_context = state.get("rag_results", {}).get("context", "") if state.get("rag_results") else ""

    result = generate_document(
        topic=topic,
        research_context=research_context,
        rag_context=rag_context,
        style_profile=style,
        citations=state.get("citations", []),
        artifact_id=state.get("doc_artifact_id"),
    )

    status = "done" if result.get("status") == "success" else "error"
    trace = _trace({**state, "agent_trace": trace}, "DocGenerator",
                   f"Document generated: v{result.get('version', '?')}", status)
    error_msg = result.get("message", "Document generation failed") if status == "error" else None

    return {
        **state,
        "generated_doc_path": result.get("file_path"),
        "doc_artifact_id": result.get("artifact_id"),
        "agent_trace": trace,
        "error": error_msg or state.get("error")
    }


def ppt_generator_node(state: AgentState) -> AgentState:
    """Run PPT Generator."""
    topic = state.get("topic", "")
    trace = _trace(state, "PPTGenerator", f"Generating presentation: {topic[:50]}", "running")

    style_dict = state.get("ppt_style_profile") or state.get("doc_style_profile") or {}
    style = StyleProfile(**{k: v for k, v in style_dict.items()
                            if k in StyleProfile.__dataclass_fields__}) if style_dict else StyleProfile()

    research_context = ""
    if state.get("research_results"):
        research_context = state["research_results"].get("combined_summary", "")
        # Include ALL web results for maximum content richness
        for r in state["research_results"].get("results", []):
            research_context += f"\n\n=== SOURCE: {r.get('title', '')} ===\n{r.get('content', '')}"

    rag_context = state.get("rag_results", {}).get("context", "") if state.get("rag_results") else ""

    slide_count = 10
    user_msg = state.get("user_instruction", "").lower()
    for token in user_msg.split():
        if token.isdigit():
            n = int(token)
            if 5 <= n <= 30:
                slide_count = n
                break

    result = generate_presentation(
        topic=topic,
        research_context=research_context,
        rag_context=rag_context,
        style_profile=style,
        citations=state.get("citations", []),
        artifact_id=state.get("ppt_artifact_id"),
        slide_count=slide_count,
    )

    status = "done" if result.get("status") == "success" else "error"
    trace = _trace({**state, "agent_trace": trace}, "PPTGenerator",
                   f"Presentation generated: {result.get('version', '?')} versions", status)
    error_msg = result.get("message", "Presentation generation failed") if status == "error" else None

    return {
        **state,
        "generated_ppt_path": result.get("file_path"),
        "ppt_artifact_id": result.get("artifact_id"),
        "agent_trace": trace,
        "error": error_msg or state.get("error")
    }


def validator_node(state: AgentState) -> AgentState:
    """Validate all generated artifacts."""
    trace = _trace(state, "Validator", "Validating generated artifacts", "running")
    validation_results = []

    for path_key in ("generated_doc_path", "generated_ppt_path"):
        fp = state.get(path_key)
        if fp and Path(fp).exists():
            result = validate_artifact(fp)
            validation_results.append(result)

    trace = _trace({**state, "agent_trace": trace}, "Validator",
                   f"Validated {len(validation_results)} artifacts", "done")
    return {**state, "validation_results": validation_results, "agent_trace": trace}


def editor_node(state: AgentState) -> AgentState:
    """Apply conversational edits to existing artifacts."""
    instruction = state.get("user_instruction", "")
    trace = _trace(state, "Editor", f"Applying edit: {instruction[:50]}", "running")

    # Determine which artifact to edit
    doc_path = state.get("generated_doc_path")
    ppt_path = state.get("generated_ppt_path")
    msg_lower = instruction.lower()

    extra_context = ""
    if state.get("research_results"):
        extra_context = state["research_results"].get("combined_summary", "")[:1500]
        for r in state["research_results"].get("results", [])[:5]:
            extra_context += f"\n\n{r.get('title', '')}: {r.get('content', '')}"

    edited_doc = None
    edited_ppt = None

    if doc_path and Path(doc_path).exists() and ("document" in msg_lower or "proposal" in msg_lower or not ppt_path):
        result = edit_artifact(doc_path, instruction, state.get("doc_artifact_id", ""), extra_context)
        if result.get("status") == "success":
            edited_doc = result.get("file_path")

    if ppt_path and Path(ppt_path).exists() and ("presentation" in msg_lower or "slide" in msg_lower or not doc_path):
        result = edit_artifact(ppt_path, instruction, state.get("ppt_artifact_id", ""), extra_context)
        if result.get("status") == "success":
            edited_ppt = result.get("file_path")

    trace = _trace({**state, "agent_trace": trace}, "Editor", "Edit complete", "done")
    return {
        **state,
        "generated_doc_path": edited_doc or doc_path,
        "generated_ppt_path": edited_ppt or ppt_path,
        "agent_trace": trace,
    }


def response_composer_node(state: AgentState) -> AgentState:
    """Compose the final user-facing response."""
    task_type = state.get("task_type", "chat")
    topic = state.get("topic", "")
    doc_path = state.get("generated_doc_path")
    ppt_path = state.get("generated_ppt_path")
    citations = state.get("citations", [])
    validation = state.get("validation_results", [])
    error = state.get("error")

    if error:
        response = f"❌ An error occurred: {error}"
    else:
        parts = []

        if task_type in ("generate_both", "generate_doc", "generate_ppt", "edit"):
            parts.append(f"✅ **Task Complete** — *{topic}*\n")

            if doc_path:
                parts.append(f"📄 **Document generated:** `{Path(doc_path).name}`")
            if ppt_path:
                parts.append(f"📊 **Presentation generated:** `{Path(ppt_path).name}`")

            # Validation summary
            for v in validation:
                status_icon = "✅" if v.get("score", 0) >= 70 else "⚠️"
                parts.append(f"{status_icon} Validation score: {v.get('score', 0)}/100 ({Path(v.get('file', '')).suffix})")
                if v.get("suggestions"):
                    parts.append(f"   💡 {v['suggestions'][0]}")

            # Citations
            if citations:
                parts.append(f"\n📚 **Sources ({len(citations)}):**")
                for i, cite in enumerate(citations[:5], 1):
                    parts.append(f"   [{i}] {cite}")
                if len(citations) > 5:
                    parts.append(f"   ... and {len(citations) - 5} more sources.")

        elif task_type == "analyze":
            parts.append(f"✅ **Analysis complete.** Documents and templates have been analyzed and indexed.")
            parts.append(f"   You can now ask me to generate documents or presentations based on them.")

        else:
            parts.append("How can I help you further? You can ask me to:")
            parts.append("- Research a topic and generate a document or presentation")
            parts.append("- Upload templates and generate styled content")
            parts.append("- Edit existing generated files")

        response = "\n".join(parts)

    # Add to messages
    messages = state.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": response,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

    trace = _trace(state, "ResponseComposer", "Final response composed", "done")
    return {**state, "final_response": response, "messages": messages, "agent_trace": trace}


# ─────────────────────────────────────────────
# Graph Routing
# ─────────────────────────────────────────────

def route_to_agents(state: AgentState) -> str:
    """Route to the next unexecuted agent or end based on trace."""
    executed = {t.get("agent") for t in state.get("agent_trace", []) if t.get("status") in ("done", "error")}
    node_to_trace = {
        "doc_analyzer": "DocumentAnalyzer",
        "ppt_analyzer": "PPTAnalyzer",
        "web_researcher": "WebResearcher",
        "rag_agent": "RAGAgent",
        "doc_generator": "DocGenerator",
        "ppt_generator": "PPTGenerator",
        "validator": "Validator",
        "editor": "Editor",
    }
    for agent in state.get("next_agents", []):
        trace_name = node_to_trace.get(agent, agent)
        if trace_name not in executed:
            return agent
    return "response_composer"


# ─────────────────────────────────────────────
# Build Graph
# ─────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Build and compile the LangGraph multi-agent state machine."""
    graph = StateGraph(AgentState)

    # Add all nodes
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("doc_analyzer", doc_analyzer_node)
    graph.add_node("ppt_analyzer", ppt_analyzer_node)
    graph.add_node("web_researcher", web_researcher_node)
    graph.add_node("rag_agent", rag_agent_node)
    graph.add_node("doc_generator", doc_generator_node)
    graph.add_node("ppt_generator", ppt_generator_node)
    graph.add_node("validator", validator_node)
    graph.add_node("editor", editor_node)
    graph.add_node("response_composer", response_composer_node)

    # Edges: START → supervisor → router
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_to_agents,
        {
            "doc_analyzer": "doc_analyzer",
            "ppt_analyzer": "ppt_analyzer",
            "web_researcher": "web_researcher",
            "rag_agent": "rag_agent",
            "doc_generator": "doc_generator",
            "ppt_generator": "ppt_generator",
            "validator": "validator",
            "editor": "editor",
            "response_composer": "response_composer",
        }
    )

    # Each agent routes back to the router (via supervisor logic)
    for node in ["doc_analyzer", "ppt_analyzer", "web_researcher", "rag_agent",
                 "doc_generator", "ppt_generator", "validator", "editor"]:
        graph.add_conditional_edges(
            node,
            route_to_agents,
            {
                "doc_analyzer": "doc_analyzer",
                "ppt_analyzer": "ppt_analyzer",
                "web_researcher": "web_researcher",
                "rag_agent": "rag_agent",
                "doc_generator": "doc_generator",
                "ppt_generator": "ppt_generator",
                "validator": "validator",
                "editor": "editor",
                "response_composer": "response_composer",
            }
        )

    graph.add_edge("response_composer", END)
    return graph.compile()


# Singleton compiled graph
_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ─────────────────────────────────────────────
# Public Interface
# ─────────────────────────────────────────────

def run_orchestrator(
    user_message: str,
    uploaded_files: Optional[list[str]] = None,
    session_id: str = "default",
    prior_state: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Run the multi-agent orchestrator for a user message.

    Args:
        user_message: The user's natural language request.
        uploaded_files: List of uploaded file paths.
        session_id: Session identifier for multi-turn conversations.
        prior_state: Previous state dict (for conversational continuity).

    Returns:
        Updated state dict with final_response, artifact paths, trace, etc.
    """
    graph = get_graph()

    # Build initial state
    messages = (prior_state or {}).get("messages", [])
    messages.append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    })

    initial_state: AgentState = {
        "messages": messages,
        "session_id": session_id,
        "uploaded_files": uploaded_files or (prior_state or {}).get("uploaded_files", []),
        "doc_style_profile": (prior_state or {}).get("doc_style_profile"),
        "ppt_style_profile": (prior_state or {}).get("ppt_style_profile"),
        "research_results": None,
        "rag_results": None,
        "citations": (prior_state or {}).get("citations", []),
        "generated_doc_path": (prior_state or {}).get("generated_doc_path"),
        "generated_ppt_path": (prior_state or {}).get("generated_ppt_path"),
        "doc_artifact_id": (prior_state or {}).get("doc_artifact_id"),
        "ppt_artifact_id": (prior_state or {}).get("ppt_artifact_id"),
        "validation_results": [],
        "agent_trace": [],
        "next_agents": [],
        "task_type": "",
        "topic": "",
        "user_instruction": user_message,
        "error": None,
        "final_response": None,
    }

    logger.info(f"[Orchestrator] Starting session={session_id} | msg='{user_message[:60]}'")

    # Run the graph with a recursion limit to prevent infinite loops
    import concurrent.futures
    TIMEOUT_SECONDS = 480  # 8 minutes — increased for richer research + content generation

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            graph.invoke,
            initial_state,
            {"recursion_limit": 25},
        )
        try:
            result = future.result(timeout=TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            logger.error(f"[Orchestrator] Timed out after {TIMEOUT_SECONDS}s")
            raise RuntimeError(
                f"The request timed out after {TIMEOUT_SECONDS // 60} minutes. "
                "Try a simpler query or disable web research."
            )

    logger.info(f"[Orchestrator] Completed. trace_steps={len(result.get('agent_trace', []))}")
    return result
