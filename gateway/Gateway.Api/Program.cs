using Gateway.Core.Services;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

// Register services
var pythonApiUrl = builder.Configuration.GetValue<string>("PythonApi:Url") ?? "http://localhost:8000";
builder.Services.AddSingleton(new PythonBridgeService(pythonApiUrl));
builder.Services.AddScoped<MemoryService>();
builder.Services.AddScoped<OrchestratorService>();
builder.Services.AddScoped<LlmService>();
builder.Services.AddScoped<KnowledgeService>();

// Add CORS
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader();
    });
});

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors();
app.MapControllers();

app.Run();
