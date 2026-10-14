# Spot-check report

| engine | scored | passed | pass rate | needs answer review |
| --- | ---: | ---: | ---: | ---: |
| release:data/kbb/serving/releases/20261014T005533322459Z | 139 | 132 | 95.0% | 17 |

## By topic (passed/total)

| topic | release:data/kbb/serving/releases/20261014T005533322459Z |
| --- | ---: |
| academics | 20/21 |
| admissions | 6/6 |
| calendar | 5/5 |
| campus | 2/3 |
| cutoffs | 42/42 |
| faculty | 3/4 |
| fees | 19/19 |
| finance | 15/15 |
| general | 5/5 |
| placements | 0/4 |
| scholarship | 15/15 |

## Failing cases – release:data/kbb/serving/releases/20261014T005533322459Z
- `new_hostel_count` (campus, english): terms_ok=False source_ok=False got=[{'file': 'admissions/JOSAA 2026 _ IIIT NAYA RAIPUR.pdf', 'page': 2}, {'file': 'general/Facilities _ IIIT NAYA RAIPUR.html', 'page': -1}, {'file': 'Faculty/*.html', 'page': -1}]
- `new_faculty_santosh` (faculty, english): terms_ok=True source_ok=False got=[{'file': 'Faculty/*.html', 'page': -1}, {'file': 'Faculty/Santosh Kumar _ IIIT NAYA RAIPUR.html', 'page': -1}, {'file': 'Faculty/Santosh Kumar _ IIIT NAYA RAIPUR.html', 'page': -1}]
- `new_median_ctc` (placements, english): terms_ok=False source_ok=True got=[{'file': 'academics/BTech_ECE_Syllabus_Book_IIIT-NR_2025.pdf', 'page': 1}, {'file': 'academics/BTech_ECE_Syllabus_Book_IIIT-NR_2025.pdf', 'page': 85}, {'file': 'academics/BTech_CSE_Syllabus_Book_IIIT-NR_2025.pdf', 'page': -1}]
- `new_top25_ctc` (placements, english): terms_ok=False source_ok=True got=[{'file': 'general/NIRFoverall.pdf', 'page': 2}, {'file': 'general/NIFRengineering.pdf', 'page': 2}, {'file': 'academics/BTech_ECE_Syllabus_Book_IIIT-NR_2025.pdf', 'page': 84}]
- `new_placed_students` (placements, english): terms_ok=False source_ok=True got=[{'file': 'general/NIFRengineering.pdf', 'page': 1}, {'file': 'general/NIFRengineering.pdf', 'page': 1}, {'file': 'Faculty/Manoj Kumar Majumder _ IIIT NAYA RAIPUR.html', 'page': -1}]
- `new_companies_recruited` (placements, english): terms_ok=False source_ok=True got=[{'file': 'general/IIIT-NR TBI&E.html', 'page': -1}, {'file': 'general/Facilities _ IIIT NAYA RAIPUR.html', 'page': -1}, {'file': 'Faculty/*.html', 'page': -1}]
- `new_curriculum_credits` (academics, english): terms_ok=False source_ok=True got=[{'file': 'academics/Curruculum/BTech/BTech_CSE_2025 ownwards.pdf', 'page': 2}, {'file': 'academics/Curruculum/BTech/BTech_CSE_2025 ownwards.pdf', 'page': 1}, {'file': 'academics/Curruculum/BTech/BTech_CSE_2025 ownwards.pdf', 'page': 4}]
