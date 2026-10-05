# GraphAide Production Docker Runner (PowerShell)
# Runs GraphAide production stack without docker-compose
# Usage: .\start-graphaide-prod.ps1 -Action start|stop|clean|logs|neo4j-logs

param(
    [string]$Action = "start",
    [string]$NEO4J_PASSWORD = "prod_password",
    [string]$DATA_DIR = ".data",
    [string]$VECTOR_STORE_DIR = ".docs"
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================="
Write-Host "GraphAide Production Docker Runner"
Write-Host "=================================================="
Write-Host ""

function Check-Container-Running {
    param([string]$ContainerName)
    $result = docker ps --filter "name=$ContainerName" --format "{{.Names}}" 2>$null
    return ![string]::IsNullOrEmpty($result)
}

switch ($Action.ToLower()) {
    "start" {
        Write-Host "[*] Starting production stack..."
        Write-Host ""

        # Check if containers are already running
        if (Check-Container-Running "graphaide-prod") {
            Write-Host "[!] GraphAide production is already running!"
            Write-Host "    To stop: .\start-graphaide-prod.ps1 -Action stop"
            exit 0
        }

        if (Check-Container-Running "neo4j-prod") {
            Write-Host "[!] Neo4j production is already running!"
            Write-Host "    To stop: .\start-graphaide-prod.ps1 -Action stop"
            exit 0
        }

        # Create data directories if they don't exist
        if (-not (Test-Path $DATA_DIR)) {
            New-Item -ItemType Directory -Path $DATA_DIR | Out-Null
            Write-Host "[*] Created data directory: $DATA_DIR"
        }
        if (-not (Test-Path $VECTOR_STORE_DIR)) {
            New-Item -ItemType Directory -Path $VECTOR_STORE_DIR | Out-Null
            Write-Host "[*] Created vector store directory: $VECTOR_STORE_DIR"
        }

        # Pull latest image
        Write-Host "[*] Pulling latest image from DockerHub..."
        docker pull pnnl/graphaide:prod

        # Start Neo4j
        Write-Host "[*] Starting Neo4j container..."
        docker run -d --name neo4j-prod `
            -p 17474:7474 `
            -p 17687:7687 `
            -e NEO4J_AUTH=neo4j/$NEO4J_PASSWORD `
            -e "NEO4J_PLUGINS=[`"apoc`"]" `
            -e NEO4J_dbms_security_procedures_unrestricted=apoc.* `
            -v neo4j-prod-data:/data `
            -v neo4j-prod-logs:/logs `
            neo4j:5-community | Out-Null

        # Wait for Neo4j to be ready
        Write-Host "[*] Waiting for Neo4j to be ready..."
        Start-Sleep -Seconds 15

        # Get absolute paths
        $AbsDataDir = (Resolve-Path $DATA_DIR).Path
        $AbsVectorDir = (Resolve-Path $VECTOR_STORE_DIR).Path

        # Start GraphAide
        Write-Host "[*] Starting GraphAide container..."
        docker run -d --name graphaide-prod `
            -p 8000:8000 `
            -e ANTHROPIC_API_KEY=$env:ANTHROPIC_API_KEY `
            -e OPENAI_API_KEY=$env:OPENAI_API_KEY `
            -e GOOGLE_API_KEY=$env:GOOGLE_API_KEY `
            -e AWS_ACCESS_KEY_ID=$env:AWS_ACCESS_KEY_ID `
            -e AWS_SECRET_ACCESS_KEY=$env:AWS_SECRET_ACCESS_KEY `
            -e AWS_DEFAULT_REGION=us-west-2 `
            -e NEO4J_URI=bolt://neo4j-prod:7687 `
            -e NEO4J_USERNAME=neo4j `
            -e NEO4J_PASSWORD=$NEO4J_PASSWORD `
            -e NEO4J_DATABASE=neo4j `
            -e VECTOR_STORE_PATH=/app/chroma `
            -v "$AbsDataDir":/data `
            -v "$AbsVectorDir":/docs `
            --link neo4j-prod:neo4j-prod `
            pnnl/graphaide:prod | Out-Null

        Write-Host "[✓] Production stack started!"
        Write-Host ""
        Write-Host "GraphAide is available at: http://localhost:8000"
        Write-Host "Neo4j is available at: http://localhost:17474"
        Write-Host ""
        Write-Host "View logs: docker logs graphaide-prod"
    }

    "stop" {
        Write-Host "[*] Stopping production stack..."
        docker stop graphaide-prod neo4j-prod 2>$null
        docker rm graphaide-prod neo4j-prod 2>$null
        Write-Host "[✓] Production stack stopped!"
    }

    "clean" {
        Write-Host "[*] Cleaning up production stack and data..."
        docker stop graphaide-prod neo4j-prod 2>$null
        docker rm graphaide-prod neo4j-prod 2>$null
        docker volume rm neo4j-prod-data neo4j-prod-logs 2>$null
        Write-Host "[✓] Production stack cleaned!"
    }

    "logs" {
        Write-Host "[*] GraphAide logs:"
        docker logs -f graphaide-prod
    }

    "neo4j-logs" {
        Write-Host "[*] Neo4j logs:"
        docker logs -f neo4j-prod
    }

    default {
        Write-Host "Usage: .\start-graphaide-prod.ps1 -Action {start|stop|clean|logs|neo4j-logs}"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  start       - Start production stack"
        Write-Host "  stop        - Stop production stack"
        Write-Host "  clean       - Stop and remove all containers and volumes"
        Write-Host "  logs        - View GraphAide logs"
        Write-Host "  neo4j-logs  - View Neo4j logs"
        Write-Host ""
        Write-Host "Environment variables:"
        Write-Host "  ANTHROPIC_API_KEY     - Anthropic API key"
        Write-Host "  OPENAI_API_KEY        - OpenAI API key"
        Write-Host "  GOOGLE_API_KEY        - Google API key"
        Write-Host "  AWS_ACCESS_KEY_ID     - AWS access key"
        Write-Host "  AWS_SECRET_ACCESS_KEY - AWS secret key"
        Write-Host ""
        Write-Host "Optional parameters:"
        Write-Host "  -NEO4J_PASSWORD       - Neo4j password (default: prod_password)"
        Write-Host "  -DATA_DIR             - Local data directory (default: .data)"
        Write-Host "  -VECTOR_STORE_DIR     - Vector store directory (default: .docs)"
        exit 1
    }
}
