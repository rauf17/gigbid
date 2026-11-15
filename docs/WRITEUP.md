# My Retrieval Evaluation Lied to Me Three Times

**By Rauf**  
*A reflection on metric hygiene, synthetic evaluation traps, and hard-won lessons from building the GigBid agentic RAG pipeline.*

---

When building an autonomous freelancer copilot, the instinct is to immediately start wiring language models together into complex agent choreographies. After all, watching an LLM read a client job, generate a proposal, and route a message feels like progress. But in an autonomous system designed to bid real capital on real contracts, the entire multi-agent architecture is only as good as the ground truth evidence fed into it. If the retrieval-augmented generation (RAG) engine surfaces the wrong case study or hallucinates a deliverable, the downstream Writer, Verifier, and Critic nodes are simply optimizing fiction.

To avoid this, I did what every diligent engineer is supposed to do: I built a quantitative retrieval benchmark. I created a synthetic dataset of 600 development jobs across three freelancer personas (AI/ML, Full-Stack Web, and Data Analysis), established pre-registered hypotheses, and wrote automated evaluation scripts to measure Recall@5, Mean Reciprocal Rank (MRR), and Normalized Discounted Cumulative Gain (nDCG@10).

And then, my retrieval evaluation lied to me. Not once, but three separate times.

Each lie produced numbers that looked plausible on the surface—sometimes flattering, sometimes catastrophic—until rigorous discrepancy testing forced me to look at the raw data beneath the abstractions. Here is the post-mortem of how my evaluation harness deceived me, what the corrected numbers actually revealed, and what it taught me about evaluating multi-agent RAG pipelines.

---

## Lie 1: The Embedder Index Mismatch

The first lie was subtle, insidious, and silent. During early prototyping, I initialized the vector index using a local SentenceTransformer model (`bge-small-en-v1.5`), generating 384-dimensional dense embeddings for every verified case study, resume section, client testimonial, and code snippet in the freelancer portfolios. The ingestion script finished cleanly, the vectors were persisted into local Qdrant collections, and the evaluation runner began computing cosine similarities.

The initial Recall@5 numbers came back around 0.12—terrible, but not so low as to trigger an immediate crash. I spent hours attempting to tune prompt phrasing in the query generation logic, suspecting that the LLM was failing to capture the nuance of client job descriptions. 

The reality was far dumber: due to an unpinned configuration override in an early `agent/config.yaml` draft, the evaluation query path was embedding runtime search strings using a completely different model checkpoint than the one that had indexed the corpus. Because both models outputted 384-dimensional vectors, the linear algebra never threw a shape mismatch exception. Dot products computed without complaint. The vectors were simply living in two entirely orthogonal, mutually unintelligible geometric spaces.

The retrieval engine was effectively playing darts in the dark. The lesson was immediate and uncompromising: vector stores must enforce manifest validation. I updated `rag/index/vector_store.py` with an immutable index manifest recording the exact model name, dimension, and content hash at ingestion time. Any retrieval attempt against an index built by a different model now raises an immediate runtime error rather than silently degrading into noise.

---

## Lie 2: The Chunk-vs-Item Identifier Disconnect

Once the embeddings were harmonized, I ran the baseline V0 Naive dense retrieval evaluation expecting a healthy bump. Instead, the console reported a devastating result: **Recall@5 = 0.0000 across all 511 evaluation queries.**

Zero. Not a single gold evidence item was apparently retrieved in the top-5 candidates for any job across 600 dev rows. 

I manually inspected the top retrieval candidates for a sample job (`job_hist_00031`, an AI/ML distributed pipeline role). The top hit was `ai_ml_cs_cs_aiml_001_chunk_00`, a detailed case study documenting distributed FastAPI and Celery streaming architectures. The gold requirement for that job explicitly listed `ai_ml_cs_cs_aiml_001`. The retrieval engine had found the exact right document—the semantic match was near-perfect, with a cosine similarity exceeding 0.78. 

Yet the evaluation harness recorded it as an utter failure. Why? Because the ingestion chunker split long markdown case studies into atomic passage chunks, appending `_chunk_00`, `_chunk_01`, and `_code_00` to the item identifiers. The gold label generator, working at the project planning level, had recorded parent document identifiers. The evaluation script was doing an exact string membership test: `if gold_id in retrieved_ids`. Because `"ai_ml_cs_cs_aiml_001"` did not strictly equal `"ai_ml_cs_cs_aiml_001_chunk_00"`, the evaluation silently discarded every correct retrieval in the entire dataset.

This is a classic failure mode of RAG benchmark design. When chunking strategies evolve, your evaluation harness must understand parent-child item provenance. Once I implemented canonical item ID resolution—mapping chunk keys back to their parent evidence entities—the measured Recall@5 jumped from a false `0.0000` to a true baseline of `0.2867` (`evals/results/rag_v0_naive_latest.json`). The model had been doing its job all along; the ruler measuring it had been broken.

---

## Lie 3: Synthetic Data Disconnect and the Leaked Answer Key

The third lie was the most intellectually humbling. To evaluate retrieval fairly without leaking test answers, I examined the relationship between the synthetic job posting text and the gold evidence IDs assigned to each job. 

In my initial data generation pipeline, job records were produced by sampling a set of required skills (e.g., `["Docker", "FastAPI", "PostgreSQL"]`) and then prompting an LLM to write a realistic, unstructured job posting incorporating those skills. The gold evidence labels (`relevant_evidence_ids`) were programmatically derived by looking up which portfolio case studies tagged those exact skills in their metadata.

