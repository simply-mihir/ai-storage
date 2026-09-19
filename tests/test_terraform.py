"""Tests for the Terraform scaffold generator."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from storage_advisor.architecture.builder import ArchitectureComponent, ArchitectureOutput
from storage_advisor.domain.scenario import Scenario
from storage_advisor.export.terraform import TerraformGenerator


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
                required_by=["object_storage", "tiered_storage"],
                configuration_notes=["S3 Standard", "Intelligent-Tiering"],
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
                component_id="analytics_store",
                component_type="analytics_store",
                service="Amazon Redshift",
                workload_domain="analytics",
                required_by=["columnar_storage"],
                configuration_notes=["Columnar format"],
                priority="RECOMMENDED",
            ),
        ],
        summary="S3 + RDS + ElastiCache + Redshift",
    )


@pytest.fixture
def export():
    gen = TerraformGenerator()
    return gen.generate(_demo_scenario(), _demo_architecture())


class TestTerraformGenerator:
    def test_generates_three_files(self, export):
        assert "main.tf" in export.files
        assert "variables.tf" in export.files
        assert "outputs.tf" in export.files

    def test_main_tf_has_terraform_block(self, export):
        main = export.files["main.tf"]
        assert "terraform {" in main
        assert "required_version" in main
        assert "hashicorp/aws" in main

    def test_rds_component_generates_resource(self, export):
        main = export.files["main.tf"]
        assert "aws_db_instance" in main
        assert "aws_db_subnet_group" in main

    def test_s3_component_generates_resource(self, export):
        assert "aws_s3_bucket" in export.files["main.tf"]

    def test_cache_component_generates_resource(self, export):
        assert "aws_elasticache_replication_group" in export.files["main.tf"]

    def test_variables_has_required_vars(self, export):
        v = export.files["variables.tf"]
        assert 'variable "aws_region"' in v
        assert 'variable "vpc_id"' in v
        assert 'variable "private_subnet_ids"' in v

    def test_outputs_match_components(self, export):
        o = export.files["outputs.tf"]
        assert 'output "rds_endpoint"' in o
        assert 'output "s3_bucket_name"' in o
        assert 'output "elasticache_endpoint"' in o

    def test_zip_is_valid(self, export):
        zf = zipfile.ZipFile(io.BytesIO(export.zip_bytes))
        names = zf.namelist()
        assert any("main.tf" in n for n in names)
        assert any("variables.tf" in n for n in names)
        assert any("README.md" in n for n in names)

    def test_high_availability_sets_multi_az(self, export):
        assert "multi_az             = true" in export.files["main.tf"]

    def test_resource_count_is_positive(self, export):
        assert export.resource_count > 0
        assert export.component_count > 0


class TestTerraformAPI:
    def setup_method(self):
        from storage_advisor.app.api import app
        self.client = TestClient(app)

    def test_api_endpoint(self):
        scenario = _demo_scenario().model_dump()
        architecture = _demo_architecture().model_dump()
        resp = self.client.post(
            "/api/v1/export/terraform",
            json={"scenario": scenario, "architecture": architecture},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "main.tf" in data["files"]
        assert "variables.tf" in data["files"]
        assert "outputs.tf" in data["files"]
        assert data["resource_count"] > 0
