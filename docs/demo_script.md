# 8-Minute Demo Script

Sections marked with a star are the 5-minute core demo. If time is short, skip unmarked sections.

## 0:00 — Problem (30 seconds) ⭐

"Startups outgrow their storage decisions silently. By the time performance
or cost becomes a crisis, the architecture is already entrenched.
AI Data Architect turns workload requirements into explainable,
cost-aware storage strategy — before growth creates the problem."

## 0:30 — Enter the scenario ⭐

Fill in or paste: 10M users, 300 GB/day, images + transactions,
HIGH read/write, 100ms latency, 99.99% availability, 7-year retention.
Click "Analyze Architecture".

## 1:00 — Show Recommendation tab ⭐

Point out: architecture summary line, REQUIRED vs RECOMMENDED badges,
the architecture components (RDS, S3, ElastiCache, Redshift, Glacier).
"The engine separated media from transactional data automatically —
not because we told it to, but because the data types and latency
requirements triggered that separation."

Show the Terraform Export section at the bottom:
Click "Download Terraform Scaffold" — a zip with `main.tf`,
`variables.tf`, `outputs.tf`, and a `terraform.tfvars.example`.
"One click from recommendation to infrastructure-as-code."

## 1:45 — Open Why? tab ⭐

Show the Bedrock explanation (or structured fallback).
Walk through one problem → recommendation chain:
"HIGH_AVAILABILITY_REQUIREMENT → Replication [REQUIRED] → Multi-AZ RDS."
"Every recommendation is traceable. No black box."

## 2:30 — Show Impact tab ⭐

Point to the three metric cards (storage, cost, latency).
Read the assumptions expander: "These are model-based estimates — we label
them explicitly. No fabricated benchmark claims."

Show the Confidence Ranges section below the estimates:
"Each metric has a 25th–75th percentile band computed from 2,000 synthetic
scenarios. The diamond is our point estimate; the bar is the range of
outcomes we've seen in similar workloads."

## 3:15 — Real Cost tab ⭐

Show the per-component cost breakdown with live AWS list prices.
"These are real prices from the AWS Pricing API, not our model estimates.
S3 at $0.023/GB, RDS at the current on-demand rate."
If time allows, change the region dropdown and show price differences.

## 4:00 — What-If tab

Change daily growth from 300 to 1,000 GB/day. Click Recalculate.
Show: "Sharding escalated from RECOMMENDED to REQUIRED. The architecture
responds to the assumption change."

## 4:30 — Growth Roadmap tab

Set growth rate to 10%, months to 24, click Simulate Growth.
Walk through:
- The summary narrative ("Architecture stable until month N")
- The trajectory chart with tipping point markers
- Open one tipping point expander: "At month 8, partitioning escalates
  from RECOMMENDED to REQUIRED because storage crossed the threshold."
"This is a 24-month crystal ball for your infrastructure."

## 5:30 — Ask Bedrock a follow-up (if available)

Type: "Why did you separate media from transactional data?"
Show the response.

## 6:00 — Analytics tab

Point to the technique frequency chart and co-occurrence network.
"2,000 synthetic scenarios. Replication and object storage dominate.
Caching and partitioning almost always co-occur."
Show the ML comparison: "0.997 F1 — the model learned the rules near-perfectly.
But 41% top-5 agreement tells us the rules have better priority reasoning
than probability ranking alone."

## 7:00 — Architecture recap (30 seconds)

"No LLM made these decisions. A deterministic rules engine evaluates
19 storage techniques against your specific workload. Bedrock explains
the results in plain language, but the authority is the engine."

Show the 8 tabs in a quick sweep: Architect, Recommendation, Impact,
Real Cost, Growth Roadmap, Why?, Analytics, What-If.

## 7:30 — Close

"Deterministic rules make the decisions. Bedrock explains them.
Real AWS pricing grounds the estimates. Terraform gets you started.
The architecture is auditable, reproducible, and cloud-native on AWS."
