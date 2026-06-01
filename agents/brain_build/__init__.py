"""Agentic build loop — KIA reads/writes files and runs commands in a loop to
accomplish a goal (ReAct), driven by the strong cloud planner model.

Public surface:
  - tools.BuildTools  — workdir-jailed file ops + host shell + url fetch + danger rating
  - agent.BuildAgent  — the step-by-step loop, yielding events for SSE
  - store.build_store  — in-memory session state for pause/resume on gated steps
"""
