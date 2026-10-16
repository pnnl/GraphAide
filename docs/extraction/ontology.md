# Using Ontologies in Extraction

Learn how to guide GraphAide extraction with domain-specific ontologies.

## What is an Ontology?

An ontology defines:

- **Entity Types** — What things exist in your domain (e.g., Person, Organization, Technology)
- **Relationship Types** — How things connect (e.g., "works for", "uses", "develops")
- **Properties** — Characteristics of entities and relationships

It acts as a blueprint that tells GraphAide: *"Look for these specific types of information."*

## Why Use Ontologies?

| Benefit | Example |
|---------|---------|
| **Precision** | Extract only relevant entity types for your domain |
| **Consistency** | All extractions use the same vocabulary |
| **Quality** | LLM focuses on domain-specific patterns |
| **Filtering** | Automatically exclude irrelevant entities |

## Ontology Formats

GraphAide supports standard semantic web formats:

- **N-Triples** (.nt) — Simple, line-based RDF format
- **Turtle** (.ttl) — More readable RDF format
- **OWL** (.owl) — Complex ontology definitions

### Simple N-Triples Example

```turtle
<http://example.org/Organization> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .
<http://example.org/Person> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .
<http://example.org/worksWith> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#ObjectProperty> .
```

## Using an Ontology

### Basic Usage

```python
from graphaide import GraphAide, ModelConfig, get_sample_data_path

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-5.6-luna", api_key="...")
)

# Extract using ontology
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.nt"
)
```

### With Sample Ontology

```python
sample_ontology = get_sample_data_path("ontology_cyber.nt")

result = graphaide.extract(
    file_path="document.pdf",
    ontology_path=sample_ontology
)
```

### Filter by Ontology Types

Only keep entities and relationships defined in the ontology:

```python
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="ontology.nt",
    filter_by_ontology=True  # Strict filtering
)
```

## Creating Your Own Ontology

### Step 1: Define Entity Types

Think about what kinds of things exist in your domain:

```
- Person (people)
- Organization (companies, institutions)
- Technology (software, tools)
- Vulnerability (security issues)
- Tactic (attack methods)
```

### Step 2: Define Relationship Types

What connections matter?

```
- develops (Person develops Technology)
- worksFor (Person worksFor Organization)
- affects (Vulnerability affects Technology)
- uses (Organization uses Technology)
```

### Step 3: Write N-Triples Ontology

```turtle
# Entity Types
<http://example.org/Person> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .
<http://example.org/Organization> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .
<http://example.org/Technology> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#Class> .

# Relationship Types
<http://example.org/worksFor> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#ObjectProperty> .
<http://example.org/develops> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#ObjectProperty> .
<http://example.org/uses> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#ObjectProperty> .
```

### Step 4: Use It

```python
result = graphaide.extract(
    file_path="document.pdf",
    ontology_path="my_ontology.nt"
)
```

## Generate Ontology Automatically

If you don't have an ontology, let GraphAide create one:

```python
result = graphaide.generate_ontology(
    node_types=["Person", "Organization", "Technology"],
    edge_types=["worksFor", "develops", "uses"],
    output_path="generated_ontology.nt"
)
```

## Common Domain Ontologies

### Cybersecurity

```python
sample_ontology = get_sample_data_path("ontology_cyber.nt")

result = graphaide.extract(
    file_path="threat_report.pdf",
    ontology_path=sample_ontology
)
```

Entity Types: Vulnerability, Malware, Tactic, Tool
Relationships: exploits, targets, related_to

### Business

```python
ontology_types = [
    "Person", "Organization", "Product", 
    "Company", "Location", "Industry"
]
ontology_rels = [
    "worksFor", "manages", "develops", 
    "competes_with", "located_in"
]

result = graphaide.generate_ontology(
    node_types=ontology_types,
    edge_types=ontology_rels,
    output_path="business_ontology.nt"
)
```

## Tips for Better Extraction

### 1. Start Simple
```python
# First, try extraction without ontology
result = graphaide.extract(file_path="doc.pdf")

# Then refine with ontology
result = graphaide.extract(
    file_path="doc.pdf",
    ontology_path="ontology.nt"
)
```

### 2. Use Descriptive Names
```python
# Good
types = ["TechnicalVulnerability", "SecurityProcedure", "RiskAssessment"]

# Less clear
types = ["Item1", "Item2", "Item3"]
```

### 3. Match Your Domain Language
```python
# For security domain, use terms experts recognize:
types = ["CVE", "CVSS_Score", "AttackVector", "CWE"]
```

### 4. Test Iteratively

```python
# Try with different filters
result1 = graphaide.extract(
    file_path="doc.pdf",
    ontology_path="ontology.nt",
    filter_by_ontology=False  # See all extractions first
)

result2 = graphaide.extract(
    file_path="doc.pdf",
    ontology_path="ontology.nt",
    filter_by_ontology=True   # Then apply strict filtering
)

# Compare results
print(f"Without filter: {len(result1.nodes)} entities")
print(f"With filter: {len(result2.nodes)} entities")
```

## Next Steps

- **[Ingest Results](../ingestion/)** — Load extracted data into Neo4j
- **[Enhance with Vector Stores](../vector-stores/usage.md)** — Add semantic search
- **[See Examples](../resources.md)** — Learn from domain-specific use cases
