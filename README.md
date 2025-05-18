# DistRAG: Distributed RAG Database System

DistRAG is a containerized, distributed database platform build on **PostreSQL** and the Citus extension, designed for scalable query processing and *Retrieval-Augmented Generation* (RAG) tasks. It combines a Citus-based Postgres cluster with additional microservices for request routing, caching and AI-powered data processing. The system enables **horizontal scaling** of the database (by adding worker nodes), **parallel query execution** across nodes, and high availability via replication and automated backup/recovery. DistRAG's design supports scenarios such as large-scale analytics or AI-assisted question-answering over a growing dataset, all while maintaining a single entry points for the clients.

## Citus Cluster

At the core of DistRAG is a Citus Cluster: one PostgreSQL instance acts as a **Coordinator** and several other acts as **Workers**. The coordinator holds metadata about the distributed tables and orchestrates queries, which each worker stores shards (horizontal partitions) of the data [^1].

[^1]: [Citus Documentation](https://docs.citusdata.com/en/v7.0/aboutcitus/introduction_to_citus.html#:~:text=Coordinator%20%2F%20Worker%20Nodes%C2%B6)
