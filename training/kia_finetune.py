#!/usr/bin/env python3
"""KIA LoRA fine-tune (Unsloth QLoRA) -- run on a free Google Colab / Kaggle T4 GPU.

Quick start (Colab):
  1) Runtime -> Change runtime type -> GPU (T4).
  2) Upload data/kia_dataset.jsonl (from scripts/build_dataset.py).
  3) pip install unsloth
  4) python kia_finetune.py
  5) Download kia-tuned.gguf, then on your laptop:  ollama create kia-tuned -f Modelfile

This trains a small LoRA adapter on your (instruction, response) pairs and exports a
GGUF you import into Ollama. Inference then runs 100% locally on your 2GB box.
"""

# ---- Config (edit these) -------------------------------------------------------
BASE_MODEL = "unsloth/Qwen2.5-Coder-1.5B-Instruct"  # or "unsloth/Llama-3.2-3B-Instruct"
DATASET = "kia_dataset.jsonl"      # OpenAI 'messages' JSONL from build_dataset.py
OUTPUT_GGUF = "kia-tuned"          # produces kia-tuned.gguf
MAX_SEQ_LEN = 2048
EPOCHS = 2
LEARNING_RATE = 2e-4
LORA_RANK = 16
# -------------------------------------------------------------------------------

from unsloth import FastLanguageModel  # noqa: E402
from unsloth.chat_templates import get_chat_template  # noqa: E402
from datasets import load_dataset  # noqa: E402
from trl import SFTTrainer, SFTConfig  # noqa: E402

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=MAX_SEQ_LEN,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_RANK,
    lora_alpha=LORA_RANK * 2,
    lora_dropout=0.0,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth",
)

# Pick the chat template that matches the base family ("qwen-2.5" or "llama-3.1").
tokenizer = get_chat_template(tokenizer, chat_template="qwen-2.5")


def fmt(batch):
    texts = [
        tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=False)
        for m in batch["messages"]
    ]
    return {"text": texts}


ds = load_dataset("json", data_files=DATASET, split="train").map(fmt, batched=True)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=ds,
    args=SFTConfig(
        dataset_text_field="text",
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs=EPOCHS,
        learning_rate=LEARNING_RATE,
        logging_steps=5,
        optim="adamw_8bit",
        output_dir="outputs",
        max_seq_length=MAX_SEQ_LEN,
    ),
)
trainer.train()

# Export a quantized GGUF for Ollama (q4_k_m is a good size/quality balance on 2GB).
model.save_pretrained_gguf(OUTPUT_GGUF, tokenizer, quantization_method="q4_k_m")
print(f"\nDone. Download {OUTPUT_GGUF}.gguf and run:  ollama create kia-tuned -f Modelfile")
