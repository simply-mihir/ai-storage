# 5-Minute Demo Script

## 0:00 — Problem (30 seconds)
"Startups outgrow their storage decisions silently. By the time performance
or cost becomes a crisis, the architecture is already entrenched.
AI Data Architect turns workload requirements into explainable,
cost-aware storage strategy — before growth creates the problem."

## 0:30 — Enter the scenario
Fill in or paste: 10M users, 300 GB/day, images + transactions,
HIGH read/write, 100ms latency, 99.99% availability, 7-year retention.
Click "Analyze Architecture".

## 1:00 — Show Recommendation tab
Point out: architecture summary line, REQUIRED vs RECOMMENDED badges,
the 3 architecture components (RDS, S3, ElastiCache).
"The engine separated media from transactional data automatically —
not because we told it to, but because the data types and latency
requirements triggered that separation."

## 1:45 — Open Why? tab
Show the Bedrock explanation (or structured fallback).
Walk through one problem → recommendation chain:
"HIGH_AVAILABILITY_REQUIREMENT → Replication [REQUIRED] → Multi-AZ RDS."

## 2:30 — Show Impact tab
Point to the three metric cards.
Read the assumptions expander: "These are model-based estimates — we label
them explicitly. No fabricated benchmark claims."

## 3:00 — What-if tab
Change daily growth from 300 to 1,000 GB/day. Click Recalculate.
Show: "Sharding escalated from RECOMMENDED to REQUIRED. The architecture
responds to the assumption change."

## 3:30 — Ask Bedrock a follow-up (if available)
Type: "Why did you separate media from transactional data?"
Show the response.

## 4:00 — Analytics tab
Point to the technique frequency chart and co-occurrence network.
"2,000 synthetic scenarios. Replication and object storage dominate.
Caching and partitioning almost always co-occur."
Show the ML comparison: "0.997 F1 — the model learned the rules near-perfectly.
But 41% top-5 agreement tells us the rules have better priority reasoning
than probability ranking alone."

## 4:45 — Close
"Deterministic rules make the decisions. Bedrock explains them.
The architecture is auditable, reproducible, and cloud-native on AWS."
