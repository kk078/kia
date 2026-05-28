namespace Gateway.Core.Services;

using Gateway.Core.Models;

public class OrchestratorService
{
    private readonly PythonBridgeService _bridge;

    public OrchestratorService(PythonBridgeService bridge)
    {
        _bridge = bridge;
    }

    public async Task<AgentResponse> RunAsync(string goal, string sessionId = "default")
    {
        var endpoint = "/api/v1/orchestrator/run";
        var data = new { goal, session_id = sessionId };
        var result = await _bridge.PostAsync<object, AgentResponse>(endpoint, data);
        return result ?? new AgentResponse("", null, DateTime.UtcNow);
    }
}

public class LlmService
{
    private readonly PythonBridgeService _bridge;

    public LlmService(PythonBridgeService bridge)
    {
        _bridge = bridge;
    }

    public async Task<string> GenerateAsync(string prompt, string taskType = "simple", string? model = null)
    {
        var endpoint = "/api/v1/llm/generate";
        var data = new { prompt, task_type = taskType, model };
        var result = await _bridge.PostAsync<object, LlmResponse>(endpoint, data);
        return result?.Response ?? "";
    }

    public async Task<TaskClassification> ClassifyTaskAsync(string task)
    {
        var endpoint = $"/api/v1/llm/route?task_type={Uri.EscapeDataString(task)}";
        var result = await _bridge.GetAsync<TaskClassification>(endpoint);
        return result ?? new TaskClassification("unknown", "unknown", "Failed to classify");
    }
}

public class KnowledgeService
{
    private readonly PythonBridgeService _bridge;

    public KnowledgeService(PythonBridgeService bridge)
    {
        _bridge = bridge;
    }

    public async Task<string> IndexDocumentAsync(string content, string source)
    {
        var endpoint = "/api/v1/knowledge/index";
        var data = new { content, source };
        var response = await _bridge.PostAsync(endpoint, data);
        return response;
    }

    public async Task<string> QueryAsync(string question, string? model = null)
    {
        var endpoint = "/api/v1/knowledge/rag";
        var data = new { question, model };
        var result = await _bridge.PostAsync<object, LlmResponse>(endpoint, data);
        return result?.Response ?? "";
    }
}
