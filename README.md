# DistRAG: Distributed RAG Database System

DistRAG is a containerized, distributed database platform build on **PostreSQL** and the Citus extension, designed for scalable query processing and *Retrieval-Augmented Generation* (RAG) tasks. It combines a Citus-based Postgres cluster with additional microservices for request routing, caching and AI-powered data processing. The system enables **horizontal scaling** of the database (by adding worker nodes), **parallel query execution** across nodes, and high availability via replication and automated backup/recovery. DistRAG's design supports scenarios such as large-scale analytics or AI-assisted question-answering over a growing dataset, all while maintaining a single entry points for the clients.

```mermaid
graph TB
    %% External Users
    Clients[External Clients]
    
    %% Load Balancer
    LoadBalancer[NGINX Load Balancer<br/>:80]

    %% External Services
    subgraph "External Services"
        Gemini[Google Gemini<br/>LLM + Embeddings]
    end
    
    %% AI Engine Cluster (RAG System)
    subgraph "AI Engine Cluster"
        subgraph "AI Engine 1 (:8001)"
            API1[FastAPI Service<br/>main.py]
            subgraph "RAG System Core 1"
                LLM1[LLM Engine<br/>llm.py]
                Indexer1[Database Indexer<br/>indexer.py]
                Pipeline1[Query Pipeline<br/>pipeline.py]
            end
            subgraph "Vector Storage 1"
                ChromaDB1[(ChromaDB<br/>Table Embeddings)]
            end
        end
        
        subgraph "AI Engine 2 (:8002)"
            API2[FastAPI Service]
            LLM2[LLM Engine]
        end
        
        subgraph "AI Engine 3 (:8003)"
            API3[FastAPI Service]
            LLM3[LLM Engine]
        end
    end
    
    %% Cache Engine
    subgraph "Cache Engine Service (:6380)"
        CacheAPI[FastAPI Interface<br/>main.py]
        CacheLogic[Cache Logic<br/>routes.py]
        RedisManager[Redis Manager<br/>utils.py]
        subgraph "Vector Storage"
            Redis[(Redis Vector Store<br/>Query Embeddings)]
        end
        subgraph "Embedding Layer"
            Embedder[Sentence Transformer<br/>Query Vectorization]
        end
    end
    
    %% Data Router
    subgraph "Data Router (:8085)"
        DataRouterAPI[FastAPI CRUD Operations<br/>main.py]
    end
    
    %% DB Engine
    subgraph "DB Engine"
        DBInit[DB Initializer<br/>db-init.py<br/>Schema Setup]
        ChangeListener[Change Listener<br/>change_listener.py<br/>PostgreSQL Notifications]
        Notifier[Notifier<br/>notifier.py<br/>Event Broadcaster]
    end
    
    %% Citus Cluster
    subgraph "Citus Distributed Cluster"
        Coordinator[PostgreSQL Coordinator<br/>pg_master<br/>:5432]
        Worker1[Worker 1<br/>pg_worker_1<br/>Data Shards]
        Worker2[Worker 2<br/>pg_worker_2<br/>Data Shards]
        ClusterManager[Cluster Manager<br/>Node Management]
        BackupService[Backup Service<br/>Data Protection]
        PgAdmin[pgAdmin<br/>Web Interface<br/>:8080]
    end

    
    %% Main Query Flow
    Clients --> LoadBalancer
    LoadBalancer --> API1
    LoadBalancer --> API2
    LoadBalancer --> API3
    
    %% AI Engine Internal Flow (Only for Engine 1)
    API1 --> CacheAPI
    API1 --> LLM1
    LLM1 --> Gemini
    LLM1 --> Pipeline1
    LLM1 --> Indexer1
    Indexer1 --> ChromaDB1
    Pipeline1 --> ChromaDB1
    
    %% Cache Engine Flow
    CacheAPI --> CacheLogic
    CacheLogic --> RedisManager
    RedisManager --> Embedder
    RedisManager --> Redis
    
    %% Data Router Flow
    DataRouterAPI --> Coordinator
    
    %% DB Engine Flow
    DBInit --> Coordinator
    Coordinator --> ChangeListener
    ChangeListener --> Notifier
    
    %% Citus Cluster Flow
    Coordinator --> Worker1
    Coordinator --> Worker2
    ClusterManager --> Coordinator
    ClusterManager --> Worker1
    ClusterManager --> Worker2
    BackupService --> Worker1
    BackupService --> Worker2
    PgAdmin --> Coordinator
    
    %% Cross-System Notifications (Only show one connection per type)
    Notifier -.->|Data Changes<br/>University-scoped| CacheAPI
    Notifier -.->|Schema Changes<br/>Full Rebuild| API1
    
    %% Database Connections (Only for one AI Engine)
    Pipeline1 --> Coordinator
    Indexer1 --> Coordinator
    
    %% Styling
    classDef loadbalancer fill:#ffcdd2
    classDef aiengine fill:#e3f2fd
    classDef cache fill:#f3e5f5
    classDef datarouter fill:#e8f5e8
    classDef dbengine fill:#fff3e0
    classDef citus fill:#e1f5fe
    classDef external fill:#ffebee
    
    class LoadBalancer loadbalancer
    class API1,API2,API3,LLM1,LLM2,LLM3,Indexer1,Pipeline1,ChromaDB1 aiengine
    class CacheAPI,CacheLogic,RedisManager,Redis,Embedder cache
    class DataRouterAPI datarouter
    class DBInit,ChangeListener,Notifier dbengine
    class Coordinator,Worker1,Worker2,ClusterManager,BackupService,PgAdmin citus
    class Clients,Gemini external
```

