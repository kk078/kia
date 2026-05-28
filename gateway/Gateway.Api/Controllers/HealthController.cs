using Microsoft.AspNetCore.Mvc;
using Gateway.Core.Services;

namespace Gateway.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class HealthController : ControllerBase
{
    private readonly PythonBridgeService _bridge;

    public HealthController(PythonBridgeService bridge)
    {
        _bridge = bridge;
    }

    [HttpGet]
    public async Task<IActionResult> Get()
    {
        var pythonHealthy = await _bridge.HealthCheckAsync();
        return Ok(new
        {
            status = pythonHealthy ? "healthy" : "degraded",
            python_api = pythonHealthy ? "connected" : "disconnected",
            timestamp = DateTime.UtcNow
        });
    }
}
