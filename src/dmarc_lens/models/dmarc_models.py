"""
DMARC data models using Python dataclasses.

This module defines the core data structures for DMARC reports
based on the DMARC aggregate report XML schema.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
import re
import json
from ipaddress import AddressValueError, ip_address


@dataclass
class ReportMetadata:
    """Metadata information about a DMARC aggregate report."""

    org_name: str
    email: str
    report_id: str
    date_range_begin: datetime
    date_range_end: datetime
    extra_contact_info: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate report metadata after initialization."""
        self._validate_org_name()
        self._validate_email()
        self._validate_report_id()
        self._validate_date_range()

    def _validate_org_name(self) -> None:
        """Validate organization name is not empty."""
        if not self.org_name or not self.org_name.strip():
            raise ValueError("Organization name cannot be empty")

    def _validate_email(self) -> None:
        """Validate email format using basic regex."""
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, self.email):
            raise ValueError(f"Invalid email format: {self.email}")

    def _validate_report_id(self) -> None:
        """Validate report ID is not empty."""
        if not self.report_id or not self.report_id.strip():
            raise ValueError("Report ID cannot be empty")

    def _validate_date_range(self) -> None:
        """Validate date range is logical."""
        if self.date_range_begin >= self.date_range_end:
            raise ValueError("Date range begin must be before date range end")


@dataclass
class PolicyPublished:
    """Published DMARC policy for a domain."""

    domain: str
    p: str  # Policy: none, quarantine, reject
    sp: Optional[str] = None  # Subdomain policy: none, quarantine, reject
    pct: int = 100  # Percentage of messages to apply policy to
    adkim: Optional[str] = None  # DKIM alignment mode: r (relaxed) or s (strict)
    aspf: Optional[str] = None  # SPF alignment mode: r (relaxed) or s (strict)

    def __post_init__(self) -> None:
        """Validate published policy after initialization."""
        self._validate_domain()
        self._validate_policy()
        self._validate_percentage()
        self._validate_alignment_modes()

    def _validate_domain(self) -> None:
        """Validate domain format."""
        if not self.domain or not self.domain.strip():
            raise ValueError("Domain cannot be empty")
        # Basic domain validation
        domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        if not re.match(domain_pattern, self.domain):
            raise ValueError(f"Invalid domain format: {self.domain}")

    def _validate_policy(self) -> None:
        """Validate policy values."""
        valid_policies = {"none", "quarantine", "reject"}
        if self.p not in valid_policies:
            raise ValueError(
                f"Invalid policy '{self.p}'. Must be one of: {valid_policies}"
            )
        if self.sp is not None and self.sp not in valid_policies:
            raise ValueError(
                f"Invalid subdomain policy '{self.sp}'. Must be one of: {valid_policies}"
            )

    def _validate_percentage(self) -> None:
        """Validate percentage is between 0 and 100."""
        if not 0 <= self.pct <= 100:
            raise ValueError(f"Percentage must be between 0 and 100, got: {self.pct}")

    def _validate_alignment_modes(self) -> None:
        """Validate alignment modes."""
        valid_modes = {"r", "s", None}
        if self.adkim not in valid_modes:
            raise ValueError(
                f"Invalid DKIM alignment mode '{self.adkim}'. Must be 'r' or 's'"
            )
        if self.aspf not in valid_modes:
            raise ValueError(
                f"Invalid SPF alignment mode '{self.aspf}'. Must be 'r' or 's'"
            )


@dataclass
class PolicyEvaluated:
    """Evaluated DMARC policy result for a record."""

    disposition: str  # none, quarantine, reject
    dkim: str  # pass, fail
    spf: str  # pass, fail
    reason: Optional[List[str]] = None  # Reasons for policy override

    def __post_init__(self) -> None:
        """Validate policy evaluation after initialization."""
        self._validate_disposition()
        self._validate_auth_results()

    def _validate_disposition(self) -> None:
        """Validate disposition value."""
        valid_dispositions = {"none", "quarantine", "reject"}
        if self.disposition not in valid_dispositions:
            raise ValueError(
                f"Invalid disposition '{self.disposition}'. Must be one of: {valid_dispositions}"
            )

    def _validate_auth_results(self) -> None:
        """Validate authentication results."""
        valid_results = {"pass", "fail"}
        if self.dkim not in valid_results:
            raise ValueError(
                f"Invalid DKIM result '{self.dkim}'. Must be 'pass' or 'fail'"
            )
        if self.spf not in valid_results:
            raise ValueError(
                f"Invalid SPF result '{self.spf}'. Must be 'pass' or 'fail'"
            )


