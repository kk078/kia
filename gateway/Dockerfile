FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY ["Gateway.Core/Gateway.Core.csproj", "Gateway.Core/"]
COPY ["Gateway.Api/Gateway.Api.csproj", "Gateway.Api/"]
COPY ["Gateway.Tests/Gateway.Tests.csproj", "Gateway.Tests/"]
COPY ["Gateway.sln", "./"]

RUN dotnet restore

COPY . .

RUN dotnet build -c Release -o /app/build
RUN dotnet publish Gateway.Api/Gateway.Api.csproj -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app

COPY --from=build /app/publish .

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:5000/health || exit 1

ENTRYPOINT ["dotnet", "Gateway.Api.dll"]
