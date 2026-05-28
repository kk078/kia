namespace Gateway.Core.Services;

using Gateway.Core.Models;

public class MemoryService
{
    private readonly PythonBridgeService _bridge;

    public MemoryService(PythonBridgeService bridge)
    {
        _bridge = bridge;
    }

    public async Task<string> StoreEpisodeAsync(string content, Dictionary<string, object>? context = null)
    {
        var endpoint = "/api/v1/memory/episodes";
        var data = new { content, context };
        var response = await _bridge.PostAsync(endpoint, data);
        return response;
    }

    public async Task<List<MemoryEpisode>> RetrieveEpisodesAsync(string query, int limit = 10)
    {
        var endpoint = $"/api/v1/memory/episodes?query={Uri.EscapeDataString(query)}&limit={limit}";
        var result = await _bridge.GetAsync<List<MemoryEpisode>>(endpoint);
        return result ?? new List<MemoryEpisode>();
    }

    public async Task<string> StoreFactAsync(string subject, string predicate, string obj, double confidence = 1.0)
    {
        var endpoint = "/api/v1/memory/facts";
        var data = new { subject, predicate, obj, confidence };
        var response = await _bridge.PostAsync(endpoint, data);
        return response;
    }

    public async Task<List<MemoryFact>> QueryFactsAsync(
        string? subject = null,
        string? predicate = null,
        string? obj = null,
        int limit = 10)
    {
        var queryParams = new List<string>();
        if (!string.IsNullOrEmpty(subject)) queryParams.Add($"subject={Uri.EscapeDataString(subject)}");
        if (!string.IsNullOrEmpty(predicate)) queryParams.Add($"predicate={Uri.EscapeDataString(predicate)}");
        if (!string.IsNullOrEmpty(obj)) queryParams.Add($"obj={Uri.EscapeDataString(obj)}");
        queryParams.Add($"limit={limit}");

        var endpoint = $"/api/v1/memory/facts?{string.Join("&", queryParams)}";
        var result = await _bridge.GetAsync<List<MemoryFact>>(endpoint);
        return result ?? new List<MemoryFact>();
    }

    public async Task<string> StoreSkillAsync(string name, string description, List<string> steps)
    {
        var endpoint = "/api/v1/memory/skills";
        var data = new { name, description, steps };
        var response = await _bridge.PostAsync(endpoint, data);
        return response;
    }

    public async Task<List<MemorySkill>> ListSkillsAsync()
    {
        var endpoint = "/api/v1/memory/skills";
        var result = await _bridge.GetAsync<List<MemorySkill>>(endpoint);
        return result ?? new List<MemorySkill>();
    }
}
