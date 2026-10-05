ontology_loader_node = agent_factory.build(
        agent_class=ontoloader.OntologyLoaderAgent,
        agent_id="ontologyloader",
        partials={"format_instructions": "format_instructions"},
    )

    extractor_node = agent_factory.build(
        agent_class=ea.ExtractorAgent,
        agent_id="extractor",
        partials={"format_instructions": "format_instructions"},
    )

    nodes4edgesloader_node = agent_factory.build(
        agent_class=ne.Nodes4EdgesLoaderAgent,
        agent_id="nodes4edgesloader",
        partials={"format_instructions": "Instruction"},
    )
    nodesloader_node = agent_factory.build(
        agent_class=nl.NodesLoaderAgent,
        agent_id="nodesloader",
        partials={"format_instructions": "Instruction"},
    )
    edgesloader_node = agent_factory.build(
        agent_class=el.EdgesLoaderAgent,
        agent_id="edgesloader",
        partials={"format_instructions": "Instruction"},
        model_config=mf.ModelConfig(
            provider="lmstudio",
            model_name="google/gemma-3-27b:2",
            embedding_model_name="text-embedding-nomic-embed-text-v1.5",
        ),
    )
    neo4jpostprocessor_node = agent_factory.build(
        agent_class=npp.Neo4jPostProcessorAgent,
        agent_id="neo4jpostprocessor",
        partials={"format_instructions": "Instruction"},
    )

    retry_policy = RetryPolicy(
        initial_interval=1.0,  # Start with 1 second
        backoff_factor=2.0,  # Exponential backoff (1s → 2s → 4s → 8s...)
        max_interval=60.0,  # Max 60 seconds between retries
        max_attempts=3,  # Retry max 3 times
        jitter=True,  # Add randomness to prevent thundering herd
    )
    # --- 3. Construct the workflow with a State ---
    # add a subgraph that combines extractor, nodes4edgesloader, nodesloader, edgesloader, and neo4jpostprocessor into a single "KnowledgeGraphLoader" node with retry policy applied to the whole subgraph
    workflow_kgloader = StateGraph(KGGenerationState)
    workflow_kgloader.add_node("extractor", extractor_node)
    workflow_kgloader.add_node("nodes4edgesloader", nodes4edgesloader_node)
    workflow_kgloader.add_node("nodesloader", nodesloader_node)
    workflow_kgloader.add_node("edgesloader", edgesloader_node)
    workflow_kgloader.add_node("neo4jpostprocessor", neo4jpostprocessor_node)
    workflow_kgloader.add_edge(START, "extractor")
    workflow_kgloader.add_edge("extractor", "nodes4edgesloader")
    workflow_kgloader.add_edge("nodes4edgesloader", "nodesloader")
    workflow_kgloader.add_edge("nodesloader", "edgesloader")
    workflow_kgloader.add_edge("edgesloader", "neo4jpostprocessor")
    workflow_kgloader.add_edge("neo4jpostprocessor", END)

    workflow_kgloader_app = workflow_kgloader.compile()

    # --- 3. Construct the workflow with a State ---
    workflow = StateGraph(KGGenerationState)

    # Add our factory-built agent as a node
    workflow.add_node(
        "knowledgegraphloader", workflow_kgloader_app, retry_policy=retry_policy
    )
    workflow.add_node("ontologyloader", ontology_loader_node)
    workflow.add_node("fileloader", fnn.fileloader, retry_policy=retry_policy)
    # Define the sequence

    workflow.add_edge(START, "ontologyloader")
    workflow.add_edge("ontologyloader", "fileloader")
    workflow.add_conditional_edges(
        "fileloader",
        fnn.make_segment_dispatcher("knowledgegraphloader"),
        ["knowledgegraphloader"],
    )
    workflow.add_edge("knowledgegraphloader", END)
    # Compile the graph
    app = workflow.compile()
    return app