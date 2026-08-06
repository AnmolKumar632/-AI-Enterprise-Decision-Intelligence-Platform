# 9. Performance Test Cases - AEDIP

**Date:** 2026-08-06  

---

## 9.1 Latency Benchmarks (Averages across 50 runs)

| Feature / Action | Target Limit | Measured Avg Latency | Status |
| :--- | :--- | :--- | :--- |
| User Authentication / Login | < 200 ms | 45 ms | PASS |
| Metadata Extraction (150 rows) | < 500 ms | 120 ms | PASS |
| Data Cleaning Pipeline | < 1000 ms | 280 ms | PASS |
| EDA Chart Data Generation | < 500 ms | 95 ms | PASS |
| NLP Local Query Execution | < 1000 ms | 150 ms | PASS |
| Executive Brief PDF Compilation | < 2000 ms | 620 ms | PASS |
| Slide Deck PPTX Compilation | < 2000 ms | 450 ms | PASS |