@dataclass
class AuthResult:
    """Authentication result for DKIM or SPF."""

    domain: str
    result: str  # pass, fail, neutral, policy, temperror, permerror
    selector: Optional[str] = None  # DKIM selector (only for DKIM results)

    def __post_init__(self) -> None:
        """Validate authentication result after initialization."""
        self._validate_domain()
        self._validate_result()

    def _validate_domain(self) -> None:
        """Validate domain format."""
        if not self.domain or not self.domain.strip():
            raise ValueError("Domain cannot be empty")

    def _validate_result(self) -> None:
        """Validate result value."""
        valid_results = {"pass", "fail", "neutral", "policy", "temperror", "permerror"}
        if self.result not in valid_results:
            raise ValueError(
                f"Invalid result '{self.result}'. Must be one of: {valid_results}"
            )


@dataclass
class DMARCRecord:
    """Individual DMARC record from an aggregate report."""

    source_ip: str
    count: int
    policy_evaluated: PolicyEvaluated
    header_from: str
    dkim_results: List[AuthResult] = field(default_factory=list)
    spf_results: List[AuthResult] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate DMARC record after initialization."""
        self._validate_source_ip()
        self._validate_count()
        self._validate_header_from()
        self._validate_auth_results()

    def _validate_source_ip(self) -> None:
        """Validate source IP address format."""
        try:
            ip_address(self.source_ip)
        except AddressValueError:
            raise ValueError(f"Invalid IP address: {self.source_ip}")

    def _validate_count(self) -> None:
        """Validate message count is positive."""
        if self.count <= 0:
            raise ValueError(f"Count must be positive, got: {self.count}")

    def _validate_header_from(self) -> None:
        """Validate header from domain."""
        if not self.header_from or not self.header_from.strip():
            raise ValueError("Header from domain cannot be empty")

    def _validate_auth_results(self) -> None:
        """Validate authentication results lists."""
        # Ensure all DKIM results are valid
        for dkim_result in self.dkim_results:
            if not isinstance(dkim_result, AuthResult):
                raise ValueError("All DKIM results must be AuthResult instances")

        # Ensure all SPF results are valid
        for spf_result in self.spf_results:
            if not isinstance(spf_result, AuthResult):
                raise ValueError("All SPF results must be AuthResult instances")

    def is_dmarc_aligned(self) -> bool:
        """Check if this record passes DMARC alignment (DKIM or SPF must pass)."""
        return (
            self.policy_evaluated.dkim == "pass" or self.policy_evaluated.spf == "pass"
        )

    def get_authentication_summary(self) -> Dict[str, Any]:
        """Get a summary of authentication results."""
        return {
            "dmarc_aligned": self.is_dmarc_aligned(),
            "dkim_pass": self.policy_evaluated.dkim == "pass",
            "spf_pass": self.policy_evaluated.spf == "pass",
            "disposition": self.policy_evaluated.disposition,
            "message_count": self.count,
        }


@dataclass
class DMARCReport:
    """Complete DMARC aggregate report."""

    metadata: ReportMetadata
    policy_published: PolicyPublished
    records: List[DMARCRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate DMARC report after initialization."""
        self._validate_records()

    def _validate_records(self) -> None:
        """Validate all records in the report."""
        for record in self.records:
            if not isinstance(record, DMARCRecord):
                raise ValueError("All records must be DMARCRecord instances")

    def get_total_messages(self) -> int:
        """Get total number of messages in this report."""
        return sum(record.count for record in self.records)

    def get_alignment_rate(self) -> float:
        """Calculate DMARC alignment rate as percentage."""
        total_messages = self.get_total_messages()
        if total_messages == 0:
            return 0.0

        aligned_messages = sum(
            record.count for record in self.records if record.is_dmarc_aligned()
        )

        return (aligned_messages / total_messages) * 100.0

    def get_source_ips(self) -> List[str]:
        """Get list of unique source IP addresses."""
        return list(set(record.source_ip for record in self.records))

    def get_records_by_disposition(self, disposition: str) -> List[DMARCRecord]:
        """Get records filtered by disposition."""
        return [
            record
            for record in self.records
            if record.policy_evaluated.disposition == disposition
        ]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get comprehensive summary statistics for the report."""
        total_messages = self.get_total_messages()

        if total_messages == 0:
            return {
                "total_messages": 0,
                "alignment_rate": 0.0,
                "unique_sources": 0,
                "disposition_breakdown": {},
                "domain": self.policy_published.domain,
                "report_period": {
                    "begin": self.metadata.date_range_begin,
                    "end": self.metadata.date_range_end,
                },
            }

        # Calculate disposition breakdown
        disposition_counts: Dict[str, int] = {}
        for record in self.records:
            disp = record.policy_evaluated.disposition
            disposition_counts[disp] = disposition_counts.get(disp, 0) + record.count

        return {
            "total_messages": total_messages,
            "alignment_rate": self.get_alignment_rate(),
            "unique_sources": len(self.get_source_ips()),
            "disposition_breakdown": disposition_counts,
            "domain": self.policy_published.domain,
            "report_period": {
                "begin": self.metadata.date_range_begin,
                "end": self.metadata.date_range_end,
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert DMARC report to dictionary for serialization.

        Returns:
            Dictionary representation of the DMARC report
        """

        def datetime_serializer(obj: Any) -> Any:
            """Convert datetime objects to ISO format strings."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        # Convert to dict using dataclasses.asdict
        report_dict = asdict(self)

        # Convert datetime objects to ISO strings
        def convert_datetimes(data: Any) -> Any:
            if isinstance(data, dict):
                return {k: convert_datetimes(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [convert_datetimes(item) for item in data]
            elif isinstance(data, datetime):
                return data.isoformat()
            else:
                return data

        return convert_datetimes(report_dict)  # type: ignore[no-any-return]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DMARCReport":
        """
        Create DMARC report from dictionary.

        Args:
            data: Dictionary representation of DMARC report

        Returns:
            DMARCReport instance

        Raises:
            ValueError: If data format is invalid
        """
        try:
            # Convert datetime strings back to datetime objects
            def convert_datetimes(data: Any) -> Any:
                if isinstance(data, dict):
                    result: Dict[str, Any] = {}
                    for k, v in data.items():
                        if k in ["date_range_begin", "date_range_end"] and isinstance(
                            v, str
                        ):
                            result[k] = datetime.fromisoformat(v)
                        else:
                            result[k] = convert_datetimes(v)
                    return result
                elif isinstance(data, list):
                    return [convert_datetimes(item) for item in data]
                else:
                    return data

            converted_data = convert_datetimes(data)

            # Reconstruct nested objects
            metadata = ReportMetadata(**converted_data["metadata"])
            policy_published = PolicyPublished(**converted_data["policy_published"])

            records = []
            for record_data in converted_data["records"]:
                policy_evaluated = PolicyEvaluated(**record_data["policy_evaluated"])

                dkim_results = [
                    AuthResult(**auth_data) for auth_data in record_data["dkim_results"]
                ]
                spf_results = [
                    AuthResult(**auth_data) for auth_data in record_data["spf_results"]
                ]

                record = DMARCRecord(
                    source_ip=record_data["source_ip"],
                    count=record_data["count"],
                    policy_evaluated=policy_evaluated,
                    header_from=record_data["header_from"],
                    dkim_results=dkim_results,
                    spf_results=spf_results,
                )
                records.append(record)

            return cls(
                metadata=metadata, policy_published=policy_published, records=records
            )

        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid DMARC report data format: {e}") from e

    def to_json(self) -> str:
        """
        Convert DMARC report to JSON string.

        Returns:
            JSON string representation of the DMARC report
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "DMARCReport":
        """
        Create DMARC report from JSON string.

        Args:
            json_str: JSON string representation of DMARC report

        Returns:
            DMARCReport instance

        Raises:
            ValueError: If JSON format is invalid
        """
        try:
            data = json.loads(json_str)

            # Ensure the parsed data is a dictionary
            if not isinstance(data, dict):
                raise ValueError("JSON must represent a dictionary object")

            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e
