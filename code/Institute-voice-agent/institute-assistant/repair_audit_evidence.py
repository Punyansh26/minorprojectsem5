"""Apply source-hash-bound technical corrections from the Demo2 audit to a candidate build."""
import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from assistant.kb.common import read_json, write_json
from assistant.kb.policies import validate

BROCHURE = '3fdcf2d380898cd2bf3487f3aef0c808b634872470d418d438aa3941399ebbac'
REPORTING = '9729957089f7c6ae4e527813271d930d7cf80816b33ddf4f02a07c9b69837744'
LOAN = '407ea840edcdf28a5191fad968eacee35bb2f9b47db1102896d1182a34d6482b'


def repair(state):
    """Preserve printed conflicts and record technical review separately from staff approval."""
    blocks = {b['id']:b for b in read_json(state/'blocks.json')}
    reviews = read_json(state/'reviews.json',{})
    now = datetime.now(timezone.utc).isoformat()
    table = blocks['f846407e3cd57d8ed8f04ce9']
    if table['source_sha256'] != REPORTING or len(table['rows']) != 14:
        raise ValueError('Reporting source changed; a new visual review is required')
    heading = 'Documents to be Produced in Original at the Time of Verification\nNo. | Document\n'
    text = heading + table['text'].removeprefix(heading)
    reviews[table['id']] = dict(source_sha256=REPORTING,status='approved',reviewer='Codex technical review of original PDF pages 1–2',
        reviewed_at=now,text=text,audience='AI',review_by='2026-10-30',source_owner='unassigned',
        scope_note='JoSAA/CSAB 2026 All India reporting. Row 14 continues on page 2; bank charges are separate. The printed amount is ₹18,1000.',
        related_evidence_block_ids=['796e132f37847af97e619507'],
        notes='Compared all 14 rows and conditional certificates with rendered original pages. This is extraction review, not institute-staff policy signoff.')
    reviews['421dfda433017502c35836fe'].update(audience='CG_NTPC',source_owner='unassigned',review_by='2026-10-30',
        conflict_note='The 2026 brochure prints a JEE (Main) 2024 rank card for CG/NTPC. The year is unresolved; confirm it with admissions. All India applicants follow JoSAA instructions.')
    # Keep native parents intact; apply only source-bound review entries to candidate blocks.
    for key,review in reviews.items():
        if key not in blocks or blocks[key]['source_sha256'] != review['source_sha256']:
            continue
        for field in ('text','years','period','rows','programme','historical','kind','topic','audience','conflict_note',
                      'scope_note','source_owner','review_by','related_evidence_block_ids'):
            if field in review: blocks[key][field] = review[field]
        blocks[key].update(verification_status=review['status'],reviewer=review['reviewer'],reviewed_at=review['reviewed_at'])
    # Eligibility details on the following page must accompany the primary criteria.
    blocks['eeff84ab2204033b8fec2d2e']['related_evidence_block_ids'] = ['d23ff110d32391bfd6cb44bc']
    reviews['eeff84ab2204033b8fec2d2e'] = dict(source_sha256=BROCHURE,status='approved',reviewer='Codex technical comparison with original brochure pages 8–9',
        reviewed_at=now,related_evidence_block_ids=['d23ff110d32391bfd6cb44bc'],source_owner='unassigned',review_by='2026-10-30')
    rules = []
    def spans(key):
        b = blocks[key]
        # Complete contiguous pieces; each keeps the exact page and original punctuation.
        pieces, current = [], ''
        for line in b['text'].splitlines():
            if len(current)+len(line)+1 > 1400:
                pieces.append(current); current=''
            current += ('\n' if current else '')+line
        if current: pieces.append(current)
        return [dict(source_sha256=b['source_sha256'],page_number=b['page_number'],quote=p) for p in pieces]
    def add(name,match,answers,evidence=(),exclude='',year=None,clarification=False):
        rules.append(dict(id=name,match=match,exclude=exclude,year=year,clarification=clarification,
            answers=dict(zip(('english','hindi','hinglish'),answers)),evidence=list(evidence)))
    fee = spans('a7706e3de1bd1e95647ab0fb')
    add('reporting_quota',r'(?=.*(?:document|certificate))(?=.*(?:report|admission|verification))',[
        'Which reporting route do you mean: JoSAA/CSAB All India, Chhattisgarh quota, or NTPC quota? The document requirements differ.',
        'आप किस प्रवेश प्रक्रिया के दस्तावेज पूछ रहे हैं: जोसा/सीसैब ऑल इंडिया, छत्तीसगढ़ कोटा या एनटीपीसी कोटा? इनके नियम अलग हैं।',
        'Aap kis reporting route ke documents pooch rahe hain: JoSAA/CSAB All India, Chhattisgarh quota, ya NTPC quota? Inke rules alag hain.'],
        exclude=r'josaa|csab|all india|chhattisgarh|\bcg\b|ntpc',clarification=True)
    checklist = spans(table['id']) + [dict(source_sha256=REPORTING,page_number=2,quote='levied by the banker will be collected separately.')]
    add('reporting_all_india_2026',r'(?=.*(?:josaa|csab|all india))(?=.*(?:documents?|certificates?|reporting))',[
        'For JoSAA/CSAB 2026 All India reporting, produce originals of Class 10 and 12 marksheets/pass certificates, transfer, migration and character certificates; applicable SC/ST/OBC-NCL/EWS and PwD certificates; the JEE (Main) 2026 rank card showing CRL; photo identity and permanent-address proof; medical fitness certificate; four colour passport photos; signed online anti-ragging undertaking; and balance-fee payment after JoSAA/CSAB adjustments. OBC-NCL/EWS status must be retained after 1 April 2026 in the JoSAA format; an undertaking is required after eligibility verification. Bank GST/transaction charges are separate. These are not the CG/NTPC checklist.',
        'जोसा/सीसैब 2026 ऑल इंडिया रिपोर्टिंग में मूल दस्तावेज लाएँ: कक्षा 10 और 12 की अंकसूची/पास प्रमाणपत्र, स्थानांतरण, माइग्रेशन और चरित्र प्रमाणपत्र; लागू होने पर एससी/एसटी/ओबीसी-एनसीएल/ईडब्ल्यूएस और दिव्यांगता प्रमाणपत्र; सीआरएल दिखाने वाला जेईई मेन 2026 रैंक कार्ड; फोटो पहचान और स्थायी पते का प्रमाण; चिकित्सा फिटनेस प्रमाणपत्र; चार रंगीन पासपोर्ट फोटो; ऑनलाइन बना हस्ताक्षरित एंटी रैगिंग शपथपत्र; और जोसा/सीसैब समायोजन के बाद शेष शुल्क। ओबीसी-एनसीएल/ईडब्ल्यूएस स्थिति 1 अप्रैल 2026 के बाद जोसा प्रारूप के अनुसार बनी हो और पात्रता जाँच के बाद अंडरटेकिंग देना होगा। बैंक के जीएसटी/लेनदेन शुल्क अलग हैं। यह सीजी/एनटीपीसी सूची नहीं है।',
        'JoSAA/CSAB 2026 All India reporting ke liye originals laayen: Class 10 aur 12 marksheets/pass certificates, transfer, migration aur character certificates; applicable SC/ST/OBC-NCL/EWS aur PwD certificates; CRL wala JEE Main 2026 rank card; photo ID aur permanent-address proof; medical fitness certificate; chaar colour passport photos; signed online anti-ragging undertaking; aur JoSAA/CSAB adjustment ke baad balance fee. OBC-NCL/EWS status 1 April 2026 ke baad JoSAA format mein retained hona chahiye; eligibility verification ke baad undertaking chahiye. Bank GST/transaction charges alag hain. Yeh CG/NTPC checklist nahi hai.'],checklist,year=2026)
    for name,match,en,hi,hing in [
        ('tuition',r'tuition', 'The B.Tech 2026–2030 fee schedule lists tuition of ₹90,000; this is not the total fee.', 'बीटेक 2026–2030 शुल्क सूची में शिक्षण शुल्क ₹90,000 है; यह कुल शुल्क नहीं है।', 'B.Tech 2026–2030 schedule mein tuition ₹90,000 hai; yeh total fee nahi hai.'),
        ('hostel_fee',r'hostel.*(?:fee|charge)|(?:fee|charge).*hostel', 'The B.Tech 2026–2030 schedule lists hostel fee of ₹15,000, separately from the ₹25,000 mess advance.', 'बीटेक 2026–2030 सूची में छात्रावास शुल्क ₹15,000 है; ₹25,000 भोजन अग्रिम अलग है।', 'B.Tech 2026–2030 mein hostel fee ₹15,000 hai; ₹25,000 mess advance alag hai.'),
        ('mess_advance',r'mess.*(?:fee|advance|charge)|(?:fee|advance).*mess', 'The B.Tech 2026–2030 schedule lists a ₹25,000 mess advance, separately from the ₹15,000 hostel fee.', 'बीटेक 2026–2030 सूची में भोजन अग्रिम ₹25,000 है; ₹15,000 छात्रावास शुल्क अलग है।', 'B.Tech 2026–2030 mein mess advance ₹25,000 hai; ₹15,000 hostel fee alag hai.'),
        ('caution',r'caution|refundable.*deposit|one.?time', 'The B.Tech 2026–2030 one-time fee is ₹31,000, including a refundable caution deposit of ₹15,000. Only the caution deposit is identified as refundable.', 'बीटेक 2026–2030 में एक बार का शुल्क ₹31,000 है, जिसमें ₹15,000 वापसी योग्य सावधानी जमा शामिल है। केवल सावधानी जमा को वापसी योग्य बताया गया है।', 'B.Tech 2026–2030 one-time fee ₹31,000 hai, jismein refundable caution deposit ₹15,000 included hai. Sirf caution deposit ko refundable bataya gaya hai.'),
        ('fees_total',r'fees?|cost.*semester', 'For the B.Tech 2026–2030 cohort, total Semester I fee is ₹1,81,000; Semester II onwards is ₹1,50,000. The first-semester institution subtotal ₹1,41,000 includes ₹31,000 one-time charges (₹15,000 refundable caution deposit), ₹90,000 tuition and ₹20,000 academic/student welfare fee; hostel ₹15,000 and mess advance ₹25,000 are additional to that subtotal.', 'बीटेक 2026–2030 के लिए प्रथम सेमेस्टर का कुल शुल्क ₹1,81,000 और दूसरे सेमेस्टर से ₹1,50,000 है। पहले सेमेस्टर के संस्थान उप-योग ₹1,41,000 में ₹31,000 एक बार का शुल्क (₹15,000 वापसी योग्य जमा), ₹90,000 शिक्षण और ₹20,000 शैक्षणिक/छात्र कल्याण शुल्क हैं। छात्रावास ₹15,000 और भोजन अग्रिम ₹25,000 इस उप-योग से अलग हैं।', 'B.Tech 2026–2030 ke liye Semester I total ₹1,81,000 aur Semester II onwards ₹1,50,000 hai. First-semester institution subtotal ₹1,41,000 mein ₹31,000 one-time charges (₹15,000 refundable deposit), ₹90,000 tuition aur ₹20,000 academic/student welfare fee hain. Hostel ₹15,000 aur mess advance ₹25,000 subtotal ke alag hain.')]:
        add(name+'_2026',match,[en,hi,hing],fee,exclude=r'vidya|scholarship|reimburse|application|loan|laundry|waiv|discount|refund policy|instal|install|payment.*plan|pay.*three',year=2026)
    eligibility = spans('eeff84ab2204033b8fec2d2e') + spans('d23ff110d32391bfd6cb44bc')
    add('cg_eligibility_2026',r'(?=.*(?:chhattisgarh|\bcg\b))(?=.*(?:eligib|admission|criteria))',[
        'For the 2026 Chhattisgarh quota, both Classes 10 and 12 must be from schools in Chhattisgarh. Class 12 PCM aggregate must be at least 50% (45% for SC/ST/OBC-NCL/PwD). Date of birth must be on/after 1 October 2000, relaxed to 1 October 1997 for those reserved categories. Eligible pass years are 2024, 2025 or 2026; a candidate who appeared and failed in 2023 but passed in 2024 is ineligible. Reserved-category certificates must be issued by the Chhattisgarh authority in the candidate’s own name at application; parents’ certificates are unacceptable. OBC-NCL certificates must be issued on/after 1 April 2026. Additional prescribed certificates apply for freedom-fighter/ex-servicemen wards and PwD applicants.',
        '2026 छत्तीसगढ़ कोटा के लिए कक्षा 10 और 12 दोनों छत्तीसगढ़ के स्कूलों से हों। कक्षा 12 में भौतिकी, रसायन और गणित का कुल न्यूनतम 50% है (एससी/एसटी/ओबीसी-एनसीएल/दिव्यांग के लिए 45%)। जन्मतिथि 1 अक्टूबर 2000 या बाद की हो; इन आरक्षित वर्गों को 1 अक्टूबर 1997 तक छूट है। पास वर्ष 2024, 2025 या 2026 हो; 2023 में परीक्षा देकर असफल और 2024 में पास अभ्यर्थी पात्र नहीं है। आवेदन के समय आरक्षित वर्ग का प्रमाणपत्र छत्तीसगढ़ प्राधिकारी से अभ्यर्थी के अपने नाम पर हो; माता-पिता का प्रमाणपत्र स्वीकार नहीं है। ओबीसी-एनसीएल प्रमाणपत्र 1 अप्रैल 2026 या बाद का हो। स्वतंत्रता सेनानी/पूर्व सैनिक आश्रित और दिव्यांग अभ्यर्थियों के अतिरिक्त निर्धारित प्रमाणपत्र भी लागू हैं।',
        '2026 CG quota mein Class 10 aur 12 dono Chhattisgarh schools se hon. Class 12 PCM aggregate minimum 50% hai (SC/ST/OBC-NCL/PwD ke liye 45%). DOB 1 October 2000 ya baad ho; in reserved categories ko 1 October 1997 tak relaxation hai. Pass year 2024, 2025 ya 2026 ho; 2023 mein appear hokar fail aur 2024 mein pass candidate eligible nahi hai. Reserved certificate CG authority se candidate ke apne naam par application ke waqt ho; parents ka certificate acceptable nahi hai. OBC-NCL certificate 1 April 2026 ya baad issued ho. Freedom-fighter/ex-servicemen wards aur PwD applicants ke additional prescribed certificates bhi apply hote hain.'],eligibility,exclude=r'rank|cut.?off|document|certificate.*report|seat|reserv.*percent',year=2026)
    loan2 = blocks['c7a239d3c84173a2c5f2173d']
    repayment = re.search(r'2\.8\..*?(?=\n2\.9)',loan2['text'],re.S).group()
    exclusion = re.search(r'5\.6\..*?(?=\n5\.7)',blocks['7175ae9f72e5482b3eb1d927']['text'],re.S).group()
    add('loan_repayment',r'(?=.*(?:vidya.?laxmi))(?=.*(?:repay|moratorium|repayment))',[
        'The PM-Vidyalaxmi guidelines allow repayment over up to 15 years, excluding the moratorium of the course period plus one year. These general guidelines do not establish current IIIT-NR or individual eligibility.',
        'पीएम विद्यालक्ष्मी दिशानिर्देशों में ऋण चुकाने की अवधि अधिकतम 15 वर्ष है; पाठ्यक्रम अवधि और उसके बाद एक वर्ष का स्थगन इसमें शामिल नहीं है। ये सामान्य नियम वर्तमान संस्थान या व्यक्तिगत पात्रता प्रमाणित नहीं करते।',
        'PM-Vidyalaxmi guidelines mein repayment up to 15 years hai, course period plus one year ka moratorium ismein included nahi hai. Yeh general rules current IIIT-NR ya individual eligibility establish nahi karte.'],[dict(source_sha256=LOAN,page_number=2,quote=repayment),dict(source_sha256=LOAN,page_number=6,quote='9.1. Under the Scheme, moratorium period is defined as Course Period plus one year.')],exclude=r'principal|मूलधन')
    add('loan_exclusion',r'(?=.*vidya.?laxmi)(?=.*(?:combin|another|other.*scholarship|fee reimbursement|exclu))',[
        'No. Section 5.6 of the PM-Vidyalaxmi guidelines excludes students already receiving another Central/State Government scholarship, interest-subvention scheme or fee reimbursement from benefits under this scheme. This is a general rule, not confirmation of current IIIT-NR or individual eligibility.',
        'नहीं। पीएम विद्यालक्ष्मी के खंड 5.6 के अनुसार अन्य केंद्र/राज्य सरकारी छात्रवृत्ति, ब्याज सहायता या शुल्क प्रतिपूर्ति पाने वाला छात्र इस योजना के लाभों का पात्र नहीं है। यह सामान्य नियम है, वर्तमान संस्थान या व्यक्तिगत पात्रता की पुष्टि नहीं।',
        'Nahi. PM-Vidyalaxmi section 5.6 ke mutabik doosri Central/State Government scholarship, interest-subvention scheme ya fee reimbursement lene wala student is scheme ke benefits ke liye eligible nahi hai. Yeh general rule hai, current IIIT-NR ya individual eligibility ki confirmation nahi.'],[dict(source_sha256=LOAN,page_number=4,quote=exclusion)])
    add('reporting_cg_ntpc_2026',r'(?=.*(?:chhattisgarh|\bcg\b|ntpc))(?=.*(?:documents?|certificates?|reporting))',[
        'The 2026 brochure lists Class 10 and 12 pass marksheets; original transfer, character, migration and medical certificates; applicable PwD and SC/ST/OBC-NCL certificates; and a JEE Main rank card. It prints 2024 for that rank card: the year conflicts with the 2026 brochure and must be confirmed with admissions. CG applicants additionally need applicable ex-servicemen/freedom-fighter/PwD certificates; NTPC applicants need the original NTPC employee-ward certificate. A permanent caste certificate must be held at online application; temporary caste certificates are not accepted. All India applicants follow the separate JoSAA instructions.',
        '2026 विवरणिका में कक्षा 10 और 12 की पास अंकसूची; मूल स्थानांतरण, चरित्र, माइग्रेशन और चिकित्सा प्रमाणपत्र; लागू दिव्यांगता तथा एससी/एसटी/ओबीसी-एनसीएल प्रमाणपत्र; और जेईई मेन रैंक कार्ड हैं। रैंक कार्ड का वर्ष 2024 छपा है, जो 2026 विवरणिका से विरोधाभासी है; प्रवेश कार्यालय से वर्ष की पुष्टि करें। छत्तीसगढ़ में लागू पूर्व सैनिक/स्वतंत्रता सेनानी/दिव्यांग प्रमाणपत्र और एनटीपीसी में मूल कर्मचारी-आश्रित प्रमाणपत्र चाहिए। ऑनलाइन आवेदन के समय स्थायी जाति प्रमाणपत्र हो; अस्थायी प्रमाणपत्र स्वीकार नहीं है। ऑल इंडिया के लिए अलग जोसा निर्देश लागू हैं।',
        '2026 brochure mein Class 10 aur 12 pass marksheets; original transfer, character, migration aur medical certificates; applicable PwD aur SC/ST/OBC-NCL certificates; aur JEE Main rank card listed hain. Rank card year 2024 printed hai, jo 2026 brochure se conflict karta hai: admissions se year confirm karein. CG mein applicable ex-servicemen/freedom-fighter/PwD certificates; NTPC mein original employee-ward certificate chahiye. Online application ke waqt permanent caste certificate ho; temporary certificate acceptable nahi hai. All India applicants ke liye alag JoSAA instructions hain.'],spans('421dfda433017502c35836fe'),year=2026)
    add('loan_security',r'(?=.*(?:vidya.?laxmi|विद्या.?लक्ष्मी))(?=.*(?:collateral|guarant|जमानत|गारंट))',[
        'The general PM-Vidyalaxmi guidelines describe collateral-free and guarantor-free education loans for merit-based admission to qualifying higher education institutions. Management-quota admissions are excluded. Section 5.6 also excludes students receiving another Central/State Government scholarship, interest subvention or fee reimbursement. This does not confirm current IIIT-NR or individual eligibility.',
        'सामान्य पीएम विद्यालक्ष्मी नियम योग्य उच्च शिक्षण संस्थान में मेरिट से प्रवेश के लिए बिना जमानत और बिना गारंटर शिक्षा ऋण बताते हैं। प्रबंधन कोटा प्रवेश पात्र नहीं है। खंड 5.6 में अन्य केंद्र/राज्य सरकारी छात्रवृत्ति, ब्याज सहायता या शुल्क प्रतिपूर्ति पाने वाले छात्र भी लाभों से बाहर हैं। इससे वर्तमान संस्थान या व्यक्तिगत पात्रता की पुष्टि नहीं होती।',
        'General PM-Vidyalaxmi rules qualifying HEIs mein merit admission ke liye collateral-free aur guarantor-free education loan batate hain. Management-quota admission eligible nahi hai. Section 5.6 mein doosri Central/State scholarship, interest subvention ya fee reimbursement lene wale students bhi benefits se excluded hain. Current IIIT-NR ya individual eligibility confirm nahi hoti.'],spans('c7a239d3c84173a2c5f2173d')+[dict(source_sha256=LOAN,page_number=4,quote=exclusion)])
    add('loan_principal',r'(?=.*vidya.?laxmi)(?=.*(?:principal|मूलधन))',[
        'Yes. The borrower must repay the entire education-loan principal and any outstanding interest due to non-payment. The guidelines also require the borrower to pay the remaining moratorium interest and all interest after the moratorium under the bank agreement. These are general scheme conditions, not confirmation of current IIIT-NR or individual eligibility.',
        'हाँ। पूरा शिक्षा ऋण मूलधन और मूलधन न चुकाने के कारण बकाया ब्याज उधारकर्ता को देना है। स्थगन अवधि में शेष ब्याज और उसके बाद बैंक समझौते के अनुसार पूरा ब्याज भी देना है। ये सामान्य योजना नियम हैं, वर्तमान संस्थान या व्यक्तिगत पात्रता की पुष्टि नहीं।',
        'Haan. Borrower ko poora education-loan principal aur principal na chukane se outstanding interest repay karna hai. Moratorium ka remaining interest aur uske baad bank agreement ke mutabik poora interest bhi dena hai. Yeh general scheme conditions hain, current IIIT-NR ya individual eligibility ki confirmation nahi.'],spans('af545ca099fb6397bea57b5f'))
    policies = dict(version=1,review_kind='technical_source_fidelity',independent_staff_review=False,rules=rules)
    validate(policies,blocks)
    write_json(state/'reviews.json',reviews)
    write_json(state/'blocks.json',list(blocks.values()))
    write_json(state/'policies.json',policies)
    return {'policies':len(rules),'reporting_rows':len(table['rows']),'staff_review':'pending'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--state',type=Path,required=True)
    print(json.dumps(repair(parser.parse_args().state)))
