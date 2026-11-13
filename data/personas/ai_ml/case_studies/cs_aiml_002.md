---
id: cs_aiml_002
project: "Real-Time Transaction Fraud Detection"
skills: ["PyTorch", "Kafka", "FastAPI", "Redis", "Docker"]
date: "2024-04-10"
client_industry: "FinTech"
outcome: "Reduced false positives by 38% while processing 14k TPS at p99 < 35ms"
synthetic: true
---

# Case Study: Real-Time Transaction Fraud Detection

**Client Industry:** FinTech  
**Date:** 2024-04-10  
**Primary Technologies:** PyTorch, Kafka, FastAPI, Redis, Docker  

## The Challenge
Legacy rule-based engine flagged legitimate customer card transactions causing high churn.

## The Solution Architecture
Trained an ensemble of gradient-boosted trees and deep representation models served via ONNX runtime.

## Measured Outcomes & Impact
- **Quantified Result:** Reduced false positives by 38% while processing 14k TPS at p99 < 35ms
- Full unit test suite and automated linting included.
- Zero production regression defects observed.
