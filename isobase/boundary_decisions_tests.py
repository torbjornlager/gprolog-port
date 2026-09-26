import copy
import unittest
from boundary_decisions import validate

class Decisions(unittest.TestCase):
    def test_complete(self):self.assertEqual(len(validate()),42)
    def test_missing_row(self):
        with self.assertRaisesRegex(AssertionError,'boundary ID'):validate(validate()[:-1])
    def test_duplicate_row(self):
        rows=copy.deepcopy(validate());rows[-1]=rows[0]
        with self.assertRaisesRegex(AssertionError,'boundary ID'):validate(rows)
    def test_required_waiver(self):
        rows=copy.deepcopy(validate());next(r for r in rows if r['probe'])['probe']=None
        with self.assertRaisesRegex(AssertionError,'Required probe missing'):validate(rows)
    def test_wrong_observation(self):
        rows=copy.deepcopy(validate());rows[0]['original_goal']='true'
        with self.assertRaisesRegex(AssertionError,'identity drift'):validate(rows)

if __name__=='__main__':unittest.main()
