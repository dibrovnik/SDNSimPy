import unittest

from secure_delivery.models.enums import MessageClass
from secure_delivery.models.message import SecureMessage
from secure_delivery.policy.backends import FilePolicyBackend
from secure_delivery.policy.manager import PolicyManager


class PolicyManagerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        backend = FilePolicyBackend("configs/policies/baseline_policies.json")
        self.manager = PolicyManager(backend)
        self.manager.switch_version("scenario_c_priority_protected", 0.0, reason="test")

    def test_authorization_respects_source(self) -> None:
        message = SecureMessage(
            message_id="m1",
            src="source_background",
            dst="receiver",
            message_class=MessageClass.CRITICAL,
            payload_bytes=64,
            generated_at=0.0,
            deadline_s=0.1,
            sequence_no=1,
        )
        message.classified_at = 0.0
        self.assertFalse(self.manager.authorize(message))

    def test_policy_resolution_applies_profile(self) -> None:
        message = SecureMessage(
            message_id="m2",
            src="source_command",
            dst="receiver",
            message_class=MessageClass.CONTROL,
            payload_bytes=128,
            generated_at=0.0,
            deadline_s=0.5,
            sequence_no=1,
        )
        policy, profile = self.manager.resolve_message_policy(message)
        self.assertEqual(policy.security_profile, "aead_control")
        self.assertEqual(profile.name, "aead_control")


if __name__ == "__main__":
    unittest.main()
