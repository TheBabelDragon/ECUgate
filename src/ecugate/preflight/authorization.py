"""Authorization grants — explicit, bound, never auto-issued by preflight."""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import Dict, Optional
from uuid import uuid4

from ecugate.preflight.models import AuthorizationGrant, OperationProposal, utc_now


class AuthorizationStore:
    """In-process grant store. No secret keys; issuer is a label only."""

    def __init__(self) -> None:
        self._grants: Dict[str, AuthorizationGrant] = {}
        self._lock = threading.Lock()

    def issue(
        self,
        proposal: OperationProposal,
        *,
        issuer: str = "manual_operator",
        ttl_seconds: int = 300,
        scope: str = "sim_only",
        single_use: bool = True,
    ) -> AuthorizationGrant:
        if proposal.bench is None:
            raise ValueError("proposal requires bench/target for authorization")
        now = utc_now()
        grant = AuthorizationGrant(
            grant_id=str(uuid4()),
            issuer=issuer,
            target_digest=proposal.bench.target.identity_digest(),
            operation_digest=proposal.operation_digest(),
            artifact_digest=proposal.artifact.digest if proposal.artifact else None,
            scope=scope,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
            single_use=single_use,
            consumed=False,
            revoked=False,
        )
        with self._lock:
            self._grants[grant.grant_id] = grant
        return grant

    def get(self, grant_id: str) -> Optional[AuthorizationGrant]:
        with self._lock:
            return self._grants.get(grant_id)

    def revoke(self, grant_id: str) -> bool:
        with self._lock:
            g = self._grants.get(grant_id)
            if not g:
                return False
            g.revoked = True
            return True

    def consume(self, grant_id: str) -> bool:
        with self._lock:
            g = self._grants.get(grant_id)
            if not g or g.revoked or g.consumed:
                return False
            if g.single_use:
                g.consumed = True
            return True
