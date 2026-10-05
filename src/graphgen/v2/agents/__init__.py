"""GraphAide Agents Module.

All agents inherit from GraphAideAgent and can be converted to LangChain tools
via the `as_tool()` method for use with ReAct agents.

Agent Tool Output Keys Reference:
---------------------------------
| Agent                        | tool_output_keys                                    |
|------------------------------|-----------------------------------------------------|
| ExtractorAgent               | ["nodes", "edges", "messages"]                      |
| EdgesLoaderAgent             | ["messages", "is_valid"]                            |
| EdgeTable2TextGeneratorAgent | ["graph_answer_text", "messages"]                   |
| EmbeddingProjectorAgent      | ["embedding_file_path", "messages"]                 |
| EmbeddingVisualizerAgent     | ["embedding_file_path", "messages"]                 |
| IntentPredictorAgent         | ["intent_scores"]                                   |
| Neo4jLoaderAgent             | ["nodes", "edges", "messages", "is_valid"]          |
| Neo4jPostProcessorAgent      | ["messages", "is_valid"]                            |
| Neo4jQueryRunnerAgent        | ["graph_answer", "messages", "is_valid"]            |
| Nodes4EdgesLoaderAgent       | ["messages", "is_valid"]                            |
| NodesLoaderAgent             | ["messages", "is_valid"]                            |
| OntologyLoaderAgent          | ["rag_context", "messages"] |
| QuestionGraphGeneratorAgent  | ["graph_question", "messages"]                      |
| SimpleAgent                  | ["raw_text", "messages"]                            |
| SimpleRAGAgent               | ["answer", "messages"]                              |
| TextAugmentorAgent           | ["extended_QA_pairs"]                               |
| VectorDBLoaderAgent          | ["messages"]                                        |
"""

from .base import GraphAideAgent
from .AgentManager import AgentFactory
from .chunktrackeragent import ChunkTrackerAgent
from .chunkgraphloadagent import ChunkGraphLoadAgent
from .extractor import ExtractorAgent, ExtractorToolSchema
from .edgesloader import EdgesLoaderAgent, EdgesLoaderToolSchema
from .nodesloader import NodesLoaderAgent, NodesLoaderToolSchema
from .neo4jloader import Neo4jLoaderAgent, Neo4jLoaderToolSchema
from .neo4jpostprocessor import Neo4jPostProcessorAgent, Neo4jPostProcessorToolSchema
from .neo4jqueryrunner import Neo4jQueryRunnerAgent, Neo4jQueryRunnerToolSchema
from .nodes4edgesloader import Nodes4EdgesLoaderAgent, Nodes4EdgesLoaderToolSchema
from .intentpredictor import IntentPredictorAgent, IntentPredictorToolSchema
from .ontologyloader import OntologyLoaderAgent, OntologyLoaderToolSchema
from .questiongraphgenerator import QuestionGraphGeneratorAgent, QuestionGraphGeneratorToolSchema
from .simpleagent import SimpleAgent, SimpleAgentToolSchema
from .simplerag import SimpleRAGAgent, SimpleRAGToolSchema
from .textaugmentor import TextAugmentorAgent, TextAugmentorToolSchema
from .edgetable2textgenerator import EdgeTable2TextGeneratorAgent, EdgeTable2TextGeneratorToolSchema
from .embeddingprojector import EmbeddingProjectorAgent, EmbeddingProjectorToolSchema
from .embeddingvisualizer import EmbeddingVisualizerAgent, EmbeddingVisualizerToolSchema
from .vectordbloader import VectorDBLoaderAgent, VectorDBLoaderToolSchema


__all__ = [
    "GraphAideAgent",
    "AgentFactory",
    "ChunkTrackerAgent",
    "ChunkGraphLoadAgent",
    "ExtractorAgent",
    "ExtractorToolSchema",
    "EdgesLoaderAgent",
    "EdgesLoaderToolSchema",
    "NodesLoaderAgent",
    "NodesLoaderToolSchema",
    "Neo4jLoaderAgent",
    "Neo4jLoaderToolSchema",
    "Neo4jPostProcessorAgent",
    "Neo4jPostProcessorToolSchema",
    "Neo4jQueryRunnerAgent",
    "Neo4jQueryRunnerToolSchema",
    "Nodes4EdgesLoaderAgent",
    "Nodes4EdgesLoaderToolSchema",
    "IntentPredictorAgent",
    "IntentPredictorToolSchema",
    "OntologyLoaderAgent",
    "OntologyLoaderToolSchema",
    "QuestionGraphGeneratorAgent",
    "QuestionGraphGeneratorToolSchema",
    "SimpleAgent",
    "SimpleAgentToolSchema",
    "SimpleRAGAgent",
    "SimpleRAGToolSchema",
    "TextAugmentorAgent",
    "TextAugmentorToolSchema",
    "EdgeTable2TextGeneratorAgent",
    "EdgeTable2TextGeneratorToolSchema",
    "EmbeddingProjectorAgent",
    "EmbeddingProjectorToolSchema",
    "EmbeddingVisualizerAgent",
    "EmbeddingVisualizerToolSchema",
    "VectorDBLoaderAgent",
    "VectorDBLoaderToolSchema",
]
