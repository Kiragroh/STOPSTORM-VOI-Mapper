import tempfile, unittest
from pathlib import Path
from voi_mapper.core import enforce_unique, laterality_conflict, check_endpoint
from voi_mapper.__main__ import load_rows, safe_cell, export_review
import csv

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
    def test_riva_is_not_rca(self):
        r=enforce_unique(rows('RIVA','RCA'),{'RIVA':('H_CA_right coronary artery',2),'RCA':('H_CA_right coronary artery',2)})
        self.assertEqual([x['automatic_master'] for x in r],['H_CA_left anterior descending artery','H_CA_right coronary artery'])
    def test_unspecified_vena_cava_is_extra(self):
        r=enforce_unique(rows('V_Venacava','V_Venacava_S'),{'V_Venacava':('GV_Vene cava superior',2),'V_Venacava_S':('GV_Vene cava superior',2)})
        self.assertEqual(r[0]['automatic_master'],'x')
        self.assertEqual(r[0]['extra_structure'],'Vena cava (unspecified)')
        self.assertEqual(r[1]['automatic_master'],'GV_Vene cava superior')
    def test_cropped_target_and_device_lead(self):
        r=enforce_unique(rows('PTV_crop','PTV','ICD electrode','ICD'),{'PTV_crop':('Target_PTV',2),'PTV':('Target_PTV',2),'ICD electrode':('ICD',2),'ICD':('ICD',2)})
        self.assertEqual([x['automatic_master'] for x in r],['x','Target_PTV','x','ICD'])
    def test_numbered_variants(self):
        for n in ['PTV_10','PTV_01','CardTV_1','PTV1.1']:
            r=enforce_unique(rows(n),{n:('Target_PTV',2)})
            self.assertEqual(r[0]['reason'],'Numbered target component')
    def test_plural_device_leads_are_not_generator(self):
        for name in ['ICD_leads','ICD leads','ICD lead','device.leads']:
            result=enforce_unique(rows(name),{name:('ICD',2)})
            self.assertEqual(result[0]['automatic_master'],'x')
            self.assertEqual(result[0]['reason'],'Device lead is not the generator')
    def test_zero_volume_excluded_unknown_kept(self):
        r=rows('Heart','Lung Left');r[0]['volume_cc']=0;r[1]['volume_cc']=None
        out=enforce_unique(r,{'Heart':('Heart',2),'Lung Left':('Lung Left',2)})
        self.assertEqual([x['automatic_master'] for x in out],['x','Lung Left'])
    def test_partial_name_with_underscores(self):
        out=enforce_unique(rows('Heart_partial'),{'Heart_partial':('Heart',2)})
        self.assertEqual(out[0]['automatic_master'],'x')
    def test_extra_export_and_missing_master(self):
        result=enforce_unique(rows('V_Venacava','Heart'),{'V_Venacava':('GV_Vene cava superior',2),'Heart':('Heart',2)})
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);export_review(out,result)
            with (out/'extras.csv').open(encoding='utf-8-sig') as f:extra=list(csv.DictReader(f))
            with (out/'missing_masters.csv').open(encoding='utf-8-sig') as f:missing=list(csv.DictReader(f))
            self.assertEqual(len(extra),1)
            self.assertEqual(len(missing),39)
            self.assertIn('class="extra"',(out/'review.html').read_text())
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
