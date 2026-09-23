"""Terraform scaffold generator — produces downloadable .tf files from architecture."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date

from jinja2 import Environment, BaseLoader

from storage_advisor.architecture.builder import ArchitectureComponent, ArchitectureOutput
from storage_advisor.domain.scenario import Scenario


@dataclass
class TerraformExport:
    files: dict[str, str]
    zip_bytes: bytes
    component_count: int
    resource_count: int
    summary: str


_MAIN_HEADER = """\
# ============================================================
# AI Data Architect — Generated Terraform Scaffold
# Generated: {{ generated_date }}
# Scenario:  {{ domain }} | {{ users }} users
# WARNING:   Review all values before applying to production.
#            This scaffold requires a configured VPC and subnets.
# ============================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}
"""

_RDS_TEMPLATE = """\

# ── RELATIONAL DATABASE ──────────────────────────────
# Required by: {{ required_by }}
# Configuration: {{ config_notes }}
# ─────────────────────────────────────────────────────

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name        = "${var.project_name}-db-subnet"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-postgres"
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = var.rds_instance_class

  db_name  = var.database_name
  username = var.database_username
  password = var.database_password

  db_subnet_group_name = aws_db_subnet_group.main.name
  multi_az             = {{ multi_az }}

  allocated_storage     = {{ allocated_storage }}
  max_allocated_storage = {{ max_allocated_storage }}
  storage_type          = "gp3"
  storage_encrypted     = true

  backup_retention_period = {{ backup_retention }}
  deletion_protection     = true

  tags = {
    Name        = "${var.project_name}-postgres"
    Environment = var.environment
    Project     = var.project_name
  }
}
"""

_S3_TEMPLATE = """\

# ── OBJECT STORAGE ───────────────────────────────────
# Required by: {{ required_by }}
# Configuration: {{ config_notes }}
# ─────────────────────────────────────────────────────

resource "aws_s3_bucket" "main" {
  bucket = "${var.project_name}-data-${data.aws_availability_zones.available.id}"

  tags = {
    Name        = "${var.project_name}-data"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket_versioning" "main" {
  bucket = aws_s3_bucket.main.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}
{% if lifecycle_enabled %}

resource "aws_s3_bucket_lifecycle_configuration" "main" {
  bucket = aws_s3_bucket.main.id

  rule {
    id     = "tiered-storage"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
{% if archive_enabled %}

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
{% endif %}
{% if expiration_days > 0 %}

    expiration {
      days = {{ expiration_days }}
    }
{% endif %}
  }
}
{% endif %}
"""

_CACHE_TEMPLATE = """\

# ── CACHE ────────────────────────────────────────────
# Required by: {{ required_by }}
# Configuration: {{ config_notes }}
# ─────────────────────────────────────────────────────

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-cache-subnet"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.project_name}-redis"
  description          = "Redis cache for ${var.project_name}"

  node_type            = var.elasticache_node_type
  num_cache_clusters   = {{ num_clusters }}
  engine               = "redis"
  engine_version       = "7.0"

  subnet_group_name          = aws_elasticache_subnet_group.main.name
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = {
    Name        = "${var.project_name}-redis"
    Environment = var.environment
    Project     = var.project_name
  }
}
"""

_ARCHIVE_TEMPLATE = """\

# ── ARCHIVE STORAGE ──────────────────────────────────
# Required by: {{ required_by }}
# Configuration: {{ config_notes }}
# ─────────────────────────────────────────────────────