This created an invisible chasm. The LLM writing the job postings frequently elaborated on business context, client tone, and peripheral requirements, sometimes completely submerging the core technical skills beneath paragraphs of generic corporate phrasing. Conversely, because the skill tags were sampled independently of the full portfolio text, a job posting might passionately describe an NLP text-mining challenge, but the synthetic gold label set demanded a Computer Vision case study because an unconstrained random seed had attached a `"PyTorch"` tag to both.

I discovered this when I built `rag_skill_tag_lookup_REFERENCE_latest.json`. When I bypassed the job text entirely and queried the vector store using only the raw synthetic skill tags, Recall@5 leaped to `0.4017` and nDCG@10 reached `0.5404`. Querying the tags was effectively leaking the answer key. But when querying the real, messy job description text via standard dense retrieval (`v0_naive`), Recall@5 dropped to `0.2867`. 

The synthetic dataset had introduced an artificial ceiling. Even an oracle retrieval algorithm querying the full text could only achieve a maximum Recall@5 of `0.5564` (`evals/results/rag_oracle_latest.json`), because the ground truth labels were tethered to metadata tags rather than textual semantic entailment. Acknowledging this limitation was critical: without understanding this ceiling, an engineer would spend weeks fruitlessly trying to tune an algorithm to hit 0.90 Recall when the data geometry makes anything above 0.56 mathematically impossible.

---

## What the Corrected Numbers Revealed

Once the metric pipeline was sanitized, I ran comprehensive benchmark ablations across all retrieval variants against the 511-query dev set. The verified results in `evals/results/` contradicted several popular industry narratives:

### 1. The Catastrophic Cost of Unfiltered Pools
In early designs, all portfolio items across all three personas were thrown into a single shared vector store. The hypothesis was that semantic dense search would naturally separate a Data Analyst's SQL queries from an AI/ML Engineer's CUDA kernels. 

The numbers proved this utterly wrong. In `evals/results/rag_v0_naive_unfiltered_latest.json`, unconstrained retrieval across all personas yielded an abysmal Recall@5 of **`0.0519`** and an nDCG@10 of **`0.0845`**. Overlapping technical terms (e.g., "Python", "ETL", "API") acted as semantic attractors, pulling in irrelevant case studies from the wrong freelancer. Enforcing strict metadata persona scoping (`v0_naive`) caused Recall@5 to soar by more than **5x to `0.2867`** and nDCG@10 to **`0.4617`** (`evals/results/rag_v0_naive_latest.json`). Metadata filtering is not an optional optimization; it is the single most impactful architectural choice in multi-persona RAG.

### 2. Hybrid Search and Cross-Encoders: Modest Gains, Heavy Latency
In my pre-registered hypothesis **H1**, I predicted that fusing BM25 lexical search with dense embeddings via Reciprocal Rank Fusion (RRF) would boost Recall@5 by at least 8.0 percentage points. 

The measured reality was far more modest: V2 Hybrid achieved Recall@5 of **`0.3121`** (`evals/results/rag_v2_hybrid_latest.json`), an improvement of only **+2.54 points** (+0.0254) over the V0 baseline. While hybrid search helped substantially on tool-dense AI/ML queries (lifting Dr. Elena Rostova's Recall@5 from `0.2222` to `0.3450`, +12.28 points), its overall impact was subdued.

Even more striking was the cross-encoder reranker (V3 Rerank). In hypothesis **H2**, I predicted that reranking the top 30 candidates with a transformer cross-encoder would dramatically lift MRR and nDCG@10. In practice, V3 Rerank nudged Recall@5 to **`0.3308`** (+1.87 points over V2) and nDCG@10 to **`0.4878`** (+0.0008), while ballooning p95 latency from **`296.7ms` to `2,982.4ms`** (`evals/results/rag_v3_rerank_latest.json`). A 10x latency penalty for an imperceptible ranking gain is an unviable trade-off in interactive agent systems.

### 3. The Decomposition Trap
The most dramatic failure was query decomposition (V1 Decompose). Following widespread advice in agentic design patterns, I built a stage where an LLM extracted atomic requirements from the job posting and issued separate retrieval queries for each requirement, merging the results.

The result was an unmitigated disaster:
- **Recall@5 fell from `0.2867` down to `0.2276`** (-5.91 percentage points).
- **MRR dropped from `0.7417` to `0.6660`**.
- **nDCG@10 dropped from `0.4617` to `0.4014`**.
- **Token overhead exploded by `363,928` tokens**, with p95 latency reaching `1,671.9ms` (`evals/results/rag_v1_decompose_latest.json`).

Breaking a holistic job posting into fragmented snippets stripped away the connective context that dense vector embeddings rely on. Isolated queries like `"experience with Docker"` pulled generic container setups rather than production MLOps pipelines. Holistic dense retrieval over the unified posting consistently outperformed fragmented multi-query decomposition.

---

## The Ultimate Lesson

Building production multi-agent systems is fundamentally an exercise in measurement discipline. It is remarkably easy to convince yourself that a complex architecture—with multi-stage decomposition, reciprocal rank fusion, cross-encoder reranking, and dynamic agent loops—is outperforming a simple baseline. The code is more impressive, the latency is higher, and the logs look busier.

Only when you ruthlessly sanitize your evaluation harness, enforce strict entity provenance, verify identifier mapping, and compare against hermetic baselines do you see the truth. In GigBid, that discipline prevented us from shipping an expensive, latency-bloated decomposition pipeline, steered us toward lightweight persona-filtered hybrid search, and provided the bedrock of verified evidence that allowed our downstream proposal verifier to eliminate 100% of hallucinated claims.

Don't trust intuition when building agentic RAG. Measure it, break your measurement, fix it, and measure it again.
