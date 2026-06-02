# mypy: ignore-errors
"""Merge the trained LoRA adapter into the base model and prep an Ollama model.

Produces a merged HF model under data/kia_coder_merged/ and a Modelfile, then prints
the (external) llama.cpp + Ollama steps to register `kia-coder`. Run after train_lora.

    python -m brain_train.export_ollama
"""

from __future__ import annotations

import os

from brain_core.config import settings

BASE_MODEL = os.environ.get("TRAIN_BASE_MODEL", "Qwen/Qwen2.5-Coder-1.5B-Instruct")


def _data_dir() -> str:
    base = settings.training_capture_path or ""
    return os.path.dirname(base) if base else "."


def main() -> int:
    """Merge adapter into base, save merged model, write a Modelfile."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    data_dir = _data_dir()
    adapter = os.path.join(data_dir, "lora_adapter")
    if not os.path.isdir(adapter):
        print(f"No adapter at {adapter}. Run `python -m brain_train.train_lora` first.")
        return 1

    merged = os.path.join(data_dir, "kia_coder_merged")
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.float16)
    model = PeftModel.from_pretrained(base, adapter).merge_and_unload()
    model.save_pretrained(merged)
    tok.save_pretrained(merged)

    modelfile = os.path.join(data_dir, "Modelfile.kia-coder")
    with open(modelfile, "w", encoding="utf-8") as f:
        f.write(f"FROM {merged}\n")

    print(f"Merged model saved to {merged}")
    print("Register it in Ollama (recent Ollama imports a safetensors dir directly):")
    print(f"  ollama create kia-coder -f {modelfile}")
    print("If your Ollama needs GGUF instead, convert with llama.cpp first:")
    print(f"  python convert_hf_to_gguf.py {merged} --outfile {data_dir}/kia-coder.gguf")
    print(f"  (then set the Modelfile to: FROM {data_dir}/kia-coder.gguf)")
    print("Finally point KIA at it: set DEFAULT_OSS_MODEL=kia-coder (or use as the build base).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
