"""Tests for the Scenario domain model — validation, normalization, and edge cases."""

import pytest
from pydantic import ValidationError

from storage_advisor.domain.scenario import (
    AccessPattern,
    BusinessDomain,
    BudgetLevel,
    CompanySize,
    ComplianceType,
    DataType,
    Intensity,
    Scenario,
)


def _valid_scenario(**overrides) -> Scenario:
    """Helper that builds a valid scenario with optional overrides."""
    defaults = dict(
        business_domain="AI",
        company_size="STARTUP",
        expected_users=1000,
        concurrent_users=100,
        current_storage_gb=100.0,
        daily_growth_gb=1.0,
        data_types=["TEXT"],
        structured_data_pct=100.0,
        semi_structured_data_pct=0.0,
        unstructured_data_pct=0.0,
        read_intensity="MEDIUM",
        write_intensity="MEDIUM",
        access_pattern="MIXED",
        latency_requirement_ms=500.0,
        availability_requirement=99.0,
        rto_minutes=60.0,
        rpo_minutes=30.0,
        retention_years=1.0,
        budget_level="MEDIUM",
        analytics_required=False,
        real_time_processing_required=False,
        sensitive_data=False,
        encryption_required=False,
        compliance_requirements=["NONE"],
    )
    defaults.update(overrides)
    return Scenario(**defaults)


class TestValidScenarios:
    def test_baseline_scenario(self):
        s = _valid_scenario()
        assert s.business_domain == "AI"
        assert s.expected_users == 1000

    def test_zero_growth_is_valid(self):
        s = _valid_scenario(daily_growth_gb=0.0)
        assert s.daily_growth_gb == 0.0

    def test_boundary_availability_90(self):
        s = _valid_scenario(availability_requirement=90.0)
        assert s.availability_requirement == 90.0

    def test_boundary_availability_100(self):
        s = _valid_scenario(availability_requirement=100.0)
        assert s.availability_requirement == 100.0

    def test_zero_retention(self):
        s = _valid_scenario(retention_years=0.0)
        assert s.retention_years == 0.0

    def test_zero_rto_rpo(self):
        s = _valid_scenario(rto_minutes=0.0, rpo_minutes=0.0)
        assert s.rto_minutes == 0.0
        assert s.rpo_minutes == 0.0

    def test_concurrent_equals_expected(self):
        s = _valid_scenario(expected_users=100, concurrent_users=100)
        assert s.concurrent_users == 100

    def test_all_data_types(self):
        s = _valid_scenario(data_types=[dt.value for dt in DataType])
        assert len(s.data_types) == len(DataType)

    def test_multiple_compliance(self):
        s = _valid_scenario(compliance_requirements=["HIPAA", "GDPR", "SOC2", "PCI_DSS"])
        assert len(s.compliance_requirements) == 4


class TestCaseInsensitiveNormalization:
    def test_lowercase_enums(self):
        s = _valid_scenario(
            business_domain="ai",
            company_size="startup",
            read_intensity="high",
            write_intensity="low",
            access_pattern="mixed",
            budget_level="low",
        )
        assert s.business_domain == "AI"
        assert s.company_size == "STARTUP"
        assert s.read_intensity == "HIGH"

    def test_mixed_case_enums(self):
        s = _valid_scenario(business_domain="Healthcare", read_intensity="High")
        assert s.business_domain == "HEALTHCARE"
        assert s.read_intensity == "HIGH"

    def test_data_types_lowercase(self):
        s = _valid_scenario(data_types=["images", "transactions"])
        assert "IMAGES" in s.data_types
        assert "TRANSACTIONS" in s.data_types

    def test_compliance_lowercase(self):
        s = _valid_scenario(compliance_requirements=["hipaa", "gdpr"])
        assert "HIPAA" in s.compliance_requirements

    def test_domain_alias_ecommerce(self):
        for alias in ["e-commerce", "E-Commerce", "ecommerce", "ECOMMERCE"]:
            s = _valid_scenario(business_domain=alias)
            assert s.business_domain == "ECOMMERCE", f"Failed for '{alias}'"

    def test_domain_alias_fintech(self):
        s = _valid_scenario(business_domain="fin-tech")
        assert s.business_domain == "FINTECH"

    def test_domain_alias_telecom(self):
        s = _valid_scenario(business_domain="telecom")
        assert s.business_domain == "TELECOMMUNICATION"


