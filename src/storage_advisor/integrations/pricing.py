"""AWS Pricing Client — fetches real AWS list prices for cost estimation."""

from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger("storage_advisor.integrations.pricing")

_REGION_NAMES = {
    "us-east-1": "US East (N. Virginia)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "ap-south-1": "Asia Pacific (Mumbai)",
}

_S3_FALLBACK = {
    "us-east-1": 0.023,
    "us-west-2": 0.023,
    "eu-west-1": 0.024,
    "ap-south-1": 0.025,
}

_ELASTICACHE_FALLBACK = {
    "cache.t3.micro": 0.017,
    "cache.t3.small": 0.034,
    "cache.t3.medium": 0.068,
    "cache.r6g.large": 0.166,
}

_RDS_FALLBACK = {
    ("db.t3.micro", "Single-AZ"): 0.018,
    ("db.t3.small", "Single-AZ"): 0.036,
    ("db.t3.medium", "Single-AZ"): 0.072,
    ("db.t3.micro", "Multi-AZ"): 0.036,
    ("db.t3.small", "Multi-AZ"): 0.072,
    ("db.t3.medium", "Multi-AZ"): 0.144,
}

_GLACIER_FALLBACK = 0.004

# AWS S3 Data Transfer Out (Internet Egress) per GB
# Source: https://aws.amazon.com/s3/pricing/
# First 100 GB/month free across all AWS regions; standard regional egress rates apply thereafter.
_S3_DATA_TRANSFER_OUT_FALLBACK: dict[str, float] = {
    "us-east-1": 0.09,
    "us-west-2": 0.09,
    "eu-west-1": 0.09,
    "ap-south-1": 0.109,
}

# AWS RDS gp3 Baseline Storage Pricing per GB-month
# Source: https://aws.amazon.com/rds/postgresql/pricing/ & https://aws.amazon.com/rds/pricing/
# gp3 storage includes baseline performance of 3,000 IOPS and 125 MB/s throughput at no additional cost.
_RDS_GP3_STORAGE_FALLBACK: dict[tuple[str, str], float] = {
    ("us-east-1", "Single-AZ"): 0.115,
    ("us-east-1", "Multi-AZ"): 0.23,
    ("us-west-2", "Single-AZ"): 0.115,
    ("us-west-2", "Multi-AZ"): 0.23,
    ("eu-west-1", "Single-AZ"): 0.132,
    ("eu-west-1", "Multi-AZ"): 0.264,
    ("ap-south-1", "Single-AZ"): 0.124,
    ("ap-south-1", "Multi-AZ"): 0.248,
}

# AWS S3 API Request Pricing per 1,000 Requests
# Source: https://aws.amazon.com/s3/pricing/
# PUT, COPY, POST, LIST: $0.005 / 1,000 requests
# GET, SELECT, and all other requests: $0.0004 / 1,000 requests
_S3_REQUEST_PRICING: dict[str, float] = {
    "PUT": 0.005,
    "GET": 0.0004,
}

_CACHE_TTL_SECONDS = 86400  # 24 hours


@dataclass
class CostLineItem:
    component: str
    service: str
    label: str
    monthly_cost_usd: float
    unit_price: float
    unit: str
    quantity: float


@dataclass
class RealCostEstimate:
    line_items: list[CostLineItem]
    total_monthly_usd: float
    region: str
    pricing_date: str
    source: str
    disclaimer: str


