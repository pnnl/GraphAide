import base64
import json
import os
import re
from pathlib import Path
from typing import List, Optional, Union

import yaml
from langchain_chroma import Chroma
from langchain_community.document_loaders import (
    CSVLoader,
    PyPDFLoader,
    TextLoader,
)

from ..ontology_utils import parse_rdf_ontology
from pydantic import BaseModel, Field

try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .. import globalconfig as gc
from ..state import KGGenerationState
from ..utils import get_logger, get_vector_store_metadata
from .base import GraphAideAgent

logger = get_logger(__name__)


class VectorDBLoaderToolSchema(BaseModel):
    """Input schema for VectorDBLoaderAgent tool."""

    file_path: Optional[str] = Field(
        default=None,
        description="Path to a single file to load (e.g., 'document.pdf'). Supports: PDF, JSON (including Wikidata), JSONL, CSV, TSV, YAML, TXT, PNG, JPG, GIF, BMP, OWL, TTL, NT. Special files detected by extension/name: .owl/.ttl/.nt (ontology), *wikidata*.json (Wikidata entities).",
    )
    file_paths: Optional[Union[List[str], str]] = Field(
        default=None,
        description="List of file paths or comma-separated paths to load multiple files at once. Examples: ['file1.pdf', 'file2.pdf'] or 'file1.pdf, file2.pdf'.",
    )
    json_line: Optional[bool] = Field(
        default=False, description="Whether JSON file is in JSONL format"
    )
    source_column: Optional[str] = Field(
        default=None, description="Column name to use as document source"
    )
    encoding: Optional[str] = Field(default="utf-8", description="File encoding")
    chunking: Optional[bool] = Field(
        default=False, description="Whether to process in batches for large files"
    )
    split_docs: Optional[bool] = Field(
        default=True, description="Whether to split documents into chunks"
    )
    append: Optional[bool] = Field(
        default=False, description="Whether to append to existing vector store"
    )
    is_raw_embedding: Optional[bool] = Field(
        default=False, description="Whether file contains pre-computed embeddings"
    )
    section_chunking: Optional[bool] = Field(
        default=False, description="For PDFs, use section-based chunking"
    )
    max_characters: Optional[int] = Field(
        default=1500, description="Max characters per section chunk"
    )
    use_vision_extraction: Optional[bool] = Field(
        default=False,
        description="For images/PDFs, use LLM to extract text via vision capability",
    )
    extract_pdf_images: Optional[bool] = Field(
        default=False,
        description="For PDFs, extract embedded images as separate documents",
    )