class TestValidationErrors:
    def test_zero_users(self):
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            _valid_scenario(expected_users=0)

    def test_negative_users(self):
        with pytest.raises(ValidationError):
            _valid_scenario(expected_users=-1)

    def test_zero_concurrent_users(self):
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            _valid_scenario(concurrent_users=0)

    def test_concurrent_exceeds_expected(self):
        with pytest.raises(ValidationError, match="cannot exceed"):
            _valid_scenario(expected_users=100, concurrent_users=200)

    def test_zero_storage(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            _valid_scenario(current_storage_gb=0)

    def test_negative_storage(self):
        with pytest.raises(ValidationError):
            _valid_scenario(current_storage_gb=-100)

    def test_negative_growth(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            _valid_scenario(daily_growth_gb=-5)

    def test_percentage_over_100(self):
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            _valid_scenario(structured_data_pct=110)

    def test_negative_percentage(self):
        with pytest.raises(ValidationError):
            _valid_scenario(structured_data_pct=-10)

    def test_percentages_dont_sum_to_100(self):
        with pytest.raises(ValidationError, match="must sum to 100"):
            _valid_scenario(
                structured_data_pct=50,
                semi_structured_data_pct=30,
                unstructured_data_pct=10,  # sum = 90
            )

    def test_percentages_strict_tolerance(self):
        with pytest.raises(ValidationError, match="must sum to 100"):
            _valid_scenario(
                structured_data_pct=33.34,
                semi_structured_data_pct=33.33,
                unstructured_data_pct=33.31,  # sum = 99.98, diff > 0.01
            )

    def test_percentages_within_tolerance(self):
        s = _valid_scenario(
            structured_data_pct=33.34,
            semi_structured_data_pct=33.33,
            unstructured_data_pct=33.33,  # sum = 100.00
        )
        assert s is not None

    def test_empty_data_types(self):
        with pytest.raises(ValidationError):
            _valid_scenario(data_types=[])

    def test_zero_latency(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            _valid_scenario(latency_requirement_ms=0)

    def test_negative_latency(self):
        with pytest.raises(ValidationError):
            _valid_scenario(latency_requirement_ms=-10)

    def test_availability_below_90(self):
        with pytest.raises(ValidationError, match="greater than or equal to 90"):
            _valid_scenario(availability_requirement=89.9)

    def test_availability_above_100(self):
        with pytest.raises(ValidationError, match="less than or equal to 100"):
            _valid_scenario(availability_requirement=100.1)

    def test_negative_rto(self):
        with pytest.raises(ValidationError):
            _valid_scenario(rto_minutes=-1)

    def test_negative_rpo(self):
        with pytest.raises(ValidationError):
            _valid_scenario(rpo_minutes=-1)

    def test_negative_retention(self):
        with pytest.raises(ValidationError):
            _valid_scenario(retention_years=-1)

    def test_invalid_enum_value(self):
        with pytest.raises(ValidationError):
            _valid_scenario(business_domain="INVALID_DOMAIN")

    def test_invalid_data_type(self):
        with pytest.raises(ValidationError):
            _valid_scenario(data_types=["MAGIC_DATA"])


class TestJsonSerialization:
    def test_round_trip(self):
        s = _valid_scenario()
        json_str = s.model_dump_json()
        s2 = Scenario.model_validate_json(json_str)
        assert s.model_dump() == s2.model_dump()

    def test_enum_values_are_strings(self):
        s = _valid_scenario()
        data = s.model_dump()
        assert isinstance(data["business_domain"], str)
        assert data["business_domain"] == "AI"
