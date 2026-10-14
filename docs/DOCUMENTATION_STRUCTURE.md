# GraphAide Documentation Structure

This file describes the complete documentation layout for GraphAide.

## Directory Structure

```
docs/
├── index.md                     # Landing page with quick start
├── installation/
│   └── index.md                # Installation guide (pip, Docker, dev setup)
├── configuration/
│   └── index.md                # LLM, Neo4j, Vector DB configuration
├── extraction/
│   ├── index.md                # Knowledge graph extraction basics
│   └── ontology.md             # Using domain ontologies in extraction
├── ingestion/
│   └── index.md                # Loading extracted data to Neo4j
├── vector-stores/
│   ├── setup.md                # Setting up ChromaDB and Qdrant
│   └── usage.md                # Using vector stores for enhanced extraction
├── resources.md                # Quick reference, examples, troubleshooting
├── api.md                      # API reference (auto-generated from docstrings)
├── assets/
│   ├── logo.png                # GraphAide logo
│   └── favicon.png             # Browser icon
└── DOCUMENTATION_STRUCTURE.md  # This file
```

## Navigation Hierarchy

### Home (index.md)
- What is GraphAide?
- Why GraphAide?
- Quick Start (two examples)
- Use Cases
- What You'll Learn (links to other sections)

### Getting Started Path
1. **Installation** → 5 ways to install
2. **Configuration** → Set up LLMs, databases, embeddings
3. **Extraction** → Extract entities and relationships
4. **Ingestion** → Load to Neo4j

### Advanced Topics
- **Ontologies** → Guide extraction with domain knowledge
- **Vector Stores** → Enhance extraction with semantic search
- **Resources** → Examples, troubleshooting, reference

### Reference
- **API Reference** → Complete API documentation
- **Resources** → Quick reference, glossary

## Page Content Summary

| Page | Purpose | Audience |
|------|---------|----------|
| **index.md** | Hook and orientation | New users |
| **installation/** | Get GraphAide running | Developers |
| **configuration/** | Customize setup | Operators |
| **extraction/** | Learn extraction basics | Users |
| **extraction/ontology.md** | Advanced extraction | Power users |
| **ingestion/** | Load to Neo4j | Users |
| **vector-stores/setup.md** | Set up vector DB | Operators |
| **vector-stores/usage.md** | Use in extraction | Users |
| **resources.md** | Utilities and reference | All |
| **api.md** | Complete API docs | Developers |

## Writing Conventions

All pages follow these conventions:

### Structure
1. **H1 Title** — Main page title
2. **Introduction** — What this page covers (1-2 sentences)
3. **Quick Start** — Simplest example first
4. **Detailed Content** — Expand on quick start
5. **Advanced Topics** — For power users
6. **Next Steps** — Links to related pages

### Code Examples
- Always show working examples
- Include both minimal and full versions
- Highlight key parameters
- Show expected output

### Language
- **Simple:** Avoid jargon where possible
- **Consistent:** Same term throughout
- **Action-oriented:** Focus on what users can do
- **Practical:** Real-world scenarios

### Navigation
- Each page ends with "Next Steps" linking to related content
- Links use relative paths: `[link](../other-page.md)`
- Sidebar (mkdocs.yml) manages overall navigation

## Building the Documentation

### Prerequisites
```bash
pip install mkdocs mkdocs-material mkdocstrings[python]
```

### Local Development
```bash
# Preview documentation locally
mkdocs serve
# Visit http://localhost:8000
```

### Build Static Site
```bash
# Generate static HTML
mkdocs build
# Output in ./site/

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### Deployment Options

#### Option 1: GitHub Pages (Easiest)
```bash
git push origin docs-mkdocs
# Create PR to develop
# After merge, run: mkdocs gh-deploy
```

#### Option 2: ReadTheDocs (Later)
When you reach v1.0+, switch to ReadTheDocs for automatic versioning.

## MkDocs Configuration

The `mkdocs.yml` file controls:
- **Theme:** Material (Material for MkDocs)
- **Logo:** docs/assets/logo.png
- **Favicon:** docs/assets/favicon.png
- **Navigation:** Structure in yaml nav section
- **Plugins:** Search, mkdocstrings for API docs
- **Extensions:** Tables, admonitions, code highlighting

## API Documentation

The `api.md` page uses mkdocstrings to auto-generate documentation from Python docstrings:

```python
# These docstrings appear in api.md
::: graphgen.graphaide_api.GraphAide
::: graphgen.config.ModelConfig
```

To update API docs: improve docstrings in source code, they appear automatically.

## Versioning (Future)

When you release v1.0.0, add versioning:

```bash
# Install mike (versioning tool)
pip install mike

# Deploy version
mike deploy 1.0.0 latest

# Users see dropdown: v0.5.x | v1.0.0 | latest
```

## Maintenance

### Adding a New Page
1. Create markdown file in appropriate folder
2. Update nav section in mkdocs.yml
3. Add "Next Steps" links to/from related pages

### Updating Content
1. Edit .md files
2. Run `mkdocs serve` locally
3. Verify changes at http://localhost:8000
4. Commit and push

### Keeping Docs Current
- Update docs when adding features
- Match version in docs to package version
- Review for broken links quarterly

## Next Steps

1. Install MkDocs: `pip install mkdocs mkdocs-material mkdocstrings[python]`
2. Test locally: `mkdocs serve`
3. Build: `mkdocs build`
4. Deploy: `mkdocs gh-deploy` (requires GitHub Pages enabled)
