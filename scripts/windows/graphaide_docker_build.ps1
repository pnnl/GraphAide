# GraphAide Docker Build and Push Script (PowerShell)
# Rebuilds both production and development images with version tagging
# Optimized with BuildKit for faster builds and better caching
# Optionally pushes to DockerHub

param(
    [string]$Version = "latest",
    [switch]$Push,
    [switch]$Clean,
    [switch]$ProdOnly
)

$ErrorActionPreference = "Stop"
$env:DOCKER_BUILDKIT = 1

$GREEN = "`e[0;32m"
$BLUE = "`e[0;34m"
$YELLOW = "`e[1;33m"
$RED = "`e[0;31m"
$NC = "`e[0m"

Write-Host "=================================================="
Write-Host "GraphAide Docker Build and Push Script"
Write-Host "=================================================="
Write-Host "Version: $Version"
Write-Host "BuildKit: Enabled"
if ($Push) { Write-Host "Mode: BUILD + PUSH" }
else { Write-Host "Mode: BUILD ONLY" }
if ($Clean) { Write-Host "Cleanup: Will prune images after push" }
if ($ProdOnly) { Write-Host "Images: Production only" }
Write-Host ""

# Check Docker
Write-Host -ForegroundColor Blue "[*] Checking Docker..."
try {
    docker ps > $null 2>&1
    Write-Host -ForegroundColor Green "✓ Docker is running"
} catch {
    Write-Host -ForegroundColor Red "✗ Error: Docker is not running"
    exit 1
}
Write-Host ""

# Build production
Write-Host -ForegroundColor Blue "[*] Building production image..."
docker build -t pnnl/graphaide:prod-$Version -t pnnl/graphaide:prod -t pnnl/graphaide:latest .
Write-Host -ForegroundColor Green "✓ Production image built"
Write-Host ""

# Build development
if (-not $ProdOnly) {
    Write-Host -ForegroundColor Blue "[*] Building development image..."
    docker build -f Dockerfile.dev -t pnnl/graphaide:dev-$Version -t pnnl/graphaide:dev .
    Write-Host -ForegroundColor Green "✓ Development image built"
    Write-Host ""
}

# Display images
Write-Host -ForegroundColor Blue "[*] Built images:"
docker images | Select-String "pnnl/graphaide" | Select-Object -First 10
Write-Host ""

# Push if requested
if ($Push) {
    Write-Host "=================================================="
    Write-Host -ForegroundColor Blue "PUSH MODE: Pushing to DockerHub"
    Write-Host "=================================================="
    Write-Host ""

    # Check login
    Write-Host -ForegroundColor Blue "[*] Checking DockerHub authentication..."
    $dockerInfo = docker info 2>&1
    if (-not ($dockerInfo -match "Username:")) {
        Write-Host -ForegroundColor Yellow "[!] Not logged in. Logging in..."
        Write-Host ""
        docker login
    }
    Write-Host -ForegroundColor Green "✓ DockerHub authenticated"
    Write-Host ""

    # Push production
    Write-Host -ForegroundColor Blue "[*] Pushing production images..."
    docker push pnnl/graphaide:prod-$Version
    Write-Host -ForegroundColor Green "  ✓ Pushed prod-$Version"
    docker push pnnl/graphaide:prod
    Write-Host -ForegroundColor Green "  ✓ Pushed prod"
    docker push pnnl/graphaide:latest
    Write-Host -ForegroundColor Green "  ✓ Pushed latest"
    Write-Host ""

    # Push development
    if (-not $ProdOnly) {
        Write-Host -ForegroundColor Blue "[*] Pushing development images..."
        docker push pnnl/graphaide:dev-$Version
        Write-Host -ForegroundColor Green "  ✓ Pushed dev-$Version"
        docker push pnnl/graphaide:dev
        Write-Host -ForegroundColor Green "  ✓ Pushed dev"
        Write-Host ""
    }

    # Logout
    Write-Host -ForegroundColor Blue "[*] Logging out..."
    docker logout 2>$null
    Write-Host -ForegroundColor Green "✓ Logged out"
    Write-Host ""

    # Cleanup
    if ($Clean) {
        Write-Host -ForegroundColor Blue "[*] Cleaning up unused images..."
        docker image prune -f 2>$null
        Write-Host -ForegroundColor Green "✓ Cleanup complete"
        Write-Host ""
    }

    # Summary
    Write-Host "=================================================="
    Write-Host -ForegroundColor Green "Build and Push Complete!"
    Write-Host "=================================================="
    Write-Host ""
    Write-Host "Pushed to DockerHub:"
    Write-Host "  - pnnl/graphaide:prod-$Version"
    Write-Host "  - pnnl/graphaide:prod"
    Write-Host "  - pnnl/graphaide:latest"
    if (-not $ProdOnly) {
        Write-Host "  - pnnl/graphaide:dev-$Version"
        Write-Host "  - pnnl/graphaide:dev"
    }
    Write-Host ""
    Write-Host "Available at: https://hub.docker.com/r/pnnl/graphaide"
    Write-Host ""
} else {
    Write-Host "=================================================="
    Write-Host -ForegroundColor Green "Build Complete!"
    Write-Host "=================================================="
    Write-Host ""
    Write-Host "To push to DockerHub, run:"
    Write-Host "  .\graphaide_docker_build.ps1 -Version $Version -Push"
    Write-Host ""
}