## Citus Cluster

At the core of DistRAG is a Citus Cluster: one PostgreSQL instance acts as a **Coordinator** and several other acts as **Workers**. The coordinator holds metadata about the distributed tables and orchestrates queries, which each worker stores shards (horizontal partitions) of the data [^1]. Incoming SQL queries (from the data-router) service are submitted to the coordinator; it then parallelizes each query for fragmenting it and sending the fragments to all the relevant workers. Each worker processes it shard locally, and the coordinator merges the results before returning them. This enables DistRAG to utilize the combined CPU and memory of the cluster for high-throughput query handling. Citus also replicates each shard on multiple workers (for redundancy), and supports **dynamic scaling**: new worker nodes can be added on-the-fly to capacity.

```mermaid
graph TB
    %% External Access
    DataRouter[Data Router<br/>FastAPI CRUD Operations<br/>]
    
    %% Citus Cluster Core
    subgraph "Citus Cluster"
        Coordinator[PostgreSQL Coordinator<br/>pg_master<br/>Query Orchestration]
        
        Worker1[Worker 1<br/>pg_worker_1<br/>Data Shards]
        Worker2[Worker 2<br/>pg_worker_2<br/>Data Shards]
        
        ClusterManager[Cluster Manager<br/>Node Management]
    end
    
    %% Services
    BackupService[Backup Service<br/>Data Protection]
    PgAdmin[pgAdmin<br/>Web Interface]
    
    %% Query Flow
    DataRouter -->|SQL Query| Coordinator
    Coordinator -->|Fragment & Distribute| Worker1
    Coordinator -->|Fragment & Distribute| Worker2
    Worker1 -->|Results| Coordinator
    Worker2 -->|Results| Coordinator
    Coordinator -->|Merged Results| DataRouter
    
    %% Management
    ClusterManager --> Coordinator
    ClusterManager --> Worker1
    ClusterManager --> Worker2
    
    BackupService --> Worker1
    BackupService --> Worker2
    
    PgAdmin --> Coordinator
    
    %% Styling
    classDef coordinator fill:#e3f2fd
    classDef worker fill:#f3e5f5
    classDef service fill:#e8f5e8
    classDef external fill:#ffebee
    
    class Coordinator coordinator
    class Worker1,Worker2 worker
    class ClusterManager,BackupService,PgAdmin service
    class DataRouter external
```

## AI Engine (RAG)

The AI Engine in DistRAG enables users to query structured data in the distributed Citus cluster using natural language through a Retrieval-Augmented Generation (RAG) pipeline. When a user submits a prompt, the engine leverages a Gemini-based language model to understand the question, retrieve relevant database tables, generate an appropriate SQL query, execute it, and return a synthesized answer. This pipeline is built using LlamaIndex components like **SQLRetriever**, **VectorStoreIndex**, and **QueryPipeline**, which combine semantic retrieval and language-to-SQL generation.

