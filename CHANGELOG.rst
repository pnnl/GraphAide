=========
Changelog
=========

Version 0.7.0
=============

- feat: Wikidata grounding agent integrated into the smart extractor workflow
- feat: Disambiguation documentation and extraction navigation
- change: Node.node_id equals the Wikidata English label when wikidata_id is set, otherwise english_name
- fix: Context builder deduplicates type definitions across summary and retrieval results
- fix: LangFuse setup no longer logs API key material
- fix: Removed hardcoded Neo4j password from package example and docs

Version 0.6.10
==============

- fix: Optional import in explain()
- fix: Removed broken KGIngest module
- docs: Updated install version

Version 0.6.9
=============

- Removed nodes4edges loader; added nodeedgefixer agent for KG consistency
- Added support for image agent and endpoint

Version 0.5.0
=============

- feat: Full LangFuse observability integration across all agent endpoints (extract, ingest, load_json)
- fix: LangFuse callback propagation through chain invocations
- fix: Extend callbacks to all agents via _invoke_chain() helper method
- feat: Debug callback for verifying LangChain event firing

Version 0.1
===========

- Feature A added
- FIX: nasty bug #1729 fixed
- add your changes here!
