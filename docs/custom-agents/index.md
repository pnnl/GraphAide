# Custom Agents

GraphAide includes three simple agents you can call directly, without building a full extraction or query workflow.

- **SimpleAgent** (`run_simple_agent`) applies an instruction to a single text file.
- **SimpleRAG** (`run_simple_rag`) answers a question from the configured vector store.
- **Image Explainer** (`explain`) describes an image using a vision-capable model.

These agents are building blocks. You can combine them to build custom workflows across different domains, such as research summaries, or product image cataloging, by choosing the agent and template that fit each domain.

All three are exposed on the `GraphAide` object.

## SimpleAgent: answer from a file

`run_simple_agent` reads a text file, fills a prompt template with your instruction and the file content, and returns the model's response.

```python
doc = "inputfile.txt"  # any .txt file
with open(doc, "w", encoding="utf-8") as f:
    f.write("AI is a good topic. Chemistry is interesting. Physics is fascinating.")

result = graphaide.run_simple_agent(
    file_path=doc,
    instruction="Follow the template instructions.",
    template_path="simpleagenttemplate.txt",
)
print(result.answer)
print(result.data["response"])
```

### Writing a template

The template controls how the model uses the file. It must contain these placeholders:

| Placeholder | Filled with |
|-------------|-------------|
| `{instruction}` | The `instruction` you pass in |
| `{file_content}` | The full text of `file_path` |
| `{file_name}` | The file's base name |

Example `simpleagenttemplate.txt` that restricts answers to the file:

```text
You are a helpful assistant. Follow the instruction below using only the provided document.

Instruction:
{instruction}

Document ({file_name}):
{file_content}

Rules:
- Base your answer on the document. If the document does not contain the answer, say so.
- Be concise.
```

If you omit `template_path`, the bundled default template is used.

## SimpleRAG: answer from the vector store

`run_simple_rag` retrieves the closest matches from the vector store for your question and asks the model to answer from them. It does not query the graph. It requires `vector_configs` in the `GraphAide` constructor.

```python
result = graphaide.run_simple_rag("What are all possible QID for Georgia?")
print(result.answer)
```

Retrieval uses the default top-k value from `globalconfig.DEFAULT_K`.

## Image Explainer: describe an image

`explain` sends an image to a vision-capable model and returns a text description. You can pass `template_path` to replace the default prompt.

```python
result = graphaide.explain("photo.jpg", template_path="imagetemplate.txt")
print(result.answer)
```

Supported formats: PNG, JPG, JPEG, GIF, BMP, WEBP. The configured LLM must accept image input. `run_simple_agent` cannot be used for images because it reads files as text.

## Notes

- `run_simple_agent` and `run_simple_rag` both return a `WorkflowResult`. The answer is in `result.answer`.
- Pass `log_level="DEBUG"` as a keyword argument to see detailed logs for a single call.
