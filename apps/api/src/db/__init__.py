"""
Database Models Package Init
============================
Exports core LearnHouse models, CSG-LMS multi-campus academic hierarchy models,
and CSG-EMS dynamic RBAC permission models.
"""

from src.db.sms_campus import (
    Campus,
    CampusBase,
    CampusCreate,
    CampusUpdate,
    CampusRead,
    AcademicYear,
    AcademicYearBase,
    AcademicYearCreate,
    AcademicYearUpdate,
    AcademicYearRead,
    AcademicTerm,
    AcademicTermBase,
    AcademicTermCreate,
    AcademicTermUpdate,
    AcademicTermRead,
    ClassSection,
    ClassSectionBase,
    ClassSectionCreate,
    ClassSectionUpdate,
    ClassSectionRead,
    StudentEnrollment,
    StudentEnrollmentBase,
    StudentEnrollmentCreate,
    StudentEnrollmentUpdate,
    StudentEnrollmentRead,
)

from src.db.ems_roles import (
    ScopeLevel,
    ResourceDomain,
    CoreRoleSlug,
    EMSRole,
    EMSRoleBase,
    EMSRoleCreate,
    EMSRoleUpdate,
    EMSRoleRead,
    EMSPermissionRule,
    EMSPermissionRuleBase,
    EMSPermissionRuleCreate,
    EMSPermissionRuleUpdate,
    EMSPermissionRuleRead,
    EMSUserRoleAssignment,
    EMSUserRoleAssignmentBase,
    EMSUserRoleAssignmentCreate,
    EMSUserRoleAssignmentUpdate,
    EMSUserRoleAssignmentRead,
    DEFAULT_EMS_ROLE_SPECS,
    seed_default_ems_roles,
    seed_default_ems_roles_sync,
)

from src.db.sms_section_subject import (
    SectionSubject,
    SectionSubjectBase,
    SectionSubjectCreate,
    SectionSubjectUpdate,
    SectionSubjectRead,
    SectionSubjectReadDetailed,
)

from src.db.sms_document_template import (
    SchoolBrandingSettings,
    SMSDocumentTemplate,
)

from src.db.sms_audit_log import (
    SMSDocumentAuditLog,
)

__all__ = [
    # Multi-Campus Models
    "Campus",
    "CampusBase",
    "CampusCreate",
    "CampusUpdate",
    "CampusRead",
    "AcademicYear",
    "AcademicYearBase",
    "AcademicYearCreate",
    "AcademicYearUpdate",
    "AcademicYearRead",
    "AcademicTerm",
    "AcademicTermBase",
    "AcademicTermCreate",
    "AcademicTermUpdate",
    "AcademicTermRead",
    "ClassSection",
    "ClassSectionBase",
    "ClassSectionCreate",
    "ClassSectionUpdate",
    "ClassSectionRead",
    "StudentEnrollment",
    "StudentEnrollmentBase",
    "StudentEnrollmentCreate",
    "StudentEnrollmentUpdate",
    "StudentEnrollmentRead",
    # Curricular Bridge Models
    "SectionSubject",
    "SectionSubjectBase",
    "SectionSubjectCreate",
    "SectionSubjectUpdate",
    "SectionSubjectRead",
    "SectionSubjectReadDetailed",
    # Dynamic RBAC Models
    "ScopeLevel",
    "ResourceDomain",
    "CoreRoleSlug",
    "EMSRole",
    "EMSRoleBase",
    "EMSRoleCreate",
    "EMSRoleUpdate",
    "EMSRoleRead",
    "EMSPermissionRule",
    "EMSPermissionRuleBase",
    "EMSPermissionRuleCreate",
    "EMSPermissionRuleUpdate",
    "EMSPermissionRuleRead",
    "EMSUserRoleAssignment",
    "EMSUserRoleAssignmentBase",
    "EMSUserRoleAssignmentCreate",
    "EMSUserRoleAssignmentUpdate",
    "EMSUserRoleAssignmentRead",
    "DEFAULT_EMS_ROLE_SPECS",
    "seed_default_ems_roles",
    "seed_default_ems_roles_sync",
    # Document Engine & Branding Models
    "SchoolBrandingSettings",
    "SMSDocumentTemplate",
    "SMSDocumentAuditLog",
]

