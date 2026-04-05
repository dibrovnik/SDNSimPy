import unittest

from secure_delivery.config import CryptoEngineConfig
from secure_delivery.crypto.engine import CryptoEngine
from secure_delivery.models.profile import SecurityProfile


class CryptoEngineTestCase(unittest.TestCase):
    def test_synthetic_cost_uses_profile_parameters(self) -> None:
        engine = CryptoEngine(CryptoEngineConfig(mode="synthetic"))
        profile = SecurityProfile(
            name="test",
            algorithm="AES-GCM",
            overhead_s=1.0,
            per_byte_s=0.1,
            verify_overhead_s=0.5,
            rekey_overhead_s=0.0,
            header_bytes=8,
            tag_bytes=8,
        )
        self.assertAlmostEqual(engine.compute_crypto_time(profile, 10), 2.5)

    def test_lookup_interpolates(self) -> None:
        engine = CryptoEngine(CryptoEngineConfig(mode="lookup_table"))
        profile = SecurityProfile(
            name="table",
            algorithm="AES-GCM",
            overhead_s=0.0,
            per_byte_s=0.0,
            verify_overhead_s=0.0,
            rekey_overhead_s=0.0,
            header_bytes=8,
            tag_bytes=8,
            lookup_table={64: 1.0, 128: 3.0},
        )
        self.assertAlmostEqual(engine.compute_crypto_time(profile, 96), 2.0)


if __name__ == "__main__":
    unittest.main()
