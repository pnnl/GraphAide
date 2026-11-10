# Disambiguation

Many names refer to more than one real-world thing. "Georgia" can be a country, a US state, or a given name. Disambiguation links each extracted entity to one unique identifier so that "Georgia the country" and "Georgia the state" stay separate in your graph.

GraphAide does this by assigning a Wikidata QID (for example `Q230`) to each node. The QID is the stable identifier; the label is only for reading.

## How It Works

During extraction, the `wikidatagrounder` step runs after the ontology filter and fills `wikidata_id` on nodes that lack one. For each node it:

1. **Exact label match.** Looks up entries in the vector store whose label equals the node's English name. If exactly one entry matches, that QID is assigned directly, with no LLM call.
2. **Ambiguous exact matches.** If several entries share the label, all of them (up to 5 candidates) go to the LLM with the node name, and the LLM picks the one that is the same entity or returns null.
3. **No exact match.** The top 5 vector-similarity matches go to the LLM the same way.

A QID is accepted only if it came from that node's candidate list. The LLM cannot invent identifiers.

Grounding only runs when the vector store contains Wikidata entity documents. See [Use a Knowledge Base](index.md#use-a-knowledge-base-for-disambiguation).

## Example: Three "Georgia" Mentions

```python
from graphaide import GraphAide, ModelConfig, VectorDBConfig, get_sample_data_path

graphaide = GraphAide(
    model_config=ModelConfig(provider="openai", model_name="gpt-4o", api_key="..."),
    vector_configs=VectorDBConfig(provider="chromadb", store_name="GA_VDB"),
)

# Load the bundled Wikidata knowledge base (once per store)
graphaide.ingest_vectors(
    file_paths=[str(get_sample_data_path("graphaide_KB.jsonl"))],
    append=False,
)

texts = {
    "country": "Georgia is a country in the Caucasus, bordering Russia and Turkey. Tbilisi is its capital.",
    "state": "Atlanta is the capital of the U.S. state of Georgia, known as the Peach State.",
    "name": "My friend Georgia called to ask about the weekend.",
}

for label, text in texts.items():
    result = graphaide.extract(input_text=text, merge=True)
    for node in result.nodes:
        if "georgia" in (node.english_name or node.node_name or "").lower():
            print(f"{label:8} {node.node_name!r:12} -> {node.wikidata_id}")

# Expected:
# country  'Georgia'      -> Q230
# state    'Georgia'      -> Q1428
# name     'Georgia'      -> Q378694
```

Each paragraph gets a different QID because the LLM sees the candidate descriptions and the sentence around the mention. Check results against the Wikidata page for each QID when accuracy matters.

## Using Disambiguation Output

Nodes that share a `wikidata_id` refer to the same entity, so merge on the QID rather than the name:

```python
by_qid = {}
for node in result.nodes:
    key = node.wikidata_id or node.english_name or node.node_name
    by_qid.setdefault(key, []).append(node)
```

Nodes without a `wikidata_id` were not matched to any candidate and should be reviewed or left as plain names.

## Limits

- Grounding quality depends on the knowledge base. A label that is not in the store cannot be grounded.
- Misspelled or duplicate labels in the store produce duplicate candidates. Each duplicate counts toward the 5-candidate limit.
- The LLM pick is only as good as the candidate descriptions. Add descriptions and aliases to your own entries.

## Next Steps

- **[Knowledge Base](index.md#use-a-knowledge-base-for-disambiguation)**: load the bundled Wikidata snapshot or your own entities
- **[Use Ontologies](ontology.md)**: restrict node types to your domain
