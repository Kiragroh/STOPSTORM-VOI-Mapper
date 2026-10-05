"""Render public synthetic naming examples. Requires matplotlib for docs only."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'
masters=json.loads((ROOT/'voi_mapper/vocabulary.json').read_text(encoding='utf8'))
examples=[
    ('Heart / heart / Herz / Coeur','Heart','Check the contour,\nnot only its label.'),
    ('Lung_L / L Lung / Lunge links','Lung Left','Keep left and right\nseparate.'),
    ('LAD / RIVA','H_CA_left anterior\ndescending artery','A coronary subsegment is not\nthe entire named artery.'),
    ('TV / CTV / GTV / CardTV','CardTV','STOPSTORM target convention;\nITV and PTV remain separate.'),
    ('Vena cava','Unspecified vena cava\n(review extra)','Do not infer superior\nor inferior.'),
    ('Heart_PRV / PTV_1 / ICD_lead','Manual review /\noutside master assignment','Risk volume, target component\nand device lead are not synonyms.'),
]
plt.rcParams.update({'font.family':'DejaVu Sans','svg.fonttype':'none','font.size':13})
fig,ax=plt.subplots(figsize=(15,8.8));fig.patch.set_facecolor('white');ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ink='#183244';blue='#087fa7';gray='#69737d';line='#dbe3e8'
ax.text(.015,.965,'Different names, reviewable VOI assignments',fontsize=23,fontweight='bold',color=ink,va='top')
ax.text(.015,.901,'SYNTHETIC EXAMPLES  |  No patient labels, study frequencies or model-performance results',fontsize=10,color=gray)
for x,title in [(.025,'Illustrative source labels'),(.425,'Candidate master'),(.735,'Review boundary')]:
    ax.text(x,.832,title,fontsize=14,fontweight='bold',color=ink)
for i,(source,target,boundary) in enumerate(examples):
    top=.79-i*.113;y=top-.037;color=gray if i>=4 else blue
    ax.plot([.015,.985],[top,top],color=line,lw=1)
    ax.text(.025,y,source,color=ink,va='center',fontsize=12.5)
    ax.annotate('',xy=(.4,y),xytext=(.372,y),arrowprops={'arrowstyle':'->','color':color,'lw':1.5})
    ax.text(.425,y,target,color=color,va='center',fontweight='bold',fontsize=12.3,linespacing=1.4)
    ax.text(.735,y,boundary,color=ink,va='center',fontsize=11.5,linespacing=1.45)
ax.text(.015,.045,'Terminology relationships are proposals for human review, not guaranteed automatic mappings.',fontsize=11,color=gray)
fig.subplots_adjust(left=.02,right=.98,top=.99,bottom=.02)
fig.canvas.draw()
renderer=fig.canvas.get_renderer()
# Catch clipped or overlapping labels before publishing generated figures.
labels=[t for t in ax.texts if t.get_text()]
boxes=[t.get_window_extent(renderer) for t in labels]
assert all(b.x0>=0 and b.y0>=0 and b.x1<=fig.bbox.width and b.y1<=fig.bbox.height for b in boxes)
assert not any(a.overlaps(b) for i,a in enumerate(boxes) for b in boxes[i+1:]),'Overlapping figure labels'
for ext in ['png','svg']:
    fig.savefig(OUT/f'naming-variation.{ext}',dpi=160,facecolor='white',metadata={'Creator':'STOPSTORM VOI Mapper documentation'})
plt.close(fig)
header='# The 40-VOI catalogue\n\nCanonical names from `voi_mapper/vocabulary.json`; these spellings are part of the software interface.\n\n'
groups=[('Targets',[m for m in masters if m in {'CardTV','Target_ITV','Target_PTV'}]),
        ('Cardiac structures',[m for m in masters if m.startswith('H_') or m in {'Heart','Heart without PTV'}]),
        ('Great vessels',[m for m in masters if m.startswith('GV_') or m=='Great Vessels']),
        ('Other organs and device',[m for m in masters if not m.startswith(('H_','GV_')) and m not in {'Heart','Heart without PTV','Great Vessels','CardTV','Target_ITV','Target_PTV'}])]
assert len(masters)==40 and sorted(m for _,group in groups for m in group)==sorted(masters)
body=''.join('## '+title+'\n\n'+''.join('- `'+m+'`\n' for m in group)+'\n' for title,group in groups)
footer=('## Interpretation\n\nCardTV groups historical TV/CTV/GTV labels for the STOPSTORM cardiac-substrate use case. '
        'ITV and PTV remain separate. This convention must not be transferred to tumour studies without adapting the vocabulary and prompt. '
        'The source spelling `GV_Vene cava superior` is retained for interface compatibility.\n\n'
        'An unspecified vena cava is a separate review extra, not an additional master or an inferred vessel subtype. '
        'Names alone do not establish anatomical identity, complete contour extent or geometric equivalence.\n')
(OUT/'vocabulary.md').write_text(header+body+footer,encoding='utf8')
print('Rendered synthetic naming figure and verified 40-master catalogue.')
