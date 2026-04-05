from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict

from secure_delivery.models.policy import PolicyVersion
from secure_delivery.models.profile import SecurityProfile


class IContractBackend(ABC):
    @abstractmethod
    def load(self) -> Dict[str, object]:
        raise NotImplementedError


class FilePolicyBackend(IContractBackend):
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, object]:
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


class EvmPolicyBackend(IContractBackend):
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def load(self) -> Dict[str, object]:
        raise NotImplementedError(
            "EvmPolicyBackend is reserved for a future integration with a local EVM stack."
        )


def load_policy_bundle(backend: IContractBackend) -> Dict[str, object]:
    payload = backend.load()
    profiles = {
        name: SecurityProfile.from_dict({"name": name, **dict(profile_payload)})
        for name, profile_payload in dict(payload.get("security_profiles", {})).items()
    }
    versions = {
        item["version_id"]: PolicyVersion.from_dict(dict(item))
        for item in payload.get("policy_versions", [])
    }
    return {
        "security_profiles": profiles,
        "policy_versions": versions,
        "metadata": dict(payload.get("metadata", {})),
    }
