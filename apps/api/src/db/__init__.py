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

from src.db.sms_facilities import (
    ClassroomType,
    Classroom,
    ClassroomBase,
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomRead,
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

from src.db.sms_curriculum import (
    Program,
    ProgramBase,
    ProgramCreate,
    ProgramUpdate,
    ProgramRead,
    SyllabusTopic,
    SyllabusTopicBase,
    SyllabusTopicCreate,
    SyllabusTopicUpdate,
    SyllabusTopicRead,
)

from src.db.sms_document_template import (
    SchoolBrandingSettings,
    SMSDocumentTemplate,
)

from src.db.sms_audit_log import (
    SMSDocumentAuditLog,
)

from src.db.sms_transport import (
    StudentTransportAssignment,
    TransportRoute,
    TransportRouteStop,
    TransportVehicle,
    VehicleTypeEnum,
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
    # Facilities Models
    "ClassroomType",
    "Classroom",
    "ClassroomBase",
    "ClassroomCreate",
    "ClassroomUpdate",
    "ClassroomRead",
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
    # Curriculum Masters (Programs & Syllabus Topics)
    "Program",
    "ProgramBase",
    "ProgramCreate",
    "ProgramUpdate",
    "ProgramRead",
    "SyllabusTopic",
    "SyllabusTopicBase",
    "SyllabusTopicCreate",
    "SyllabusTopicUpdate",
    "SyllabusTopicRead",
    # Document Engine & Branding Models
    "SchoolBrandingSettings",
    "SMSDocumentTemplate",
    "SMSDocumentAuditLog",
    # Transport Fleet & Routes
    "TransportVehicle",
    "TransportRoute",
    "TransportRouteStop",
    "StudentTransportAssignment",
    "VehicleTypeEnum",
]

