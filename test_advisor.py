"""Regression checks for decisions with absent, stale and conflicting data."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent


class AdvisorBuildTests(unittest.TestCase):
    def build(self, records):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('build.py', 'advisor_ui.py', 'advisor.js', 'advisor.css'):
                shutil.copyfile(ROOT / name, root / name)
            (root / 'data').mkdir()
            for name, value in records.items():
                (root / 'data' / name).write_text(json.dumps(value), encoding='utf-8')
            subprocess.run([sys.executable, str(root/'build.py')], check=True, capture_output=True)
            return (root/'dashboard.html').read_text(encoding='utf-8')

    def records(self, age=0):
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        dates = [(today-timedelta(days=i+age)).isoformat() for i in range(35)]
        return {
            'daily_summaries.json': [{'calendarDate':d,'heartRate':{'restingValue':54},'bodyBattery':{'latestValue':95},'stress':{'avgLevel':5}} for d in dates],
            'sleep.json': [{'calendarDate':d,'sleepTimeSeconds':7*3600,'sleepScores':{'overall':{'value':95}},'sleepNeed':{'actual':510}} for d in dates],
            'hrv.json': [{'calendarDate':d,'lastNightAvg':60,'weeklyAvg':60,'status':'BALANCED','baseline':{'balancedLow':50,'balancedUpper':80}} for d in dates],
        }

    def test_absent_records_build_and_withhold_training(self):
        result = self.build({})
        self.assertIn('id="advisorDecision">Check your data first', result)
        self.assertIn('Daily <b>Unavailable</b>', result)

    def test_stale_records_never_grant_training_clearance(self):
        result = self.build(self.records(age=10))
        self.assertIn('id="advisorDecision">Check your data first', result)
        self.assertNotIn('Train as planned, but keep the first', result)

    def test_supportive_current_score_cannot_override_mixed_trend(self):
        result = self.build(self.records())
        self.assertIn('id="advisorDecision">Keep it controlled', result)
        self.assertNotIn('Train as planned, but keep the first', result)
        self.assertNotIn('points to target', result)
        self.assertNotIn('Speed reserve', result)
        self.assertIn('Test 30 minutes more time in bed', result)


if __name__ == '__main__':
    unittest.main()
