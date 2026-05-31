from datetime import UTC, datetime
import unittest

from app.models.entities import ManagedEntityRecord
from app.services.target_preferences import build_quick_pick_records, rank_channel_records


class TargetPreferencesTests(unittest.TestCase):
    def test_rank_channel_records_prioritizes_favorites_then_recents(self) -> None:
        records = [
            ManagedEntityRecord(1, "@news", "News", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(2, "@deals", "Deals", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(3, "@alerts", "Alerts", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(4, "@updates", "Updates", 1, "ACTIVE", datetime.now(UTC)),
        ]

        ranked = rank_channel_records(records, {3}, [2, 1])
        ranked_ids = [item.id for item, _, _ in ranked]

        self.assertEqual(ranked_ids, [3, 2, 1, 4])
        self.assertEqual(ranked[0][1:], (True, False))
        self.assertEqual(ranked[1][1:], (False, True))

    def test_rank_channel_records_keeps_alphabetical_tail(self) -> None:
        records = [
            ManagedEntityRecord(10, "@zeta", "Zeta", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(11, "@alpha", "Alpha", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(12, "@beta", "Beta", 1, "ACTIVE", datetime.now(UTC)),
        ]

        ranked = rank_channel_records(records, set(), [])
        ranked_ids = [item.id for item, _, _ in ranked]
        self.assertEqual(ranked_ids, [11, 12, 10])

    def test_build_quick_pick_records_prioritizes_last_used_then_favorites(self) -> None:
        records = [
            ManagedEntityRecord(1, "@news", "News", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(2, "@deals", "Deals", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(3, "@alerts", "Alerts", 1, "ACTIVE", datetime.now(UTC)),
            ManagedEntityRecord(4, "@updates", "Updates", 1, "ACTIVE", datetime.now(UTC)),
        ]
        quick = build_quick_pick_records(records, {1, 3}, [2, 1], limit=3)
        quick_ids = [item.id for item, _, _ in quick]

        self.assertEqual(quick_ids, [2, 1, 3])


if __name__ == "__main__":
    unittest.main()