```mermaid
graph TB
    %% External Systems
    Client[Client]
    PostgresDB[(PostgreSQL)]
    CacheEngine[Cache Service]

    %% Main Components
    subgraph "API Layer"
        FastAPI[FastAPI Service<br/>main.py]
    end

    subgraph "RAG System Core"
        LLM[LLM Engine<br/>llm.py]
        Indexer[Database Indexer<br/>indexer.py]
        Pipeline[Query Pipeline<br/>pipeline.py]
    end

    subgraph "Vector Storage"
        ChromaDB[(ChromaDB<br/>Table Embeddings)]
    end

    subgraph "External Services"
        Gemini[Google Gemini<br/>LLM + Embeddings]
    end

    %% RAG Flow
    Client --> FastAPI
    FastAPI --> CacheEngine
    FastAPI --> LLM
    
    %% Indexing Flow (Retrieval Preparation)
    LLM --> Indexer
    Indexer --> PostgresDB
    Indexer -->|Schema Analysis| Gemini
    Indexer -->|Table Descriptions| ChromaDB
    
    %% Query Flow (Retrieval + Generation)
    LLM --> Pipeline
    Pipeline -->|Table Retrieval| ChromaDB
    Pipeline -->|Text-to-SQL| Gemini
    Pipeline -->|SQL Execution| PostgresDB
    Pipeline -->|Response Generation| Gemini

    %% Styling
    classDef external fill:#e1f5fe
    classDef rag fill:#f3e5f5
    classDef storage fill:#e8f5e8
    classDef service fill:#fff3e0

    class Client,PostgresDB,CacheEngine,Gemini external
    class LLM,Indexer,Pipeline rag
    class ChromaDB storage
    class FastAPI service
```

Behind the scenes, the system is composed of three main modules: indexer.py, which semantically summarizes and embeds table schemas into a vector store; pipeline.py, which builds a modular SQL query pipeline that interprets user intent and executes SQL; and llm.py, which manages threading, environment config, model/key rotation, and persistent vector stores (via Chroma). The architecture ensures scalable, schema-aware, and human-friendly querying over large datasets without requiring SQL knowledge from the end user.

#### NGINX (nginx-ai-engine) 
An NGINX proxy/load balancer in front of the AI Engine. It distributes incoming inference requests across one or more AI engine containers for high throughput and fault tolerance.

## Cache Engine

The Cache Engine in DistRAG acts as a caching layer that reduces redundant computation and database load by storing and retrieving previously seen query-response pairs. Backed by Redis with **vector search capabilities**, this service semantically caches responses by embedding incoming queries and indexing them in Redis for **approximate nearest-neighbor (ANN)** search.

At its core, the RedisManager (defined in utils.py) initializes a Redis instance and a SentenceTransformer-based embedder, both configurable via environment variables. Each user query is encoded into a dense vector and stored along with its response under a namespace defined by the **partitioning index** (multi-tenancy). The system supports configurable cache eviction (e.g., by size or policy) and can flush entries per university.

This caching strategy offers significant performance benefits by offloading repeat queries and enabling fast semantic lookups without full SQL execution. It also provides a foundation for personalization (e.g., cache per university or user group) and aligns well with the vector-based retrieval paradigm used throughout DistRAG.

```mermaid
graph TB
    %% External Systems
    Client[AI Engine]
    
    %% Cache Engine Components
    subgraph "Cache Engine Service"
        API[FastAPI Interface<br/>main.py]
        CacheLogic[Cache Logic<br/>routes.py]
        RedisManager[Redis Manager<br/>utils.py]
    end

    %% Storage & Processing
    subgraph "Vector Storage"
        Redis[(Redis Vector Store<br/>Query Embeddings)]
    end

    subgraph "Embedding Layer"
        Embedder[Sentence Transformer<br/>Query Vectorization]
    end

    %% Flow
    Client -->|Query Request| API
    Client -->|Cache Response| API
    
    API --> CacheLogic
    CacheLogic --> RedisManager
    
    RedisManager --> Embedder
    RedisManager --> Redis
    
    %% Semantic Operations (as labels)
    CacheLogic -.->|Semantic Search| Redis
    RedisManager -.->|Multi-tenant Partitioning| Redis
    Redis -.->|Similarity Matching| CacheLogic

    %% Styling
    classDef external fill:#e1f5fe
    classDef core fill:#f3e5f5
    classDef storage fill:#e8f5e8
    classDef ml fill:#fff3e0

    class Client external
    class API,CacheLogic,RedisManager core
    class Redis storage
    class Embedder ml
```

