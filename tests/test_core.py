import tempfile, unittest
from pathlib import Path
from voi_mapper.core import enforce_unique, laterality_conflict, check_endpoint
from voi_mapper.__main__ import load_rows, safe_cell

def rows(*names):
    return [{'case':'SYNTHETIC','key':str(i),'name':n} for i,n in enumerate(names)]

class CoreTests(unittest.TestCase):
    def test_duplicate_abstains(self):
        result=enforce_unique(rows('Lung_L','Left lung'),{'Lung_L':('Lung Left',2),'Left lung':('Lung Left',2)})
        self.assertTrue(all(r['automatic_master']=='x' for r in result))
    def test_exact_name_wins(self):
        result=enforce_unique(rows('Lung_L','Lung Left'),{'Lung_L':('Lung Left',2),'Lung Left':('Lung Left',2)})
        self.assertEqual([r['automatic_master'] for r in result],['x','Lung Left'])
    def test_two_identical_names_abstain(self):
        result=enforce_unique(rows('Heart','Heart'),{'Heart':('Heart',2)})
        self.assertEqual([r['automatic_master'] for r in result],['x','x'])
    def test_laterality(self):
        self.assertTrue(laterality_conflict('Lung_R','Lung Left'))
        self.assertTrue(laterality_conflict('Vorhof links','H_Chambers_Atrium_R'))
        self.assertFalse(laterality_conflict('Lung_L','Lung Left'))
    def test_uncertainty(self):
        self.assertEqual(enforce_unique(rows('ambiguous'),{'ambiguous':('Heart',1)})[0]['automatic_master'],'x')
    def test_numbered_target_needs_review(self):
        r=enforce_unique(rows('PTV_1','CTV2'),{'PTV_1':('Target_PTV',2),'CTV2':('CardTV',2)})
        self.assertTrue(all(x['automatic_master']=='x' and x['reason']=='Numbered target component' for x in r))
    def test_cases_independent(self):
        r=rows('Heart','Heart');r[1]['case']='OTHER'
        self.assertEqual(sum(x['automatic_master']=='Heart' for x in enforce_unique(r,{'Heart':('Heart',2)})),2)
    def test_remote_endpoint_refused(self):
        for url in ['https://example.com','http://127.0.0.1.example.com','http://localhost@evil.test','http://localhost:11434/api?x=2']:
            with self.assertRaises(ValueError):check_endpoint(url)
        self.assertEqual(check_endpoint('http://127.0.0.1:11434/'),'http://127.0.0.1:11434')
    def test_csv_injection(self):
        self.assertEqual(safe_cell('=HYPERLINK("bad")'),'\'=HYPERLINK("bad")')
        self.assertEqual(safe_cell(12.3),12.3)
    def test_duplicate_keys_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.csv';p.write_text('Case,ROI_ID,StructureName\nDEMO,1,Heart\nDEMO,1,Lung\n')
            with self.assertRaises(ValueError):load_rows(p)
    def test_missing_headers(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.csv';p.write_text('Patient,Structure\nDemo,Heart\n')
            with self.assertRaises(ValueError):load_rows(p)

if __name__=='__main__':unittest.main()
