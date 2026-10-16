# GraphAide

<p align="center">
  <img src="https://raw.githubusercontent.com/pnnl/GraphAide/develop/tests/notebooks/GraphAideLogo_Label_Final.png" alt="GraphAide Logo" width="400">
</p>

**Build knowledge graphs from any document with LLMs and Neo4j.** GraphAide is a multi-agentic platform for building intelligent applications powered by Large Language Models (LLMs). Knowledge graph construction is one powerful example—transforming documents into queryable knowledge graphs by extracting entities and relationships. But GraphAide's capabilities extend far beyond KGs.

## Quick Start

### Install (Version 0.6.4)

**Using uv (Recommended - Fastest):**
```bash
uv pip install graphaide==0.6.4
```

**Or using pip:**
```bash
pip install graphaide==0.6.4
```

### 30-Second Example

```python
from graphaide import GraphAide, ModelConfig, get_sample_data_path

# Setup
graphaide = GraphAide(
    model_config=ModelConfig(
        provider="openai", 
        model_name="gpt-4o",
        api_key="..."
    )
)

# Extract from sample document
sample_pdf = get_sample_data_path("PNNL_About.pdf")
result = graphaide.extract(file_path=sample_pdf)
print(f"✓ Extracted {len(result.nodes)} entities, {len(result.edges)} relationships")
```

## What It Does

- **Extract** entities & relationships from PDFs, text, images, or web data
- **Process** diverse data with multiple LLM providers and models
- **Ground** information to external knowledge bases and sources
- **Build** intelligent workflows with minimal setup
- **Track** data provenance and attribution throughout
- **Scale** from single documents to large datasets

## Documentation

📚 **Full documentation:** https://pnnl.github.io/GraphAide

**Getting Started:**
- **[Installation](https://pnnl.github.io/GraphAide/installation/)** — Setup instructions for uv, pip, Docker, and development
- **[Configuration](https://pnnl.github.io/GraphAide/configuration/)** — Configure LLMs, Neo4j, vector stores
- **[Extraction Guide](https://pnnl.github.io/GraphAide/extraction/)** — Learn entity and relationship extraction
- **[Vector Stores](https://pnnl.github.io/GraphAide/vector-stores/setup.md)** — Setup ChromaDB for semantic search
- **[Ingestion](https://pnnl.github.io/GraphAide/ingestion/)** — Load extracted data into Neo4j
- **[Resources](https://pnnl.github.io/GraphAide/resources/)** — Tutorials and examples

## Supported Providers

| LLM | Embedding | Vector Store |
|-----|-----------|--------------|
| OpenAI, Anthropic, Google, AWS Bedrock, LMStudio | OpenAI, Sentence Transformers, AWS Bedrock | ChromaDB |

## Use Cases

- **Knowledge Management** — Build searchable knowledge graphs from company documents
- **Research Analysis** — Extract and connect findings across papers and reports
- **Data Integration** — Merge information from multiple sources with automatic entity linking
- **Compliance Auditing** — Track relationships and dependencies with full provenance
- **Domain Expertise** — Answer questions requiring reasoning across documents

## Project Status

- **Version:** 0.6.4
- **Status:** Active Development
- **License:** MIT

## Citation

If you use GraphAide in your research, please cite:

```bibtex
@inproceedings{purohit2024graphaide,
  title={GraphAide: Advanced Graph-Assisted Query and Reasoning System},
  author={Purohit, Sumit and Chin, George and Mackey, Patrick S and Cottam, Joseph A},
  booktitle={2024 IEEE International Conference on Big Data (BigData)},
  pages={3485--3493},
  year={2024},
  organization={IEEE}
}
```

## Support & Contributing

- 📚 **See [full documentation](https://pnnl.github.io/GraphAide)** for detailed guides
- 🐛 **Report issues** on [GitHub Issues](https://github.com/pnnl/GraphAide/issues)
- 💬 **Ask questions** via [GitHub Discussions](https://github.com/pnnl/GraphAide/discussions)
- 📖 **Check [QUICKSTART.md](https://github.com/pnnl/GraphAide/blob/develop/QUICKSTART.md)** for detailed setup

## Legal

- **[License](https://github.com/pnnl/GraphAide/blob/develop/LICENSE.txt)** — MIT License
- **[Disclaimer](https://github.com/pnnl/GraphAide/blob/develop/DISCLAIMER)** — Important legal notices
- **[Acknowledgments](https://github.com/pnnl/GraphAide/blob/develop/ACKNOWLEDGMENT)** — Credits and funding

---

**Ready to build your first knowledge graph?** Start with [Installation](https://pnnl.github.io/GraphAide/installation/).
