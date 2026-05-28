namespace Gateway.Core.Models;

public record MemoryEpisode(
    string Id,
    string Content,
    Dictionary<string, object>? Context,
    DateTime Timestamp
);

public record MemoryFact(
    string Id,
    string Subject,
    string Predicate,
    string Object,
    double Confidence,
    DateTime Timestamp
);

public record MemorySkill(
    string Id,
    string Name,
    string Description,
    List<string> Steps,
    DateTime CreatedAt
);

public record AgentResponse(
    string Content,
    Dictionary<string, object>? Metadata,
    DateTime Timestamp
);

public record TaskClassification(
    string Framework,
    string Complexity,
    string Reasoning
);

public record LlmResponse(
    string Response
);

public record StatusResponse(
    string Status,
    string Timestamp
);
