from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Tuple

from secure_delivery.models.enums import MessageClass
from secure_delivery.models.message import SecureMessage
from secure_delivery.models.policy import ClassPolicy, PolicyVersion
from secure_delivery.models.profile import SecurityProfile
from secure_delivery.policy.backends import IContractBackend, load_policy_bundle


class PolicyManager:
    def __init__(self, backend: IContractBackend) -> None:
        bundle = load_policy_bundle(backend)
        self.security_profiles: Dict[str, SecurityProfile] = bundle["security_profiles"]
        self.policy_versions: Dict[str, PolicyVersion] = bundle["policy_versions"]
        self.metadata: Dict[str, object] = bundle["metadata"]
        self.current_version_id: str = ""
        self.events: List[Dict[str, object]] = []

    def switch_version(self, version_id: str, at_time: float, reason: str = "scheduled") -> PolicyVersion:
        if version_id not in self.policy_versions:
            raise KeyError(f"Unknown policy version: {version_id}")
        self.current_version_id = version_id
        self.events.append(
            {
                "time_s": at_time,
                "event": "policy_switch",
                "version_id": version_id,
                "reason": reason,
            }
        )
        return self.policy_versions[version_id]

    def get_current_version(self) -> PolicyVersion:
        if not self.current_version_id:
            raise RuntimeError("Policy version is not initialized")
        return self.policy_versions[self.current_version_id]

    def resolve_message_policy(self, message: SecureMessage) -> Tuple[ClassPolicy, SecurityProfile]:
        version = self.get_current_version()
        class_policy = version.class_policies[message.message_class]
        profile = self.security_profiles[class_policy.security_profile]
        message.policy_version_id = version.version_id
        message.requested_profile = profile.name
        return class_policy, profile

    def authorize(self, message: SecureMessage) -> bool:
        class_policy, _ = self.resolve_message_policy(message)
        allowed = class_policy.is_authorized(message.src)
        self.events.append(
            {
                "time_s": message.classified_at if message.classified_at is not None else message.generated_at,
                "event": "authorization",
                "version_id": self.current_version_id,
                "message_id": message.message_id,
                "message_class": message.message_class.value,
                "src": message.src,
                "allowed": allowed,
            }
        )
        return allowed

    def get_class_policy(self, message_class: MessageClass) -> ClassPolicy:
        return self.get_current_version().class_policies[message_class]

    def export_events(self) -> List[Dict[str, object]]:
        return list(self.events)

    def export_manifest(self) -> Dict[str, object]:
        return {
            "current_version_id": self.current_version_id,
            "available_versions": list(self.policy_versions.keys()),
            "available_profiles": list(self.security_profiles.keys()),
            "metadata": self.metadata,
        }

    def describe_version(self, version_id: str) -> Dict[str, object]:
        version = self.policy_versions[version_id]
        return {
            "version_id": version.version_id,
            "description": version.description,
            "class_policies": {
                message_class.value: asdict(policy)
                for message_class, policy in version.class_policies.items()
            },
        }
