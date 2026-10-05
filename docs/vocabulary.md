# The 40-VOI catalogue

Canonical names from `voi_mapper/vocabulary.json`; these spellings are part of the software interface.

## Targets

- `CardTV`
- `Target_ITV`
- `Target_PTV`

## Cardiac structures

- `H_CA (Coronary arteries; combined)`
- `H_CA_left anterior descending artery`
- `H_CA_left circumflex artery`
- `H_CA_left main artery`
- `H_CA_right coronary artery`
- `H_Chambers_Atrium_L`
- `H_Chambers_Atrium_R`
- `H_Chambers_Ventricle_L`
- `H_Chambers_Ventricle_R`
- `H_LVW_anterior`
- `H_LVW_inferior`
- `H_LVW_lateral`
- `H_LVW_septal`
- `H_Nodes_atrioventricular`
- `H_Nodes_sinoatrial`
- `H_Valves_aortic`
- `H_Valves_mitral`
- `H_Valves_pulmonic`
- `H_Valves_tricuspid`
- `Heart`
- `Heart without PTV`

## Great vessels

- `Great Vessels`
- `GV_Aorta`
- `GV_Pulmonary artery`
- `GV_Vena cava inferior`
- `GV_Vene cava superior`

## Other organs and device

- `Bronchus`
- `Esophagus`
- `ICD`
- `Lung Left`
- `Lung Right`
- `Lungs`
- `Ribs`
- `Skin`
- `Spinal canal`
- `Stomach`
- `Trachea`

## Interpretation

CardTV groups historical TV/CTV/GTV labels for the STOPSTORM cardiac-substrate use case. ITV and PTV remain separate. This convention must not be transferred to tumour studies without adapting the vocabulary and prompt. The source spelling `GV_Vene cava superior` is retained for interface compatibility.

An unspecified vena cava is a separate review extra, not an additional master or an inferred vessel subtype. Names alone do not establish anatomical identity, complete contour extent or geometric equivalence.
