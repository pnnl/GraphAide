import json
import logging

from pydantic import BaseModel, Field

from ..state import Node, KGGenerationState
from .base import GraphAideAgent

logger = logging.getLogger("graphgen.agents.wikidatagrounder")

ENTITY_TYPE = "wikidata_entity"
TOP_K = 5


class QIDChoice(BaseModel):
    node_id: str = Field(description="node_id of the node being grounded")
    qid: str | None = Field(default=None, description="QID picked from this node's candidates, or null")


class QIDChoices(BaseModel):
    choices: list[QIDChoice]


def lookup_name(node: Node) -> str:
    return node.english_name or node.node_name or ""


def has_entity_documents(collection) -> bool:
    return bool(collection.get(where={"type": ENTITY_TYPE}, limit=1)["ids"])


def exact_label_candidates(collection, names: list[str], k: int = TOP_K) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {name: [] for name in names}
    if not names:
        return out
    hits = collection.get(
        where={"$and": [{"type": ENTITY_TYPE}, {"label": {"$in": list(names)}}]},
    )
    for meta in hits["metadatas"] or []:
        bucket = out.get(meta.get("label"))
        if bucket is not None and len(bucket) < k and meta.get("qid"):
            bucket.append({"qid": meta["qid"], "label": meta["label"]})
    return out


def similar_label_candidates(collection, embeddings, names: list[str], k: int = TOP_K) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {name: [] for name in names}
    if not names:
        return out
    res = collection.query(
        query_embeddings=embeddings.embed_documents(list(names)),
        n_results=k,
        where={"type": ENTITY_TYPE},
    )
    for name, metas in zip(names, res["metadatas"] or []):
        out[name] = [
            {"qid": m["qid"], "label": m["label"]}
            for m in (metas or [])
            if m.get("qid")
        ]
    return out


class WikidataGrounderAgent(GraphAideAgent):
    """Fill wikidata_id on nodes that lack one, using the Wikidata entity collection.

    Order: exact label match (one get), then similarity query for unmatched names
    (one query), then one structured LLM pick for names with several or only
    similarity candidates. A QID is accepted only if it came from that node's candidates.

    Output state keys:
        nodes (List[Node]): Full node list with wikidata_id filled where grounded.
        messages, agent_status.
    """

    def __call__(self, state: KGGenerationState) -> dict:
        nodes = list(state.get("nodes", []))
        vector_store = self.settings.get("vector_store")
        pending = [n for n in nodes if not n.wikidata_id and lookup_name(n)]

        if not pending or vector_store is None:
            message = f"Grounding skipped: {len(pending)} nodes without wikidata_id"
            return self._result(nodes, message)

        collection = vector_store._collection
        if not has_entity_documents(collection):
            message = (
                f"Grounding skipped: vector store has no '{ENTITY_TYPE}' documents; "
                f"load Wikidata entities with vectordbloader first"
            )
            logger.warning(message)
            return self._result(nodes, message)

        names = sorted({lookup_name(n) for n in pending})

        exact = exact_label_candidates(collection, names)
        unmatched = [name for name in names if not exact[name]]
        similar = (
            similar_label_candidates(collection, vector_store.embeddings, unmatched) if unmatched else {}
        )

        grounded_exact = 0
        ambiguous = []
        for node in pending:
            name = lookup_name(node)
            exact_hits = exact[name]
            if len(exact_hits) == 1:
                node.wikidata_id = exact_hits[0]["qid"]
                grounded_exact += 1
                continue
            candidates = exact_hits or similar.get(name, [])
            if candidates:
                ambiguous.append((node, candidates))

        grounded_llm = self._pick_with_llm(ambiguous)

        message = (
            f"Grounded {grounded_exact} nodes by exact label, {grounded_llm} by LLM pick, "
            f"{len(pending) - grounded_exact - grounded_llm} left without wikidata_id"
        )
        logger.info(f"SmartExtractor[wikidatagrounder] chunk={state.get('current_chunk_id')}: {message}")
        return self._result(nodes, message)

    def _pick_with_llm(self, ambiguous: list[tuple[Node, list[dict]]]) -> int:
        if not ambiguous:
            return 0

        payload = [
            {
                "node_id": node.node_id,
                "node_name": node.node_name,
                "english_name": node.english_name,
                "candidates": candidates,
            }
            for node, candidates in ambiguous
        ]
        chain = self.prompt | self.model.with_structured_output(QIDChoices)
        try:
            result = self._invoke_chain(chain, {"nodes": json.dumps(payload, ensure_ascii=False)})
            chosen = {c.node_id: c.qid for c in result.choices}
        except Exception as e:
            logger.warning(f"Wikidata grounding LLM pick failed, leaving nodes ungrounded: {e}")
            return 0

        grounded = 0
        for node, candidates in ambiguous:
            allowed = {c["qid"] for c in candidates}
            qid = chosen.get(node.node_id)
            if qid in allowed:
                node.wikidata_id = qid
                grounded += 1
        return grounded

    def _result(self, nodes: list[Node], message: str) -> dict:
        return {
            "nodes": nodes,
            "messages": [message],
            "current_agent": [self.__class__.__name__],
            "agent_status": {self.__class__.__name__: True},
        }