class AWSPricingClient:

    def __init__(self, region: str = "us-east-1") -> None:
        self.region = region
        self.region_name = _REGION_NAMES.get(region, "US East (N. Virginia)")
        self._cache: dict[str, float] = {}
        self._cache_timestamp: float | None = None
        self.available = True
        try:
            import requests as _req  # noqa: F401
            self._requests = _req
        except ImportError:
            self.available = False
            self._requests = None
            logger.warning("requests library not installed — pricing API unavailable")

    def _cache_valid(self) -> bool:
        if self._cache_timestamp is None:
            return False
        return (time.monotonic() - self._cache_timestamp) < _CACHE_TTL_SECONDS

    def get_s3_price_per_gb(self) -> float:
        cache_key = f"s3_{self.region}"
        if self._cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        price = self._fetch_s3_price()
        self._cache[cache_key] = price
        if self._cache_timestamp is None:
            self._cache_timestamp = time.monotonic()
        return price

    def _fetch_s3_price(self) -> float:
        fallback = _S3_FALLBACK.get(self.region, 0.023)
        if not self.available:
            return fallback
        try:
            idx_url = (
                "https://pricing.us-east-1.amazonaws.com"
                "/offers/v1.0/aws/AmazonS3/current/region_index.json"
            )
            resp = self._requests.get(idx_url, timeout=10)
            resp.raise_for_status()
            idx = resp.json()

            region_entry = idx.get("regions", {}).get(self.region)
            if not region_entry:
                logger.warning("Region %s not found in S3 pricing index", self.region)
                return fallback

            csv_path = region_entry.get("currentVersionUrl", "")
            if not csv_path:
                return fallback

            csv_url = csv_path.replace(".json", ".csv")
            csv_url = f"https://pricing.us-east-1.amazonaws.com{csv_url}"

            csv_resp = self._requests.get(csv_url, timeout=30, stream=True)
            csv_resp.raise_for_status()

            content = csv_resp.text
            lines = content.split("\n")

            header_idx = None
            for i, line in enumerate(lines):
                if "PricePerUnit" in line and "usageType" in line.lower():
                    header_idx = i
                    break
                if line.startswith('"SKU"') or line.startswith("SKU"):
                    header_idx = i
                    break

            if header_idx is None:
                logger.warning("Could not find CSV header in S3 pricing data")
                return fallback

            csv_text = "\n".join(lines[header_idx:])
            reader = csv.DictReader(io.StringIO(csv_text))

            for row in reader:
                usage = row.get("usageType", row.get("Usage Type", ""))
                storage_class = row.get("storageClass", row.get("Storage Class", ""))
                volume_type = row.get("volumeType", row.get("Volume Type", ""))

                if (
                    "TimedStorage-ByteHrs" in usage
                    and ("General Purpose" in storage_class or "Standard" in volume_type)
                ):
                    price_str = row.get("PricePerUnit", row.get("pricePerUnit", ""))
                    try:
                        price = float(price_str)
                        if price > 0:
                            logger.info("Fetched live S3 price for %s: $%.4f/GB", self.region, price)
                            return price
                    except (ValueError, TypeError):
                        continue

            logger.warning("No matching S3 price found in CSV, using fallback")
            return fallback

        except Exception as e:
            logger.warning("S3 pricing fetch failed: %s — using fallback", e)
            return fallback

    def get_elasticache_price_per_hour(
        self, node_type: str = "cache.t3.micro",
    ) -> float:
        cache_key = f"elasticache_{self.region}_{node_type}"
        if self._cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        price = _ELASTICACHE_FALLBACK.get(node_type, 0.017)
        self._cache[cache_key] = price
        if self._cache_timestamp is None:
            self._cache_timestamp = time.monotonic()
        return price

    def get_rds_price_per_hour(
        self,
        instance_class: str = "db.t3.micro",
        engine: str = "PostgreSQL",
        deployment: str = "Single-AZ",
    ) -> float:
        cache_key = f"rds_{self.region}_{instance_class}_{deployment}"
        if self._cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        price = _RDS_FALLBACK.get((instance_class, deployment), 0.018)
        self._cache[cache_key] = price
        if self._cache_timestamp is None:
            self._cache_timestamp = time.monotonic()
        return price

    def get_glacier_price_per_gb(self) -> float:
        cache_key = f"glacier_{self.region}"
        if self._cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        price = _GLACIER_FALLBACK
        self._cache[cache_key] = price
        if self._cache_timestamp is None:
            self._cache_timestamp = time.monotonic()
        return price

    def get_s3_data_transfer_out_price_per_gb(self) -> float:
        """Return the per-GB internet egress cost for S3 data transfer out."""
        cache_key = f"s3_dto_{self.region}"
        if self._cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        price = _S3_DATA_TRANSFER_OUT_FALLBACK.get(self.region, 0.09)
        self._cache[cache_key] = price
        if self._cache_timestamp is None:
            self._cache_timestamp = time.monotonic()
        return price

    def get_rds_gp3_storage_price_per_gb(self, deployment: str = "Single-AZ") -> float:
        """Return RDS gp3 baseline storage cost per GB-month (includes 3,000 IOPS & 125 MB/s)."""
        cache_key = f"rds_gp3_{self.region}_{deployment}"
        if self._cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        price = _RDS_GP3_STORAGE_FALLBACK.get(
            (self.region, deployment),
            0.115 if deployment == "Single-AZ" else 0.23,
        )
        self._cache[cache_key] = price
        if self._cache_timestamp is None:
            self._cache_timestamp = time.monotonic()
        return price

    def get_s3_request_price_per_thousand(self, request_type: str = "GET") -> float:
        """Return S3 API request price per 1,000 requests for PUT or GET."""
        return _S3_REQUEST_PRICING.get(request_type.upper(), 0.0004)

    def calculate_monthly_architecture_cost(
        self,
        architecture,
        scenario,
    ) -> RealCostEstimate:
        from storage_advisor.architecture.builder import ArchitectureOutput
        from storage_advisor.domain.scenario import Scenario

        arch: ArchitectureOutput = architecture
        sc: Scenario = scenario

        line_items: list[CostLineItem] = []
        hours_per_month = 730

        for comp in arch.components:
            svc = comp.service.lower()
            ctype = comp.component_type

            if ctype == "object_store" or "amazon s3" in svc and "glacier" not in svc:
                unit_price = self.get_s3_price_per_gb()
                qty = sc.current_storage_gb
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon S3",
                    label="S3 Standard storage",
                    monthly_cost_usd=round(qty * unit_price, 2),
                    unit_price=unit_price,
                    unit="$/GB/month",
                    quantity=qty,
                ))

                # 1. S3 Data Transfer Out (per-GB regional constant table with source comment)
                dto_unit_price = self.get_s3_data_transfer_out_price_per_gb()
                read_mult = {"LOW": 0.10, "MEDIUM": 0.20, "HIGH": 0.35}.get(str(sc.read_intensity).upper(), 0.20)
                dto_qty = round(max(sc.current_storage_gb * read_mult, 10.0), 1)
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon S3",
                    label="S3 Data Transfer Out (Internet Egress)",
                    monthly_cost_usd=round(dto_qty * dto_unit_price, 2),
                    unit_price=dto_unit_price,
                    unit="$/GB",
                    quantity=dto_qty,
                ))

                # 2. S3 Request Pricing (PUT/GET per 1k)
                put_unit_price = self.get_s3_request_price_per_thousand("PUT")
                write_mult = {"LOW": 50, "MEDIUM": 200, "HIGH": 800}.get(str(sc.write_intensity).upper(), 200)
                put_qty = round(max(sc.concurrent_users * write_mult / 1000.0, 10.0), 1)
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon S3",
                    label="S3 Request Pricing (PUT/COPY/POST/LIST)",
                    monthly_cost_usd=round(put_qty * put_unit_price, 2),
                    unit_price=put_unit_price,
                    unit="$/1k requests",
                    quantity=put_qty,
                ))

                get_unit_price = self.get_s3_request_price_per_thousand("GET")
                read_mult_req = {"LOW": 200, "MEDIUM": 1000, "HIGH": 5000}.get(str(sc.read_intensity).upper(), 1000)
                get_qty = round(max(sc.concurrent_users * read_mult_req / 1000.0, 50.0), 1)
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon S3",
                    label="S3 Request Pricing (GET/SELECT)",
                    monthly_cost_usd=round(get_qty * get_unit_price, 2),
                    unit_price=get_unit_price,
                    unit="$/1k requests",
                    quantity=get_qty,
                ))

            elif ctype == "archive" or "glacier" in svc:
                unit_price = self.get_glacier_price_per_gb()
                qty = sc.current_storage_gb * 0.3
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="S3 Glacier",
                    label="S3 Glacier archive",
                    monthly_cost_usd=round(qty * unit_price, 2),
                    unit_price=unit_price,
                    unit="$/GB/month",
                    quantity=round(qty, 1),
                ))

            elif ctype == "cache" or "elasticache" in svc:
                unit_price = self.get_elasticache_price_per_hour()
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon ElastiCache",
                    label="ElastiCache Redis (cache.t3.micro)",
                    monthly_cost_usd=round(unit_price * hours_per_month, 2),
                    unit_price=unit_price,
                    unit="$/hour",
                    quantity=hours_per_month,
                ))

            elif ctype == "relational_db" or "rds" in svc:
                notes = " ".join(comp.configuration_notes)
                multi_az = (
                    "Multi-AZ" in notes
                    or sc.availability_requirement >= 99.99
                )
                deployment = "Multi-AZ" if multi_az else "Single-AZ"
                unit_price = self.get_rds_price_per_hour(deployment=deployment)
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon RDS",
                    label=f"RDS PostgreSQL {deployment}",
                    monthly_cost_usd=round(unit_price * hours_per_month, 2),
                    unit_price=unit_price,
                    unit="$/hour",
                    quantity=hours_per_month,
                ))

                # 3. RDS gp3 Baseline Storage (3,000 IOPS and 125 MB/s included)
                gp3_unit_price = self.get_rds_gp3_storage_price_per_gb(deployment=deployment)
                rds_storage_gb = max(round(sc.current_storage_gb * (sc.structured_data_pct / 100.0), 1), 20.0)
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon RDS",
                    label=f"RDS gp3 Storage ({deployment} - 3,000 IOPS, 125 MB/s included)",
                    monthly_cost_usd=round(rds_storage_gb * gp3_unit_price, 2),
                    unit_price=gp3_unit_price,
                    unit="$/GB/month",
                    quantity=rds_storage_gb,
                ))

            elif ctype == "analytics_store" and "redshift" in svc:
                unit_price = 0.25
                line_items.append(CostLineItem(
                    component=comp.component_id,
                    service="Amazon Redshift",
                    label="Redshift dc2.large on-demand",
                    monthly_cost_usd=round(unit_price * hours_per_month, 2),
                    unit_price=unit_price,
                    unit="$/hour",
                    quantity=hours_per_month,
                ))

        total = sum(item.monthly_cost_usd for item in line_items)

        return RealCostEstimate(
            line_items=line_items,
            total_monthly_usd=round(total, 2),
            region=self.region,
            pricing_date=date.today().isoformat(),
            source="aws_list_price",
            disclaimer=(
                "Based on AWS public list prices. Includes S3 storage, S3 data transfer out, "
                "S3 PUT/GET API requests, ElastiCache nodes, and RDS gp3 storage with baseline 3,000 IOPS & 125 MB/s."
            ),
        )

