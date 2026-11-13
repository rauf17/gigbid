#!/usr/bin/env python3
"""Synthetic Persona Data Generator (AI-4016 GigBid Phase 1a).

Deterministic generator producing synthetic persona corpora under data/personas/<persona_id>/:
  - profile.json
  - cv.md & cv.pdf
  - case_studies/*.md (15-25 files with YAML front-matter)
  - repos/<name>/README.md + 2-4 small realistic code files each
  - reviews.json
  - past_proposals.jsonl (~150 items with plausible outcome correlation)

Usage:
  python data/scripts/gen_personas.py --seed 42 --output-dir data/personas
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def write_clean_pdf(lines: list[str], output_path: Path) -> None:
    """Deterministic, pure-python standard-compliant minimal PDF writer."""
    # Chunk lines into pages of max 42 lines
    pages: list[list[str]] = []
    current_page: list[str] = []
    for line in lines:
        current_page.append(line)
        if len(current_page) >= 42:
            pages.append(current_page)
            current_page = []
    if current_page or not pages:
        pages.append(current_page)

    font_obj_id = 3 + len(pages) * 2
    kids = []
    page_objs = []
    content_objs = []

    for i, p_lines in enumerate(pages):
        page_id = 3 + i * 2
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R")

        stream_content = "BT\n/F1 10 Tf\n50 740 Td\n15 TL\n"
        for line in p_lines:
            clean = line.encode("ascii", errors="replace").decode("ascii")
            safe = clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream_content += f"({safe}) ' \n"
        stream_content += "ET"
        s_bytes = stream_content.encode("latin1")

        p_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_obj_id} 0 R >> >> >>"
        ).encode("latin1")
        c_obj = f"<< /Length {len(s_bytes)} >>\nstream\n".encode("latin1") + s_bytes + b"\nendstream"
        page_objs.append((page_id, p_obj))
        content_objs.append((content_id, c_obj))

    kids_str = " ".join(kids)
    pages_obj = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(pages)} >>".encode("latin1")

    all_objs = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: pages_obj,
    }
    for pid, pbytes in page_objs:
        all_objs[pid] = pbytes
    for cid, cbytes in content_objs:
        all_objs[cid] = cbytes
    all_objs[font_obj_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    total_objs = len(all_objs)
    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj_num in range(1, total_objs + 1):
        offsets.append(len(body))
        body += f"{obj_num} 0 obj\n".encode("latin1") + all_objs[obj_num] + b"\nendobj\n"

    startxref = len(body)
    body += f"xref\n0 {total_objs + 1}\n0000000000 65535 f \n".encode("latin1")
    for off in offsets[1:]:
        body += f"{off:010d} 00000 n \n".encode("latin1")
    body += f"trailer\n<< /Size {total_objs + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("latin1")

    output_path.write_bytes(body)


def get_persona_definitions() -> dict[str, dict]:
    return {
        "ai_ml": {
            "id": "ai_ml",
            "name": "Dr. Elena Rostova",
            "title": "Lead AI/ML Systems Engineer & LLM Specialist",
            "rates": {"hourly": 95, "fixed_minimum": 1500},
            "floor_hourly_rate": 70,
            "weekly_connects_budget": 80,
            "filters": {
                "min_client_spend": 5000,
                "min_client_rating": 4.7,
                "disallowed_keywords": ["homework", "exam", "crypto bot", "trading bot", "unpaid test"],
                "preferred_job_types": ["fixed_price", "hourly"],
                "preferred_categories": [
                    "Machine Learning", "Artificial Intelligence", "NLP", "LLM", "Data Science"
                ],
            },
            "skills": [
                "Python", "PyTorch", "Transformers", "LangChain", "FastAPI",
                "Docker", "vLLM", "PostgreSQL", "pgvector", "RAG", "MLOps"
            ],
            "bio": (
                "PhD in Applied Machine Learning with 7+ years delivering production LLM and RAG pipelines, "
                "vector databases, real-time fraud models, and autonomous evaluation systems for enterprise clients."
            ),
            "education": "Ph.D. in Computer Science (Machine Learning), Technical University of Munich, 2018",
            "case_studies": [
                {
                    "id": "cs_aiml_001",
                    "project": "Enterprise RAG Document Intelligence System",
                    "aliases": [
                        "Enterprise RAG Document Intelligence System",
                        "the 4.5M page semantic legal search engine I shipped in Q1",
                        "our vector retrieval backend and chunking pipeline"
                    ],
                    "skills": ["Python", "pgvector", "LangChain", "FastAPI", "Docker"],
                    "date": "2024-02-18",
                    "client_industry": "LegalTech",
                    "outcome": "Sub-second retrieval latency on 4.5M pages with 91% factual accuracy",
                    "metric_short": "sub-second latency on 4.5M pages with 91% accuracy",
                    "challenge": "Client law firm struggled with slow keyword search across 4.5M unstructured legal filings.",
                    "solution": "Built a hybrid BM25 + dense vector retrieval pipeline using pgvector and LangChain with re-ranking.",
                },
                {
                    "id": "cs_aiml_002",
                    "project": "Real-Time Transaction Fraud Detection",
                    "aliases": [
                        "Real-Time Transaction Fraud Detection",
                        "the sub-35ms fraud prevention service deployed last year",
                        "our streaming inference scoring architecture"
                    ],
                    "skills": ["PyTorch", "Kafka", "FastAPI", "Redis", "Docker"],
                    "date": "2024-04-10",
                    "client_industry": "FinTech",
                    "outcome": "Reduced false positives by 38% while processing 14k TPS at p99 < 35ms",
                    "metric_short": "reduced false positives by 38% at 14k TPS with p99 < 35ms",
                    "challenge": "Legacy rule-based engine flagged legitimate customer card transactions causing high churn.",
                    "solution": "Trained an ensemble of gradient-boosted trees and deep representation models served via ONNX runtime.",
                },
                {
                    "id": "cs_aiml_003",
                    "project": "Clinical Trial Patient Eligibility Matching",
                    "aliases": [
                        "Clinical Trial Patient Eligibility Matching",
                        "the clinical cohort screening system for oncology trials",
                        "our BioBERT medical entity extraction pipeline"
                    ],
                    "skills": ["Transformers", "BioBERT", "Python", "spaCy", "PostgreSQL"],
                    "date": "2023-11-05",
                    "client_industry": "HealthTech",
                    "outcome": "Accelerated cohort screening by 75% with 94.2% precision",
                    "metric_short": "accelerated cohort screening by 75% with 94.2% precision",
                    "challenge": "Medical researchers spent 20+ hours per trial manually reviewing EHR notes against inclusion criteria.",
                    "solution": "Fine-tuned domain-specific Transformers to parse complex clinical trial criteria and patient medical records.",
                },
                {
                    "id": "cs_aiml_004",
                    "project": "Automated Customer Support Agentic Triage",
                    "aliases": [
                        "Automated Customer Support Agentic Triage",
                        "the multi-agent customer ticket router we launched in August",
                        "our LangGraph intent classifier and routing graph"
                    ],
                    "skills": ["LangGraph", "FastAPI", "Redis", "OpenAI", "Python"],
                    "date": "2024-08-22",
                    "client_industry": "E-Commerce",
                    "outcome": "Cut median first-response time from 4 hours to 3 minutes across 80k tickets/month",
                    "metric_short": "cut first-response time from 4 hours to 3 minutes across 80k tickets/mo",
                    "challenge": "Support team was overwhelmed with repetitive order status inquiries during peak shopping seasons.",
                    "solution": "Designed a LangGraph supervisor agent with strict state validation and human-in-the-loop interrupts.",
                },
                {
                    "id": "cs_aiml_005",
                    "project": "Predictive Equipment Maintenance Anomaly Detector",
                    "aliases": [
                        "Predictive Equipment Maintenance Anomaly Detector",
                        "the industrial vibration anomaly detector for manufacturing turbines",
                        "our time-series autoencoder monitoring service"
                    ],
                    "skills": ["PyTorch", "TimeSeries", "Scikit-Learn", "Docker", "FastAPI"],
                    "date": "2023-09-14",
                    "client_industry": "Manufacturing",
                    "outcome": "Prevented 14 unplanned downtime events saving $420k in first two quarters",
                    "metric_short": "prevented 14 unplanned downtime events saving $420k",
                    "challenge": "Turbine failures caused sudden halts in production line operations costing $30k/hour.",
                    "solution": "Implemented unsupervised convolutional autoencoders on 50Hz sensor streams with edge inference.",
                },
                {
                    "id": "cs_aiml_006",
                    "project": "Multi-Modal E-Commerce Visual Search",
                    "aliases": [
                        "Multi-Modal E-Commerce Visual Search",
                        "the visual product match engine deployed on our retail catalog",
                        "our CLIP embedding similarity service"
                    ],
                    "skills": ["PyTorch", "CLIP", "Qdrant", "FastAPI", "Python"],
                    "date": "2024-01-30",
                    "client_industry": "Retail",
                    "outcome": "Lifted search conversion by 22% with CLIP-based cross-modal embedding search",
                    "metric_short": "lifted search conversion by 22% with cross-modal embeddings",
                    "challenge": "Shoppers had difficulty finding fashion apparel when descriptions didn't match catalogue keywords.",
                    "solution": "Engineered dual-encoder vision-text representations indexed in Qdrant with sub-50ms vector queries.",
                },
                {
                    "id": "cs_aiml_007",
                    "project": "Autonomous Regulatory Compliance Auditor",
                    "aliases": [
                        "Autonomous Regulatory Compliance Auditor",
                        "the automated SOX compliance verification agent",
                        "our policy rule evaluation and evidence extraction pipeline"
                    ],
                    "skills": ["LangChain", "Llama-3", "PostgreSQL", "Python", "Docker"],
                    "date": "2024-05-18",
                    "client_industry": "FinTech",
                    "outcome": "Automated 85% of quarterly SOX control verification with zero audit findings",
                    "metric_short": "automated 85% of quarterly SOX audits with zero findings",
                    "challenge": "Quarterly IT control audits required hundreds of person-hours collecting and cross-checking logs.",
                    "solution": "Constructed an automated LLM pipeline verifying security policy checklists against system logs.",
                },
                {
                    "id": "cs_aiml_008",
                    "project": "Speech-to-Text Clinical Scribe",
                    "aliases": [
                        "Speech-to-Text Clinical Scribe",
                        "the ambient clinical transcription tool built for telehealth",
                        "our fine-tuned Whisper medical dictation model"
                    ],
                    "skills": ["Whisper", "PyTorch", "FastAPI", "Docker", "Python"],
                    "date": "2023-12-11",
                    "client_industry": "HealthTech",
                    "outcome": "Reduced clinician note-taking time by 60% with 96.5% medical entity accuracy",
                    "metric_short": "reduced clinician note-taking time by 60% with 96.5% accuracy",
                    "challenge": "Physicians spent up to 3 hours every evening dictating chart notes and medical summaries.",
                    "solution": "Fine-tuned Whisper on medical lexicon and structured transcribed outputs into standard SOAP formats.",
                },
                {
                    "id": "cs_aiml_009",
                    "project": "Supply Chain Demand Forecasting Engine",
                    "aliases": [
                        "Supply Chain Demand Forecasting Engine",
                        "the 15k SKU hierarchical inventory demand predictor",
                        "our gradient-boosted time-series forecasting model"
                    ],
                    "skills": ["LightGBM", "Pandas", "Scikit-Learn", "MLflow", "Python"],
                    "date": "2024-03-01",
                    "client_industry": "Logistics",
                    "outcome": "Lowered mean absolute error by 27% across 15,000 SKUs",
                    "metric_short": "lowered MAE by 27% across 15,000 SKUs",
                    "challenge": "Volatile demand patterns caused chronic overstocking in regional fulfillment distribution hubs.",
                    "solution": "Built a hierarchical multi-level forecasting model combining seasonal factors and promotional uplift.",
                },
                {
                    "id": "cs_aiml_010",
                    "project": "Cybersecurity Threat Log Anomaly Hunter",
                    "aliases": [
                        "Cybersecurity Threat Log Anomaly Hunter",
                        "the zero-day intrusion detection model running on VPC flow logs",
                        "our real-time autoencoder threat detector"
                    ],
                    "skills": ["Autoencoders", "PyTorch", "PySpark", "ElasticSearch", "Python"],
                    "date": "2023-10-19",
                    "client_industry": "CyberSec",
                    "outcome": "Identified 3 zero-day penetration attempts with 0.02% false alert rate",
                    "metric_short": "detected 3 zero-day intrusions with 0.02% false alert rate",
                    "challenge": "SOC analysts experienced alert fatigue from tens of thousands of daily low-fidelity IDS triggers.",
                    "solution": "Trained unsupervised deep clustering models on VPC flow logs to isolate stealthy lateral movement.",
                },
                {
                    "id": "cs_aiml_011",
                    "project": "Personalized Educational Curriculum Recommender",
                    "aliases": [
                        "Personalized Educational Curriculum Recommender",
                        "the adaptive learning pathway engine for 120k students",
                        "our matrix factorization and sequence prediction system"
                    ],
                    "skills": ["PyTorch", "Redis", "FastAPI", "Python", "PostgreSQL"],
                    "date": "2024-06-04",
                    "client_industry": "EdTech",
                    "outcome": "Increased course completion rate by 31% across 120,000 active students",
                    "metric_short": "increased course completion rate by 31% for 120k students",
                    "challenge": "High drop-off rate on online learning platform due to one-size-fits-all curriculum pacing.",
                    "solution": "Developed a knowledge tracing recurrent neural network that tailored module recommendations to quiz performance.",
                },
                {
                    "id": "cs_aiml_012",
                    "project": "Automated RFP Proposal Generator",
                    "aliases": [
                        "Automated RFP Proposal Generator",
                        "the enterprise RFP drafting assistant for consulting bids",
                        "our multi-stage citation grounded generation pipeline"
                    ],
                    "skills": ["LangGraph", "Claude", "pgvector", "Python", "FastAPI"],
                    "date": "2024-07-15",
                    "client_industry": "Professional Services",
                    "outcome": "Cut RFP preparation time from 16 hours to 45 minutes with 88% win rate",
                    "metric_short": "cut RFP preparation from 16 hours to 45 minutes with 88% win rate",
                    "challenge": "Consulting partners spent entire weekends formatting and tailoring 50-page proposals.",
                    "solution": "Built a LangGraph graph that retrieved relevant past proposals and generated evidence-grounded responses.",
                },
                {
                    "id": "cs_aiml_013",
                    "project": "Insurance Claim Auto-Adjudication Engine",
                    "aliases": [
                        "Insurance Claim Auto-Adjudication Engine",
                        "the automated dental claim adjudication service",
                        "our supervised decision tree verification system"
                    ],
                    "skills": ["XGBoost", "FastAPI", "PostgreSQL", "Python", "Docker"],
                    "date": "2024-02-02",
                    "client_industry": "Insurance",
                    "outcome": "Automated 42% of routine claims with zero human intervention and 99.1% audit pass",
                    "metric_short": "automated 42% of routine claims with 99.1% audit pass",
                    "challenge": "Claim adjusters faced backlogs of 14,000 dental claims per week.",
                    "solution": "Constructed a calibrated risk-scoring model that fast-tracked low-risk standard claims safely.",
                },
                {
                    "id": "cs_aiml_014",
                    "project": "Satellite Imagery Deforestation Tracker",
                    "aliases": [
                        "Satellite Imagery Deforestation Tracker",
                        "the 2.4M hectare canopy change detection system",
                        "our UNet segmentation satellite processing pipeline"
                    ],
                    "skills": ["PyTorch", "UNet", "OpenCV", "GDAL", "Python"],
                    "date": "2023-08-25",
                    "client_industry": "ESG / Climate",
                    "outcome": "Monitored 2.4M hectares at 10m resolution with 93% canopy change detection",
                    "metric_short": "monitored 2.4M hectares at 10m resolution with 93% accuracy",
                    "challenge": "Environmental watchdog had no automated means of monitoring remote illegal logging.",
                    "solution": "Trained semantic segmentation models on Sentinel-2 multispectral imagery with bi-weekly updates.",
                },
                {
                    "id": "cs_aiml_015",
                    "project": "SaaS Churn Propensity Predictor",
                    "aliases": [
                        "SaaS Churn Propensity Predictor",
                        "the B2B customer churn warning pipeline",
                        "our Shapley-explained account health model"
                    ],
                    "skills": ["XGBoost", "Shapley", "Snowflake", "Python", "FastAPI"],
                    "date": "2024-05-30",
                    "client_industry": "SaaS",
                    "outcome": "Decreased annualized gross revenue churn by 3.2 percentage points ($1.8M ARR)",
                    "metric_short": "decreased annual gross revenue churn by 3.2% ($1.8M ARR saved)",
                    "challenge": "Enterprise customer success reps received no early warning when accounts decreased product usage.",
                    "solution": "Developed daily feature store aggregation scoring accounts with Shapley-based risk factor explanations.",
                },
                {
                    "id": "cs_aiml_016",
                    "project": "Real-Time Video Action Recognition for Safety",
                    "aliases": [
                        "Real-Time Video Action Recognition for Safety",
                        "the job-site PPE compliance video detector",
                        "our low-latency YOLOv8 edge vision detector"
                    ],
                    "skills": ["YOLOv8", "PyTorch", "DeepStream", "RTSP", "Python"],
                    "date": "2023-11-28",
                    "client_industry": "Construction",
                    "outcome": "Flagged safety gear violations in under 200ms across 32 live camera feeds",
                    "metric_short": "flagged PPE violations in < 200ms across 32 live streams",
                    "challenge": "Safety managers could not manually monitor dozens of cameras on high-risk construction sites.",
                    "solution": "Deployed quantized YOLO models on Jetson edge devices alerting supervisors via webhooks.",
                },
                {
                    "id": "cs_aiml_017",
                    "project": "Smart Code Review & Security Vulnerability Scanner",
                    "aliases": [
                        "Smart Code Review & Security Vulnerability Scanner",
                        "the automated AST and LLM vulnerability reviewer",
                        "our CI/CD security scanning agent"
                    ],
                    "skills": ["Tree-sitter", "AST", "CodeLlama", "Python", "Docker"],
                    "date": "2024-06-20",
                    "client_industry": "DevTools",
                    "outcome": "Intercepted 140+ SQL injection and secret leaks before merge across 50 repos",
                    "metric_short": "intercepted 140+ vulnerabilities before merge across 50 repos",
                    "challenge": "Engineering team struggled with security vulnerabilities slipping past manual PR reviews.",
                    "solution": "Combined AST static analysis with fine-tuned code LLM verification in GitHub Actions.",
                },
                {
                    "id": "cs_aiml_018",
                    "project": "B2B Sales Lead Scoring & Intent Miner",
                    "aliases": [
                        "B2B Sales Lead Scoring & Intent Miner",
                        "the buyer intent classification engine for inbound leads",
                        "our RoBERTa web visit intent model"
                    ],
                    "skills": ["RoBERTa", "Scikit-Learn", "PostgreSQL", "FastAPI", "Python"],
                    "date": "2024-03-24",
                    "client_industry": "MarTech",
                    "outcome": "Boosted sales development rep qualified meeting rate by 44%",
                    "metric_short": "boosted SDR qualified meeting rate by 44%",
                    "challenge": "Sales team wasted 65% of prospecting time on non-responsive cold leads.",
                    "solution": "Engineered an intent-scoring model aggregating website behavioral signals and firmographic data.",
                },
                {
                    "id": "cs_aiml_019",
                    "project": "Automated Financial Statement Parser",
                    "aliases": [
                        "Automated Financial Statement Parser",
                        "the 10-K and 10-Q balance sheet table extractor",
                        "our LayoutLM financial document processor"
                    ],
                    "skills": ["LayoutLM", "PyPDF", "FastAPI", "Python", "PostgreSQL"],
                    "date": "2024-04-05",
                    "client_industry": "Accounting",
                    "outcome": "Extracted balance sheet tables from 25,000 PDFs with 99.4% field accuracy",
                    "metric_short": "extracted tables from 25k PDFs with 99.4% field accuracy",
                    "challenge": "Financial analysts manually re-keyed financial statements into valuation models.",
                    "solution": "Built a multimodal document parser reconciling bounding boxes and optical character recognition.",
                },
                {
                    "id": "cs_aiml_020",
                    "project": "Dynamic Pricing Engine for Ride-Hailing",
                    "aliases": [
                        "Dynamic Pricing Engine for Ride-Hailing",
                        "the real-time reinforcement learning dispatch price optimizer",
                        "our contextual bandit pricing service"
                    ],
                    "skills": ["Reinforcement Learning", "PyTorch", "Redis", "Kafka", "Python"],
                    "date": "2024-01-12",
                    "client_industry": "Mobility",
                    "outcome": "Optimized driver utilization by 19% while maintaining 95% rider pickup fulfillment",
                    "metric_short": "optimized driver utilization by 19% at 95% fulfillment",
                    "challenge": "Supply-demand imbalances created severe vehicle shortages during bad weather events.",
                    "solution": "Implemented multi-armed bandit pricing models balancing driver incentives and rider elasticity.",
                },
            ],
            "repos": [
                {
                    "name": "rag-eval-pipeline",
                    "description": "Enterprise-grade RAG evaluation harness measuring faithfulness, context precision, and latency.",
                    "files": {
                        "pipeline.py": '''# synthetic: true
"""RAG retrieval and verification pipeline."""
from dataclasses import dataclass

import numpy as np


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    similarity: float


class RetrievalPipeline:
    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def score_chunks(self, query_vec: list[float], index_vecs: list[list[float]]) -> list[int]:
        q = np.array(query_vec, dtype=np.float32)
        idx = np.array(index_vecs, dtype=np.float32)
        scores = np.dot(idx, q) / (np.linalg.norm(idx, axis=1) * np.linalg.norm(q) + 1e-8)
        return list(np.argsort(scores)[::-1][:self.top_k])
''',
                        "evaluator.py": '''# synthetic: true
"""Faithfulness and hallucination evaluation runner."""


class HallucinationDetector:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def verify_claims(self, response_claims: list[str], context_facts: list[str]) -> dict:
        supported = [c for c in response_claims if any(f in c or c in f for f in context_facts)]
        ratio = len(supported) / max(len(response_claims), 1)
        return {"supported_ratio": ratio, "pass": ratio >= self.threshold}
''',
                        "chunker.py": '''# synthetic: true
"""Document chunking with recursive sliding windows."""


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
'''
                    }
                },
                {
                    "name": "llm-guardrails",
                    "description": "High-throughput token validator and prompt injection defense filter.",
                    "files": {
                        "guardrail.py": '''# synthetic: true
"""Prompt injection and system prompt leak defense."""
import re

PATTERNS = [
    r"ignore previous instructions",
    r"you are now an unrestricted assistant",
    r"reveal your system prompt",
]


def scan_prompt(prompt: str) -> bool:
    for pat in PATTERNS:
        if re.search(pat, prompt, re.IGNORECASE):
            return False
    return True
''',
                        "validators.py": '''# synthetic: true
"""Structured output JSON schema validator."""
import json


def validate_json_output(raw_str: str, required_keys: list[str]) -> bool:
    try:
        data = json.loads(raw_str)
        return all(k in data for k in required_keys)
    except (json.JSONDecodeError, TypeError):
        return False
''',
                        "schemas.py": '''# synthetic: true
"""Pydantic schemas for LLM agent actions."""
from pydantic import BaseModel, Field


class AgentAction(BaseModel):
    tool_name: str
    parameters: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
'''
                    }
                }
            ],
            "code_snippets": [
                '```python\nembeddings = client.embeddings.create(input=doc, model="text-embedding-3-small")\nsimilarity = cosine_similarity(query_emb, embeddings)\n```',
                '```python\nscores = np.dot(embeddings, q_vec) / (np.linalg.norm(embeddings, axis=1) * np.linalg.norm(q_vec))\n```',
                '```python\nasync def stream_rag_tokens(prompt: str):\n    async for chunk in client.chat.completions.create(stream=True, ...):\n        yield chunk\n```'
            ],
            "implied_skills": [
                "benchmarked cosine vs inner product distances over high-dimensional float32 tensors with HNSW index tuning",
                "tuned token generation parameters to eliminate decoding drift on long-context medical transcripts",
                "instrumented OpenTelemetry traces across asynchronous microservices to eliminate streaming bottleneck latency",
            ]
        },
        "fullstack": {
            "id": "fullstack",
            "name": "Marcus Vance",
            "title": "Full-Stack Web & Cloud Systems Architect",
            "rates": {"hourly": 85, "fixed_minimum": 1200},
            "floor_hourly_rate": 65,
            "weekly_connects_budget": 75,
            "filters": {
                "min_client_spend": 3000,
                "min_client_rating": 4.6,
                "disallowed_keywords": ["wordpress theme tweak", "wix", "squarespace", "fixed $50"],
                "preferred_job_types": ["fixed_price", "hourly"],
                "preferred_categories": [
                    "Full Stack Development", "Frontend Development", "Backend Development",
                    "Web Applications", "API Development"
                ],
            },
            "skills": [
                "TypeScript", "React", "Next.js", "Node.js", "Python", "FastAPI",
                "Tailwind CSS", "PostgreSQL", "Redis", "Docker", "AWS"
            ],
            "bio": (
                "Senior Full-Stack Architect with 8+ years building enterprise React/Next.js web apps, "
                "robust FastAPI/Node backend APIs, Stripe billing infrastructures, and scalable cloud systems."
            ),
            "education": "B.S. in Software Engineering, University of Waterloo, 2016",
            "case_studies": [
                {
                    "id": "cs_fs_001",
                    "project": "Multi-Tenant B2B SaaS Billing Platform",
                    "aliases": [
                        "Multi-Tenant B2B SaaS Billing Platform",
                        "the $12M subscription billing portal I architected",
                        "our multi-tenant Stripe Connect integration"
                    ],
                    "skills": ["Next.js", "TypeScript", "Stripe", "FastAPI", "PostgreSQL"],
                    "date": "2024-03-12",
                    "client_industry": "FinTech / SaaS",
                    "outcome": "Scaled to 45,000 active subscriptions with zero billing discrepancies across $12M volume",
                    "metric_short": "scaled to 45k subscriptions with zero billing errors across $12M volume",
                    "challenge": "Client struggled with prorated plan upgrades and invoice synchronization across 45k accounts.",
                    "solution": "Built an idempotent webhook listener and billing state machine on FastAPI and PostgreSQL.",
                },
                {
                    "id": "cs_fs_002",
                    "project": "Real-Time Collaborative Document Canvas",
                    "aliases": [
                        "Real-Time Collaborative Document Canvas",
                        "the 50-user concurrent multiplayer editor built in Next.js",
                        "our Yjs CRDT WebSocket sync server"
                    ],
                    "skills": ["React", "WebSockets", "Yjs", "Node.js", "Redis"],
                    "date": "2024-05-20",
                    "client_industry": "Productivity",
                    "outcome": "Maintained sub-16ms multiplayer synchronization across 50 simultaneous editors",
                    "metric_short": "maintained sub-16ms sync across 50 simultaneous editors",
                    "challenge": "Engineering team faced race conditions and conflict resolution crashes in collaborative note taking.",
                    "solution": "Implemented conflict-free replicated data types (CRDTs) over secure WebSockets with Redis pub/sub.",
                },
                {
                    "id": "cs_fs_003",
                    "project": "High-Throughput Logistics Dispatch Dashboard",
                    "aliases": [
                        "High-Throughput Logistics Dispatch Dashboard",
                        "the 3,500 active driver dispatch management portal",
                        "our live geospatial routing table"
                    ],
                    "skills": ["TypeScript", "React", "Tailwind", "Go", "PostgreSQL"],
                    "date": "2023-10-14",
                    "client_industry": "Logistics",
                    "outcome": "Reduced fleet dispatch delays by 35% managing 3,500 active drivers simultaneously",
                    "metric_short": "reduced dispatch delays by 35% for 3,500 active drivers",
                    "challenge": "Dispatchers suffered from UI freezing when tracking thousands of GPS location pings.",
                    "solution": "Designed virtualized tables and WebGL map layers rendering thousands of fleet markers at 60fps.",
                },
                {
                    "id": "cs_fs_004",
                    "project": "HIPAA-Compliant Telehealth Consultation Portal",
                    "aliases": [
                        "HIPAA-Compliant Telehealth Consultation Portal",
                        "the 120k session telehealth video consult platform",
                        "our end-to-end encrypted WebRTC medical portal"
                    ],
                    "skills": ["Next.js", "WebRTC", "Node.js", "PostgreSQL", "AWS"],
                    "date": "2024-01-18",
                    "client_industry": "HealthTech",
                    "outcome": "Handled 120,000 secure video visits with 99.98% uptime and zero security breaches",
                    "metric_short": "handled 120k visits with 99.98% uptime and zero security breaches",
                    "challenge": "Clinic network needed a turnkey WebRTC video suite complying with strict HIPAA audit rules.",
                    "solution": "Engineered automated waiting rooms, encrypted session recording, and audit trail databases.",
                },
                {
                    "id": "cs_fs_005",
                    "project": "Headless E-Commerce Storefront & Checkout Engine",
                    "aliases": [
                        "Headless E-Commerce Storefront & Checkout Engine",
                        "the high-converting Next.js 14 Shopify storefront",
                        "our edge-rendered mobile checkout flow"
                    ],
                    "skills": ["Next.js", "Shopify Storefront API", "Tailwind", "Edge Functions"],
                    "date": "2023-11-29",
                    "client_industry": "Retail",
                    "outcome": "Decreased page load time by 62% resulting in a 24% boost in mobile checkout conversion",
                    "metric_short": "cut page load time by 62% boosting mobile checkout conversion by 24%",
                    "challenge": "Monolithic store experienced 4.2s page loads causing 68% cart abandonment on mobile devices.",
                    "solution": "Re-platformed to Next.js App Router on Vercel Edge with incremental static regeneration.",
                },
                {
                    "id": "cs_fs_006",
                    "project": "Real-Time IoT Fleet Monitoring Portal",
                    "aliases": [
                        "Real-Time IoT Fleet Monitoring Portal",
                        "the 8k events/sec telemetry tracking console",
                        "our TimescaleDB and MQTT telemetry streaming service"
                    ],
                    "skills": ["React", "TypeScript", "FastAPI", "MQTT", "TimescaleDB"],
                    "date": "2024-02-14",
                    "client_industry": "Automotive",
                    "outcome": "Processed 8,000 telemetry messages/second with sub-100ms dashboard widget refresh",
                    "metric_short": "processed 8k telemetry msgs/sec with sub-100ms dashboard refresh",
                    "challenge": "Commercial truck fleet needed instant alerts on engine temperature anomalies.",
                    "solution": "Built high-throughput ingestion microservice with MQTT broker and Timescale continuous aggregates.",
                },
                {
                    "id": "cs_fs_007",
                    "project": "Corporate Expense Management & Card System",
                    "aliases": [
                        "Corporate Expense Management & Card System",
                        "the 800-seat automated corporate card reconciliation app",
                        "our Plaid and card ledger backend"
                    ],
                    "skills": ["Next.js", "Node.js", "Plaid API", "PostgreSQL", "Redis"],
                    "date": "2024-06-11",
                    "client_industry": "FinTech",
                    "outcome": "Cut expense report reconciliation turnaround from 5 days to 2 hours for 800 employees",
                    "metric_short": "cut reconciliation turnaround from 5 days to 2 hours for 800 seats",
                    "challenge": "Employees submitted paper receipts causing week-long delays in accounting closes.",
                    "solution": "Built mobile-first receipt capture with OCR and automated bank statement transaction matching.",
                },
                {
                    "id": "cs_fs_008",
                    "project": "Automated Customer Support Helpdesk Portal",
                    "aliases": [
                        "Automated Customer Support Helpdesk Portal",
                        "the omnichannel live chat and ticket desk for 40 agents",
                        "our WebSocket message dispatcher"
                    ],
                    "skills": ["React", "WebSocket", "FastAPI", "Redis", "Tailwind"],
                    "date": "2023-09-08",
                    "client_industry": "SaaS",
                    "outcome": "Enabled 40 support agents to resolve 350 tickets daily with unified omnichannel chat",
                    "metric_short": "resolved 350 tickets daily with unified omnichannel chat",
                    "challenge": "Support conversations were fragmented across email, WhatsApp, and in-app chat.",
                    "solution": "Centralized messaging onto unified WebSocket queues with typing indicators and automated macros.",
                },
                {
                    "id": "cs_fs_009",
                    "project": "Interactive Real Estate Property Tour & Booking App",
                    "aliases": [
                        "Interactive Real Estate Property Tour & Booking App",
                        "the 3D interactive property showcase with calendar booking",
                        "our Three.js spatial floorplan renderer"
                    ],
                    "skills": ["Three.js", "React", "Node.js", "Google Calendar API", "Tailwind"],
                    "date": "2024-04-28",
                    "client_industry": "PropTech",
                    "outcome": "Doubled tour booking rate with interactive 3D floorplans and automated calendar sync",
                    "metric_short": "doubled tour booking rate with 3D floorplans and calendar sync",
                    "challenge": "Static 2D image galleries had low engagement and required back-and-forth email scheduling.",
                    "solution": "Integrated Three.js interactive 3D navigation linked to instant agent calendar slot reservations.",
                },
                {
                    "id": "cs_fs_010",
                    "project": "Developer API Platform & Documentation Portal",
                    "aliases": [
                        "Developer API Platform & Documentation Portal",
                        "the 15M call/month developer hub with OpenAPI interactive playground",
                        "our rate-limited developer gateway"
                    ],
                    "skills": ["Next.js", "FastAPI", "PostgreSQL", "Swagger", "Docker"],
                    "date": "2024-07-02",
                    "client_industry": "DevTools",
                    "outcome": "Served 15M monthly API calls with auto-generated OpenAPI client SDKs and playground",
                    "metric_short": "served 15M monthly API calls with interactive playground",
                    "challenge": "Third-party developers complained about outdated documentation and broken curl examples.",
                    "solution": "Created an automated documentation engine parsing code annotations into live interactive consoles.",
                },
                {
                    "id": "cs_fs_011",
                    "project": "Digital Asset Management & Processing Workspace",
                    "aliases": [
                        "Digital Asset Management & Processing Workspace",
                        "the 500k video asset transcoding catalog",
                        "our asynchronous BullMQ video queue"
                    ],
                    "skills": ["React", "Node.js", "AWS S3", "BullMQ", "Tailwind"],
                    "date": "2023-12-05",
                    "client_industry": "Media",
                    "outcome": "Streamlined batch transcoding and tagging of 500k video assets saving 20 hrs/week",
                    "metric_short": "streamlined batch transcoding of 500k video assets saving 20 hrs/wk",
                    "challenge": "Marketing agency lost video files across disconnected Dropbox folders.",
                    "solution": "Engineered automated S3 multipart uploads, background ffmpeg transcoding, and tag search.",
                },
                {
                    "id": "cs_fs_012",
                    "project": "University Course Registration & Portal",
                    "aliases": [
                        "University Course Registration & Portal",
                        "the 15,000 student surge registration system",
                        "our distributed Redis lock course reservation service"
                    ],
                    "skills": ["Next.js", "TypeScript", "Redis", "PostgreSQL", "Docker"],
                    "date": "2024-03-05",
                    "client_industry": "EdTech",
                    "outcome": "Handled 15,000 concurrent students during registration spike without a single dropped session",
                    "metric_short": "handled 15k concurrent registrations without dropped sessions",
                    "challenge": "University database crashed every semester opening day under intense seat-claiming loads.",
                    "solution": "Implemented distributed Redis locking with atomic seat decrements and asynchronous db persistence.",
                },
                {
                    "id": "cs_fs_013",
                    "project": "Inventory & Warehouse Management System",
                    "aliases": [
                        "Inventory & Warehouse Management System",
                        "the barcode-driven fulfillment center picker app",
                        "our live warehouse aisle mapping tool"
                    ],
                    "skills": ["React", "Node.js", "PostgreSQL", "WebSockets", "Tailwind"],
                    "date": "2023-10-30",
                    "client_industry": "Supply Chain",
                    "outcome": "Decreased stock picking errors by 41% with barcode scan integration and live map",
                    "metric_short": "decreased picking errors by 41% with barcode scan integration",
                    "challenge": "Warehouse staff spent 40% of their shift walking inefficient paths to locate bins.",
                    "solution": "Developed a mobile tablet interface plotting shortest route pick lists in real time.",
                },
                {
                    "id": "cs_fs_014",
                    "project": "Restaurant POS & Kitchen Display System",
                    "aliases": [
                        "Restaurant POS & Kitchen Display System",
                        "the 18-location offline-first restaurant terminal system",
                        "our SQLite replication kitchen screen"
                    ],
                    "skills": ["Electron", "React", "Node.js", "SQLite", "WebSockets"],
                    "date": "2024-04-14",
                    "client_industry": "Hospitality",
                    "outcome": "Reduced average table turn time by 12 minutes across 18 chain locations",
                    "metric_short": "reduced average table turn time by 12 minutes across 18 stores",
                    "challenge": "Internet outages halted restaurant credit card checkout and kitchen ticket printing.",
                    "solution": "Built an offline-first POS using local SQLite queues with automatic cloud reconciliation.",
                },
                {
                    "id": "cs_fs_015",
                    "project": "Human Resources Onboarding & Compliance Portal",
                    "aliases": [
                        "Human Resources Onboarding & Compliance Portal",
                        "the 1,200 hire automated HR document portal",
                        "our DocuSign webhook and checklist engine"
                    ],
                    "skills": ["Next.js", "DocuSign API", "PostgreSQL", "Tailwind", "Docker"],
                    "date": "2024-01-22",
                    "client_industry": "Enterprise",
                    "outcome": "Automated document collection and e-signatures for 1,200 annual hires saving $85k",
                    "metric_short": "automated onboarding for 1,200 hires saving $85k annually",
                    "challenge": "Manual PDF forms and email follow-ups caused 3-week delays in new hire equipment delivery.",
                    "solution": "Built a self-service onboarding portal tracking checklist milestones and e-signatures.",
                },
                {
                    "id": "cs_fs_016",
                    "project": "Crypto Asset Custody & Settlement Dashboard",
                    "aliases": [
                        "Crypto Asset Custody & Settlement Dashboard",
                        "the $40M daily batch transaction settlement portal",
                        "our multi-sig quorum authorization interface"
                    ],
                    "skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Docker"],
                    "date": "2023-11-15",
                    "client_industry": "Web3 / FinTech",
                    "outcome": "Facilitated $40M in automated daily batch settlements with multi-sig approval flows",
                    "metric_short": "settled $40M daily volume with multi-sig approval flows",
                    "challenge": "Treasury team had no unified interface to enforce 3-of-5 keyholder signing policies.",
                    "solution": "Architected a secure browser dashboard managing time-locked multi-sig authorization quorums.",
                },
                {
                    "id": "cs_fs_017",
                    "project": "Energy Consumption & Smart Grid Analytics Portal",
                    "aliases": [
                        "Energy Consumption & Smart Grid Analytics Portal",
                        "the 40,000 home smart meter live consumption dashboard",
                        "our ClickHouse 60fps high-resolution visualizer"
                    ],
                    "skills": ["Next.js", "D3.js", "FastAPI", "ClickHouse", "Tailwind"],
                    "date": "2024-06-25",
                    "client_industry": "CleanTech",
                    "outcome": "Visualized 10-second smart meter data across 40,000 homes with 60fps chart rendering",
                    "metric_short": "rendered 10-sec meter data across 40k homes with 60fps charts",
                    "challenge": "Utility provider lacked customer-facing dashboards capable of loading gigabytes of interval data.",
                    "solution": "Built a ClickHouse backend paired with custom D3 Canvas rendering widgets in Next.js.",
                },
                {
                    "id": "cs_fs_018",
                    "project": "Freelancer Marketplace Milestone Escrow Portal",
                    "aliases": [
                        "Freelancer Marketplace Milestone Escrow Portal",
                        "the 8,500 milestone transaction escrow payment workflow",
                        "our Stripe Connect custom account payout engine"
                    ],
                    "skills": ["Next.js", "Stripe Connect", "PostgreSQL", "Redis", "Tailwind"],
                    "date": "2024-02-28",
                    "client_industry": "Gig Economy",
                    "outcome": "Processed 8,500 milestone payments with zero chargeback disputes via Stripe Connect",
                    "metric_short": "processed 8.5k milestone payments with zero disputes",
                    "challenge": "Gig platform had manual escrow releases resulting in disputes and payout delays.",
                    "solution": "Engineered automated milestone approvals, charge hold releases, and tax form generation.",
                },
                {
                    "id": "cs_fs_019",
                    "project": "Automated Content Scheduling & Social Publisher",
                    "aliases": [
                        "Automated Content Scheduling & Social Publisher",
                        "the 250,000 multi-channel marketing post scheduler",
                        "our AWS SQS distributed social publishing pipeline"
                    ],
                    "skills": ["React", "Node.js", "Redis", "PostgreSQL", "AWS SQS"],
                    "date": "2023-12-18",
                    "client_industry": "Marketing",
                    "outcome": "Scheduled and published 250,000 multi-channel social posts with 99.9% delivery rate",
                    "metric_short": "published 250k social posts with 99.9% delivery reliability",
                    "challenge": "Agency social media managers experienced frequent rate-limit bans and missed scheduled posts.",
                    "solution": "Designed token bucket rate limiters and retry queues across Twitter, LinkedIn, and Meta APIs.",
                },
                {
                    "id": "cs_fs_020",
                    "project": "Construction Project Management & Blueprint Viewer",
                    "aliases": [
                        "Construction Project Management & Blueprint Viewer",
                        "the 60-site field blueprint markup tablet tool",
                        "our HTML5 Canvas vector CAD layer viewer"
                    ],
                    "skills": ["React", "Canvas API", "TypeScript", "Node.js", "PostgreSQL"],
                    "date": "2024-05-08",
                    "client_industry": "Construction",
                    "outcome": "Enabled rapid field blueprint markup on mobile tablets for 60 job sites",
                    "metric_short": "enabled rapid blueprint markup on tablets across 60 job sites",
                    "challenge": "Job site foremen carried 20-pound paper rolls and missed architect revisions.",
                    "solution": "Built a high-performance vector PDF/CAD tile viewer with offline layer drawing capabilities.",
                },
            ],
            "repos": [
                {
                    "name": "saas-subscription-core",
                    "description": "Production multi-tenant subscription billing engine with Stripe webhook synchronization.",
                    "files": {
                        "billing.ts": '''// synthetic: true
/**
 * Stripe customer lifecycle and checkout session creator.
 */
export interface CheckoutPayload {
  customerId: string;
  priceId: string;
  successUrl: string;
  cancelUrl: string;
}

export async function createBillingSession(payload: CheckoutPayload): Promise<{ url: string }> {
  // Simulates creating checkout session
  return {
    url: `https://checkout.stripe.com/pay/${payload.priceId}?customer=${payload.customerId}`
  };
}
''',
                        "webhooks.py": '''# synthetic: true
"""Idempotent Stripe webhook receiver with signature validation."""
from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()


@router.post("/stripe/webhook")
async def handle_stripe_event(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    # Process event idempotently
    return {"status": "received", "length": len(payload)}
''',
                        "SubscriptionCard.tsx": '''// synthetic: true
import React from 'react';

interface Props {
  planName: string;
  priceMonthly: number;
  features: string[];
  onSelect: () => void;
}

export const SubscriptionCard: React.FC<Props> = ({ planName, priceMonthly, features, onSelect }) => {
  return (
    <div className="border rounded-xl p-6 shadow-sm hover:shadow-md transition">
      <h3 className="text-xl font-bold">{planName}</h3>
      <p className="text-3xl font-extrabold my-4">${priceMonthly}<span className="text-sm font-normal">/mo</span></p>
      <ul className="space-y-2 mb-6">
        {features.map((f, i) => <li key={i} className="text-sm text-gray-600">✓ {f}</li>)}
      </ul>
      <button onClick={onSelect} className="w-full bg-blue-600 text-white py-2 rounded-lg font-medium">Select Plan</button>
    </div>
  );
};
'''
                    }
                },
                {
                    "name": "realtime-ops-dashboard",
                    "description": "Live WebSocket streaming server and virtualized React KPI widget console.",
                    "files": {
                        "socket_server.py": '''# synthetic: true
"""High-concurrency async WebSocket hub with connection pooling."""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
active_clients: list[WebSocket] = []


@app.websocket("/ws/metrics")
async def metrics_feed(ws: WebSocket):
    await ws.accept()
    active_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        active_clients.remove(ws)
''',
                        "LiveMetrics.tsx": '''// synthetic: true
import React, { useEffect, useState } from 'react';

export const LiveMetrics: React.FC = () => {
  const [cpu, setCpu] = useState(45);
  useEffect(() => {
    const timer = setInterval(() => setCpu(Math.floor(40 + Math.random() * 30)), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="p-4 bg-slate-900 text-white rounded-lg">
      <h4 className="text-sm text-slate-400">Cluster CPU Load</h4>
      <div className="text-2xl font-mono">{cpu}%</div>
    </div>
  );
};
''',
                        "schema.sql": '''-- synthetic: true
CREATE TABLE IF NOT EXISTS system_telemetry (
    id BIGSERIAL PRIMARY KEY,
    node_id VARCHAR(64) NOT NULL,
    cpu_percent NUMERIC(5, 2) NOT NULL,
    memory_mb INTEGER NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_telemetry_node_time ON system_telemetry(node_id, recorded_at DESC);
'''
                    }
                }
            ],
            "code_snippets": [
                '```typescript\nconst session = await stripe.checkout.sessions.create({\n  customer: custId,\n  line_items: [{ price: priceId, quantity: 1 }],\n  mode: "subscription",\n});\n```',
                '```typescript\nconst { data, error } = await supabase.from("projects").select("*").eq("tenant_id", tenantId);\n```',
                '```python\n@app.get("/api/v1/health")\nasync def health():\n    return {"status": "healthy", "redis": await redis.ping()}\n```'
            ],
            "implied_skills": [
                "handled idempotency keys on payment webhooks and wrapped mutations in serializable database transactions",
                "structured Next.js layout trees to avoid client bundle waterfalls on heavy nested admin routes",
                "orchestrated multi-region zero-downtime blue-green deployments using Docker containers behind Traefik reverse proxies",
            ]
        },
        "data_analyst": {
            "id": "data_analyst",
            "name": "Amina Al-Mansoor",
            "title": "Lead Data Analyst & Analytics Engineering Specialist",
            "rates": {"hourly": 75, "fixed_minimum": 1000},
            "floor_hourly_rate": 55,
            "weekly_connects_budget": 70,
            "filters": {
                "min_client_spend": 2500,
                "min_client_rating": 4.6,
                "disallowed_keywords": ["data entry", "copy paste", "pdf to excel manual", "scrape email"],
                "preferred_job_types": ["fixed_price", "hourly"],
                "preferred_categories": [
                    "Data Analytics", "Business Intelligence", "SQL / Databases",
                    "Data Visualization", "ETL Pipelines"
                ],
            },
            "skills": [
                "SQL", "Python", "PostgreSQL", "Snowflake", "dbt", "Power BI",
                "Tableau", "Pandas", "DuckDB", "Looker", "Airflow"
            ],
            "bio": (
                "Lead Data Analyst and Analytics Engineer with 6+ years transforming messy transactional databases "
                "into clean dbt semantic layers, executive Power BI/Tableau dashboards, and cohort retention models."
            ),
            "education": "M.S. in Business Analytics & Statistics, NYU Stern, 2018",
            "case_studies": [
                {
                    "id": "cs_da_001",
                    "project": "SaaS Customer Churn & Cohort Retention Analysis",
                    "aliases": [
                        "SaaS Customer Churn & Cohort Retention Analysis",
                        "the $950k ARR churn driver analysis",
                        "our monthly cohort retention model in dbt"
                    ],
                    "skills": ["SQL", "Snowflake", "dbt", "Python", "Tableau"],
                    "date": "2024-03-10",
                    "client_industry": "SaaS",
                    "outcome": "Identified churn driver reducing annual gross dollar churn by 2.8% ($950k ARR)",
                    "metric_short": "reduced gross dollar churn by 2.8% ($950k ARR)",
                    "challenge": "Executive team noticed escalating enterprise cancellations but had no insight into usage precursors.",
                    "solution": "Built automated cohort retention curves and product event correlation matrices in Snowflake.",
                },
                {
                    "id": "cs_da_002",
                    "project": "E-Commerce Multi-Touch Attribution & Marketing ROI",
                    "aliases": [
                        "E-Commerce Multi-Touch Attribution & Marketing ROI",
                        "the $1.4M ad spend attribution reallocation project",
                        "our Shapley multi-touch marketing attribution model"
                    ],
                    "skills": ["SQL", "BigQuery", "dbt", "Looker", "Python"],
                    "date": "2024-05-15",
                    "client_industry": "E-Commerce",
                    "outcome": "Reallocated $1.4M ad spend resulting in 32% increase in ROAS across paid channels",
                    "metric_short": "reallocated $1.4M ad spend achieving 32% higher ROAS",
                    "challenge": "First-click and last-click attribution credited brand search, starving upper-funnel discovery.",
                    "solution": "Implemented position-based and Markov-chain attribution across 2.2M customer touchpoints.",
                },
                {
                    "id": "cs_da_003",
                    "project": "Hospital Emergency Department Patient Flow Optimization",
                    "aliases": [
                        "Hospital Emergency Department Patient Flow Optimization",
                        "the hospital ED triage bottleneck analysis",
                        "our acute care bed turnaround tracking dashboard"
                    ],
                    "skills": ["SQL", "PostgreSQL", "Power BI", "Python", "R"],
                    "date": "2023-11-20",
                    "client_industry": "HealthTech",
                    "outcome": "Reduced median ED wait time by 28 minutes through triage bottleneck analysis",
                    "metric_short": "cut median ED wait time by 28 minutes through triage modeling",
                    "challenge": "Emergency rooms faced critical bed blockades and 3-hour waits for incoming ambulances.",
                    "solution": "Modeled queueing theory arrival distributions and highlighted radiology diagnostic delays.",
                },
                {
                    "id": "cs_da_004",
                    "project": "Subscription Revenue Recognition & ASC 606 Reporting",
                    "aliases": [
                        "Subscription Revenue Recognition & ASC 606 Reporting",
                        "the automated monthly accounting close pipeline",
                        "our dbt ASC 606 revenue amortization schedule"
                    ],
                    "skills": ["SQL", "Snowflake", "dbt", "Excel", "Looker"],
                    "date": "2024-01-30",
                    "client_industry": "FinTech",
                    "outcome": "Automated monthly accounting close cycle from 7 days down to 6 hours with 100% audit pass",
                    "metric_short": "shortened close cycle from 7 days to 6 hours with 100% audit pass",
                    "challenge": "Finance team manually calculated deferred revenue across multi-year contracts in broken spreadsheets.",
                    "solution": "Created automated dbt daily amortization models reconciling invoices against contract performance.",
                },
                {
                    "id": "cs_da_005",
                    "project": "Retail Inventory Stockout Prediction & Reorder Modeling",
                    "aliases": [
                        "Retail Inventory Stockout Prediction & Reorder Modeling",
                        "the 45-store inventory safety stock rebalance model",
                        "our reorder point dynamic lead-time simulator"
                    ],
                    "skills": ["SQL", "Python", "Pandas", "Tableau", "PostgreSQL"],
                    "date": "2024-04-18",
                    "client_industry": "Retail",
                    "outcome": "Lowered inventory stockout events by 36% while reducing safety stock holding cost by 14%",
                    "metric_short": "cut stockouts by 36% while lowering holding costs by 14%",
                    "challenge": "Stores ran out of top-selling items while over-ordering slow-moving seasonal merchandise.",
                    "solution": "Formulated probabilistic inventory reorder thresholds accounting for supplier lead-time variance.",
                },
                {
                    "id": "cs_da_006",
                    "project": "B2B Sales Pipeline Velocity & Win-Rate Analytics",
                    "aliases": [
                        "B2B Sales Pipeline Velocity & Win-Rate Analytics",
                        "the sales pipeline forecasting overhaul",
                        "our Salesforce opportunity conversion analytics"
                    ],
                    "skills": ["Salesforce API", "SQL", "Power BI", "Python", "Snowflake"],
                    "date": "2023-10-12",
                    "client_industry": "Professional Services",
                    "outcome": "Increased quarterly sales pipeline forecast accuracy from 71% to 93%",
                    "metric_short": "improved pipeline forecast accuracy from 71% to 93%",
                    "challenge": "Sales leaders relied on rep intuition for deal close dates, consistently missing quarterly targets.",
                    "solution": "Built a historical stage-progression probability model predicting close velocity from engagement signals.",
                },
                {
                    "id": "cs_da_007",
                    "project": "Mobile Gaming Player Lifetime Value (LTV) Segmentation",
                    "aliases": [
                        "Mobile Gaming Player Lifetime Value (LTV) Segmentation",
                        "the mobile game Day-30 ARPU optimization analysis",
                        "our behavioral cluster and whale segmentation pipeline"
                    ],
                    "skills": ["SQL", "DuckDB", "Python", "Looker", "Streamlit"],
                    "date": "2024-06-08",
                    "client_industry": "Gaming",
                    "outcome": "Uncovered high-value whale behavioral triggers boosting Day-30 ARPU by 19%",
                    "metric_short": "boosted Day-30 ARPU by 19% through behavioral segmentation",
                    "challenge": "Game studio struggled to convert non-paying players into recurring in-app purchase customers.",
                    "solution": "Ran k-means clustering on telemetry event logs isolating early micro-progression hurdles.",
                },
                {
                    "id": "cs_da_008",
                    "project": "Supply Chain Freight Cost & Delivery SLA Benchmarking",
                    "aliases": [
                        "Supply Chain Freight Cost & Delivery SLA Benchmarking",
                        "the $380k freight surcharge reduction project",
                        "our carrier performance and cost audit dashboard"
                    ],
                    "skills": ["SQL", "Snowflake", "Power BI", "Python", "dbt"],
                    "date": "2024-02-19",
                    "client_industry": "Logistics",
                    "outcome": "Uncovered carrier route inefficiencies saving $380,000 in annual freight surcharges",
                    "metric_short": "saved $380k in annual carrier freight surcharges",
                    "challenge": "Logistics coordinator was blind to hidden fuel surcharges and late-delivery penalty rebates.",
                    "solution": "Constructed an automated invoice reconciliation model checking billing against agreed tariff contracts.",
                },
                {
                    "id": "cs_da_009",
                    "project": "Customer Support CSAT & Agent Productivity Dashboard",
                    "aliases": [
                        "Customer Support CSAT & Agent Productivity Dashboard",
                        "the telecom support resolution efficiency analytics",
                        "our support ticket deflection and CSAT driver analysis"
                    ],
                    "skills": ["SQL", "PostgreSQL", "Tableau", "Python", "Pandas"],
                    "date": "2023-09-28",
                    "client_industry": "Telecom",
                    "outcome": "Surfaced repetitive ticket causes, resolving 22% of issues via self-service KB",
                    "metric_short": "deflected 22% of tickets through root-cause analysis",
                    "challenge": "Call center costs were surging while customer satisfaction scores dropped below 70%.",
                    "solution": "Categorized ticket text and phone transfers to identify top self-service documentation opportunities.",
                },
                {
                    "id": "cs_da_010",
                    "project": "Banking Credit Risk & Loan Delinquency Monitoring",
                    "aliases": [
                        "Banking Credit Risk & Loan Delinquency Monitoring",
                        "the $250M loan portfolio early-warning delinquency system",
                        "our vintage analysis credit loss forecasting dashboard"
                    ],
                    "skills": ["SQL", "Oracle", "Power BI", "Python", "Scikit-Learn"],
                    "date": "2024-03-22",
                    "client_industry": "Banking",
                    "outcome": "Built real-time delinquency early-warning dashboard covering $250M loan portfolio",
                    "metric_short": "monitored $250M loan portfolio with early delinquency warnings",
                    "challenge": "Credit committee only learned of loan defaults after 90 days past due.",
                    "solution": "Implemented credit score trend tracking and liquidity indicators to flag pre-delinquent accounts.",
                },
                {
                    "id": "cs_da_011",
                    "project": "Product Feature Adoption & Funnel Drop-Off Audit",
                    "aliases": [
                        "Product Feature Adoption & Funnel Drop-Off Audit",
                        "the SaaS user onboarding funnel optimization",
                        "our Mixpanel event funnel drop-off analysis"
                    ],
                    "skills": ["Mixpanel", "SQL", "BigQuery", "Looker", "Python"],
                    "date": "2024-07-10",
                    "client_industry": "SaaS",
                    "outcome": "Pinpointed onboarding friction point, increasing trial-to-paid conversion by 17%",
                    "metric_short": "increased trial-to-paid conversion by 17%",
                    "challenge": "80% of free trial signups abandoned the product before completing workspace configuration.",
                    "solution": "Mapped step-by-step telemetry paths and removed an unnecessary mandatory team invite step.",
                },
                {
                    "id": "cs_da_012",
                    "project": "Employee Retention & Compensation Equity Analysis",
                    "aliases": [
                        "Employee Retention & Compensation Equity Analysis",
                        "the tech staff voluntary turnover reduction model",
                        "our tenure hazard rate and compensation equity review"
                    ],
                    "skills": ["SQL", "Python", "Tableau", "Excel", "PostgreSQL"],
                    "date": "2023-12-04",
                    "client_industry": "HR / Enterprise",
                    "outcome": "Reduced regrettable voluntary tech turnover by 21% using tenure hazard models",
                    "metric_short": "reduced voluntary tech turnover by 21%",
                    "challenge": "Mid-level engineers were departing for competitors at an unsustainable 28% annual rate.",
                    "solution": "Conducted market salary benchmarking and isolated manager review score anomalies.",
                },
                {
                    "id": "cs_da_013",
                    "project": "Digital Advertising Click Fraud & Invalid Traffic Audit",
                    "aliases": [
                        "Digital Advertising Click Fraud & Invalid Traffic Audit",
                        "the $165k ad publisher credit recovery audit",
                        "our click fraud telemetry audit queries"
                    ],
                    "skills": ["SQL", "ClickHouse", "Python", "Pandas", "dbt"],
                    "date": "2024-01-14",
                    "client_industry": "AdTech",
                    "outcome": "Identified invalid bot traffic, recouping $165,000 in publisher ad credits",
                    "metric_short": "recouped $165k in ad credits by detecting invalid bot traffic",
                    "challenge": "E-commerce client suspected ad networks were billing for automated click farms.",
                    "solution": "Analyzed IP subnet repetition, time-to-click milliseconds, and user-agent entropy.",
                },
                {
                    "id": "cs_da_014",
                    "project": "Procurement Spend Analytics & Supplier Consolidation",
                    "aliases": [
                        "Procurement Spend Analytics & Supplier Consolidation",
                        "the $620k procurement contract renegotiation analysis",
                        "our enterprise vendor spend cube and taxonomy"
                    ],
                    "skills": ["SQL", "Snowflake", "dbt", "Power BI", "Python"],
                    "date": "2024-04-02",
                    "client_industry": "Manufacturing",
                    "outcome": "Consolidated redundant vendor contracts delivering $620,000 in direct procurement savings",
                    "metric_short": "saved $620k through vendor contract consolidation",
                    "challenge": "Independent subsidiary business units were buying identical raw materials at differing price tiers.",
                    "solution": "Built a unified vendor spend cube grouping fuzzy vendor names with Levenshtein distance matching.",
                },
                {
                    "id": "cs_da_015",
                    "project": "Subscription Streaming Viewer Churn & Content Valuation",
                    "aliases": [
                        "Subscription Streaming Viewer Churn & Content Valuation",
                        "the OTT streaming catalog acquisition valuation model",
                        "our content engagement and churn risk score"
                    ],
                    "skills": ["SQL", "BigQuery", "Tableau", "Python", "dbt"],
                    "date": "2023-10-25",
                    "client_industry": "Entertainment",
                    "outcome": "Optimized content catalog acquisition budget, lifting subscriber retention by 12%",
                    "metric_short": "lifted subscriber retention by 12% via content catalog optimization",
                    "challenge": "Streaming platform was overbidding on prestige films that drove zero long-term subscriber renewals.",
                    "solution": "Measured completion rates, series binge velocity, and second-title exploration probabilities.",
                },
                {
                    "id": "cs_da_016",
                    "project": "Hotel Dynamic Room Rate Competitor Intelligence",
                    "aliases": [
                        "Hotel Dynamic Room Rate Competitor Intelligence",
                        "the boutique hotel RevPAR yield management model",
                        "our competitor rate scraping and elasticity dashboard"
                    ],
                    "skills": ["Python", "SQL", "PostgreSQL", "Power BI", "BeautifulSoup"],
                    "date": "2024-05-02",
                    "client_industry": "Hospitality",
                    "outcome": "Boosted RevPAR (Revenue Per Available Room) by 14% via automated scraper and pricing model",
                    "metric_short": "boosted RevPAR by 14% through dynamic competitor rate tracking",
                    "challenge": "Hotel property managers adjusted nightly room prices manually once a week, trailing market trends.",
                    "solution": "Constructed daily OTA scraper pipelines paired with local event calendar demand multipliers.",
                },
                {
                    "id": "cs_da_017",
                    "project": "Call Center Interactive Voice Response (IVR) Routing Analysis",
                    "aliases": [
                        "Call Center Interactive Voice Response (IVR) Routing Analysis",
                        "the insurance IVR voice tree redesign project",
                        "our caller journey path and drop-off analysis"
                    ],
                    "skills": ["SQL", "Tableau", "Python", "Snowflake", "dbt"],
                    "date": "2024-02-08",
                    "client_industry": "Insurance",
                    "outcome": "Lowered call transfer rate by 31% by redesigning top 5 voice menu journeys",
                    "metric_short": "cut call transfer rate by 31% by restructuring IVR menus",
                    "challenge": "Policyholders pressed random keypad numbers to escape endless telephone menus.",
                    "solution": "Analyzed telephony log paths and rep routed skills, placing the 3 most frequent tasks on top level.",
                },
                {
                    "id": "cs_da_018",
                    "project": "Clinical Trial Site Milestone Tracker",
                    "aliases": [
                        "Clinical Trial Site Milestone Tracker",
                        "the 45-site global oncology patient enrollment tracker",
                        "our clinical milestone risk and delay projection tool"
                    ],
                    "skills": ["SQL", "PostgreSQL", "Power BI", "Python", "Pandas"],
                    "date": "2023-11-12",
                    "client_industry": "Pharma",
                    "outcome": "Accelerated Phase II patient enrollment tracking across 45 global hospital sites by 3 weeks",
                    "metric_short": "accelerated patient enrollment tracking by 3 weeks across 45 sites",
                    "challenge": "Pharmaceutical trial coordinator experienced communication lag from foreign hospital investigator sites.",
                    "solution": "Developed standardized weekly data ingestion feeds with automated screening discrepancy alerts.",
                },
                {
                    "id": "cs_da_019",
                    "project": "Real Estate Commercial Lease Renewal & Vacancy Forecaster",
                    "aliases": [
                        "Real Estate Commercial Lease Renewal & Vacancy Forecaster",
                        "the 3.2M sqft commercial office vacancy forecasting model",
                        "our tenant lease expiry and retention schedule"
                    ],
                    "skills": ["SQL", "Excel", "Tableau", "Python", "Snowflake"],
                    "date": "2024-06-18",
                    "client_industry": "PropTech",
                    "outcome": "Reduced commercial property vacancy rate by 4.5% across a 3.2M sqft portfolio",
                    "metric_short": "lowered vacancy rate by 4.5% across 3.2M sqft portfolio",
                    "challenge": "Asset managers had 12-month notice blind spots on expiring enterprise floor leases.",
                    "solution": "Built a predictive tenant renewal model factoring in tenant headcount growth and submarket rates.",
                },
                {
                    "id": "cs_da_020",
                    "project": "University Student Enrollment Yield & Retention Modeling",
                    "aliases": [
                        "University Student Enrollment Yield & Retention Modeling",
                        "the freshman matriculation yield financial aid optimization",
                        "our student retention and enrollment propensity model"
                    ],
                    "skills": ["SQL", "R", "Tableau", "BigQuery", "dbt"],
                    "date": "2024-03-30",
                    "client_industry": "Higher Education",
                    "outcome": "Increased freshman matriculation yield by 8.4% through financial aid optimization",
                    "metric_short": "increased freshman matriculation yield by 8.4%",
                    "challenge": "Admissions office misallocated merit scholarship funds to students who were already committed.",
                    "solution": "Built price elasticity models optimizing scholarship grant distributions across applicant tiers.",
                },
            ],
            "repos": [
                {
                    "name": "dbt-analytics-warehouse",
                    "description": "Production dbt repository containing dimensional modeling, cohort retention, and tests.",
                    "files": {
                        "fct_customer_retention.sql": '''-- synthetic: true
WITH monthly_activity AS (
    SELECT
        user_id,
        DATE_TRUNC('month', activity_date) AS activity_month
    FROM {{ ref('stg_user_events') }}
    GROUP BY 1, 2
),
cohort_base AS (
    SELECT
        user_id,
        MIN(activity_month) AS cohort_month
    FROM monthly_activity
    GROUP BY 1
)
SELECT
    cb.cohort_month,
    ma.activity_month,
    COUNT(DISTINCT ma.user_id) AS active_users
FROM cohort_base cb
JOIN monthly_activity ma ON cb.user_id = ma.user_id
GROUP BY 1, 2;
''',
                        "dim_subscriptions.sql": '''-- synthetic: true
SELECT
    subscription_id,
    account_id,
    plan_tier,
    mrr_usd,
    started_at,
    ended_at,
    CASE WHEN ended_at IS NULL THEN TRUE ELSE FALSE END AS is_active
FROM {{ ref('stg_stripe_subscriptions') }};
''',
                        "schema.yml": '''# synthetic: true
version: 2
models:
  - name: fct_customer_retention
    description: Monthly cohort retention table tracking user activity across tenures.
    columns:
      - name: cohort_month
        tests:
          - not_null
      - name: active_users
        tests:
          - not_null
'''
                    }
                },
                {
                    "name": "kpi-executive-dashboard",
                    "description": "Automated ETL script and SQL queries powering executive reporting metrics.",
                    "files": {
                        "etl_extract.py": '''# synthetic: true
"""Postgres to data warehouse batch extractor."""
import pandas as pd


def extract_daily_sales(engine, target_date: str) -> pd.DataFrame:
    query = f"""
        SELECT order_id, customer_id, gross_amount, net_margin
        FROM orders
        WHERE order_date = '{target_date}'
    """
    return pd.read_sql(query, engine)
''',
                        "kpi_metrics.py": '''# synthetic: true
"""KPI computation functions for net retention and customer acquisition cost."""


def compute_net_dollar_retention(starting_mrr: float, expansion: float, contraction: float, churn: float) -> float:
    if starting_mrr == 0:
        return 0.0
    return ((starting_mrr + expansion - contraction - churn) / starting_mrr) * 100.0
''',
                        "dashboard_queries.sql": '''-- synthetic: true
-- High-level executive gross margin and revenue run rate
SELECT
    DATE_TRUNC('quarter', recorded_at) AS fiscal_quarter,
    SUM(gross_revenue_usd) AS total_revenue,
    SUM(gross_margin_usd) / NULLIF(SUM(gross_revenue_usd), 0) * 100 AS margin_percentage
FROM analytics.fct_daily_revenue
GROUP BY 1
ORDER BY 1 DESC;
'''
                    }
                }
            ],
            "code_snippets": [
                '```sql\nSELECT DATE_TRUNC("month", signup_date) AS cohort, COUNT(DISTINCT user_id) AS signups\nFROM users GROUP BY 1;\n```',
                '```sql\nWITH lag_mrr AS (\n  SELECT account_id, mrr, LAG(mrr) OVER (PARTITION BY account_id ORDER BY month) AS prev_mrr\n  FROM fct_mrr\n)\n```',
                '```python\ndf["churn_flag"] = (df["days_since_last_login"] > 45).astype(int)\nchurn_rate = df["churn_flag"].mean()\n```'
            ],
            "implied_skills": [
                "eliminated fan-out joins using surrogate keys and windowed partitioned lag functions across monthly billing events",
                "structured dbt incremental models with unique keys and pre-hook partition pruning for petabyte-scale Snowflake runs",
                "modeled Kimball dimensional star schemas with slowly changing dimensions (SCD Type 2) to preserve historical reporting accuracy",
            ]
        }
    }


def generate_cv_markdown(persona: dict) -> str:
    lines = [
        f"# {persona['name']} - CV (SYNTHETIC PERSONA PROFILE)",
        "",
        f"**Role:** {persona['title']}  ",
        f"**Hourly Rate:** ${persona['rates']['hourly']}/hr | **Minimum Project:** ${persona['rates']['fixed_minimum']} | **Location:** Remote  ",
        "**Synthetic Data:** true (Generated for AI-4016 GigBid Project)  ",
        "",
        "## Professional Summary",
        persona["bio"],
        "",
        "## Core Competencies",
        ", ".join(persona["skills"]),
        "",
        "## Education",
        persona["education"],
        "",
        "## Representative Enterprise Projects & Case Studies",
        ""
    ]
    for cs in persona["case_studies"][:8]:
        lines.append(f"### {cs['project']} ({cs['client_industry']})")
        lines.append(f"- **Key Outcome:** {cs['outcome']}")
        lines.append(f"- **Technologies:** {', '.join(cs['skills'])}")
        lines.append(f"- **Description:** {cs['solution']}")
        lines.append("")
    return "\n".join(lines)


def generate_reviews(persona: dict, rng: random.Random) -> list[dict]:
    reviews = []
    first_names = ["Sarah", "David", "Jessica", "Michael", "Emily", "Robert", "Chloe", "Alexander", "Rachel", "Daniel", "Samantha", "Marcus"]
    last_names = ["Chen", "Miller", "Dubois", "Kowalski", "Patel", "Johansson", "Nakamura", "O'Connor", "Rossi", "Schmidt", "Alvarez", "Taylor"]

    for i in range(12):
        client_name = f"{first_names[i]} {last_names[i]}"
        cs = persona["case_studies"][i % len(persona["case_studies"])]
        rating = rng.choice([4.9, 5.0, 5.0, 5.0, 4.8])
        spend = rng.randint(3000, 18000)
        feedbacks = [
            f"Exceptional work by {persona['name']} on our {cs['project']}. Delivered ahead of schedule and the results were stunning: {cs['outcome']}.",
            f"{persona['name']} is a true expert. Handled all complexity with {cs['skills'][0]} effortlessly. Would hire again in a heartbeat.",
            f"Outstanding technical competence and communication. Solved our bottleneck with {cs['project']} and saved us hundreds of engineering hours.",
            f"High quality, deep domain mastery, and flawless execution. {cs['project']} was delivered cleanly and documented impeccably."
        ]
        reviews.append({
            "review_id": f"rev_{persona['id']}_{i+1:03d}",
            "client_name": client_name,
            "client_industry": cs["client_industry"],
            "project_title": cs["project"],
            "rating": rating,
            "amount_earned_usd": spend,
            "feedback": feedbacks[i % len(feedbacks)],
            "date": f"2024-{(i%10)+1:02d}-15",
            "synthetic": True,
        })
    return reviews


def generate_past_proposals(persona: dict, total_count: int, rng: random.Random) -> list[dict]:
    """Generates ~150 proposals following strict outcome rules:
      - Won: cites specific project and metric from case studies, plausible quality, messiness
      - Replied: cites skills and architecture concepts, but NO metrics
      - Ignored: generic openers without metrics or specifics
    """
    proposals = []
    # Target distribution: ~42 won, ~51 replied, ~57 ignored = 150
    won_count = int(total_count * 0.28)
    replied_count = int(total_count * 0.34)
    ignored_count = total_count - won_count - replied_count

    outcomes = (
        ["won"] * won_count +
        ["replied"] * replied_count +
        ["ignored"] * ignored_count
    )
    rng.shuffle(outcomes)

    job_titles_by_cat = {
        "ai_ml": [
            "Senior LLM Engineer needed for Enterprise RAG Pipeline",
            "Build real-time fraud detection microservice in Python/FastAPI",
            "Fine-tune Whisper speech-to-text model on clinical recordings",
            "Multi-agent LangGraph workflow for customer support routing",
            "Develop custom embedding search with pgvector and FastAPI",
            "Machine learning engineer to build predictive maintenance pipeline",
            "Computer vision specialist for real-time safety detection YOLOv8",
            "Automate document parsing and table extraction with LLM",
        ],
        "fullstack": [
            "Full-Stack Next.js 14 and FastAPI developer for SaaS billing",
            "Real-time WebSocket multiplayer collaborative editor in React",
            "Build developer API documentation portal and interactive console",
            "Senior TypeScript / Node.js developer for Stripe Connect platform",
            "Lead fullstack engineer for logistics dispatch map application",
            "Telehealth portal development with WebRTC and HIPAA compliance",
            "E-commerce storefront optimization and headless Shopify checkout",
            "Interactive Three.js 3D property tour and booking application",
        ],
        "data_analyst": [
            "Lead Data Analyst to build customer churn retention models",
            "Multi-touch marketing attribution and ROAS analytics in BigQuery",
            "dbt analytics engineer to model subscription revenue ASC 606",
            "Power BI and SQL dashboard specialist for hospital operations",
            "Retail inventory stockout prediction and safety stock modeling",
            "Executive revenue and gross margin dashboard in Snowflake and Tableau",
            "Mobile gaming player LTV cohort segmentation and behavioral analysis",
            "Supply chain freight cost and carrier SLA benchmarking analysis",
        ]
    }

    won_templates = [
        (
            "Hi, I reviewed your project '{job_title}' and I have built this exact architecture before. "
            "Recently, in my project '{project_ref}' for a {client_industry} client, I achieved {outcome_ref}. "
            "Here is the technical approach I recommend:\n"
            "1. Decouple ingestion from inference to ensure sub-50ms responsiveness.\n"
            "2. {implied_skill}.\n"
            "{code_snippet}\n"
            "I can deliver this initial vertical slice within 10 days. Happy to share a live architecture walk-through."
        ),
        (
            "Hello, your requirements for '{job_title}' closely mirror {project_ref} where I delivered {outcome_ref}. "
            "My solution leveraged {skill_combo} with an emphasis on production resilience. In that build, I {implied_skill}.\n"
            "I would structure your milestones into two phases: core engine implementation and performance hardening. "
            "Looking forward to discussing the specifics."
        ),
        (
            "Hi there, this is right in my wheelhouse. I recently shipped {project_ref} for an enterprise {client_industry} client, "
            "achieving {outcome_ref}. A common pitfall in these systems is unmanaged tail latency and failure recovery; "
            "I address this by ensuring that {implied_skill}.\n"
            "{code_snippet}\n"
            "I am available to start immediately and maintain 100% test coverage with automated CI runs."
        ),
        (
            "Greetings, regarding '{job_title}': I have direct hands-on experience solving this. "
            "Specifically, in {project_ref}, my implementation achieved {outcome_ref}. "
            "For your system, I suggest configuring the pipeline so we {implied_skill}.\n"
            "Let's jump on a quick discovery call to review your current schema and data volume."
        )
    ]

    replied_templates = [
        (
            "Hello! I am very interested in '{job_title}'. I specialize in {skill_combo} and have built scalable, production-tested architectures. "
            "In similar systems, I typically set up modular components where we {implied_skill}. "
            "{code_snippet}\n"
            "I can commit 30+ hours per week and deliver clean, well-tested code with Dockerized deployment. What is your preferred timeline?"
        ),
        (
            "Hi, I have extensive experience with {skill_combo} and have delivered high-throughput systems for various clients. "
            "For '{job_title}', I would focus on clean interfaces, robust error handling, and end-to-end integration tests. "
            "I have worked extensively with asynchronous architectures where we {implied_skill}. "
            "Let me know if you would like to see my GitHub portfolio or schedule a technical chat."
        ),
        (
            "Dear hiring team, I read through your brief for '{job_title}' and can help you implement this cleanly. "
            "My core stack includes {skill_combo}. I ensure all code is strictly typed, modular, and accompanied by automated tests. "
            "Could you clarify the expected concurrent load and whether you have an existing staging environment?"
        ),
        (
            "Hi, I am an experienced engineer with deep expertise across {skill_combo}. "
            "For your project '{job_title}', I recommend a clean decoupled architecture ensuring high availability and zero downtime. "
            "I have worked with distributed queues and databases where we {implied_skill}.\n"
            "I am ready to review your codebase and start right away."
        )
    ]

    ignored_templates = [
        (
            "Hello! I am very interested in your job posting '{job_title}'. I am an experienced developer with many years in the industry. "
            "I deliver high quality work on time and on budget. Please hire me and I will get started right now. Thanks!"
        ),
        (
            "Dear Client, I saw your post '{job_title}' and I can do this project easily. I have 100% job success score and great reviews. "
            "Please check my profile and let's discuss details in chat."
        ),
        (
            "Hi there, I am a senior engineer ready to work on '{job_title}'. Fast turnaround guaranteed, lowest price, 24/7 support. "
            "Contact me today so we can begin immediately."
        ),
        (
            "Greetings! I have read your job description for '{job_title}' carefully. I am confident I can complete it to your full satisfaction. "
            "Looking forward to hearing from you soon to discuss pricing and scope."
        ),
        (
            "Hello, please consider my bid for '{job_title}'. I have strong programming skills and have done similar jobs in the past. "
            "I am available to start today and work full time. Thank you."
        )
    ]

    case_studies = persona["case_studies"]

    for idx, outcome in enumerate(outcomes):
        prop_id = f"prop_{persona['id']}_{idx+1:04d}"
        job_title = rng.choice(job_titles_by_cat[persona["id"]])
        month = rng.randint(1, 10)
        day = rng.randint(1, 28)
        date_str = f"2024-{month:02d}-{day:02d}"

        if outcome == "won":
            cs = rng.choice(case_studies)
            # Pick one of 3 aliases for messiness
            project_ref = rng.choice(cs["aliases"])
            outcome_ref = cs["outcome"]
            template = rng.choice(won_templates)
            skill_combo = ", ".join(rng.sample(persona["skills"], 3))
            implied_skill = rng.choice(persona["implied_skills"])
            code_snippet = rng.choice(persona["code_snippets"]) if rng.random() > 0.3 else ""
            text = template.format(
                job_title=job_title,
                project_ref=project_ref,
                client_industry=cs["client_industry"],
                outcome_ref=outcome_ref,
                skill_combo=skill_combo,
                implied_skill=implied_skill,
                code_snippet=code_snippet,
            )
        elif outcome == "replied":
            template = rng.choice(replied_templates)
            skill_combo = ", ".join(rng.sample(persona["skills"], 3))
            implied_skill = rng.choice(persona["implied_skills"])
            code_snippet = rng.choice(persona["code_snippets"]) if rng.random() > 0.5 else ""
            text = template.format(
                job_title=job_title,
                skill_combo=skill_combo,
                implied_skill=implied_skill,
                code_snippet=code_snippet,
            )
        else:  # ignored
            template = rng.choice(ignored_templates)
            text = template.format(job_title=job_title)

        proposals.append({
            "id": prop_id,
            "job_title": job_title,
            "text": text,
            "outcome": outcome,
            "category": persona["title"],
            "date": date_str,
            "synthetic": True,
        })

    return proposals


def generate_all_personas(output_dir: Path, seed: int = 42, proposals_per_persona: int = 150) -> None:
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    personas_def = get_persona_definitions()

    for pid, pdata in personas_def.items():
        p_dir = output_dir / pid
        p_dir.mkdir(parents=True, exist_ok=True)

        # 1. profile.json
        profile = {
            "id": pdata["id"],
            "name": pdata["name"],
            "title": pdata["title"],
            "hourly_rate": pdata["rates"]["hourly"],
            "floor_hourly_rate": pdata["floor_hourly_rate"],
            "min_fixed_rate": pdata["rates"]["fixed_minimum"],
            "weekly_connects_budget": pdata["weekly_connects_budget"],
            "filters": pdata["filters"],
            "skills": pdata["skills"],
            "bio": pdata["bio"],
            "education": pdata["education"],
            "synthetic": True,
        }
        (p_dir / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

        # 2. cv.md & cv.pdf
        cv_md = generate_cv_markdown(pdata)
        (p_dir / "cv.md").write_text(cv_md, encoding="utf-8")
        write_clean_pdf(cv_md.splitlines(), p_dir / "cv.pdf")

        # 3. case_studies/*.md (20 case studies)
        cs_dir = p_dir / "case_studies"
        cs_dir.mkdir(parents=True, exist_ok=True)
        for cs in pdata["case_studies"]:
            cs_frontmatter = (
                "---\n"
                f"id: {cs['id']}\n"
                f'project: "{cs["project"]}"\n'
                f"skills: {json.dumps(cs['skills'])}\n"
                f'date: "{cs["date"]}"\n'
                f'client_industry: "{cs["client_industry"]}"\n'
                f'outcome: "{cs["outcome"]}"\n'
                "synthetic: true\n"
                "---\n\n"
                f"# Case Study: {cs['project']}\n\n"
                f"**Client Industry:** {cs['client_industry']}  \n"
                f"**Date:** {cs['date']}  \n"
                f"**Primary Technologies:** {', '.join(cs['skills'])}  \n\n"
                "## The Challenge\n"
                f"{cs['challenge']}\n\n"
                "## The Solution Architecture\n"
                f"{cs['solution']}\n\n"
                "## Measured Outcomes & Impact\n"
                f"- **Quantified Result:** {cs['outcome']}\n"
                "- Full unit test suite and automated linting included.\n"
                "- Zero production regression defects observed.\n"
            )
            (cs_dir / f"{cs['id']}.md").write_text(cs_frontmatter, encoding="utf-8")

        # 4. repos/<name>/README.md + 2-4 code files
        repos_dir = p_dir / "repos"
        repos_dir.mkdir(parents=True, exist_ok=True)
        for repo in pdata["repos"]:
            r_dir = repos_dir / repo["name"]
            r_dir.mkdir(parents=True, exist_ok=True)
            readme_content = (
                f"# {repo['name']} (SYNTHETIC REPO)\n\n"
                f"{repo['description']}\n\n"
                "**Synthetic:** true (Stand-in for GitHub portfolio ingestion)\n"
            )
            (r_dir / "README.md").write_text(readme_content, encoding="utf-8")
            for fname, fcontent in repo["files"].items():
                (r_dir / fname).write_text(fcontent, encoding="utf-8")

        # 5. reviews.json
        reviews = generate_reviews(pdata, rng)
        (p_dir / "reviews.json").write_text(json.dumps(reviews, indent=2), encoding="utf-8")

        # 6. past_proposals.jsonl (~150 items)
        proposals = generate_past_proposals(pdata, proposals_per_persona, rng)
        with (p_dir / "past_proposals.jsonl").open("w", encoding="utf-8") as pf:
            for p in proposals:
                pf.write(json.dumps(p) + "\n")

    print(f"Generated synthetic persona data for 3 personas in {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic persona corpora for GigBid.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation.")
    parser.add_argument("--output-dir", type=str, default="data/personas", help="Output directory path.")
    parser.add_argument(
        "--proposals-per-persona",
        type=int,
        default=150,
        help="Number of proposals to generate per persona (default: 150).",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent.parent
    output_path = Path(args.output_dir)
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    generate_all_personas(
        output_dir=output_path,
        seed=args.seed,
        proposals_per_persona=args.proposals_per_persona,
    )


if __name__ == "__main__":
    main()
