"""Bedrock integration — LLM-powered explanation and NL extraction.

The deterministic rule engine remains the authority. Bedrock adds
natural-language explanation on top of structured output.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from storage_advisor.domain.recommendations import RecommendationResult
from storage_advisor.domain.scenario import Scenario
from storage_advisor.estimation.impact_estimator import ImpactReport

logger = logging.getLogger(__name__)


@dataclass
class ExplanationResult:
    text: str
    source: str  # "bedrock" | "structured_fallback"


_EXPLAIN_SYSTEM = (
    "You are a senior data architect explaining storage architecture decisions "
    "to a technical founder. Be concise, specific, and honest about trade-offs. "
    "Do not invent numbers or claim real-world benchmarks. The estimates provided "
    "are model-based, not empirical measurements."
)

_EXTRACT_SYSTEM = (
    "Extract structured workload information from a free-text description. "
    'Return ONLY a JSON object with these fields (omit fields you cannot determine): '
    "business_domain, users (integer), daily_growth_gb (number), data_types (list of strings), "
    "latency_ms (integer), availability_pct (number), retention_years (number), "
    "read_intensity (LOW/MEDIUM/HIGH), write_intensity (LOW/MEDIUM/HIGH), "
    "compliance (list of strings from: HIPAA, PCI, GDPR, SOC2). "
    "Return valid JSON only. No explanation."
)


def structured_fallback(
    result: RecommendationResult,
    scenario: Scenario,
) -> ExplanationResult:
    top = result.recommendations[:3]
    problems = result.detected_problems[:3]

    problem_lead = (
        problems[0]["problem_id"]
        if problems and isinstance(problems[0], dict)
        else "scale requirements"
    )

    lines = [
        f"For a {scenario.business_domain} workload at {scenario.expected_users:,} users:",
        (
            f"The system detected {len(result.detected_problems)} architectural pressures, "
            f"led by {problem_lead}."
        ),
    ]
    if top:
        lines.append(
            f"The primary recommendation is {top[0].technique_id} because {top[0].rationale}."
        )
    lines.append(
        f"Key trade-off: implementing these {len(result.recommendations)} techniques "
        f"together reduces storage and cost but increases operational complexity."
    )
    lines.append("(Bedrock explanation unavailable — showing structured summary.)")

    return ExplanationResult(
        text=" ".join(lines),
        source="structured_fallback",
    )


class BedrockExplainer:

    def __init__(
        self,
        region: str | None = None,
        model_id: str | None = None,
    ):
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0",
        )
        self.available = False
        self._client = None

        try:
            import boto3
            self._client = boto3.client(
                "bedrock-runtime", region_name=self.region,
            )
            self._client.meta.endpoint_url
            self.available = True
            logger.info(
                "Bedrock client ready (region=%s, model=%s)",
                self.region, self.model_id,
            )
        except Exception as e:
            logger.warning("Bedrock unavailable: %s", e)

    def explain(
        self,
        result: RecommendationResult,
        scenario: Scenario,
        impact: ImpactReport | None = None,
    ) -> ExplanationResult:
        if not self.available:
            return structured_fallback(result, scenario)

        try:
            user_prompt = self._build_explain_prompt(result, scenario, impact)
            response_text = self._invoke(
                system=_EXPLAIN_SYSTEM, user=user_prompt,
            )
            return ExplanationResult(text=response_text, source="bedrock")
        except Exception as e:
            logger.error("Bedrock explain failed: %s", e)
            return structured_fallback(result, scenario)

    def extract_scenario_from_text(self, user_text: str) -> dict:
        if not self.available:
            return {}

        try:
            response_text = self._invoke(
                system=_EXTRACT_SYSTEM,
                user=f"Workload description: {user_text}",
            )
            return json.loads(response_text)
        except Exception as e:
            logger.error("Bedrock extraction failed: %s", e)
            return {}

    def _invoke(self, system: str, user: str) -> str:
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": user}]}],
            "system": [{"text": system}],
            "inferenceConfig": {
                "maxTokens": 512,
                "temperature": 0.3,
            },
        })
        response = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]

    @staticmethod
    def _build_explain_prompt(
        result: RecommendationResult,
        scenario: Scenario,
        impact: ImpactReport | None,
    ) -> str:
        top_problems = result.detected_problems[:5]
        problem_lines = []
        for p in top_problems:
            if isinstance(p, dict):
                problem_lines.append(
                    f"  - {p['problem_id']} ({p['severity']}): {p.get('evidence', '')}"
                )

        top_recs = result.recommendations[:5]
        rec_lines = [
            f"  - {r.technique_id} [{r.priority}]: {r.rationale}"
            for r in top_recs
        ]

        parts = [
            "The system analysed this workload:",
            f"- Business domain: {scenario.business_domain}",
            f"- Scale: {scenario.expected_users:,} users, {scenario.daily_growth_gb} GB/day growth",
            f"- Data types: {scenario.data_types}",
            f"- Requirements: {scenario.latency_requirement_ms}ms latency, "
            f"{scenario.availability_requirement}% availability, "
            f"{scenario.retention_years} year retention",
            "",
            "It detected these architectural pressures:",
            *problem_lines,
            "",
            "It recommends this strategy (top 5):",
            *rec_lines,
        ]

        if impact:
            parts.extend([
                "",
                "Model-based impact estimates (synthetic — not production measurements):",
                f"- Storage: {impact.storage.current_storage_gb} GB → "
                f"{impact.storage.projected_storage_gb} GB "
                f"({impact.storage.estimated_reduction_pct:.1f}% reduction)",
                f"- Cost: ${impact.cost.estimated_monthly_baseline_usd} → "
                f"${impact.cost.estimated_monthly_optimized_usd}/mo "
                f"({impact.cost.estimated_savings_pct:.1f}% reduction)",
                f"- Latency: {impact.latency.current_effective_latency_ms}ms → "
                f"{impact.latency.estimated_optimized_latency_ms}ms",
            ])

        parts.extend([
            "",
            "In 3-4 sentences, explain the key architectural decisions and the most important "
            "trade-off the team should understand before implementing this architecture. "
            "Do not repeat the numbers — the user can see them. Focus on the reasoning.",
        ])

        return "\n".join(parts)
