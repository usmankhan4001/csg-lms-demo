# System Architecture: Dynamic RBAC Technical Specification

**Document Reference:** CSG-ARCH-004  
**Target Audience:** Security Architects, Backend Engineers  
**Classification:** Technical Architecture Specification  
**Status:** Canonical Implementation Baseline (LearnHouse Role & Rights Revamped)  

---

## 1. Technical Premise: Dynamic Rights Over Hardcoded Personas

Rather than hardcoding static role enums into code, CSG-LMS adopts the flexible **LearnHouse Rights Model** (`apps/api/src/db/roles.py`), storing fine-grained CRUD and ownership permissions in a structured JSON column on the `Role` entity.

This architecture decouples the authorization logic from code deployments, allowing school administrators to create, clone, and configure custom institutional roles on the fly.

---

## 2. SQLModel Entity & Rights JSON Schema

### 2.1 The `Role` SQLModel Entity

```python
from sqlmodel import SQLModel, Field
from sqlalchemy import JSON, Column
from typing import Optional, Dict, Any

class Role(MultiTenantBase, table=True):
    __tablename__ = "roles"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    role_uuid: str = Field(unique=True, index=True)
    name: str = Field(index=True)  # e.g., "Department Head", "Admissions Officer"
    role_type: str = Field(default="custom")  # system, custom
    description: Optional[str] = None
    
    # Granular JSON Permissions mapping resource -> action flags
    rights: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
```

### 2.2 Granular Action Permission Structure
Every domain resource in the `rights` JSON object defines explicit action flags:

```json
{
  "academics_calendar": {
    "action_create": false,
    "action_read": true,
    "action_update": false,
    "action_delete": false
  },
  "courses": {
    "action_create": true,
    "action_read": true,
    "action_read_own": false,
    "action_update": true,
    "action_update_own": true,
    "action_delete": false,
    "action_delete_own": false
  },
  "attendance": {
    "action_create": true,
    "action_read": true,
    "action_update": true,
    "action_delete": false
  },
  "gradebook": {
    "action_create": false,
    "action_read": true,
    "action_update": false,
    "action_publish": false
  },
  "psychological_notes": {
    "action_read": false,
    "action_create": false
  }
}
```

---

## 3. FastAPI Authorization Guard & Middleware

### 3.1 Permission Evaluator Dependency
Every protected endpoint in FastAPI declares required permission rights using dependency injection:

```python
from fastapi import Depends, HTTPException, status

def require_permission(resource: str, action: str):
    async def permission_checker(current_user: User = Depends(get_current_user), current_org: Organization = Depends(get_current_org)):
        # 1. Superadmin bypass
        if current_user.is_superadmin:
            return True
            
        # 2. Retrieve user role in current organization
        user_role = await get_user_role(current_user.id, current_org.id)
        if not user_role or not user_role.rights:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assigned in organization")
            
        # 3. Evaluate specific resource action flag
        resource_rights = user_role.rights.get(resource, {})
        has_permission = resource_rights.get(action, False)
        
        if not has_permission:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing required permission: {resource}.{action}")
            
        return True
    return permission_checker
```

### 3.2 Endpoint Application Example

```python
@router.post("/student-batches", response_model=StudentBatchRead)
async def create_student_batch(
    batch_data: StudentBatchCreate,
    current_org: Organization = Depends(get_current_org),
    authorized: bool = Depends(require_permission("academics_batch", "action_create"))
):
    return await batch_service.create_batch(current_org.id, batch_data)
```

---

## 4. Performance & Caching Strategy
- **Redis Session Caching:** Resolved role rights are cached in Redis under `org:{org_id}:user:{user_id}:rights` with a 15-minute TTL.
- **Immediate Invalidation on Mutation:** When an administrator edits a role's permissions, the API flushes all Redis cached rights keys for that organization, enforcing permission updates globally within 50ms.
