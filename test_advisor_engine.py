import unittest
from datetime import date

from advisor_engine import decide, epley_1rm, match_week, measured


class DecisionTests(unittest.TestCase):
    def test_negative_stress_is_missing(self):
        self.assertIsNone(measured(-1))
        result = decide({"rhr": 54, "hrv": 70, "sleep_h": 7, "stress": -1}, {"rhr_30d_median": 54, "hrv_balanced_low": 56, "sleep_need_h": 8}, {}, [])
        self.assertTrue(any(row["signal"] == "Stress" and row["today"] == "Not measured" for row in result["reasons"]))

    def test_missing_hrv_lowers_confidence(self):
        result = decide({"rhr": 54, "hrv": None, "sleep_h": 7, "stress": 20}, {"rhr_30d_median": 54, "hrv_balanced_low": 56}, {}, [])
        self.assertEqual(result["confidence"], "medium")
        self.assertIn("overnight HRV", result["missingInputs"])

    def test_reliable_rhr_spike_forces_rest_and_verify(self):
        result = decide({"rhr": 76, "hrv": None, "sleep_h": 7.2, "stress": -1, "rhr_partial": False}, {"rhr_30d_median": 54, "hrv_balanced_low": 56}, {}, [{"kind": "strength", "label": "Day 2 · Pull"}])
        self.assertEqual(result["verdict"], "REST")
        self.assertIn("verify the reading", " ".join(row["read"] for row in result["reasons"]).lower())

    def test_partial_rhr_requires_confirmation(self):
        result = decide({"rhr": 76, "hrv": 62, "sleep_h": 7.2, "rhr_partial": True}, {"rhr_30d_median": 54, "hrv_balanced_low": 56}, {}, [])
        self.assertEqual(result["verdict"], "UNCONFIRMED")

    def test_partial_rhr_confirmation_changes_verdict(self):
        today = {"rhr": 76, "hrv": 62, "sleep_h": 7.2, "rhr_partial": True}
        baseline = {"rhr_30d_median": 54, "hrv_balanced_low": 56}
        self.assertEqual(decide(today, baseline, {"rhr_confirmation": "normal"}, [])["verdict"], "GO")
        self.assertEqual(decide(today, baseline, {"rhr_confirmation": "high"}, [])["verdict"], "REST")
        self.assertEqual(decide(today, baseline, {"rhr_confirmation": "not_sure"}, [])["verdict"], "MODIFY")

    def test_ill_precedes_sensor_rules(self):
        result = decide({"rhr": 54, "hrv": 70, "sleep_h": 8}, {"rhr_30d_median": 54, "hrv_balanced_low": 56}, {"body": "Ill or in pain"}, [])
        self.assertEqual(result["rulesFired"], [2])

    def test_epley_limit(self):
        self.assertEqual(epley_1rm(100, 6), 120)
        self.assertIsNone(epley_1rm(100, 11))


class PlanTests(unittest.TestCase):
    def test_two_sessions_stay_separate(self):
        plan = {"effective_from": "2026-11-16", "weekly_schedule": [{"day": "tuesday", "strength": "push", "run": "easy"}], "strength_sessions": {"push": {"label": "Push"}}, "runs": {"easy": {"label": "Easy run", "target_distance_km": 4, "hr_cap_bpm": 152}}}
        activities = [
            {"startTimeLocal": "2026-11-17 07:00:00", "activityType": {"typeKey": "strength_training"}, "duration": 1800},
            {"startTimeLocal": "2026-11-17 08:00:00", "activityType": {"typeKey": "treadmill_running"}, "duration": 1800, "distance": 4000, "averageHR": 145},
        ]
        week = match_week(plan, activities, date(2026, 11, 16), date(2026, 11, 18))
        tuesday = week["days"][1]
        self.assertEqual(len(tuesday["sessions"]), 2)
        self.assertEqual([row["status"] for row in tuesday["sessions"]], ["done", "done"])

    def test_pre_effective_week_is_not_active(self):
        plan = {"effective_from": "2026-11-16", "weekly_schedule": [], "strength_sessions": {}, "runs": {}}
        week = match_week(plan, [], date(2026, 11, 9), date(2026, 11, 18))
        self.assertFalse(week["active"])
        self.assertEqual(week["planned"], 0)


if __name__ == "__main__":
    unittest.main()

