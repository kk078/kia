# mypy: ignore-errors
"""LoRA fine-tune of KIA's local coder model on its own winning build traces.

Heavy ML deps (torch/transformers/peft/trl/datasets) are imported lazily, so this
module only pulls them in when you actually train. Install them first:

    uv pip install --python agents/.venv -r agents/requirements-train.txt

then build the dataset and train:

    python -m brain_train.prepare
    python -m brain_train.train_lora

Outputs a LoRA adapter under data/lora_adapter/. A CUDA GPU is strongly recommended;
it will run on CPU but slowly. TRL's API shifts between versions — if an arg is
rejected, check `pip show trl` and adjust SFTConfig accordingly.
"""

from __future__ import annotations

import os

from brain_core.config import settings

BASE_MODEL = os.environ.get("TRAIN_BASE_MODEL", "Qwen/Qwen2.5-Coder-1.5B-Instruct")


def _data_dir() -> str:
    base = settings.training_capture_path or ""
    return os.path.dirname(base) if base else "."


def main() -> int:
    """Run LoRA SFT and save the adapter."""
    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    data_dir = _data_dir()
    train_file = os.path.join(data_dir, "sft", "train.jsonl")
    if not os.path.isfile(train_file):
        print(f"No training data at {train_file}. Run `python -m brain_train.prepare` first.")
        return 1

    ds = load_dataset("json", data_files={"train": train_file}, split="train")
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    use_cuda = torch.cuda.is_available()
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.bfloat16 if use_cuda else torch.float32
    )

    lora = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    out_dir = os.path.join(data_dir, "lora_adapter")
    cfg = SFTConfig(
        output_dir=out_dir,
        num_train_epochs=3,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=5,
        save_strategy="epoch",
        bf16=use_cuda,
        max_length=8192,
    )
    trainer = SFTTrainer(
        model=model, args=cfg, train_dataset=ds, peft_config=lora, processing_class=tok
    )
    trainer.train()
    trainer.save_model(out_dir)
    tok.save_pretrained(out_dir)
    print(f"LoRA adapter saved to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
