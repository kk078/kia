# Open-Source LLM Providers Guide

## Overview

The Secondary Brain system now supports **7 open-source LLM providers** in addition to commercial APIs. All open-source providers run locally or on your own infrastructure, providing:

- **Zero cost** - No API fees
- **Privacy** - Data never leaves your network
- **Customization** - Fine-tune models for your use case
- **No rate limits** - Unlimited requests

## Supported Providers

| Provider | GitHub | Best For | Models |
|----------|--------|----------|--------|
| **Ollama** | [ollama/ollama](https://github.com/ollama/ollama) | General purpose, easiest setup | Llama 3.1, Mistral, CodeLlama, Phi-3, Gemma 2, Qwen 2.5 |
| **llama.cpp** | [ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp) | Maximum performance, GGUF models | Any GGUF model |
| **vLLM** | [vllm-project/vllm](https://github.com/vllm-project/vllm) | High-throughput serving | Llama 3.1, Mixtral, any HuggingFace model |
| **LocalAI** | [mudler/LocalAI](https://github.com/mudler/LocalAI) | OpenAI-compatible API | Multiple formats (GGUF, GPTQ, AWQ) |
| **LM Studio** | [lmstudio-ai](https://lmstudio.ai) | Desktop app with API | Any GGUF model |
| **GPT4All** | [nomic-ai/gpt4all](https://github.com/nomic-ai/gpt4all) | Lightweight, CPU-friendly | Mistral, Llama 2, Falcon |
| **bitnet.cpp** | [microsoft/BitNet](https://github.com/microsoft/BitNet) | 1-bit quantized models | BitNet b1.58 models |

## Quick Start

### Option 1: Ollama (Recommended)

**Easiest setup with Docker:**

```powershell
# Start Ollama (included in docker-compose)
docker-compose up -d ollama

# Pull a model
docker exec -it brain-ollama ollama pull llama3.1

# Test it
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1",
  "prompt": "Hello!"
}'
```

**Or install natively:**

```powershell
# Windows
winget install Ollama.Ollama

# Pull a model
ollama pull llama3.1

# Run
ollama run llama3.1
```

### Option 2: llama.cpp (Maximum Performance)

```bash
# Clone and build
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build
cmake --build build --config Release

# Download a GGUF model (e.g., from HuggingFace)
# https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF

# Start server
./build/bin/server -m models/llama-2-7b-chat.Q4_K_M.gguf --port 8080
```

### Option 3: vLLM (High Throughput)

```bash
# Install
pip install vllm

# Start server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --port 8000
```

### Option 4: LocalAI (OpenAI-Compatible)

```bash
# Docker
docker run -p 8080:8080 localai/localai:latest

# Or with GPU support
docker run -p 8080:8080 --gpus all localai/localai:latest-gpu
```

### Option 5: LM Studio (Desktop App)

1. Download from https://lmstudio.ai
2. Install and launch
3. Download a model from the UI
4. Start local server (default port 1234)

### Option 6: GPT4All (Lightweight)

```bash
# Install
pip install gpt4all

# Or download desktop app from https://gpt4all.io
# Start API server
gpt4all serve --model mistral-7b-instruct
```

### Option 7: bitnet.cpp (1-Bit Models)

```bash
# Clone
git clone https://github.com/microsoft/BitNet
cd BitNet

# Follow setup instructions in README
# Start server with 1-bit model
```

## Configuration

### Environment Variables

All providers are configured via `.env`:

```bash
# Ollama (recommended)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1

# llama.cpp
LLAMACPP_BASE_URL=http://localhost:8080
LLAMACPP_MODEL=local-model

# vLLM
VLLM_BASE_URL=http://localhost:8000
VLLM_MODEL=meta-llama/Llama-3.1-8B-Instruct

# LocalAI
LOCALAI_BASE_URL=http://localhost:8080
LOCALAI_MODEL=gpt-4

# LM Studio
LMSTUDIO_BASE_URL=http://localhost:1234
LMSTUDIO_MODEL=local-model

# GPT4All
GPT4ALL_BASE_URL=http://localhost:4891
GPT4ALL_MODEL=mistral-7b-instruct

# bitnet.cpp
BITNET_BASE_URL=http://localhost:8080
BITNET_MODEL=bitnet-model

# Default provider (used when no commercial API keys are set)
DEFAULT_OSS_PROVIDER=ollama
DEFAULT_OSS_MODEL=llama3.1
```

### Model Strings

Use the format `provider/model` when calling the API:

```python
# Ollama
"ollama/llama3.1"
"ollama/mistral"
"ollama/codellama"

# llama.cpp
"llamacpp/local-model"

# vLLM
"vllm/meta-llama/Llama-3.1-8B-Instruct"

# LocalAI
"localai/gpt-4"

# LM Studio
"lmstudio/local-model"

# GPT4All
"gpt4all/mistral-7b-instruct"

# bitnet.cpp
"bitnet/bitnet-model"
```

## Usage Examples

### Python API

```python
from brain_core.llm import LLMRouter

router = LLMRouter()

# Use Ollama (default)
response = await router.generate(
    prompt="Explain quantum computing",
    task_type="simple"
)

# Explicitly use llama.cpp
response = await router.complete(
    model="llamacpp/local-model",
    messages=[{"role": "user", "content": "Hello!"}]
)

# Use vLLM for high-throughput
response = await router.complete(
    model="vllm/meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Write a poem"}]
)
```

### REST API

```bash
# Use default OSS provider
curl -X POST http://localhost:8000/api/v1/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!", "task_type": "simple"}'

# Specify model explicitly
curl -X POST http://localhost:8000/api/v1/llm/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello!", "model": "ollama/llama3.1"}'
```

## Recommended Models

### General Purpose
- **ollama/llama3.1** - Best overall (8B params, 4.7GB)
- **ollama/mistral** - Fast and capable (7B params, 4.1GB)
- **ollama/qwen2.5** - Excellent multilingual (7B params, 4.4GB)

### Code Generation
- **ollama/codellama** - Specialized for code (7B params, 3.8GB)
- **ollama/deepseek-coder-v2** - State-of-the-art code (16B params, 9GB)

### Fast/Lightweight
- **ollama/phi3** - Microsoft's efficient model (3.8B params, 2.3GB)
- **ollama/gemma2** - Google's lightweight model (2B params, 1.6GB)
- **ollama/llama3.2** - Compact Llama (3B params, 2GB)

### High Quality (Requires More VRAM)
- **ollama/llama3.1:70b** - Large model (70B params, 40GB)
- **vllm/meta-llama/Llama-3.1-70B-Instruct** - Via vLLM (70B params, 40GB)

## Performance Comparison

| Provider | Throughput | Latency | VRAM Usage | Best For |
|----------|-----------|---------|------------|----------|
| Ollama | Medium | Low | Medium | General use |
| llama.cpp | High | Very Low | Low | Maximum speed |
| vLLM | Very High | Low | High | Production serving |
| LocalAI | Medium | Medium | Medium | OpenAI compatibility |
| LM Studio | Low | Medium | Medium | Desktop use |
| GPT4All | Medium | Medium | Low | CPU-only systems |
| bitnet.cpp | High | Low | Very Low | 1-bit models |

## Docker Integration

Ollama is included in both `docker-compose.yml` and `docker-compose.prod.yml`:

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: brain-ollama
  ports:
    - "11434:11434"
  volumes:
    - ollama-data:/root/.ollama
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

**Note:** GPU support requires NVIDIA Container Toolkit. For CPU-only, remove the `deploy` section.

## Troubleshooting

### Ollama not responding
```bash
# Check if running
docker ps | grep ollama

# View logs
docker logs brain-ollama

# Restart
docker-compose restart ollama
```

### Model not found
```bash
# List available models (Ollama)
ollama list

# Pull a model
ollama pull llama3.1
```

### Out of memory
- Use a smaller model (e.g., `phi3` instead of `llama3.1`)
- Reduce context window size
- Use quantized models (Q4_K_M instead of Q8_0)

### Slow inference
- Enable GPU acceleration
- Use llama.cpp or vLLM for better performance
- Reduce batch size

## Migration from Commercial APIs

The system automatically falls back to open-source providers when commercial API keys are not set:

```python
# If ANTHROPIC_API_KEY is empty, uses DEFAULT_OSS_PROVIDER
response = await router.generate(prompt="Hello", task_type="simple")
```

To force open-source usage:

```bash
# In .env
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEFAULT_OSS_PROVIDER=ollama
DEFAULT_OSS_MODEL=llama3.1
```

## Cost Comparison

| Provider | Cost per 1M tokens | Monthly (1M tokens/day) |
|----------|-------------------|------------------------|
| Ollama | $0.00 | $0.00 |
| llama.cpp | $0.00 | $0.00 |
| vLLM | $0.00 | $0.00 |
| Anthropic Claude 3.5 Sonnet | $3.00-$15.00 | $90-$450 |
| OpenAI GPT-4 | $10.00-$30.00 | $300-$900 |
| OpenAI GPT-3.5 | $0.50-$1.50 | $15-$45 |

**Savings:** Running open-source models can save $45-$900+ per month depending on usage.

## Resources

- [Ollama Models](https://ollama.ai/library)
- [HuggingFace Models](https://huggingface.co/models)
- [TheBloke GGUF Models](https://huggingface.co/TheBloke)
- [llama.cpp Documentation](https://github.com/ggerganov/llama.cpp)
- [vLLM Documentation](https://docs.vllm.ai/)

## Support

For issues with specific providers:
- Ollama: https://github.com/ollama/ollama/issues
- llama.cpp: https://github.com/ggerganov/llama.cpp/issues
- vLLM: https://github.com/vllm-project/vllm/issues
- LocalAI: https://github.com/mudler/LocalAI/issues
- GPT4All: https://github.com/nomic-ai/gpt4all/issues
- bitnet.cpp: https://github.com/microsoft/BitNet/issues
