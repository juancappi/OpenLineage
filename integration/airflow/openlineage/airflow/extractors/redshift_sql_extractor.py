# SPDX-License-Identifier: Apache-2.0.
from typing import List, TYPE_CHECKING
from openlineage.airflow.extractors.postgres_extractor import PostgresExtractor
import logging
import boto3

if TYPE_CHECKING:
    from airflow.models import BaseHook

logger = logging.getLogger(__name__)


class RedshiftSQLExtractor(PostgresExtractor):
    default_schema = "public"

    @classmethod
    def get_operator_classnames(cls) -> List[str]:
        return ["RedshiftSQLOperator"]

    def _get_scheme(self) -> str:
        return "redshift"

    def _get_hook(self) -> "BaseHook":
        from airflow.providers.amazon.aws.hooks.redshift_sql import RedshiftSQLHook

        return RedshiftSQLHook(
            redshift_conn_id=self.operator.redshift_conn_id,
        )

    def _get_authority(self) -> str:
        # If IAM enabled disregard hostname, use info from extras
        # Important: RedshiftSQLOperator does not handle
        # Redshift Serverless connections yet neither Airflow AWS provider does.
        extras = self.conn.extra_dejson
        if extras.get("iam") is True:
            host = extras.get("cluster_identifier")
            region = extras.get("region")
            if not region:
                profile = extras.get('profile', None)
                session = boto3.Session(profile_name=profile)
                region = session.region_name
            port = extras.get("port", 5439)
            identifier = f"{host}.{region}"
        elif not self.conn.host:
            raise ValueError(
                "Missing host in connection since there" "s no IAM setting"
            )
        else:
            identifier = self._get_cluster_identifier_from_hostname(self.conn.host)
            port = self.conn.port or 5439
        return f"{identifier}:{port}"

    def _get_cluster_identifier_from_hostname(self, hostname: str) -> str:
        parts = hostname.split(".")
        if "amazonaws.com" in hostname and len(parts) == 6:
            return f"{parts[0]}.{parts[2]}"
        else:
            logger.warning(
                """Could not parse identifier from hostname '%s'.
            You are probably using IP to connect to Redshift cluster.
            Expected format: 'cluster_identifier.id.region_name.redshift.amazonaws.com'
            Falling back to whole hostname.""",
                hostname,
            )
            return hostname