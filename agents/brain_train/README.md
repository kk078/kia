# KIA build-agent fine-tuning

Turn KIA's own *winning* build traces into a LoRA fine-tune of the local coder model,
so KIA's own brain gets better at the `think -> act -> verify` loop and leans on the
Claude escalation tier less over time.

## How the corpus grows
Every successful `/agent` build and every passing eval scenario appends its full
transcript to `data/kia_build_traces.jsonl` automatically (see `brain_build/agent.py`).
The more you build and run `kia_eval.ps1`, the bigger the corpus. Fine-tuning is only
worthwhile once you have a few hundred unique examples.

## Pipeline

1. **Prepare the dataset** (stdlib only, instant):
   ```
   python -m brain_train.prepare
   ```
   Reads `data/kia_build_traces.jsonl`, dedupes, splits, and writes
   `data/sft/train.jsonl` + `data/sft/val.jsonl`. Prints how many examples you have and
   warns if it's too few.

2. **Install the training deps** (one time, heavy — torch/transformers are already
   present; this adds peft/trl/datasets/accelerate):
   ```
   uv pip install --python agents/.venv -r agents/requirements-train.txt
   ```

3. **Train the LoRA adapter** (GPU strongly recommended):
   ```
   python -m brain_train.train_lora
   ```
   Base model defaults to `Qwen/Qwen2.5-Coder-1.5B-Instruct` (override with
   `TRAIN_BASE_MODEL`). Saves the adapter to `data/lora_adapter/`.

4. **Merge + register in Ollama**:
   ```
   python -m brain_train.export_ollama
   ```
   Merges the adapter into the base model under `data/kia_coder_merged/`, writes a
   `Modelfile`, and prints the `ollama create kia-coder` command (plus the llama.cpp
   GGUF fallback if your Ollama needs it).

5. **Point KIA at the tuned model**: set `DEFAULT_OSS_MODEL=kia-coder` in `.env`, or use
   it as the build agent's base model, and re-run `kia_eval.ps1` to measure whether the
   tuned local brain now clears scenarios that previously needed Claude escalation.

## Notes
- This is a scaffold: TRL/PEFT APIs shift between versions; if `train_lora.py` rejects an
  arg, check the installed versions and adjust `SFTConfig`.
- `train_lora.py` and `export_ollama.py` carry `# mypy: ignore-errors` since the heavy ML
  libs aren't part of the type-checked runtime. `prepare.py` is fully typed.
- Everything writes under `data/` (gitignored) — no model weights or datasets are committed.
