"""Tests for the Architecture Builder — technique-to-service mapping."""

from storage_advisor.architecture.builder import ArchitectureBuilder
from storage_advisor.domain.scenario import Scenario
from storage_advisor.recommendation.recommendation_engine import run_recommendation_engine


def _scenario(**overrides) -> Scenario:
    defaults = dict(
        business_domain="AI", company_size="STARTUP",
        expected_users=1000, concurrent_users=100,
        current_storage_gb=100.0, daily_growth_gb=1.0,
        data_types=["TEXT"],
        structured_data_pct=100.0, semi_structured_data_pct=0.0, unstructured_data_pct=0.0,
        read_intensity="LOW", write_intensity="LOW", access_pattern="MIXED",
        latency_requirement_ms=1000.0, availability_requirement=95.0,
        rto_minutes=480.0, rpo_minutes=240.0,
        retention_years=0.5, budget_level="MEDIUM",
        analytics_required=False, real_time_processing_required=False,
        sensitive_data=False, encryption_required=False,
        compliance_requirements=["NONE"],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


class TestDemoScenario:
    """Test 1: Demo scenario (10M users, 300 GB/day) produces S3, RDS, ElastiCache."""

    def test_demo_produces_s3_rds_elasticache(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
            structured_data_pct=20, semi_structured_data_pct=20, unstructured_data_pct=60,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            rto_minutes=60, rpo_minutes=15,
            retention_years=7, analytics_required=True,
            real_time_processing_required=True,
            sensitive_data=True, encryption_required=True,
        )
        result = run_recommendation_engine(s)
        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        services = {c.service for c in arch.components}
        component_types = {c.component_type for c in arch.components}

        assert "object_store" in component_types
        assert "relational_db" in component_types
        assert "cache" in component_types

        assert any("S3" in svc for svc in services)
        assert any("RDS" in svc for svc in services)
        assert any("ElastiCache" in svc for svc in services)

        assert arch.summary != ""
        assert len(arch.components) >= 3


class TestHIPAACompliance:
    """Test 2: HIPAA compliance forces ElastiCache service name."""

    def test_hipaa_forces_elasticache(self):
        s = _scenario(
            expected_users=100_000, concurrent_users=5_000,
            current_storage_gb=5_000, daily_growth_gb=50,
            data_types=["TRANSACTIONS", "DOCUMENTS"],
            structured_data_pct=70, semi_structured_data_pct=20, unstructured_data_pct=10,
            read_intensity="HIGH", write_intensity="MEDIUM",
            latency_requirement_ms=50, availability_requirement=99.9,
            rto_minutes=30, rpo_minutes=15,
            retention_years=7, budget_level="HIGH",
            sensitive_data=True, encryption_required=True,
            compliance_requirements=["HIPAA"],
        )
        result = run_recommendation_engine(s)
        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        cache_components = [c for c in arch.components if c.component_type == "cache"]
        assert len(cache_components) == 1

        cache = cache_components[0]
        assert "ElastiCache" in cache.service
        assert any("HIPAA" in note for note in cache.configuration_notes)


class TestConfigNoteOnly:
    """Test 3: Config-note-only techniques produce notes, not new components."""

    def test_indexing_compression_add_notes_not_components(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS", "LOGS"],
            structured_data_pct=20, semi_structured_data_pct=20, unstructured_data_pct=60,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            rto_minutes=60, rpo_minutes=15,
            retention_years=7, analytics_required=True,
        )
        result = run_recommendation_engine(s)
        rec_ids = {r.technique_id for r in result.recommendations}
        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        component_ids = [c.component_id for c in arch.components]
        assert "indexing" not in component_ids
        assert "compression" not in component_ids

        if "indexing" in rec_ids:
            rds = [c for c in arch.components if c.component_type == "relational_db"]
            assert len(rds) == 1
            assert "indexing" in rds[0].required_by
            assert any("index" in note.lower() for note in rds[0].configuration_notes)

        if "compression" in rec_ids:
            primary = [c for c in arch.components if c.component_type in ("object_store", "relational_db")]
            assert len(primary) >= 1
            all_required_by = []
            for p in primary:
                all_required_by.extend(p.required_by)
            assert "compression" in all_required_by


class TestComponentMerging:
    """Test 4: object_storage + tiered_storage + lifecycle_management → 1 S3 component."""

    def test_s3_techniques_merge_into_one_component(self):
        s = _scenario(
            expected_users=1_000_000, concurrent_users=50_000,
            current_storage_gb=10_000, daily_growth_gb=200,
            data_types=["IMAGES", "DOCUMENTS", "VIDEOS", "LOGS"],
            structured_data_pct=10, semi_structured_data_pct=20, unstructured_data_pct=70,
            read_intensity="MEDIUM", write_intensity="HIGH",
            latency_requirement_ms=200, availability_requirement=99.9,
            rto_minutes=60, rpo_minutes=30,
            retention_years=5, budget_level="MEDIUM",
        )
        result = run_recommendation_engine(s)
        rec_ids = {r.technique_id for r in result.recommendations}
        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        s3_components = [c for c in arch.components if c.component_type == "object_store"]
        assert len(s3_components) == 1, (
            f"Expected exactly 1 S3 component, got {len(s3_components)}"
        )

        s3 = s3_components[0]
        assert "Amazon S3" in s3.service

        s3_techniques = {"object_storage", "tiered_storage", "lifecycle_management"}
        present = s3_techniques & rec_ids
        for tid in present:
            assert tid in s3.required_by, f"{tid} should be in required_by"


class TestRedshiftOverride:
    """Users > 5M with columnar_storage should use Redshift instead of DuckDB."""

    def test_large_scale_uses_redshift(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["TRANSACTIONS", "LOGS"],
            structured_data_pct=60, semi_structured_data_pct=30, unstructured_data_pct=10,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=100, availability_requirement=99.99,
            rto_minutes=60, rpo_minutes=15,
            retention_years=5, analytics_required=True,
        )
        result = run_recommendation_engine(s)
        rec_ids = {r.technique_id for r in result.recommendations}

        if "columnar_storage" not in rec_ids:
            return

        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        analytics = [c for c in arch.components if c.component_type == "analytics_store"]
        assert len(analytics) == 1
        assert "Redshift" in analytics[0].service


class TestPriorityPropagation:
    """Component priority reflects the highest priority of its required_by techniques."""

    def test_required_technique_makes_component_required(self):
        s = _scenario(
            expected_users=10_000_000, concurrent_users=100_000,
            current_storage_gb=25_000, daily_growth_gb=300,
            data_types=["IMAGES", "DOCUMENTS", "TRANSACTIONS"],
            structured_data_pct=20, semi_structured_data_pct=20, unstructured_data_pct=60,
            read_intensity="HIGH", write_intensity="HIGH",
            latency_requirement_ms=50, availability_requirement=99.99,
            rto_minutes=15, rpo_minutes=5,
            retention_years=7,
        )
        result = run_recommendation_engine(s)
        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        rec_map = {r.technique_id: r.priority for r in result.recommendations}
        for comp in arch.components:
            has_required = any(
                rec_map.get(tid) == "REQUIRED" for tid in comp.required_by
            )
            if has_required:
                assert comp.priority == "REQUIRED", (
                    f"{comp.component_id} should be REQUIRED"
                )


class TestEmptyArchitecture:
    """Minimal scenario with no problems should produce empty or minimal architecture."""

    def test_baseline_produces_summary(self):
        s = _scenario()
        result = run_recommendation_engine(s)
        builder = ArchitectureBuilder()
        arch = builder.build(s, result)

        assert isinstance(arch.summary, str)
        assert isinstance(arch.components, list)
