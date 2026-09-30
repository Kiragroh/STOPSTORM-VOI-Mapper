"""Read ROI names only. DICOM remains unchanged; no PatientName/PatientID export."""
from pathlib import Path
import argparse, csv, hashlib, sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('folder',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--case',required=True,help='User-supplied pseudonymous case ID')
    args=p.parse_args()
    try:import pydicom
    except ImportError:p.error('Install the optional reader: pip install pydicom')
    if not args.folder.is_dir():p.error('Input must be a case directory')
    if args.output.exists():p.error('Output exists; choose a new filename')
    sets=[];errors=0
    for file in sorted(args.folder.rglob('*')):
        if not file.is_file():continue
        try:
            ds=pydicom.dcmread(file,stop_before_pixels=True,specific_tags=['Modality','StructureSetROISequence'],force=True)
            if getattr(ds,'Modality','')!='RTSTRUCT':continue
            rois=[(str(r.ROINumber),str(r.ROIName)) for r in getattr(ds,'StructureSetROISequence',[])]
            if rois:sets.append((file,rois))
        except Exception:errors+=1
    if len(sets)!=1:p.error(f'Expected exactly one readable RTSTRUCT, found {len(sets)}. Select a case folder with the intended structure set; no automatic selection.')
    file,rois=sets[0]
    from .__main__ import write_csv
    write_csv(args.output,['Case','ROI_ID','StructureName','Volume_cc','SourceGroup'],[[args.case,i,name,'','RTSTRUCT'] for i,name in rois])
    print(f'Exported {len(rois)} ROI names. Skipped unreadable files: {errors}. RTSTRUCT SHA256: {hashlib.sha256(file.read_bytes()).hexdigest()}')

if __name__=='__main__':main()
