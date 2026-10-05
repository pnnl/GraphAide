#!/bin/bash
# GraphAide Production Docker Runner
# Runs GraphAide production stack without docker-compose
# Usage: ./start-graphaide-prod.sh [start|stop|logs]

set -e

ACTION=${1:-start}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-prod_password}
DATA_DIR=${DATA_DIR:-.data}
VECTOR_STORE_DIR=${VECTOR_STORE_DIR:-.docs}

echo "=================================================="
echo "GraphAide Production Docker Runner"
echo "=================================================="

case $ACTION in
  start)
    echo "[*] Starting production stack..."
    
    # Check if containers are already running
    if docker ps | grep -q graphaide-prod; then
      echo "[!] GraphAide production is already running!"
      echo "    To stop: ./start-graphaide-prod.sh stop"
      exit 0
    fi
    
    if docker ps | grep -q neo4j-prod; then
      echo "[!] Neo4j production is already running!"
      echo "    To stop: ./start-graphaide-prod.sh stop"
      exit 0
    fi
    
    # Create data directories if they don't exist
    mkdir -p "$DATA_DIR" "$VECTOR_STORE_DIR"
    
    # Pull latest image
    echo "[*] Pulling latest image from DockerHub..."
    docker pull pnnl/graphaide:prod
    
    # Start Neo4j
    echo "[*] Starting Neo4j container..."
    docker run -d --name neo4j-prod \
      -p 17474:7474 \
      -p 17687:7687 \
      -e NEO4J_AUTH=neo4j/$NEO4J_PASSWORD \
      -e NEO4J_PLUGINS='["apoc"]' \
      -e NEO4J_dbms_security_procedures_unrestricted=apoc.* \
      -v neo4j-prod-data:/data \
      -v neo4j-prod-logs:/logs \
      neo4j:5-community
    
    # Wait for Neo4j to be ready
    echo "[*] Waiting for Neo4j to be ready..."
    sleep 15
    
    # Start GraphAide
    echo "[*] Starting GraphAide container..."
    docker run -d --name graphaide-prod \
      -p 8000:8000 \
      -e ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-} \
      -e OPENAI_API_KEY=${OPENAI_API_KEY:-} \
      -e GOOGLE_API_KEY=${GOOGLE_API_KEY:-} \
      -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-} \
      -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-} \
      -e AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-west-2} \
      -e NEO4J_URI=bolt://neo4j-prod:7687 \
      -e NEO4J_USERNAME=neo4j \
      -e NEO4J_PASSWORD=$NEO4J_PASSWORD \
      -e NEO4J_DATABASE=${NEO4J_DATABASE:-neo4j} \
      -e VECTOR_STORE_PATH=/app/chroma \
      -v "$(pwd)/$DATA_DIR":/data \
      -v "$(pwd)/$VECTOR_STORE_DIR":/docs \
      --link neo4j-prod:neo4j-prod \
      pnnl/graphaide:prod
    
    echo "[✓] Production stack started!"
    echo ""
    echo "GraphAide is available at: http://localhost:8000"
    echo "Neo4j is available at: http://localhost:17474"
    echo ""
    echo "View logs: docker logs graphaide-prod"
    ;;

  stop)
    echo "[*] Stopping production stack..."
    docker stop graphaide-prod neo4j-prod 2>/dev/null || true
    docker rm graphaide-prod neo4j-prod 2>/dev/null || true
    echo "[✓] Production stack stopped!"
    ;;

  clean)
    echo "[*] Cleaning up production stack and data..."
    docker stop graphaide-prod neo4j-prod 2>/dev/null || true
    docker rm graphaide-prod neo4j-prod 2>/dev/null || true
    docker volume rm neo4j-prod-data neo4j-prod-logs 2>/dev/null || true
    echo "[✓] Production stack cleaned!"
    ;;

  logs)
    echo "[*] GraphAide logs:"
    docker logs -f graphaide-prod
    ;;

  neo4j-logs)
    echo "[*] Neo4j logs:"
    docker logs -f neo4j-prod
    ;;

  *)
    echo "Usage: $0 {start|stop|clean|logs|neo4j-logs}"
    echo ""
    echo "Commands:"
    echo "  start       - Start production stack"
    echo "  stop        - Stop production stack"
    echo "  clean       - Stop and remove all containers and volumes"
    echo "  logs        - View GraphAide logs"
    echo "  neo4j-logs  - View Neo4j logs"
    echo ""
    echo "Environment variables:"
    echo "  ANTHROPIC_API_KEY     - Anthropic API key"
    echo "  OPENAI_API_KEY        - OpenAI API key"
    echo "  GOOGLE_API_KEY        - Google API key"
    echo "  AWS_ACCESS_KEY_ID     - AWS access key"
    echo "  AWS_SECRET_ACCESS_KEY - AWS secret key"
    echo "  NEO4J_PASSWORD        - Neo4j password (default: prod_password)"
    echo "  DATA_DIR              - Local data directory (default: .data)"
    echo "  VECTOR_STORE_DIR      - Vector store directory (default: .docs)"
    exit 1
    ;;
esac
