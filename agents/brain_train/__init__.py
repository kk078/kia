"""Local fine-tuning pipeline for KIA's build agent.

Turns KIA's own winning build traces (data/kia_build_traces.jsonl) into a LoRA
fine-tune of the local coder model, so KIA's own brain improves at the agentic
think -> act -> verify format over time and needs Claude escalation less often.

Stages:
  - prepare.py       traces -> SFT chat dataset (stdlib only)
  - train_lora.py    LoRA SFT on the base coder model (heavy ML deps, lazy)
  - export_ollama.py merge adapter -> HF model -> Ollama model (heavy deps, lazy)

See brain_train/README.md for the end-to-end runbook.
"""
