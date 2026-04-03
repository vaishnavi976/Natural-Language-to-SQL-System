"""
vanna_setup.py
Initialises the Vanna 2.0 Agent with correct API signatures from official docs.

Correct patterns sourced from:
  https://vanna.ai/docs/configure/gemini/sqlite
  https://vanna.ai/docs/configure/ollama/sqlite  (structural reference)
"""

import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "clinic.db"

_agent = None


def get_agent():
    global _agent
    if _agent is not None:
        return _agent

    # ── Vanna 2.0 imports (exact paths from official docs) ─────────────────
    from vanna import Agent
    from vanna.core.registry import ToolRegistry
    from vanna.core.user import UserResolver, User, RequestContext
    from vanna.tools import RunSqlTool, VisualizeDataTool
    from vanna.tools.agent_memory import (
        SaveQuestionToolArgsTool,
        SearchSavedCorrectToolUsesTool,
        SaveTextMemoryTool,
    )
    from vanna.integrations.sqlite import SqliteRunner
    from vanna.integrations.local.agent_memory import DemoAgentMemory
    from vanna.integrations.google import GeminiLlmService

    # ── 1. LLM ─────────────────────────────────────────────────────────────
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Add it to your .env file."
        )

    llm = GeminiLlmService(
        model="gemini-2.5-flash",
        api_key=google_api_key,
    )

    # ── 2. Database tool  (database_path= is the correct kwarg) ────────────
    db_tool = RunSqlTool(
        sql_runner=SqliteRunner(database_path=DB_PATH)
    )

    # ── 3. Agent memory ────────────────────────────────────────────────────
    agent_memory = DemoAgentMemory(max_items=1000)

    # ── 4. Tool registry  (register_local_tool with access_groups) ─────────
    tools = ToolRegistry()
    tools.register_local_tool(db_tool,                           access_groups=["admin", "user"])
    tools.register_local_tool(SaveQuestionToolArgsTool(),        access_groups=["admin"])
    tools.register_local_tool(SearchSavedCorrectToolUsesTool(),  access_groups=["admin", "user"])
    tools.register_local_tool(SaveTextMemoryTool(),              access_groups=["admin", "user"])
    tools.register_local_tool(VisualizeDataTool(),               access_groups=["admin", "user"])

    # ── 5. User resolver  (resolve_user is async in Vanna 2.0) ─────────────
    class DefaultUserResolver(UserResolver):
        async def resolve_user(self, request_context: RequestContext) -> User:
            return User(
                id="clinic_user",
                email="staff@clinic.local",
                group_memberships=["admin", "user"],
            )

    # ── 6. Agent ───────────────────────────────────────────────────────────
    _agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        user_resolver=DefaultUserResolver(),
        agent_memory=agent_memory,
    )

    return _agent


def get_agent_memory():
    """Return the DemoAgentMemory instance from a running agent."""
    return get_agent().agent_memory