resource "aws_s3_bucket" "archive" {
  bucket = "${var.project_name}-archive-${data.aws_availability_zones.available.id}"

  tags = {
    Name        = "${var.project_name}-archive"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "archive" {
  bucket = aws_s3_bucket.archive.id

  rule {
    id     = "archive-tiering"
    status = "Enabled"

    transition {
      days          = 0
      storage_class = "GLACIER_IR"
    }

    transition {
      days          = 180
      storage_class = "DEEP_ARCHIVE"
    }
  }
}
"""

_REDSHIFT_TEMPLATE = """\

# ── ANALYTICS ────────────────────────────────────────
# Required by: {{ required_by }}
# Configuration: {{ config_notes }}
# ─────────────────────────────────────────────────────

resource "aws_redshift_cluster" "analytics" {
  cluster_identifier = "${var.project_name}-analytics"
  node_type          = "dc2.large"
  number_of_nodes    = 2

  database_name   = "analytics"
  master_username = var.redshift_username
  master_password = var.redshift_password

  encrypted = true

  tags = {
    Name        = "${var.project_name}-analytics"
    Environment = var.environment
    Project     = var.project_name
  }
}
"""

_VARIABLES_BASE = """\
variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming and tagging"
  type        = string
  default     = "{{ project_name }}"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "vpc_id" {
  description = "VPC ID where resources will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for database and cache resources"
  type        = list(string)
}
"""

_VARIABLES_RDS = """\

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "database_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "app"
}

variable "database_username" {
  description = "PostgreSQL master username"
  type        = string
  default     = "dbadmin"
}

variable "database_password" {
  description = "PostgreSQL master password"
  type        = string
  sensitive   = true
}
"""

_VARIABLES_CACHE = """\

variable "elasticache_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}
"""

_VARIABLES_REDSHIFT = """\

variable "redshift_username" {
  description = "Redshift master username"
  type        = string
  default     = "admin"
}

variable "redshift_password" {
  description = "Redshift master password"
  type        = string
  sensitive   = true
}
"""


class TerraformGenerator:

    def __init__(self) -> None:
        self._env = Environment(loader=BaseLoader(), keep_trailing_newline=True)

    def generate(
        self,
        scenario: Scenario,
        architecture: ArchitectureOutput,
    ) -> TerraformExport:
        comp_map: dict[str, ArchitectureComponent] = {}
        for c in architecture.components:
            comp_map.setdefault(c.component_type, c)

        main_tf = self._build_main(scenario, comp_map)
        variables_tf = self._build_variables(scenario, comp_map)
        outputs_tf = self._build_outputs(comp_map)

        resource_count = sum(
            main_tf.count(f"resource \"{rtype}\"")
            for rtype in [
                "aws_db_subnet_group", "aws_db_instance",
                "aws_s3_bucket", "aws_s3_bucket_versioning",
                "aws_s3_bucket_server_side_encryption_configuration",
                "aws_s3_bucket_lifecycle_configuration",
                "aws_elasticache_subnet_group",
                "aws_elasticache_replication_group",
                "aws_redshift_cluster",
            ]
        )

        files = {
            "main.tf": main_tf,
            "variables.tf": variables_tf,
            "outputs.tf": outputs_tf,
        }
        zip_bytes = self._create_zip(files, scenario)

        summary = (
            f"Generated {len(files)} Terraform files with "
            f"{resource_count} AWS resources for "
            f"{len(comp_map)} architecture components."
        )

        return TerraformExport(
            files=files,
            zip_bytes=zip_bytes,
            component_count=len(comp_map),
            resource_count=resource_count,
            summary=summary,
        )

    def _render(self, template_str: str, **kwargs: object) -> str:
        return self._env.from_string(template_str).render(**kwargs)

    def _build_main(
        self,
        scenario: Scenario,
        comp_map: dict[str, ArchitectureComponent],
    ) -> str:
        parts = [self._render(
            _MAIN_HEADER,
            generated_date=date.today().isoformat(),
            domain=scenario.business_domain,
            users=f"{scenario.expected_users:,}",
        )]

        if "relational_db" in comp_map:
            c = comp_map["relational_db"]
            multi_az = (
                any("Multi-AZ" in n for n in c.configuration_notes)
                or scenario.availability_requirement >= 99.99
            )
            backup_retention = max(7, int(scenario.retention_years * 12 / 10))
            allocated = max(20, int(scenario.current_storage_gb * 0.4 / 10) * 10)
            parts.append(self._render(
                _RDS_TEMPLATE,
                required_by=", ".join(c.required_by),
                config_notes="; ".join(c.configuration_notes),
                multi_az="true" if multi_az else "false",
                backup_retention=backup_retention,
                allocated_storage=allocated,
                max_allocated_storage=allocated * 4,
            ))

        if "object_store" in comp_map:
            c = comp_map["object_store"]
            lifecycle_techs = {"tiered_storage", "lifecycle_management"}
            lifecycle_enabled = bool(lifecycle_techs & set(c.required_by))
            archive_enabled = "archiving" in c.required_by
            expiration_days = (
                int(scenario.retention_years * 365)
                if scenario.retention_years > 0 else 0
            )
            parts.append(self._render(
                _S3_TEMPLATE,
                required_by=", ".join(c.required_by),
                config_notes="; ".join(c.configuration_notes),
                lifecycle_enabled=lifecycle_enabled,
                archive_enabled=archive_enabled,
                expiration_days=expiration_days,
            ))

        if "cache" in comp_map:
            c = comp_map["cache"]
            num_clusters = 2 if scenario.availability_requirement >= 99.99 else 1
            parts.append(self._render(
                _CACHE_TEMPLATE,
                required_by=", ".join(c.required_by),
                config_notes="; ".join(c.configuration_notes),
                num_clusters=num_clusters,
            ))

        has_object_lifecycle = (
            "object_store" in comp_map
            and {"tiered_storage", "lifecycle_management"}
            & set(comp_map["object_store"].required_by)
        )
        if "archive" in comp_map and not has_object_lifecycle:
            c = comp_map["archive"]
            parts.append(self._render(
                _ARCHIVE_TEMPLATE,
                required_by=", ".join(c.required_by),
                config_notes="; ".join(c.configuration_notes),
            ))

        if "analytics_store" in comp_map and scenario.expected_users > 1_000_000:
            c = comp_map["analytics_store"]
            parts.append(self._render(
                _REDSHIFT_TEMPLATE,
                required_by=", ".join(c.required_by),
                config_notes="; ".join(c.configuration_notes),
            ))

        return "\n".join(parts)

    def _build_variables(
        self,
        scenario: Scenario,
        comp_map: dict[str, ArchitectureComponent],
    ) -> str:
        project_name = f"{scenario.business_domain.lower()}-storage"
        parts = [self._render(_VARIABLES_BASE, project_name=project_name)]

        if "relational_db" in comp_map:
            parts.append(_VARIABLES_RDS)
        if "cache" in comp_map:
            parts.append(_VARIABLES_CACHE)
        if "analytics_store" in comp_map and scenario.expected_users > 1_000_000:
            parts.append(_VARIABLES_REDSHIFT)

        return "\n".join(parts)

    def _build_outputs(
        self,
        comp_map: dict[str, ArchitectureComponent],
    ) -> str:
        parts: list[str] = []

        if "relational_db" in comp_map:
            parts.append("""\
output "rds_endpoint" {
  description = "RDS PostgreSQL connection endpoint"
  value       = aws_db_instance.main.endpoint
}

output "rds_port" {
  description = "RDS PostgreSQL port"
  value       = aws_db_instance.main.port
}
""")

        if "object_store" in comp_map:
            parts.append("""\
output "s3_bucket_name" {
  description = "S3 data bucket name"
  value       = aws_s3_bucket.main.bucket
}

output "s3_bucket_arn" {
  description = "S3 data bucket ARN"
  value       = aws_s3_bucket.main.arn
}
""")

        if "cache" in comp_map:
            parts.append("""\
output "elasticache_endpoint" {
  description = "ElastiCache Redis primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}
""")

        if "analytics_store" in comp_map and any(
            "Redshift" in (comp_map.get("analytics_store") or ArchitectureComponent(
                component_id="", component_type="", service="",
                workload_domain="", required_by=[], configuration_notes=[],
                priority="",
            )).service
            for _ in [None]
        ):
            parts.append("""\
output "redshift_endpoint" {
  description = "Redshift analytics cluster endpoint"
  value       = aws_redshift_cluster.analytics.endpoint
}
""")

        return "\n".join(parts) if parts else "# No outputs — no components generated.\n"

    def _create_zip(
        self,
        files: dict[str, str],
        scenario: Scenario,
    ) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in files.items():
                zf.writestr(f"terraform/{filename}", content)
            zf.writestr("terraform/README.md", self._readme_content())
            zf.writestr(
                "terraform/terraform.tfvars.example",
                self._tfvars_example(scenario, files),
            )
        return buffer.getvalue()

    def _readme_content(self) -> str:
        return """\
# Terraform Scaffold — AI Data Architect

## Generated by AI Data Architect

## How to use

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill in values
2. Run: `terraform init`
3. Run: `terraform plan`
4. Review the plan carefully before applying
5. Run: `terraform apply`

## Prerequisites

- Terraform >= 1.5
- AWS credentials configured
- An existing VPC with private subnets

## Important

- All passwords must be set in terraform.tfvars (never commit this file)
- Review instance sizes before applying — defaults are conservative
- This scaffold was generated from a workload analysis, not a production audit
"""

    def _tfvars_example(
        self,
        scenario: Scenario,
        files: dict[str, str],
    ) -> str:
        project_name = f"{scenario.business_domain.lower()}-storage"
        lines = [
            'aws_region         = "us-east-1"',
            f'project_name       = "{project_name}"',
            'environment        = "production"',
            'vpc_id             = "vpc-xxxxxxxxxxxxxxxxx"',
            'private_subnet_ids = ["subnet-xxxxxxxxxxxxxxxxx", "subnet-xxxxxxxxxxxxxxxxx"]',
        ]
        vars_tf = files.get("variables.tf", "")
        if "database_password" in vars_tf:
            lines.append('database_password   = "CHANGE_ME"')
        if "redshift_password" in vars_tf:
            lines.append('redshift_password   = "CHANGE_ME"')
        return "\n".join(lines) + "\n"
