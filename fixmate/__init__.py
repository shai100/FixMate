"""FixMate — an AI troubleshooting assistant for field technicians.

Top-level package. Subpackages mirror the system's layers: ``core`` (config, DB,
storage, models), ``api`` (HTTP surface), ``answers`` (the RAG pipeline),
``retrieval`` (hybrid search), ``ingestion`` (turning PDFs into searchable
chunks), ``llm`` (provider abstraction), ``curation`` (the fix review workflow),
``feedback``, and ``evals``. See ``docs/ARCHITECTURE.md`` for the big picture.
"""
