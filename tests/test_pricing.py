"""Tests for AWS pricing integration."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from storage_advisor.architecture.builder import ArchitectureComponent, ArchitectureOutput
from storage_advisor.domain.scenario import Scenario
from storage_advisor.integrations.pricing import AWSPricingClient


def _demo_scenario() -> Scenario:
    return Scenario(
        business_domain="E_COMMERCE",
        company_size="LARGE",
        expected_users=10_000_000,
        concurrent_users=500_000,
        current_storage_gb=5000,
        daily_growth_gb=300,
        data_types=["IMAGES", "TRANSACTIONS"],
        structured_data_pct=40,
        semi_structured_data_pct=10,
        unstructured_data_pct=50,
        read_intensity="HIGH",
        write_intensity="HIGH",
        access_pattern="MIXED",
        latency_requirement_ms=100,
        availability_requirement=99.99,
        rto_minutes=15,
        rpo_minutes=5,
        retention_years=7,
        budget_level="HIGH",
        analytics_required=True,
        real_time_processing_required=True,
        sensitive_data=True,
        encryption_required=True,
        compliance_requirements=["SOC2", "PCI_DSS"],
    )


def _demo_architecture() -> ArchitectureOutput:
    return ArchitectureOutput(
        components=[
            ArchitectureComponent(
                component_id="s3_object_store",
                component_type="object_store",
                service="Amazon S3",
                workload_domain="object",
                required_by=["object_storage"],
                configuration_notes=["S3 Standard"],
                priority="RECOMMENDED",
            ),
            ArchitectureComponent(
                component_id="elasticache_redis",
                component_type="cache",
                service="Amazon ElastiCache (Redis)",
                workload_domain="cache",
                required_by=["caching"],
                configuration_notes=["TTL strategy"],
                priority="RECOMMENDED",
            ),
            ArchitectureComponent(
                component_id="rds_postgresql",
                component_type="relational_db",
                service="Amazon RDS for PostgreSQL",
                workload_domain="transactional",
                required_by=["partitioning", "replication"],
                configuration_notes=["Multi-AZ deployment"],
                priority="REQUIRED",
            ),
        ],
        summary="S3 + ElastiCache + RDS",
    )


class TestFallbackPrices:
    def test_s3_price_in_range(self):
        pricing = AWSPricingClient()
        assert 0.01 < pricing.get_s3_price_per_gb() < 0.10

    def test_elasticache_price_in_range(self):
        pricing = AWSPricingClient()
        assert 0.01 < pricing.get_elasticache_price_per_hour() < 1.00

    def test_rds_price_in_range(self):
        pricing = AWSPricingClient()
        assert 0.01 < pricing.get_rds_price_per_hour() < 1.00

    def test_glacier_price_in_range(self):
        pricing = AWSPricingClient()
        assert 0.001 < pricing.get_glacier_price_per_gb() < 0.05


class TestMonthlyCostCalculation:
    def test_total_is_positive(self):
        pricing = AWSPricingClient()
        result = pricing.calculate_monthly_architecture_cost(
            _demo_architecture(), _demo_scenario(),
        )
        assert result.total_monthly_usd > 0

    def test_line_item_count(self):
        pricing = AWSPricingClient()
        result = pricing.calculate_monthly_architecture_cost(
            _demo_architecture(), _demo_scenario(),
        )
        assert len(result.line_items) == 7
        labels = [item.label for item in result.line_items]
        assert any("Data Transfer Out" in lbl for lbl in labels)
        assert any("gp3 Storage" in lbl for lbl in labels)
        assert any("PUT" in lbl for lbl in labels)
        assert any("GET" in lbl for lbl in labels)

    def test_source_field(self):
        pricing = AWSPricingClient()
        result = pricing.calculate_monthly_architecture_cost(
            _demo_architecture(), _demo_scenario(),
        )
        assert result.source in ("aws_list_price", "fallback")

    def test_disclaimer_nonempty(self):
        pricing = AWSPricingClient()
        result = pricing.calculate_monthly_architecture_cost(
            _demo_architecture(), _demo_scenario(),
        )
        assert len(result.disclaimer) > 20
        assert "3,000 IOPS" in result.disclaimer

    def test_new_pricing_getters(self):
        pricing = AWSPricingClient()
        assert pricing.get_s3_data_transfer_out_price_per_gb() > 0
        assert pricing.get_rds_gp3_storage_price_per_gb("Single-AZ") > 0
        assert pricing.get_rds_gp3_storage_price_per_gb("Multi-AZ") > pricing.get_rds_gp3_storage_price_per_gb("Single-AZ")
        assert pricing.get_s3_request_price_per_thousand("PUT") == 0.005
        assert pricing.get_s3_request_price_per_thousand("GET") == 0.0004

    def test_storage_heavy_scenario_line_items(self):
        storage_heavy = Scenario(
            business_domain="AI",
            company_size="ENTERPRISE",
            expected_users=20_000_000,
            concurrent_users=1_000_000,
            current_storage_gb=100_000,
            daily_growth_gb=2_000,
            data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
            structured_data_pct=25,
            semi_structured_data_pct=25,
            unstructured_data_pct=50,
            read_intensity="HIGH",
            write_intensity="HIGH",
            access_pattern="MIXED",
            latency_requirement_ms=50,
            availability_requirement=99.99,
            rto_minutes=15,
            rpo_minutes=5,
            retention_years=7,
            budget_level="HIGH",
            analytics_required=True,
            real_time_processing_required=True,
            sensitive_data=True,
            encryption_required=True,
            compliance_requirements=["SOC2"],
        )
        pricing = AWSPricingClient(region="us-east-1")
        result = pricing.calculate_monthly_architecture_cost(_demo_architecture(), storage_heavy)

        # 1. S3 Data Transfer Out
        dto = next((item for item in result.line_items if "Data Transfer Out" in item.label), None)
        assert dto is not None
        assert dto.service == "Amazon S3"
        assert dto.unit == "$/GB"
        assert dto.unit_price == 0.09
        assert dto.quantity > 10_000
        assert dto.monthly_cost_usd > 0

        # 2. RDS gp3 baseline IOPS/throughput
        gp3 = next((item for item in result.line_items if "gp3 Storage" in item.label), None)
        assert gp3 is not None
        assert gp3.service == "Amazon RDS"
        assert "3,000 IOPS" in gp3.label
        assert "125 MB/s" in gp3.label
        assert gp3.monthly_cost_usd > 0
        assert gp3.quantity >= 20.0

        # 3. S3 Request Pricing PUT and GET
        put_item = next((item for item in result.line_items if "PUT" in item.label), None)
        assert put_item is not None
        assert put_item.unit_price == 0.005
        assert put_item.monthly_cost_usd > 0

        get_item = next((item for item in result.line_items if "GET" in item.label), None)
        assert get_item is not None
        assert get_item.unit_price == 0.0004
        assert get_item.monthly_cost_usd > 0


class TestRegionPricing:
    def test_region_affects_price(self):
        us_east = AWSPricingClient(region="us-east-1")
        ap_south = AWSPricingClient(region="ap-south-1")
        assert us_east.get_s3_price_per_gb() <= ap_south.get_s3_price_per_gb()
        assert us_east.get_s3_data_transfer_out_price_per_gb() <= ap_south.get_s3_data_transfer_out_price_per_gb()


class TestPricingAPI:
    def setup_method(self):
        from storage_advisor.app.api import app
        self.client = TestClient(app)

    def test_pricing_endpoint(self):
        resp = self.client.get("/api/v1/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "s3_per_gb" in data
        assert "s3_data_transfer_out_per_gb" in data
        assert "s3_request_put_per_1k" in data
        assert "s3_request_get_per_1k" in data
        assert "rds_gp3_storage_single_az_per_gb" in data
        assert "rds_gp3_storage_multi_az_per_gb" in data
        assert "elasticache_per_hour" in data
        assert "rds_per_hour" in data
        assert "glacier_per_gb" in data

    def test_real_cost_endpoint(self):
        scenario = _demo_scenario().model_dump()
        resp = self.client.post(
            "/api/v1/real-cost",
            json={"scenario": scenario},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_monthly_usd"] > 0
        assert len(data["line_items"]) >= 6

