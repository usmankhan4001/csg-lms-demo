"""
Utility functions for API token access control.

This module is separate from auth.py to avoid circular imports.
"""

from typing import Union
from fastapi import Depends, HTTPException, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.events.database import get_db_session
from src.db.users import AnonymousUser, APITokenUser, PublicUser


def reject_api_token_access(
    current_user: Union[PublicUser, APITokenUser, AnonymousUser]
) -> None:
    """
    Reject access if the current user is an API token.

    Use this function at the start of any endpoint or service function
    that should NOT be accessible via API tokens.

    Args:
        current_user: The authenticated user (could be PublicUser, APITokenUser, or AnonymousUser)

    Raises:
        HTTPException: 403 if current_user is an APITokenUser
    """
    if isinstance(current_user, APITokenUser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API tokens cannot access this resource. Only user authentication is allowed.",
        )


async def require_non_api_token_user(
    current_user: Union[PublicUser, APITokenUser, AnonymousUser]
) -> Union[PublicUser, AnonymousUser]:
    """
    FastAPI dependency that rejects API token access.

    Use this in router dependencies to block entire routers from API tokens.
    This is cleaner than calling reject_api_token_access in every endpoint.

    Example:
        from src.security.auth import get_current_user

        router.include_router(
            some_router,
            dependencies=[Depends(lambda user=Depends(get_current_user): require_non_api_token_user(user))]
        )

    Or create a helper in the router file:
        def get_non_api_token_user(user = Depends(get_current_user)):
            return require_non_api_token_user(user)

        router.include_router(
            some_router,
            dependencies=[Depends(get_non_api_token_user)]
        )

    Args:
        current_user: The authenticated user (injected by FastAPI)

    Returns:
        The current user if not an API token

    Raises:
        HTTPException: 403 if current_user is an APITokenUser
    """
    reject_api_token_access(current_user)
    return current_user


async def get_authenticated_non_api_token_user(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> PublicUser:
    """
    FastAPI dependency that requires an authenticated, non-API-token user.

    SECURITY: Use this as the router-level dependency on any router that has
    *no* public endpoints. The historical ``get_non_api_token_user`` helper
    only rejects API tokens — it silently admits ``AnonymousUser``. Swapping
    to this dependency closes that gap for routers that should always
    require an active session.

    Raises:
        HTTPException 401 if the request is unauthenticated.
        HTTPException 403 if the caller is an API token.
    """
    # Imported locally to avoid a circular dependency on auth.py, which in
    # turn imports from this module.
    from src.security.auth import get_authenticated_user

    user = await get_authenticated_user(request, db_session)
    if isinstance(user, APITokenUser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API tokens cannot access this resource. Only user authentication is allowed.",
        )
    return user


async def require_authenticated_user_or_api_token(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    FastAPI dependency that requires an authenticated session OR a valid API token.

    Rejects anonymous callers (401) but — unlike ``get_authenticated_non_api_token_user`` —
    admits API tokens. Use as the router-level dependency on routers that expose some
    endpoints to headless API-token clients while still gating individual handlers
    internally.

    Raises:
        HTTPException 401 if the request is unauthenticated.
    """
    # Imported locally to avoid a circular dependency on auth.py.
    from src.security.auth import get_authenticated_user

    return await get_authenticated_user(request, db_session)


def token_has_scope(user: Union[PublicUser, APITokenUser, AnonymousUser], required_scope: str) -> bool:
    """
    Evaluate if an APITokenUser has the specified scope.
    Session users (PublicUser) automatically return True (gated by RBAC).
    Anonymous users return False.
    """
    if isinstance(user, AnonymousUser):
        return False
    if not isinstance(user, APITokenUser):
        return True

    user_scopes = getattr(user, "scopes", None) or []
    
    # 1. Full wildcard
    if "*" in user_scopes or "*:*" in user_scopes:
        return True

    # 2. Exact match
    if required_scope in user_scopes:
        return True

    # 3. Domain/action wildcard matching (e.g. "academic:*" covers "academic:read")
    if ":" in required_scope:
        domain, action = required_scope.split(":", 1)
        if f"{domain}:*" in user_scopes or f"*:{action}" in user_scopes:
            return True

    # 4. Fallback for legacy rights dict if scopes array is empty
    if not user_scopes and user.rights:
        if required_scope.startswith("academic:") and user.rights.get("courses", {}).get("action_read"):
            return True
        if required_scope.startswith("users:") and user.rights.get("users", {}).get("action_read"):
            return True

    return False


def require_api_scope(required_scope: str):
    """
    FastAPI dependency factory to gate an endpoint by a specific granular API token scope.
    If caller is an APITokenUser, enforces the scope. If caller is a session user, admits through to RBAC.
    """
    async def _scope_checker(
        request: Request,
        db_session: AsyncSession = Depends(get_db_session),
    ):
        from src.security.auth import get_authenticated_user
        user = await get_authenticated_user(request, db_session)
        if isinstance(user, AnonymousUser):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
            )
        if isinstance(user, APITokenUser):
            if not token_has_scope(user, required_scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"API token lacks required scope: '{required_scope}'",
                )
        return user

    return _scope_checker

