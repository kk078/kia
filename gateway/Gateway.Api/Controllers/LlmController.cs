using Microsoft.AspNetCore.Mvc;
using Gateway.Core.Services;

namespace Gateway.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class LlmController : ControllerBase
{
    private readonly LlmService _llmService;

    public LlmController(LlmService llmService)
    {
        _llmService = llmService;
    }

    [HttpPost("generate")]
    public async Task<IActionResult> Generate([FromBody] GenerateRequest request)
    {
        var result = await _llmService.GenerateAsync(request.Prompt, request.TaskType, request.Model);
        return Ok(new { response = result });
    }

    [HttpGet("route")]
    public async Task<IActionResult> Route([FromQuery] string taskType)
    {
        var classification = await _llmService.ClassifyTaskAsync(taskType);
        return Ok(classification);
    }
}

public record GenerateRequest(string Prompt, string TaskType = "simple", string? Model = null);
