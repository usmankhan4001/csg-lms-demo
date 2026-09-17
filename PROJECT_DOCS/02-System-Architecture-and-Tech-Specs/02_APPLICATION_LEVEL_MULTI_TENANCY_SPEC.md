# System Architecture: Application-Level Multi-Tenancy Model

**Document Reference:** CSG-ARCH-002  
**Target Audience:** Backend Engineers, Database Architects, Security Leads  
**Classification:** Technical Architecture Specification  
**Status:** Canonical Implementation Baseline (Zero PostgreSQL RLS)  

---

## 1. Architectural Decision: Rejection of PostgreSQL Row-Level Security (RLS)

### 1.1 Context & Historical Issues with RLS
Earlier design specifications attempted to enforce multi-tenancy at the PostgreSQL database engine layer using Row-Level Security (`ALTER TABLE ... ENABLE ROW LEVEL SECURITY`) and dynamic session variables (`SET LOCAL app.current_org_id = ...`). 

In production, database-level RLS introduces severe liabilities:
- **Connection Pooling Incompatibilities:** Database connection poolers (e.g., PgBouncer, SQLAlchemy AsyncEngine connection pools) reuse physical database connections. RLS session variables risk connection contamination across tenant requests unless aggressively reset on every checkout, introducing significant latency overhead.
- **Complex Query Optimization Degradation:** PostgreSQL query planners frequently degrade into sequential table scans when executing complex analytical joins across RLS-constrained tables.
- **Developer Friction & Migration Overhead:** Maintaining hundreds of repetitive RLS security policies across dozens of database tables drastically increases migration fragility.

### 1.2 The Solution: High-Performance Application-Level Multi-Tenancy
CSG-LMS strictly adopts **Application-Level Multi-Tenancy**, inheriting the proven model from **LearnHouse**:
- Every database model explicitly includes an `org_id: int` (foreign key to `organization.id`).
- Tenant resolution occurs at the HTTP request boundary via host custom domain, subdomain slug, or authenticated JWT claims.
- FastAPI dependency injection automatically injects the verified `current_org` into database query sessions.
- All SQLModel / SQLAlchemy queries strictly apply `.where(Model.org_id == current_org.id)`.

---

## 2. Technical Implementation Specification

### 2.1 Tenant Context Resolution Flow
```
Client HTTP Request
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ Nginx Gateway / Host Header Inspection                  │
│ • Inspects Host: 'downtown.csg-schools.com' or custom   │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│ FastAPI Tenant Middleware / Dependency Injection        │
│ 1. Queries Organization by custom domain or header slug │
│ 2. Validates Organization status (Active, Not Suspended)│
│ 3. Resolves current_org_id                              │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│ Database Query Execution (SQLModel / SQLAlchemy)        │
│ session.exec(select(Course).where(                      │
│     Course.org_id == current_org_id,                    │
│     Course.id == course_id                              │
│ ))                                                      │
└─────────────────────────────────────────────────────────┘
```

### 2.2 Reusable SQLModel Multi-Tenant Base Model
All persistent database entities inherit from a standardized multi-tenant mixin:

```python
# Conceptual Architecture Pattern in FastAPI / SQLModel
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class MultiTenantBase(SQLModel):
    org_id: int = Field(foreign_key="organization.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
```

### 2.3 Cross-Tenant Isolation Enforcement
- **Automated Query Guards:** Every API endpoint receiving an entity ID verifies that the entity's `org_id` matches the authenticated `current_org_id`.
- **404 Not Found on Tenant Mismatch:** If an authenticated user from Tenant A requests an entity ID belonging to Tenant B, the API returns a generic `404 Not Found` (never a `403 Forbidden`), preventing malicious tenant enumeration.

---

## 3. Performance & Scalability Advantages
- **Blazing Fast Query Execution:** Eliminates RLS policy evaluation overhead on every database row fetch, achieving sub-10ms query execution.
- **Seamless Async Connection Pooling:** Works natively with high-concurrency async connection pools without risky session state contamination.
- **Simplified Database Migrations:** Alembic migrations manage pure relational foreign keys and indexes without maintaining brittle procedural SQL policies.
