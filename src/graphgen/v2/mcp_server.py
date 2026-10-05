# from agents.base import GraphAideAgent
from fastmcp import FastMCP

import graphgen.v2.agents.AgentManager as af
import graphgen.v2.agents.vectordbloader as vdl
import graphgen.v2.GraphDBManager as ggm
import graphgen.v2.ModelManager as mf
import graphgen.v2.VectorStoreManager as vsm

# 1. Initialize MCP
mcp = FastMCP("KnowledgeGraphSystemV2")

# 2. Initialize your Infrastructure (Once)
model_factory = mf.ModelFactory()
graphdb_factory = ggm.GraphDBFactory()
# Point to your 'templates' folder
vector_store_manager = vsm.VectorFactory(model_factory)
agent_factory = af.AgentFactory(
    model_factory,
    vector_store_manager,
    template_dir="templates",
    graphdb_factory=graphdb_factory,
)


@mcp.tool()
def load_vdata(file_path: str, append: bool = True) -> str:
    vectordbloader_node = agent_factory.build(
        agent_class=vdl.VectorDBLoaderAgent,
        agent_id="vectordbloader",
        partials={"format_instructions": "format_instructions"},
    )

    result = vectordbloader_node({"file_path": file_path, "append": append})
    return f"Success: {result}"


# 3. Run the server
if __name__ == "__main__":
    mcp.run(transport="stdio")
