from typing import Optional, Union


class AuthorizationService:
    """Service abstraction for document access authorization and ownership security."""

    async def can_access_document(
        self,
        application: str,
        user_id: Union[int, str],
        document_id: Union[int, str],
    ) -> bool:
        """Verify whether user_id is authorized to access document_id under application tenant."""
        # Phase 4 Stub: All requests within valid application tenant are allowed
        # Real RBAC / document permission checks will hook into Laravel / HR API in future phases
        if not application or not document_id:
            return False
        return True
