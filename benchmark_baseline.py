import asyncio
import time
import json
from typing import Dict, Any, List
from app.schemas.chat import ChatRequest
from app.agent.orchestrator import agent_orchestrator
from app.agent.router import intent_router
from app.agent.normalizer import intent_normalizer
from app.agent.fuzzy_matcher import fuzzy_intent_matcher
from app.mcp.server import mcp_server
from app.tools.auth import UserAuthContext

TEST_PROMPTS = [
    {"id": 1, "prompt": "Halo", "expected_mode": "GENERAL_CHAT"},
    {"id": 2, "prompt": "Selamat malam", "expected_mode": "GENERAL_CHAT"},
    {"id": 3, "prompt": "Apa itu AI?", "expected_mode": "GENERAL_CHAT"},
    {"id": 4, "prompt": "Berapa progress saya?", "expected_mode": "GROUNDED"},
    {"id": 5, "prompt": "Progres bljr saya berapa?", "expected_mode": "GROUNDED"},
    {"id": 6, "prompt": "Apa hasil assessment saya?", "expected_mode": "GROUNDED"},
    {"id": 7, "prompt": "Rekomendasikan pembelajaran untuk saya", "expected_mode": "GROUNDED"},
    {
        "id": 8,
        "prompt": "Analisis profile, progress, assessment saya dan berikan rekomendasi pembelajaran.",
        "expected_mode": "GROUNDED",
    },
]


async def benchmark_prompt(item: Dict[str, Any]) -> Dict[str, Any]:
    prompt = item["prompt"]
    user_id = 1
    app_name = "owl"
    auth_ctx = UserAuthContext(user_id=user_id, application=app_name)

    # 1. Measure Normalizer
    t0 = time.perf_counter()
    normalized = intent_normalizer.normalize(prompt)
    t_norm = (time.perf_counter() - t0) * 1000

    # 2. Measure Router
    t0 = time.perf_counter()
    intents, candidate_tools = intent_router.classify_intent(prompt)
    t_router = (time.perf_counter() - t0) * 1000

    # 3. Measure Fuzzy Matcher
    t0 = time.perf_counter()
    fuzzy_res = fuzzy_intent_matcher.match_intent(normalized)
    t_fuzzy = (time.perf_counter() - t0) * 1000

    # 4. Measure Individual MCP Tools if any candidates
    mcp_timings = {}
    t_mcp_total = 0.0
    if candidate_tools:
        t0_mcp_tot = time.perf_counter()
        for tool_name in candidate_tools:
            args = {"user_id": user_id}
            if tool_name == "get_learning_recommendations":
                args["limit"] = 5
            t0_tool = time.perf_counter()
            await mcp_server.execute_tool(tool_name, args, auth_context=auth_ctx)
            mcp_timings[tool_name] = round((time.perf_counter() - t0_tool) * 1000, 3)
        t_mcp_total = (time.perf_counter() - t0_mcp_tot) * 1000

    # 5. Measure Full Orchestrator End-to-End
    req = ChatRequest(application=app_name, user_id=user_id, message=prompt)
    t0_e2e = time.perf_counter()
    res = await agent_orchestrator.process_chat(req)
    t_e2e = (time.perf_counter() - t0_e2e) * 1000

    return {
        "id": item["id"],
        "prompt": prompt,
        "intents": [i.value for i in intents],
        "candidate_tools": candidate_tools,
        "tools_used": res.tools_used,
        "normalization_ms": round(t_norm, 3),
        "router_ms": round(t_router, 3),
        "fuzzy_ms": round(t_fuzzy, 3),
        "mcp_total_ms": round(t_mcp_total, 3),
        "mcp_breakdown_ms": mcp_timings,
        "e2e_total_ms": round(t_e2e, 3),
        "answer_preview": res.message[:60] + "..." if len(res.message) > 60 else res.message,
    }


async def main():
    print("=== ESTABLISHING BASELINE BENCHMARK (PHASE 21) ===")
    results = []
    # Warmup run
    await agent_orchestrator.process_chat(ChatRequest(application="owl", user_id=1, message="Halo"))

    # Multi-iteration benchmark (3 iterations for statistical stability)
    for item in TEST_PROMPTS:
        iteration_runs = []
        for _ in range(3):
            r = await benchmark_prompt(item)
            iteration_runs.append(r)

        # Average timings across 3 runs
        avg_r = dict(iteration_runs[0])
        avg_r["normalization_ms"] = round(sum(x["normalization_ms"] for x in iteration_runs) / 3, 3)
        avg_r["router_ms"] = round(sum(x["router_ms"] for x in iteration_runs) / 3, 3)
        avg_r["fuzzy_ms"] = round(sum(x["fuzzy_ms"] for x in iteration_runs) / 3, 3)
        avg_r["mcp_total_ms"] = round(sum(x["mcp_total_ms"] for x in iteration_runs) / 3, 3)
        avg_r["e2e_total_ms"] = round(sum(x["e2e_total_ms"] for x in iteration_runs) / 3, 3)
        results.append(avg_r)

    print(json.dumps(results, indent=2))

    print("\n--- SUMMARY TABLE ---")
    print(f"{'#':<3} | {'Prompt':<45} | {'Router (ms)':<11} | {'MCP (ms)':<10} | {'E2E (ms)':<10} | {'Tools'}")
    print("-" * 105)
    for r in results:
        tools_str = ", ".join(r["tools_used"]) if r["tools_used"] else "None (General Chat)"
        print(f"{r['id']:<3} | {r['prompt']:<45} | {r['router_ms']:<11.3f} | {r['mcp_total_ms']:<10.3f} | {r['e2e_total_ms']:<10.3f} | {tools_str}")


if __name__ == "__main__":
    asyncio.run(main())
