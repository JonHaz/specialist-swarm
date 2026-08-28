---
name: technical-fit
description: BTS-Synthetic product capability map and fit-scoring rubric for inbound RFPs. Use whenever assessing whether our platform actually does what an RFP asks for — covers architecture, ingest, analytics, governance, ML, SLA tiers, compliance, known weaknesses, and typical implementation timelines. Trigger on any request to assess technical fit, score capability coverage, answer "do we cover this requirement", identify gaps, or flag technical risk in an RFP or customer requirements document.
---

# Technical Fit Assessment

This is the authoritative capability map. Assess every requirement against it and nothing else — if a
capability is not listed here, we do not have it, however reasonable it sounds.

## 1. Core architecture

**What we have:** Lakehouse with native Delta, Iceberg, and Parquet. Object storage backend
(bring-your-own S3, Azure Blob, or GCS). Compute decoupled from storage, with SQL, Spark-equivalent,
and streaming engines. Deployable on AWS, Azure, and GCP, multi-region within each. Self-hosted
option for sovereignty-sensitive customers.

## 2. Ingest

**What we have:** Batch ETL with 80+ connectors out of the box (Salesforce, SAP, NetSuite, common
databases). Native Kafka and Kinesis consumers for real-time streaming, **tested up to 250K
events/second on single-region deployments**. CDC from major databases via Debezium-compatible
connectors.

## 3. Analytics

**What we have:** Full ANSI SQL, sub-second on warmed caches up to 10TB. Notebooks in Python, R, and
Scala. Certified BI integrations with Power BI, Tableau, Looker, and Qlik — **Power BI is our most
mature integration, with a dedicated DirectQuery adapter**. Low-code self-service data prep for
analyst personas.

## 4. Governance

**What we have:** Unity-style catalog for tables, models, and dashboards. Row-level and column-level
security with attribute-based access control. Per-table data residency enforcement — EU tables can
be pinned to EU regions. Every read and write logged and exportable to a customer SIEM. Built-in PII
detection and masking.

## 5. ML / AI

**What we have:** Model registry with versioning. Feature store for offline and online serving.
Native model serving with autoscaling. Bring-your-own-model: any HuggingFace, Anthropic, or OpenAI
model callable from inside the platform.

## 6. SLA tiers

**What we have:** **99.95% monthly uptime on Enterprise tier.** 99.99% is available as a custom
add-on requiring multi-region active-active architecture, typically $80K–$120K/year premium.

Treat any RFP demanding 99.99% as a **partial** fit, not a full one. It is reachable, but only as a
priced add-on with an architectural precondition — say so plainly rather than ticking the box.

## 7. Compliance

**What we have:** SOC 2 Type II, ISO 27001, HIPAA-eligible, GDPR-aligned (DPA available), FedRAMP
Moderate (US Gov tier only).

## 8. Where we are weak

This section is the reason the assessment is credible. Never omit or soften it.

- **Real-time analytics below 100ms latency.** We are not best-in-class. We hit ~250ms–1s on
  streaming queries. Any RFP demanding sub-100ms is a **partial** fit at best.
- **Geospatial workloads.** Basic support only. No advanced geospatial indexing.
- **Graph workloads.** Not natively supported. Customers run these in a separate graph database.
- **No native Power Apps connector.** Power BI yes, Power Apps no. Customers are usually fine with
  this, but in a Microsoft-stack account say it rather than letting it surface later.

## 9. Implementation timeline

- **8 weeks** to first production workload with clean source systems.
- **16 weeks** for full migration from a legacy warehouse (Teradata, Hadoop).
- **24 weeks** for very large multi-region, multi-source customers.

## 10. Scoring rubric

Score each requirement, then roll up. Do not invent intermediate grades.

**Per requirement:**

| Grade | Means |
| --- | --- |
| **Full** | We meet it as shipped, on the Enterprise tier, with no add-on and no caveat. |
| **Partial** | We meet it with a priced add-on, an architectural precondition, or below the level asked for. State the gap and its cost. |
| **None** | Not in this capability map. Say so directly and do not propose a roadmap date. |

**Overall fit:**

| Score | Means |
| --- | --- |
| **High** | No requirement scores None, and any Partials are commercial (add-on priced) rather than technical. |
| **Medium** | At least one Partial is technical, or one None exists on a requirement the RFP does not mark as mandatory. |
| **Low** | Any None on a requirement the RFP marks non-negotiable. |

## 11. Claim discipline

The fit assessment feeds a customer-facing proposal, so every number has to survive being quoted
back. Three rules:

- **Never upgrade a tested figure to a production claim.** This map says 250K events/second was
  *tested*. Write "tested to 250K events/second". Do not write "250K events/second in production".
- **Never round a tier up.** 99.95% is not "approximately 99.99%".
- **Name the precondition with the capability.** "99.99% available" is incomplete; "99.99%
  available as an add-on requiring multi-region active-active, ~$80K–$120K/year" is the claim.

## How to report

Use this format:

```
REQUIREMENT: Real-time ingest, 80,000 events/second peak
Grade: FULL
Evidence: Native Kafka/Kinesis consumers, tested to 250K events/sec single-region — 3x headroom.

REQUIREMENT: 99.99% monthly uptime
Grade: PARTIAL
Evidence: Enterprise tier is 99.95%. 99.99% is an add-on requiring multi-region active-active.
Gap + cost: ~$80K-$120K/year premium.

OVERALL FIT: High
BIGGEST RISK: The 99.99% SLA demand is commercial, not technical — it needs a pricing decision
before the response goes out, not an engineering one.
```

Close with exactly one "biggest risk" line. If you cannot name one, you have not read the RFP
closely enough.
