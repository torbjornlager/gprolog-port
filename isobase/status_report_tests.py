"""Reconciliation must fail when a required mapping or evidence link disappears."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import status_report

class Reconciliation(unittest.TestCase):
    def modified_input(self,name,change,error):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for source in status_report.ROOT.iterdir():(root/source.name).symlink_to(source,target_is_directory=source.is_dir())
            path=root/name;data=json.loads(path.read_text());path.unlink();change(data);path.write_text(json.dumps(data))
            with patch.object(status_report,'ROOT',root),self.assertRaisesRegex(AssertionError,error):status_report.render()
    def test_required_predicate_cannot_disappear(self):
        self.modified_input('predicate-inventory.json',lambda rows:rows.pop(0),'required mapping drift')
    def test_missing_evidence_cannot_pass(self):
        self.modified_input('status-obligations.json',lambda data:data['obligations'][0]['evidence'].append('missing-test.py'),'Missing obligation mapping file')
    def test_unknown_decision_cannot_pass(self):
        self.modified_input('status-obligations.json',lambda data:data['obligations'][0].update(decision='D99'),'D99')
    def test_required_result_cannot_disappear(self):
        self.modified_input('boundary-evidence.json',lambda data:data['results'].pop(),'Incomplete targeted evidence')
    def test_required_failure_cannot_be_unscored(self):
        self.modified_input('boundary-evidence.json',lambda data:data['results'][0].update({'pass':None}),'Unscored required evidence')
    def test_generated_report_is_current(self):
        self.assertEqual((status_report.ROOT/'STATUS.md').read_text(),status_report.render())

if __name__=='__main__':unittest.main()
