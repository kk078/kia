using Microsoft.AspNetCore.Mvc;
using Gateway.Core.Services;

namespace Gateway.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class OrchestratorController : ControllerBase
{
    private readonly OrchestratorService _orchestratorService;

    public OrchestratorController(OrchestratorService orchestratorService)
    {
        _orchestratorService = orchestratorService;
    }

    [HttpPost("run")]
    public async Task<IActionResult> Run([FromBody] RunOrchestratorRequest request)
    {
        var result = await _orchestratorService.RunAsync(request.Goal, request.SessionId);
        return Ok(result);
    }
}

public record RunOrchestratorRequest(string Goal, string SessionId = "default");
