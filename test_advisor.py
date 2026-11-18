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
            for name in ('build.py', 'advisor_ui.py', 'advisor.js', 'advisor.css', 'advisor_portal.py', 'advisor_engine.py', 'advisor_v2.js', 'advisor_v2.css', 'routine.json'):
                shutil.copyfile(ROOT / name, root / name)
            (root / 'data').mkdir()
            for name, value in records.items():
                (root / 'data' / name).write_text(json.dumps(value), encoding='utf-8')
            subprocess.run([sys.executable, str(root/'build.py')], check=True, capture_output=True)
            return (root/'dashboard.html').read_text(encoding='utf-8')

    @staticmethod
    def embedded_data(result):
        payload = result.split('const DATA=', 1)[1]
        return json.JSONDecoder().raw_decode(payload)[0]

    def records(self, age=0):
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        dates = [(today-timedelta(days=i+age)).isoformat() for i in range(35)]
        return {
            'daily_summaries.json': [{'calendarDate':d,'heartRate':{'restingValue':54},'bodyBattery':{'latestValue':95},'stress':{'avgLevel':5}} for d in dates],
            'sleep.json': [{'calendarDate':d,'sleepTimeSeconds':7*3600,'sleepScores':{'overall':{'value':95}},'sleepNeed':{'actual':510}} for d in dates],
            'hrv.json': [{'calendarDate':d,'lastNightAvg':60,'weeklyAvg':60,'status':'BALANCED','baseline':{'balancedLow':50,'balancedUpper':80}} for d in dates],
        }

    def test_absent_records_build_and_lower_confidence(self):
        data = self.embedded_data(self.build({}))
        self.assertEqual(data['defaultDecision']['confidence'], 'low')
        self.assertCountEqual(data['defaultDecision']['missingInputs'], ['resting heart rate', 'overnight HRV', 'sleep'])
        self.assertIsNone(data['current']['daily'].get('stress'))

    def test_stale_records_are_not_used_as_current_signals(self):
        data = self.embedded_data(self.build(self.records(age=10)))
        self.assertIsNone(data['current']['daily'].get('rhr'))
        self.assertIn('resting heart rate', data['defaultDecision']['missingInputs'])
        self.assertIn('overnight HRV', data['defaultDecision']['missingInputs'])

    def test_negative_stress_and_missing_hrv_never_support_rhr_spike(self):
        records = self.records()
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
        daily = next(item for item in records['daily_summaries.json'] if item['calendarDate'] == today)
        daily['heartRate'] = {'restingValue': 76, 'minValue': 76, 'maxValue': 76}
        daily['stress'] = {'avgLevel': -1}
        hrv = next(item for item in records['hrv.json'] if item['calendarDate'] == today)
        hrv['lastNightAvg'] = None
        data = self.embedded_data(self.build(records))
        self.assertIsNone(data['current']['daily']['stress'])
        self.assertIsNone(data['current']['hrv']['night'])
        self.assertEqual(data['defaultDecision']['verdict'], 'UNCONFIRMED')
        self.assertIn('overnight HRV', data['defaultDecision']['missingInputs'])
        self.assertIn('confirm the morning reading', json.dumps(data['defaultDecision']).lower())
        self.assertFalse(data['planWeeks'][-2]['active'])
        self.assertEqual(data['adherenceWeeks'], 1)
        self.assertEqual(data['currentWeek']['easyRunsTotal'], 3)


if __name__ == '__main__':
    unittest.main()
