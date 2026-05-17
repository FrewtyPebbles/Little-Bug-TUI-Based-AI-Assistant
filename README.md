# Little Bug 🐛

A terminal-based assistant using agentic AI built for security and scale. This software is made to be deployed on an intranet utilizing self hosted AI models.  Although it will eventually support certain cloud LLM providers aswel.

## 🌟 Features

 - **Streaming Responses**: Real-time chat updates as the model generates text
 - **Local Model Tools and RAG**: Basic file system reading RAG tools along with email drafting and mailto
 - **Vector Embeddings**: Local and (soon) centralized contact database RAG (Retrieval-Augmented Generation) support via SQLite-Vec (local) and Cassandra (centralized)

## Experimental Backend features (currently WIP)

> A checked box means the feature has been tested and is functional.

 - [ ] Enables chat communications between users
 - [ ] Network centralized contact / document embeddings based RAG using mongodb
 - [ ] Global RBAC and user level secured RAG
