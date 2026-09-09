import io
from app import _validated_upload
from extraction import normalize_documents

class Upload:
    def __init__(self, name, data):
        self.name = name
        self._data = data
    def getvalue(self):
        return self._data


def expect_error(upload, fragment):
    try:
        _validated_upload(upload)
    except ValueError as exc:
        assert fragment in str(exc), (str(exc), fragment)
    else:
        raise AssertionError(f'Expected validation error containing {fragment!r}')

expect_error(Upload('claim.exe', b'MZ' + b'0' * 20), 'Unsupported file type')
expect_error(Upload('empty.pdf', b''), 'empty')
expect_error(Upload('fake.pdf', b'not a pdf'), 'signature')
expect_error(Upload('fake.png', b'not an image'), 'signature')

missing = normalize_documents([{
    'document_id': 'bill-1', 'original_name': 'bill.png', 'document_type': 'medical_bill',
    'text': 'Patient Name: Jane Doe\nTotal Amount: INR 145000',
    'evidence': [],
}]).to_dict()
assert 'hospital_name' in missing['missing_fields'], missing

low_confidence = normalize_documents([{
    'document_id': 'bill-2', 'original_name': 'bill.png', 'document_type': 'medical_bill',
    'text': 'Patient Name: Jane Doe\nHospital: City Care Hospital\nPolicy Number: POL-1\nClaim Number: CLM-1\nDiagnosis: Acute appendicitis\nTotal Amount: INR 145000',
    'evidence': [{'document_id': 'bill-2', 'source_name': 'bill.png', 'page': 1, 'method': 'tesseract', 'text': 'low confidence', 'confidence': 45}],
}]).to_dict()
assert 'patient_name' in low_confidence['review_fields'] or 'total_amount' in low_confidence['review_fields'], low_confidence

policy_only = normalize_documents([{
    'document_id': 'policy-1', 'original_name': 'policy.pdf', 'document_type': 'policy',
    'text': 'Annual Policy Limit: INR 500000\nDeductible: INR 10000', 'evidence': [],
}]).to_dict()
assert policy_only['total_amount'] is None, policy_only
print('PHASE2_FAILURE_PATHS_OK')
