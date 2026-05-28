using Microsoft.AspNetCore.Mvc;
using Gateway.Core.Services;
using Gateway.Core.Models;

namespace Gateway.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class MemoryController : ControllerBase
{
    private readonly MemoryService _memoryService;

    public MemoryController(MemoryService memoryService)
    {
        _memoryService = memoryService;
    }

    [HttpPost("episodes")]
    public async Task<IActionResult> StoreEpisode([FromBody] StoreEpisodeRequest request)
    {
        var result = await _memoryService.StoreEpisodeAsync(request.Content, request.Context);
        return Ok(result);
    }

    [HttpGet("episodes")]
    public async Task<IActionResult> RetrieveEpisodes([FromQuery] string query, [FromQuery] int limit = 10)
    {
        var episodes = await _memoryService.RetrieveEpisodesAsync(query, limit);
        return Ok(episodes);
    }

    [HttpPost("facts")]
    public async Task<IActionResult> StoreFact([FromBody] StoreFactRequest request)
    {
        var result = await _memoryService.StoreFactAsync(
            request.Subject,
            request.Predicate,
            request.Object,
            request.Confidence);
        return Ok(result);
    }

    [HttpGet("facts")]
    public async Task<IActionResult> QueryFacts(
        [FromQuery] string? subject,
        [FromQuery] string? predicate,
        [FromQuery] string? obj,
        [FromQuery] int limit = 10)
    {
        var facts = await _memoryService.QueryFactsAsync(subject, predicate, obj, limit);
        return Ok(facts);
    }

    [HttpPost("skills")]
    public async Task<IActionResult> StoreSkill([FromBody] StoreSkillRequest request)
    {
        var result = await _memoryService.StoreSkillAsync(
            request.Name,
            request.Description,
            request.Steps);
        return Ok(result);
    }

    [HttpGet("skills")]
    public async Task<IActionResult> ListSkills()
    {
        var skills = await _memoryService.ListSkillsAsync();
        return Ok(skills);
    }
}

public record StoreEpisodeRequest(string Content, Dictionary<string, object>? Context);
public record StoreFactRequest(string Subject, string Predicate, string Object, double Confidence = 1.0);
public record StoreSkillRequest(string Name, string Description, List<string> Steps);
