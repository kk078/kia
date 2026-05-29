# KIA Training Kit (Phase 3)

Free, no-rent path to fine-tune KIA on your own data. See `../PHASE3_TRAINING_PLAN.md`
for the full plan and honest expectations.

## Pipeline

```
capture loop  ->  build_dataset.py  ->  kia_finetune.py (Colab T4)  ->  Modelfile -> Ollama
(live, auto)      (merge + teacher)     (free GPU, ~30 min)             (local serve)
```

## 1. Capture (automatic, already running)
Every KIA chat is logged to `data/kia_train.jsonl` (mounted from the container).
Check how much you've banked:
```
curl.exe -s http://localhost:8000/api/v1/training/stats
```

## 2. Build the dataset (local, free)
Merge captured chats (and optionally generate repo Q&A via a teacher):
```
# just merge captured chats
python scripts/build_dataset.py

# also add repo Q&A using Ollama Cloud as the teacher (stays provider-free)
python scripts/build_dataset.py --repo C:\dev\agents ^
  --teacher-url https://ollama.com/v1 --teacher-model gpt-oss:120b --teacher-key <OLLAMA_KEY>
```
Output: `data/kia_dataset.jsonl`

## 3. Fine-tune (free Google Colab / Kaggle T4, ~30 min)
1. New Colab notebook -> Runtime -> Change runtime type -> GPU (T4).
2. Upload `data/kia_dataset.jsonl` and `training/kia_finetune.py`.
3. `!pip install unsloth`
4. `!python kia_finetune.py`  (edit BASE_MODEL/template at the top for qwen vs llama)
5. Download `kia-tuned.gguf`.

## 4. Serve locally
```
# put kia-tuned.gguf next to training/Modelfile, then:
ollama create kia-tuned -f training/Modelfile
# point KIA at it (.env):  DEFAULT_OSS_MODEL=kia-tuned   (or KIA_CODER_MODEL=ollama/kia-tuned)
docker compose -f docker-compose.prod.yml up -d python-api
```
KIA's /v1 layer already routes through whatever model those vars name -- no code change.

## Notes
- Quality > quantity: a few hundred good pairs beat thousands of noisy ones.
- Keep the base model pinned; re-tune periodically as your capture set grows.
- The 3B ceiling persists -- this makes KIA sharper on *your* tasks, not a small Opus.