class VectorDBLoaderAgent(GraphAideAgent):
    """Load documents from various file formats into a ChromaDB vector store.

    Supports loading PDF, JSON, JSONL, CSV, TSV, YAML, and text files. Handles
    document chunking, metadata extraction, and batch processing for large files.
    Can also load pre-computed embeddings from TSV files.

    YAML files are expected to have a nested control structure where each top-level
    key (except 'name') becomes a separate document. Useful for loading security
    control catalogs.

    Input state keys:
        file_path (str, optional): Path to a single file to load into the vector store.
        file_paths (list or str, optional): List of file paths or comma-separated string of paths.
        json_line (bool, optional): Whether JSON file is in JSONL format.
        source_column (str, optional): Column name to use as document source.
        encoding (str, optional): File encoding, defaults to 'utf-8'.
        chunking (bool, optional): Whether to process in batches for large files.
        split_docs (bool, optional): Whether to split documents into chunks.
        append (bool, optional): Whether to append to existing vector store.
        is_raw_embedding (bool, optional): Whether file contains pre-computed embeddings.
        section_chunking (bool, optional): For PDFs, if True uses unstructured with
            by_title chunking to keep each section's text together. Defaults to False.
        max_characters (int, optional): Max characters per section chunk when
            section_chunking=True. Defaults to 1500.

    Output state keys:
        messages (List[str]): Status messages about the loading operation.

    Requires settings:
        vector_store: ChromaDB vector store instance to load documents into.
        persist_directory: Directory path for vector store persistence.
    """

    tool_schema = VectorDBLoaderToolSchema
    tool_description = "Load documents from various file formats (PDF, JSON, CSV, YAML, text) into a ChromaDB vector store"
    tool_output_keys = ["messages", "document_id_to_title"]

    def _extract_id_title_mapping(self, documents: List[Document]) -> dict:
        """Extract ID→Title mapping from documents.

        For each document, looks for 'id' and 'title' in metadata.
        If 'id' exists, creates mapping id→title for O(1) lookups.

        Args:
            documents: List of Document objects with metadata

        Returns:
            Dictionary mapping document ID to title {id: title, ...}
        """
        id_to_title = {}
        for doc in documents:
            doc_id = doc.metadata.get("id")
            title = doc.metadata.get("title", "")
            if doc_id:
                id_to_title[doc_id] = title
        return id_to_title

    def loadWikidataJSON(self, wikidata_file_path: str, vector_store):
        """Load Wikidata JSON file into vector store.

        Expected format: {QID: {label, description, aliases, edges}}
        For each entity (QID), creates a document with:
        - documentID: the QID
        - description: label + description + aliases + edges info
        - metadata includes edge relationships
        """
        wikidata_path = Path(wikidata_file_path)
        if not wikidata_path.exists():
            raise FileNotFoundError(f"Wikidata file not found: {wikidata_path}")

        logger.info(f"Loading Wikidata JSON: {wikidata_file_path}")

        with open(wikidata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        documents = []

        for qid, entity_data in data.items():
            label = entity_data.get("label", qid)
            description = entity_data.get("description", "")
            aliases = entity_data.get("aliases", [])
            edges = entity_data.get("edges", [])

            # Build document content
            doc_content = f"QID: {qid}\nLabel: {label}\n"

            if description:
                doc_content += f"Description: {description}\n"

            if aliases:
                doc_content += f"Aliases: {', '.join(aliases)}\n"

            if edges:
                doc_content += f"\nRelationships ({len(edges)}):\n"
                for edge in edges:
                    predicate = edge.get("predicate", "")
                    obj = edge.get("object", "")
                    edge_desc = edge.get("description", "")
                    doc_content += f"  - {predicate} → {obj}: {edge_desc}\n"

            # Create document with metadata including edge info
            metadata = {
                "id": qid,  # ChromaDB document ID
                "title": label,  # Document title
                "source": f"{qid}|{label}",  # Format for ExtractorAgent Wikidata parsing
                "type": "wikidata_entity",
                "qid": qid,
                "label": label,
            }

            # Include predicates as metadata for relationship discovery
            if edges:
                predicates = [e.get("predicate", "") for e in edges]
                metadata["predicates"] = ",".join(set(predicates))

            doc = Document(page_content=doc_content, metadata=metadata)
            documents.append(doc)

        # Add documents to vector store
        if documents:
            vector_store.add_documents(documents)
            logger.info(f"Loaded {len(documents)} Wikidata entities into vector store")
        else:
            logger.info("No Wikidata entities found in file")

        return documents, [f"Loaded {len(documents)} Wikidata entities from {wikidata_file_path}"]

    def loadOntologyFile(self, ontology_file_path: str, embedding_function: Embeddings, vector_store):
        """Load ontology file (OWL, TTL, NT) into vector store.

        For each node/edge type in ontology, creates a document with:
        - documentID: the type name
        - description: definitions and examples from RDF metadata

        Uses shared parse_rdf_ontology() to avoid code duplication.
        """
        logger.info(f"Loading ontology: {ontology_file_path}")

        # Use shared ontology parser
        ontology_data = parse_rdf_ontology(ontology_file_path)

        documents = []

        # Process node types (classes)
        for node_type in ontology_data["node_types"]:
            description = ""

            # Get definition
            if node_type in ontology_data["node_definitions"]:
                description += f"Definition: {ontology_data['node_definitions'][node_type]}\n"

            # Get examples
            if node_type in ontology_data["node_examples"]:
                examples = ontology_data["node_examples"][node_type]
                description += f"Examples: {', '.join(examples[:5])}\n"  # Limit to 5

            # Create document
            doc_content = f"Node Type: {node_type}\n{description}" if description else f"Node Type: {node_type}"
            doc = Document(
                page_content=doc_content,
                metadata={"id": node_type, "title": node_type, "source": node_type, "type": "node_type"}
            )
            documents.append(doc)

        # Process edge types (properties)
        for edge_type in ontology_data["edge_types"]:
            description = ""

            # Get definition
            if edge_type in ontology_data["edge_definitions"]:
                description += f"Definition: {ontology_data['edge_definitions'][edge_type]}\n"

            # Get examples
            if edge_type in ontology_data["edge_examples"]:
                examples = ontology_data["edge_examples"][edge_type]
                description += f"Examples: {', '.join(examples[:5])}\n"  # Limit to 5

            # Create document
            doc_content = f"Edge Type: {edge_type}\n{description}" if description else f"Edge Type: {edge_type}"
            doc = Document(
                page_content=doc_content,
                metadata={"id": edge_type, "title": edge_type, "source": edge_type, "type": "edge_type"}
            )
            documents.append(doc)

        # Add documents to vector store
        if documents:
            vector_store.add_documents(documents)
            logger.info(f"Loaded {len(documents)} ontology types into vector store")
        else:
            logger.info("No ontology types found in file")

        return documents, [f"Loaded {len(documents)} ontology types from {ontology_file_path}"]

    def __call__(self, state: KGGenerationState) -> dict:
        logger.debug(
            f"VectorDBLoaderAgent called with state keys: {list(state.keys())}"
        )
        logger.debug(f"DEFAULT_EXTERNAL_METADATA: {gc.DEFAULT_EXTERNAL_METADATA}")

        # 1. Access the Vector Store from the factory-injected settings
        vector_store = self.settings.get("vector_store")
        if not vector_store:
            raise ValueError(
                f"Agent '{self.__class__.__name__}' requires a vector_store but none was provided."
            )
        elif vector_store._collection.count() == 0 or state.get("append", False):
            vector_count = vector_store._collection.count()
            logger.debug(f"vector store has {vector_count} vectors currently")

            # Log vector store metadata/categories
            if vector_count > 0:
                try:
                    metadata = get_vector_store_metadata(vector_store)
                    logger.debug(f"vector store categories: {metadata}")
                except Exception as e:
                    logger.debug(f"Could not retrieve vector store metadata: {e}")

            # Normalize file inputs to a list
            file_path = state.get("file_path", None)
            file_paths = state.get("file_paths", None)

            if file_paths is not None:
                if isinstance(file_paths, str):
                    files_to_load = [f.strip() for f in file_paths.split(",")]
                else:
                    files_to_load = (
                        file_paths if isinstance(file_paths, list) else [file_paths]
                    )
            elif file_path is not None:
                if isinstance(file_path, str) and "," in file_path:
                    files_to_load = [f.strip() for f in file_path.split(",")]
                else:
                    files_to_load = [file_path]
            else:
                raise ValueError(
                    f"Either file_path or file_paths must be provided in state for '{self.__class__.__name__}'"
                )

            # Check if any files are ontology files (.ttl, .nt, .owl) or Wikidata JSON files
            ontology_files = [f for f in files_to_load if f.lower().endswith(('.ttl', '.nt', '.owl'))]
            wikidata_files = [f for f in files_to_load if f.lower().endswith('.json') and 'wikidata' in f.lower()]
            regular_files = [f for f in files_to_load if not f.lower().endswith(('.ttl', '.nt', '.owl')) and not (f.lower().endswith('.json') and 'wikidata' in f.lower())]

            # Process ontology files first
            all_messages = []
            document_id_to_title = {}

            for ontology_file in ontology_files:
                docs, messages = self.loadOntologyFile(ontology_file, vector_store.embeddings, vector_store)
                all_messages.extend(messages)
                # Extract ID→Title mappings
                id_to_title = self._extract_id_title_mapping(docs)
                document_id_to_title.update(id_to_title)

            # Process Wikidata JSON files
            for wikidata_file in wikidata_files:
                try:
                    docs, messages = self.loadWikidataJSON(wikidata_file, vector_store)
                    all_messages.extend(messages)
                    # Extract ID→Title mappings
                    id_to_title = self._extract_id_title_mapping(docs)
                    document_id_to_title.update(id_to_title)
                except Exception as e:
                    logger.error(f"Failed to load Wikidata file {wikidata_file}: {e}")
                    all_messages.append(f"❌ Failed to load Wikidata file {wikidata_file}: {e}")

            # If only ontology/wikidata files, return early
            if not regular_files:
                result = {"messages": all_messages}
                if document_id_to_title:
                    result["document_id_to_title"] = document_id_to_title
                return result

            # Update files_to_load for regular file processing
            files_to_load = regular_files

            # Get other params
            embedding_function = vector_store.embeddings
            json_line = state.get("json_line", False)
            source_column = state.get("source_column", None)
            encoding = state.get("encoding", "utf-8")
            chunking = state.get("chunking", False)
            split_docs = state.get("split_docs", True)
            internal_metadata = state.get("internal_metadata", None)
            external_metadata = state.get(
                "external_metadata", gc.DEFAULT_EXTERNAL_METADATA
            )
            splitter = state.get("splitter", None)
            persist_directory = self.settings.get("persist_directory")
            offset = state.get("offset", 1)
            header = state.get("header", "infer")
            section_chunking = state.get("section_chunking", False)
            max_characters = state.get("max_characters", 1500)
            should_append = state.get("append", False)

            # all_messages was initialized earlier with ontology messages, extend it
            for idx, file_path in enumerate(files_to_load):
                if not os.path.exists(file_path):
                    msg = f"❌ File not found: {file_path}"
                    logger.error(msg)
                    all_messages.append(msg)
                    continue

                logger.info(
                    f"Loading {file_path} [file {idx + 1}/{len(files_to_load)}]"
                )

                # Load file based on type
                if str(file_path).endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
                    # Image files with optional vision extraction
                    use_vision = state.get("use_vision_extraction", False)
                    docs = self.loadImageFiles(
                        [file_path],
                        use_vision_extraction=use_vision,
                        model=self.model if use_vision else None,
                        external_metadata=external_metadata,
                    )
                elif str(file_path).endswith(".pdf"):
                    # PDF files - check for image extraction
                    extract_images = state.get("extract_pdf_images", False)
                    use_vision = state.get("use_vision_extraction", False)

                    if extract_images:
                        docs = self.loadPDFImages(
                            file_path,
                            use_vision_extraction=use_vision,
                            model=self.model if use_vision else None,
                        )
                    else:
                        # Standard PDF text extraction
                        docs = self.loadPDFFile(
                            file_path,
                            section_chunking=section_chunking,
                            max_characters=max_characters,
                        )
                elif str(file_path).endswith(".yml") or str(file_path).endswith(
                    ".yaml"
                ):
                    docs = self.loadYAMLFile(
                        file_path, external_metadata=external_metadata
                    )
                elif (
                    str(file_path).endswith("json")
                    or str(file_path).endswith("jsonl")
                    or str(file_path).endswith("json.")
                ):
                    docs = self.loadJSONFile(
                        file_path,
                        json_lines=json_line,
                        external_metadata=external_metadata,
                        source_column=source_column,
                    )
                elif state.get("is_raw_embedding", False) is True:
                    result = self.loadCSV_Embedding(
                        file_path, persist_directory, offset, header
                    )
                    all_messages.append(f"✅ Loaded embeddings from {file_path}")
                    continue
                elif str(file_path).endswith("tsv") or str(file_path).endswith("tsv."):
                    docs = (
                        self.loadCSVFile(
                            file_path,
                            source_column,
                            encoding=encoding,
                            sep="\t",
                            chunking=chunking,
                            internal_metadata=internal_metadata,
                            external_metadata=external_metadata,
                        )
                        if source_column is not None
                        else self.loadTXTFile(file_path, encoding=encoding)
                    )
                else:
                    logger.debug(f"Source column: {source_column}, file: {file_path}")
                    docs = (
                        self.loadCSVFile(
                            file_path,
                            source_column,
                            encoding=encoding,
                            internal_metadata=internal_metadata,
                            external_metadata=external_metadata,
                        )
                        if source_column is not None
                        else self.loadTXTFile(file_path)
                    )

                # Add metadata if needed
                if source_column is not None:
                    for doc in docs:
                        doc.metadata.update({"raw_source": file_path})

                # Log the metadata_filter being used
                if docs:
                    metadata_filter = docs[0].metadata.get("metadata_filter", "")
                    logger.debug(
                        f"File '{os.path.basename(file_path)}' → metadata_filter='{metadata_filter}'"
                    )

                text_splitter = (
                    RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
                    if splitter is None
                    else splitter
                )

                splits = (
                    docs if split_docs is False else text_splitter.split_documents(docs)
                )

                # First file uses append flag, remaining files always append
                append_mode = should_append or idx > 0

                # Clear collection on first file if not appending
                if idx == 0 and not should_append:
                    collection = vector_store._collection
                    existing_ids = collection.get()["ids"]
                    if existing_ids:
                        collection.delete(existing_ids)
                        logger.info("Cleared vector store collection for fresh load")

                # Extract ID→Title mappings from this file's documents
                id_to_title = self._extract_id_title_mapping(splits)
                document_id_to_title.update(id_to_title)

                if chunking is False:
                    # Batch documents to avoid ChromaDB max batch size limit (5461)
                    batch_size = 5000
                    for i in range(0, len(splits), batch_size):
                        batch_splits = splits[i : i + batch_size]
                        vector_store.add_documents(batch_splits)
                    msg = f"✅ Loaded {len(splits)} docs from {file_path} ({(len(splits) + batch_size - 1) // batch_size} batches)"
                    logger.info(msg)
                    all_messages.append(msg)
                else:
                    collection = vector_store._collection
                    batch_size = 10000
                    for i in range(0, len(splits), batch_size):
                        try:
                            batch_splits = splits[i : i + batch_size]
                            embeddings = embedding_function.embed_documents(
                                [doc.page_content for doc in batch_splits]
                            )
                            for idx_batch, doc in enumerate(batch_splits):
                                collection.add(
                                    documents=[doc.page_content],
                                    metadatas=[doc.metadata],
                                    embeddings=[embeddings[idx_batch]],
                                    ids=[str(i + idx_batch)],
                                )
                        except Exception as e:
                            logger.error(
                                f"Failed to ingest batch {i // batch_size + 1}: {e}"
                            )
                    msg = f"✅ Loaded {len(splits)} docs from {file_path} (batched)"
                    logger.info(msg)
                    all_messages.append(msg)

            result = {"messages": all_messages}
            if document_id_to_title:
                result["document_id_to_title"] = document_id_to_title
            return result
        else:
            return {"messages": ["Zero document ingested."]}

    """Helper function to load PDF using PyPDFLoader, with error handling and logging."""

    def loadPDFFile(self, file_path, section_chunking=False, max_characters=1500):
        """Load PDF file into documents.

        Args:
            file_path: Path to the PDF file.
            section_chunking: If True, use unstructured with by_title chunking
                to keep each section's text together. If False, use PyPDFLoader.
            max_characters: Maximum characters per chunk when section_chunking=True.

        Returns:
            List of Document objects.
        """
        if section_chunking:
            return self.loadPDFFile_by_section(file_path, max_characters)

        loader = PyPDFLoader(file_path)
        try:
            docs = loader.load()
        except Exception as e:
            logger.error(f"Error loading PDF file at {file_path}: {e}")
            docs = []
        logger.debug(f"Loaded {len(docs)} documents from {file_path} using PyPDFLoader")
        return docs

    def loadPDFFile_by_section(
        self,
        file_path,
        max_characters=1500,
        external_metadata=gc.DEFAULT_EXTERNAL_METADATA,
    ):
        """Load PDF with section-based chunking using PyMuPDF.

        Detects headings based on font size and groups text under each heading
        into a single document. Each section becomes one Document.

        Args:
            file_path: Path to the PDF file.
            max_characters: Maximum characters per section chunk.
            external_metadata: Optional dictionary of metadata to attach to each section.
        Returns:
            List of Document objects, one per section.
        """
        logger.info(f"Loading PDF with section chunking: {file_path}")

        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available. Falling back to PyPDFLoader")
            return self.loadPDFFile(file_path, section_chunking=False)

        try:
            pdf_doc = fitz.open(file_path)
            sections = []
            current_section_title = "Introduction"
            current_section_text = []
            filename = os.path.basename(file_path)

            # Collect font sizes to determine heading threshold
            all_font_sizes = []
            for page in pdf_doc:
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line["spans"]:
                                if span["text"].strip():
                                    all_font_sizes.append(span["size"])

            if not all_font_sizes:
                logger.warning("No text found in PDF. Falling back to PyPDFLoader")
                return self.loadPDFFile(file_path, section_chunking=False)

            # Heading threshold: font size larger than 75th percentile
            avg_font_size = sum(all_font_sizes) / len(all_font_sizes)
            heading_threshold = avg_font_size * 1.15

            # Extract sections
            for page_num, page in enumerate(pdf_doc):
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        line_text = ""
                        is_heading = False
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if not text:
                                continue
                            line_text += text + " "
                            # Check if this is a heading (larger font or bold)
                            if (
                                span["size"] >= heading_threshold
                                or "bold" in span["font"].lower()
                            ):
                                is_heading = True

                        line_text = line_text.strip()
                        if not line_text:
                            continue

                        if (
                            is_heading and len(line_text) < 200
                        ):  # Headings are usually short
                            # Save previous section if it has content
                            if current_section_text:
                                section_content = "\n".join(current_section_text)
                                # Split if exceeds max_characters
                                if len(section_content) > max_characters:
                                    chunks = [
                                        section_content[i : i + max_characters]
                                        for i in range(
                                            0, len(section_content), max_characters
                                        )
                                    ]
                                    for idx, chunk in enumerate(chunks):
                                        title = (
                                            f"{current_section_title}"
                                            if idx == 0
                                            else f"{current_section_title} (cont. {idx + 1})"
                                        )
                                        sections.append(
                                            {
                                                "title": title,
                                                "content": chunk,
                                            }
                                        )
                                else:
                                    sections.append(
                                        {
                                            "title": current_section_title,
                                            "content": section_content,
                                        }
                                    )
                            current_section_title = line_text
                            current_section_text = []
                        else:
                            current_section_text.append(line_text)

            # Don't forget the last section
            if current_section_text:
                section_content = "\n".join(current_section_text)
                if len(section_content) > max_characters:
                    chunks = [
                        section_content[i : i + max_characters]
                        for i in range(0, len(section_content), max_characters)
                    ]
                    for idx, chunk in enumerate(chunks):
                        title = (
                            f"{current_section_title}"
                            if idx == 0
                            else f"{current_section_title} (cont. {idx + 1})"
                        )
                        sections.append(
                            {
                                "title": title,
                                "content": chunk,
                            }
                        )
                else:
                    sections.append(
                        {
                            "title": current_section_title,
                            "content": section_content,
                        }
                    )

            pdf_doc.close()

            # Convert to Document objects, skip empty or near-empty sections
            docs = []
            for section in sections:
                content = section["content"].strip()
                title = section["title"].strip()

                # Skip sections with symbol-only titles (no alphanumeric chars)
                if not any(c.isalnum() for c in title):
                    logger.debug(f"Skipping symbol-only title: '{title}'")
                    continue

                # Skip sections with very short titles (likely not real headings)
                if len(title) < 3:
                    logger.debug(f"Skipping short title: '{title}'")
                    continue

                # Skip sections with no meaningful content (less than 50 chars)
                if not content or len(content) < 50:
                    logger.debug(f"Skipping empty/short section: {title}")
                    continue
                doc_metadata_filter = ""
                if external_metadata:
                    for key, value in external_metadata.items():
                        if key in filename:
                            doc_metadata_filter = f"{value}"
                            break

                doc = Document(
                    page_content=f"{section['title']}\n\n{content}",
                    metadata={
                        "raw_source": file_path,
                        "file_name": filename,
                        "section_title": section["title"],
                        "source": f"{filename}",  # it becomes the categories in the plot
                        "title": f"{filename}:{section['title']}",
                        "metadata_filter": doc_metadata_filter,
                    },
                )
                docs.append(doc)

            logger.debug(
                f"Loaded {len(docs)} section-chunked documents from {file_path} using PyMuPDF"
            )
            return docs

        except Exception as e:
            logger.error(
                f"Error loading PDF with section chunking at {file_path}: {e}. Falling back to PyPDFLoader"
            )
            return self.loadPDFFile(file_path, section_chunking=False)

    def loadYAMLFile(
        self,
        file_path,
        external_metadata=gc.DEFAULT_EXTERNAL_METADATA,
    ):
        """Load YAML file with nested control structures into documents.

        Expected YAML format:
            name: SOMENAME
            SOMEKEY:
              family: SOMEFAMILY
              name: Some descriptive name
              description: |2
                 - a. Develop, document...
            SOMEOtherKEY:
              family: ....

        Each top-level key (except 'name') becomes a separate Document with:
        - source: filename
        - title: key + name field (e.g., "SOMEKEY: Some descriptive name")
        - content: YAML dump of the entire subsection
        - metadata_filter: based on filename substring in external_metadata

        Args:
            file_path: Path to the YAML file.
            external_metadata: Dictionary mapping filename substrings to metadata values.

        Returns:
            List of Document objects, one per entry.
        """
        logger.info(f"Loading YAML file: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                logger.error(
                    f"YAML file {file_path} does not contain a dictionary at root level"
                )
                return []

            filename = os.path.basename(file_path)
            documents = []

            # Determine metadata_filter based on filename
            logger.debug(f"External metadata mapping: {external_metadata}")
            doc_metadata_filter = ""
            if external_metadata:
                for key, value in external_metadata.items():
                    if key in filename:
                        doc_metadata_filter = value
                        break

            # Skip the 'name' key at the top level if present
            file_name_field = data.get("name", filename)
            # control is just a variable name
            for control_id, control_data in data.items():
                # Skip the 'name' field at root level
                if control_id == "name":
                    continue

                # Skip if not a dict (unexpected structure)
                if not isinstance(control_data, dict):
                    logger.warning(f"Skipping non-dict entry: {control_id}")
                    continue

                # Build title: control_id + name field
                control_name = control_data.get("name", "")
                title = f"{control_id}: {control_name}" if control_name else control_id

                # Content is the full YAML dump of the subsection
                content = yaml.dump(
                    {control_id: control_data},
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

                # Use matched metadata_filter if found, else fallback to default
                metadata_filter_value = doc_metadata_filter or getattr(
                    gc, "YML_METADATA_FILTER", "source"
                )
                doc = Document(
                    page_content=content,
                    metadata={
                        "raw_source": file_path,
                        "file_name": filename,
                        "control_id": control_id,
                        "control_name": control_name,
                        "family": control_data.get("family", ""),
                        "source": filename,
                        "title": title,
                        "metadata_filter": metadata_filter_value,
                    },
                )
                documents.append(doc)

            logger.debug(
                f"Loaded {len(documents)} control documents from {file_path} using YAML loader"
            )
            return documents

        except Exception as e:
            logger.error(f"Error loading YAML file at {file_path}: {e}")
            return []

    def loadTXTFile(self, file_path, encoding="utf-8"):
        loader = TextLoader(file_path, encoding=encoding)

        try:
            docs = loader.load()
        except Exception as e:
            logger.error(f"Error loading text file at {file_path}: {e}")
            docs = []
        logger.debug(f"Loaded {len(docs)} documents from {file_path} using TextLoader")
        return docs

    def loadJSONFile(
        self,
        file_path,
        jq_schema=".",
        json_lines=False,
        external_metadata=None,
        source_column=None,
        metadata_field=None,
    ):
        # Load JSON data into a Python list
        # Initialize an empty list to hold documents
        documents = []

        # Get metadata_filter based on filename match
        filename = os.path.basename(file_path)
        doc_metadata_filter = ""
        if external_metadata:
            for key, value in external_metadata.items():
                if key in filename:
                    doc_metadata_filter = value
                    break

        # Read the JSON file
        if json_lines:
            # Open the file and read line by line
            with open(file_path, "r", encoding="utf-8") as file:
                for line in file:
                    # Parse JSON object from the line
                    json_object = json.loads(line)
                    # Get metadata_filter: field takes precedence, then filename match
                    field_metadata = (
                        json_object.get(metadata_field) if metadata_field else None
                    )
                    metadata_filter_value = field_metadata or doc_metadata_filter

                    if source_column is not None:
                        documents.append(
                            Document(
                                page_content=line,
                                metadata={
                                    "id": json_object[source_column],
                                    "title": json_object[source_column],
                                    "source": filename,
                                    "metadata_filter": metadata_filter_value,
                                },
                            )
                        )
                    else:
                        documents.append(
                            Document(
                                page_content=line,
                                metadata={
                                    "id": json_object.get("id"),
                                    "title": json_object.get("id"),
                                    "source": filename,
                                    "metadata_filter": metadata_filter_value,
                                },
                            )
                        )
        else:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                # Check if data is a list or a dictionary
                if isinstance(data, list):
                    # If the JSON file contains a list of documents
                    for item in data:
                        if "n" in item:
                            item = item["n"]
                        # Get metadata_filter: field takes precedence, then filename match
                        field_metadata = (
                            item.get(metadata_field) if metadata_field else None
                        )
                        metadata_filter_value = field_metadata or doc_metadata_filter

                        documents.append(
                            Document(
                                page_content=item.get(
                                    "desc",
                                    item.get(
                                        "description", item.get("text", item["id"])
                                    ),
                                ),
                                metadata={
                                    "id": item["id"],
                                    "title": item["id"],
                                    "source": filename,
                                    "metadata_filter": metadata_filter_value,
                                },
                            )
                        )
                elif isinstance(data, dict):
                    if len(data) == 1:
                        # If the JSON file contains a single document
                        # Get metadata_filter: field takes precedence, then filename match
                        field_metadata = (
                            data.get(metadata_field) if metadata_field else None
                        )
                        metadata_filter_value = field_metadata or doc_metadata_filter

                        documents.append(
                            Document(
                                page_content=data["text"],
                                metadata={
                                    "id": data["id"],
                                    "title": data["id"],
                                    "source": filename,
                                    "metadata_filter": metadata_filter_value,
                                },
                            )
                        )
                    else:
                        for k, v in data.items():
                            # Initialize an empty list to collect matching values
                            filtered_values = []

                            # Iterate through the dictionary
                            for kv, vv in v.items():
                                # Use regex to match keys ending with "description", "label", or "desc"
                                if re.match(
                                    r".*(description|descriptions|label|desc|aliases|text)$",
                                    kv,
                                ):  # Match based on the regex
                                    # if re.match(r".*(label)$", kv):  # Match based on the regex
                                    filtered_values.append(
                                        str(vv)
                                    )  # Collect the value (ensure it's string)

                            result_string = " ".join(filtered_values) + " "
                            docid = k + "|" + v.get("label", "")
                            # Get metadata_filter: field takes precedence, then filename match
                            field_metadata = (
                                v.get(metadata_field) if metadata_field else None
                            )
                            metadata_filter_value = (
                                field_metadata or doc_metadata_filter
                            )

                            documents.append(
                                Document(
                                    page_content=result_string,
                                    metadata={
                                        "id": docid,
                                        "title": docid,
                                        "source": filename,
                                        "metadata_filter": metadata_filter_value,
                                    },
                                )
                            )
        return documents

    def loadCSV_Embedding(self, embedding_file_path, persist_directory, offset, header):
        import pandas as pd

        df = pd.read_csv(embedding_file_path, sep="\t", header=header)

        # Create LangChain Document objects and store embeddings separately
        documents = []
        embeddings = {}
        for index, row in df.iterrows():
            doc_id = str(row[0])  # Assuming the first column is the document name
            embedding = row[
                offset:
            ].tolist()  # Convert the rest of the columns to a list for the embedding
            if not embedding:
                raise ValueError(f"Empty embedding at row {index}")
            documents.append(Document(page_content=doc_id, metadata={"id": doc_id}))
            embeddings[doc_id] = embedding

        # Custom embedding function that retrieves embeddings from the precomputed dictionary
        class CustomEmbeddings(Embeddings):
            def embed_documents(self, docs):
                if isinstance(docs[0], Document):
                    return [embeddings[doc.metadata["id"]] for doc in docs]
                else:
                    return [embeddings[str(doc).strip()] for doc in docs]

            def embed_query(self, text):
                # Dummy implementation for the sake of completeness
                return [0] * len(next(iter(embeddings.values())))

        # Initialize the custom embedding function
        custom_embeddings = CustomEmbeddings()

        vectordb = Chroma.from_documents(
            documents=documents,
            embedding=custom_embeddings,
            persist_directory=persist_directory,  # Specify the directory if you want to persist the database
        )

        # # Add documents to Chroma (manually setting embeddings)
        # for doc in documents:
        #     vectordb.add_document(doc)

        # vectordb.add_documents(documents=documents, {"embedding":embedding})
        # sys.stderr.write(f"#Collections : {vectordb._collection.count()}")
        return vectordb

    # if no source_column is setup, file_path is "source" in the metadata.
    # If source_column is set, that is the "source"
    # content_columns (Sequence[str]) – A sequence of column names to use for the document content.
    # If not present, use all columns that are not part of the metadata.
    def loadCSVFile(
        self,
        file_path,
        source_column,
        encoding,
        sep=",",
        chunking=False,
        internal_metadata=None,
        external_metadata=None,
    ):
        # Get metadata_filter based on filename match
        filename = os.path.basename(file_path)
        doc_metadata_filter = ""
        if external_metadata:
            for key, value in external_metadata.items():
                if key in filename:
                    doc_metadata_filter = value
                    break
        if not doc_metadata_filter:
            doc_metadata_filter = getattr(gc, "CSV_METADATA_FILTER", "csvsource")

        # sys.stderr.write("seperator is " + sep + ".")
        if chunking is False:
            docs = []
            try:
                if internal_metadata:
                    loader = CSVLoader(
                        file_path,
                        source_column,
                        encoding=encoding,
                        csv_args={"delimiter": sep},
                        metadata_columns=internal_metadata,
                    )
                else:
                    loader = CSVLoader(
                        file_path,
                        source_column,
                        encoding=encoding,
                        csv_args={"delimiter": sep},
                    )
                docs = loader.load()
            except (ValueError, KeyError, RuntimeError) as e:
                # CSVLoader fails on special chars in column names or multiline quoted fields
                logger.warning(f"CSVLoader failed: {e}, falling back to pandas")
                import pandas as pd

                df = pd.read_csv(file_path, sep=sep, encoding=encoding)

                if source_column not in df.columns:
                    logger.error(f"Column '{source_column}' not found in CSV, available: {list(df.columns)}")
                    raise ValueError(
                        f"Source column '{source_column}' not found in CSV file"
                    )

                for _, row in df.iterrows():
                    doc_content = str(row[source_column])
                    metadata = {"source": str(row[source_column])}
                    if internal_metadata:
                        for col in internal_metadata:
                            if col in df.columns:
                                metadata[col] = str(row[col])
                    docs.append(Document(page_content=doc_content, metadata=metadata))

                logger.info(f"Loaded {len(docs)} docs using pandas fallback")
            # sys.stderr.write(len(docs))

            # Filter documents based on whether the column is present in content
            filtered_docs = []
            for doc in docs:
                # Check if the column exists in the document (present in doc.metadata)
                if (
                    "source" in doc.metadata and doc.metadata["source"] != ""
                ):  # Column exists and has value
                    doc.metadata["metadata_filter"] = doc_metadata_filter
                    filtered_docs.append(doc)
            # sys.stderr.write(len(filtered_docs))
            return filtered_docs
        else:
            import dask.dataframe as dd

            df = dd.read_csv(file_path, sep=sep, blocksize="500MB")
            docs = []
            batchid = 0
            # Process each partition in batches
            for batch in df.to_delayed():
                batch_df = (
                    batch.compute()
                )  # Convert the partition into a Pandas DataFrame

                # Save to a temporary file (needed for CSVLoader)
                temp_file = "temp_chunk.csv"
                batch_df.to_csv(temp_file, index=False, sep=sep)

                # Load the batch using LangChain's CSVLoader
                logger.debug(f"Loading batch {batchid}")
                batchid += 1
                loader = CSVLoader(
                    temp_file,
                    source_column,
                    encoding=encoding,
                    csv_args={"delimiter": sep},
                )
                batch_docs = loader.load()

                # Accumulate documents instead of overwriting
                docs.extend(batch_docs)
            # sys.stderr.write("All batches complete")
            return docs

    def loadImageFiles(
        self,
        file_paths: List[str],
        use_vision_extraction: bool = False,
        model=None,
        external_metadata: Optional[dict] = None,
    ) -> List[Document]:
        """Load PNG/JPG images as documents with optional vision model text extraction.

        Args:
            file_paths: List of image file paths (PNG, JPG)
            use_vision_extraction: If True, extract text from images using LLM
            model: LLM model instance (Claude/GPT-4o with vision capability)
            external_metadata: Optional metadata mapping by filename

        Returns:
            List of Document objects with images as content
        """
        if not PIL_AVAILABLE:
            logger.warning("PIL not available, cannot load images")
            return []

        docs = []
        supported_formats = (".png", ".jpg", ".jpeg", ".gif", ".bmp")

        for file_path in file_paths:
            if not file_path.lower().endswith(supported_formats):
                logger.warning(f"Skipping {file_path}: unsupported image format")
                continue

            if not os.path.exists(file_path):
                logger.error(f"Image file not found: {file_path}")
                continue

            try:
                # Verify it's a valid image
                Image.open(file_path)

                # Extract text if model available
                if use_vision_extraction and model:
                    content = self._extract_image_text(file_path, model)
                else:
                    # Default: use filename/basic metadata as content
                    content = f"Image: {os.path.basename(file_path)}"

                # Create metadata
                metadata = {
                    "source": os.path.basename(file_path),
                    "type": "image",
                    "image_path": file_path,
                }

                # Add external metadata if available
                if (
                    external_metadata
                    and os.path.basename(file_path) in external_metadata
                ):
                    metadata["category"] = external_metadata[
                        os.path.basename(file_path)
                    ]

                doc = Document(page_content=content, metadata=metadata)
                docs.append(doc)
                logger.info(f"Loaded image: {file_path}")

            except Exception as e:
                logger.error(f"Error loading image {file_path}: {e}")
                continue

        return docs

    def loadPDFImages(
        self,
        file_path: str,
        use_vision_extraction: bool = False,
        model=None,
    ) -> List[Document]:
        """Extract images from a PDF and return as documents with optional text extraction.

        Args:
            file_path: Path to PDF file
            use_vision_extraction: If True, extract text from images using LLM
            model: LLM model instance (Claude/GPT-4o with vision capability)

        Returns:
            List of Document objects for each image in PDF
        """
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available, cannot extract images from PDF")
            return []

        docs = []

        if not os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return docs

        try:
            pdf_document = fitz.open(file_path)
            pdf_name = os.path.basename(file_path)

            for page_num, page in enumerate(pdf_document):
                image_list = page.get_images(full=True)

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)

                    # Convert to PNG bytes
                    image_bytes = pix.tobytes("png")

                    # Extract text if model available
                    if use_vision_extraction and model:
                        img_base64 = base64.b64encode(image_bytes).decode("utf-8")
                        content = self._extract_image_text_from_base64(
                            img_base64, model
                        )
                    else:
                        content = f"Image from {pdf_name} (page {page_num + 1}, image {img_index + 1})"

                    metadata = {
                        "source": pdf_name,
                        "type": "image",
                        "page": page_num + 1,
                        "image_index": img_index,
                    }

                    doc = Document(page_content=content, metadata=metadata)
                    docs.append(doc)
                    logger.info(f"Extracted image from {pdf_name} page {page_num + 1}")

            pdf_document.close()

        except Exception as e:
            logger.error(f"Error extracting images from {file_path}: {e}")

        return docs

    def _extract_image_text(self, image_path: str, model) -> str:
        """Extract text from image file using LLM with vision capability.

        Args:
            image_path: Path to image file
            model: LLM model with vision support (ChatOpenAI, ChatAnthropic, etc.)

        Returns:
            Extracted text description
        """
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            img_base64 = base64.b64encode(image_bytes).decode("utf-8")
            return self._extract_image_text_from_base64(img_base64, model)

        except Exception as e:
            logger.error(f"Error extracting text from {image_path}: {e}")
            return f"Image: {os.path.basename(image_path)}"

    def _extract_image_text_from_base64(self, img_base64: str, model) -> str:
        """Extract text from base64 image using LLM with vision capability.

        Args:
            img_base64: Base64-encoded image string
            model: LLM model with vision support (Claude or GPT-4o)

        Returns:
            Extracted text description
        """
        try:
            from langchain_core.messages import HumanMessage

            # Use the model's native vision capability
            message = HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                    },
                    {
                        "type": "text",
                        "text": "Analyze this image and extract all visible text, key concepts, entities, and describe important visual relationships. Be concise.",
                    },
                ]
            )

            response = model.invoke([message])
            return response.content

        except Exception as e:
            logger.error(f"Error extracting image text via model: {e}")
            return "Image: [unable to extract]"
