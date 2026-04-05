import unittest

from secure_delivery.crypto.replay import ReplayWindow


class ReplayWindowTestCase(unittest.TestCase):
    def test_rejects_duplicate_sequence(self) -> None:
        window = ReplayWindow(size=4)
        self.assertTrue(window.accept(1, 0.0, "source", "critical"))
        self.assertFalse(window.accept(1, 1.0, "source", "critical"))

    def test_rejects_far_out_of_window_sequence(self) -> None:
        window = ReplayWindow(size=2)
        self.assertTrue(window.accept(10, 0.0, "source", "critical"))
        self.assertTrue(window.accept(11, 0.1, "source", "critical"))
        self.assertFalse(window.accept(7, 0.2, "source", "critical"))


if __name__ == "__main__":
    unittest.main()
