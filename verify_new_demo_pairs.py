from pathlib import Path
from extraction import extract_document, normalize_documents
root=Path(r'C:\MediGaurd AI\sample_documents')
pairs=[('demo_1_medical_bill_CLM-DEMO-APPROVED-001.pdf','demo_1_policy_POL-DEMO-APPROVED-2026.pdf'),('demo_2_medical_bill_CLM-DEMO-PARTIAL-002.pdf','demo_2_policy_POL-DEMO-PARTIAL-2026.pdf')]
for i,(bill_name,policy_name) in enumerate(pairs,1):
    bill_evidence,bill_raw,bill_pages=extract_document(root/bill_name, f'demo_bill_{i}', bill_name)
    policy_evidence,policy_raw,policy_pages=extract_document(root/policy_name, f'demo_policy_{i}', policy_name)
    bill_doc={'document_id':f'demo_bill_{i}','document_type':'medical_bill','text':'\n'.join(bill_raw.values()),'evidence':[x.to_dict() for x in bill_evidence],'raw_by_page':bill_raw,'original_name':bill_name}
    policy_doc={'document_id':f'demo_policy_{i}','document_type':'policy','text':'\n'.join(policy_raw.values()),'evidence':[x.to_dict() for x in policy_evidence],'raw_by_page':policy_raw,'original_name':policy_name}
    normalized=normalize_documents([bill_doc,policy_doc]).to_dict()
    print('PAIR',i)
    print('NORMALIZED',normalized)
    assert normalized['patient_name']['value']
    assert normalized['hospital_name']['value']
    assert float(normalized['total_amount']['value']) > 0
    assert normalized['policy_number']['value'] == normalized['policy_number']['value']
print('NEW_DEMO_PAIRS_NORMALIZATION_OK')
