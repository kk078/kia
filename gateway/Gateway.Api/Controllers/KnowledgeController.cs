using Microsoft.AspNetCore.Mvc;
using Gateway.Core.Services;

namespace Gateway.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class KnowledgeController : ControllerBase
{
    private readonly KnowledgeService _knowledgeService;

    public KnowledgeController(KnowledgeService knowledgeService)
    {
        _knowledgeService = knowledgeService;
    }

    [HttpPost("index")]
    public async Task<IActionResult> IndexDocument([FromBody] IndexDocumentRequest request)
    {
        var result = await _knowledgeService.IndexDocumentAsync(request.Content, request.Source);
        return Ok(result);
    }

    [HttpPost("query")]
    public async Task<IActionResult> Query([FromBody] QueryRequest request)
    {
        var result = await _knowledgeService.QueryAsync(request.Question, request.Model);
        return Ok(new { answer = result });
    }
}

public record IndexDocumentRequest(string Content, string Source);
public record QueryRequest(string Question, string? Model = null);
