"""
Schemas for M19 cross-module reports.

THE LOAD-BEARING TYPE HERE IS `Metric`. A principal reading "0%" and a
principal reading "nothing recorded yet" make completely different decisions,
and this codebase has had fabricated reporting torn out three times -- a GPA
endpoint returning 4.0 for a student with zero grades, a parent digest
inventing attendance rates and teacher praise, and outbound copy naming a
school that does not exist. So a rate over an empty set is NOT zero: `value`
is None, `has_data` is False, and `no_data_reason` says what is missing.
Counts are different -- "3 leads" and "0 leads" are both real answers, so
counts stay plain integers.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Metric(BaseModel):
    """One computed figure that may legitimately have no value.

    `value is None` means "not computable from the data present", never zero.
    `sample_size` is the denominator the value was computed over, so a caller
    can tell a 100% built on 2 records from one built on 2000.
    """

    value: Optional[float] = Field(
        default=None,
        description="The figure, or null when there is no data to compute it from. Never defaulted to 0.",
    )
    unit: str = Field(default="percent", description="percent | currency | count | gpa")
    has_data: bool = Field(default=False, description="False when value is null because nothing was recorded.")
    no_data_reason: Optional[str] = Field(
        default=None,
        description="Plain-language reason the value is null, shown to the reader instead of a number.",
    )
    sample_size: int = Field(default=0, description="How many source records the value was computed over.")

    @classmethod
    def absent(cls, reason: str, unit: str = "percent") -> "Metric":
        """No data. The only way to build a valueless Metric, so the reason is never forgotten."""
        return cls(value=None, unit=unit, has_data=False, no_data_reason=reason, sample_size=0)

    @classmethod
    def of(cls, value: float, sample_size: int, unit: str = "percent") -> "Metric":
        """A real computed figure, with the denominator it came from."""
        return cls(value=value, unit=unit, has_data=True, no_data_reason=None, sample_size=sample_size)


class AttendanceReport(BaseModel):
    """Attendance over a date range, from sms_student_attendance rows."""

    attendance_rate: Metric
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    excused_count: int = 0
    records_counted: int = 0
    source_module: str = "M06 Attendance"


class GradeDistributionReport(BaseModel):
    """Grade spread, computed with the gradebook's own scale resolver."""

    average_percentage: Metric
    average_gpa: Metric
    letter_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Letter grade -> student-assessment count. Empty when nothing is graded.",
    )
    entries_counted: int = 0
    source_module: str = "M07 Gradebook"


class FeeCollectionReport(BaseModel):
    """Billed vs collected, from sms_student_fee_voucher rows."""

    collection_rate: Metric
    total_invoiced: float = 0.0
    total_collected: float = 0.0
    total_outstanding: float = 0.0
    voucher_count: int = 0
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    source_module: str = "M09 Fees"


class AdmissionsFunnelReport(BaseModel):
    """Funnel occupancy and conversion, from sms_admissions_lead rows."""

    conversion_rate: Metric
    stage_counts: Dict[str, int] = Field(default_factory=dict)
    total_leads: int = 0
    enrolled_count: int = 0
    lost_count: int = 0
    stalled_count: int = 0
    source_module: str = "M21 Admissions / RevOps"


class SchoolOverviewReport(BaseModel):
    """The principal's single view. Every section names the module it came from.

    Deliberately carries no authenticity marker: an earlier endpoint here
    emitted a forgeable "OFFICIAL"/"COGNIA-VERIFIED" seal, which is worse than
    no seal at all.
    """

    campus_id: Optional[int] = None
    campus_name: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    attendance: AttendanceReport
    grades: GradeDistributionReport
    fees: FeeCollectionReport
    admissions: AdmissionsFunnelReport
    sections_covered: int = 0
    students_covered: int = 0
    warnings: List[str] = Field(
        default_factory=list,
        description="What could not be reported and why, so silence is never mistaken for a zero.",
    )