## DB Engine

The DB Engine in DistRAG is a PostgreSQL-based data infrastructure component built atop a Citus coordinator. Beyond storing and distributing data shards across workers, this engine includes intelligent runtime services to initialize the schema, listen for database changes, and notify external systems (like the cache and AI engine) when updates occur. This ensures data consistency, schema awareness, and cache invalidation across the distributed system.

When a schema change (such as table creation or modification) occurs, the engine broadcasts notifications to all registered LLM Engine instances. This triggers a full pipeline rebuild, ensuring that the AI system stays aware of the latest database structure and can continue generating accurate SQL from natural language prompts. In contrast, when a data update happens—specifically involving the partitioning key (e.g., university_id)—the DB Engine selectively notifies the Cache Engine. This results in a targeted flush of only the cache entries associated with the affected partition, preserving other cached results and minimizing performance impact. This bifurcation of update handling—schema-triggered pipeline rebuilds and data-triggered scoped cache invalidation—ensures the system remains both up-to-date and efficient, particularly in multi-tenant deployments.

```mermaid
graph TB
    %% Core Components
    subgraph "DB Engine"
        DBInit[DB Initializer<br/>db-init.py<br/>Schema Setup]
        ChangeListener[Change Listener<br/>change_listener.py<br/>PostgreSQL Notifications]
        Notifier[Notifier<br/>notifier.py<br/>Event Broadcaster]
    end

    %% Database
    subgraph "Citus Cluster"
        Coordinator[PostgreSQL Coordinator<br/>with Event Triggers]
    end

    %% External Systems
    CacheEngine[Cache Engine<br/>Selective Invalidation]
    LLMEngines[AI Engines<br/>Pipeline Rebuild]

    %% Flow
    DBInit -->|Initialize Schema & Triggers| Coordinator
    Coordinator -->|LISTEN/NOTIFY| ChangeListener
    ChangeListener -->|Parse Events| Notifier
    
    %% Notification Types
    Notifier -->|Data Changes<br/>Selective Cache Flush| CacheEngine
    Notifier -->|Schema Changes<br/>Full Rebuild| LLMEngines
    Notifier -->|Schema Changes<br/>Flush All Cache| CacheEngine

    %% Event Types
    subgraph "Event Handling"
        DataChange[Data Change Event<br/>Partition-specific]
        SchemaChange[Schema Change Event<br/>System-wide]
    end

    ChangeListener --> DataChange
    ChangeListener --> SchemaChange
    DataChange --> CacheEngine
    SchemaChange --> LLMEngines
    SchemaChange --> CacheEngine

    %% Styling
    classDef dbengine fill:#e3f2fd
    classDef database fill:#f3e5f5
    classDef external fill:#e8f5e8
    classDef events fill:#fff3e0

    class DBInit,ChangeListener,Notifier dbengine
    class Coordinator database
    class CacheEngine,LLMEngines external
    class DataChange,SchemaChange events
```

## Worker Backup/Recovery

DistRAG’s **Worker Backup and Worker Recovery** services ensure fault tolerance and data durability across the distributed Citus worker nodes. The backup service is initiated only after the worker cluster signals successful initialization. It performs periodic incremental WAL archiving and scheduled full backups of each worker using PostgreSQL-native tools like pg_basebackup. These operations are coordinated via worker-backup.sh, which supports dynamic worker discovery, retry logic, and backup rotation with configurable retention policies. The backup process is monitored through a dedicated entrypoint script that verifies readiness and ensures that initial snapshots are successfully taken before the system proceeds to serve traffic.

On the other hand, the Worker Recovery service continuously monitors the backup signal and launches a watchdog (worker-recovery.py) that uses the Docker API to detect failed or missing worker containers. When a failure is detected, the recovery logic automatically provisions a new container and restores the most recent backup for the corresponding worker using the available archive data. This hands-free approach allows DistRAG to quickly recover from node crashes, data corruption, or machine failures without manual intervention, ensuring high availability and minimal data loss across the Citus cluster.

[^1]: [Citus Documentation](https://docs.citusdata.com/en/v7.0/aboutcitus/introduction_to_citus.html#:~:text=Coordinator%20%2F%20Worker%20Nodes%C2%B6)
