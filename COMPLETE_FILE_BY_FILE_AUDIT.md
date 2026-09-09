# Medi Gaurd AI — Complete File-by-File Audit

**Audit path:** `C:\MediGaurd AI`  
**Scope:** Project-owned files excluding `.venv`, `.git`, `__pycache__`, `.pytest_cache`, and `EXTRA` backup files.

## Executive conclusion

> The core claim-verification path is present and has previously passed the clean end-to-end fixture, but the repository is not cleanly release-ready. The main audit risks are missing tracked project hygiene files, a large unreviewed `EXTRA` backup folder, runtime data committed or mixed with source, and a security code defect requiring confirmation: `app.py` uses `base64` in password/MFA functions but the inspected import section does not import `base64`. Authentication is currently bypassed by core-demo mode and must not be used for real medical documents.

## Inventory summary

| Category | Count |
|---|---:|
| Total in-scope files | 1203 |
| Python source files | 9 |
| Python tests/tools | 6 |
| Documentation/reports | 23 |
| Fixtures/media | 1105 |
| Runtime-data files | 13 |

## File-by-file register

| File | Category | Bytes | Lines | TODO/severity markers | Literal-secret pattern |
|---|---|---:|---:|---:|---|
| `agents.py` | source | 13,645 | 232 | 0 | No |
| `app.py` | source | 98,146 | 1523 | 0 | No |
| `backend_full_audit_test_results.txt` | documentation/report | 39 | 1 | 0 | No |
| `clean_mobile_bill_ocr.txt` | documentation/report | 520 | 19 | 0 | No |
| `CORE_MVP_SIMPLIFICATION.md` | documentation/report | 1,469 | 42 | 0 | No |
| `data/agent_metrics.jsonl` | runtime-data | 30,442 | — | 0 | No |
| `data/chroma/2890eceb-d9c5-44b7-9a9e-f2fb6031cccc/data_level0.bin` | runtime-data | 167,600 | — | 0 | No |
| `data/chroma/2890eceb-d9c5-44b7-9a9e-f2fb6031cccc/header.bin` | runtime-data | 100 | — | 0 | No |
| `data/chroma/2890eceb-d9c5-44b7-9a9e-f2fb6031cccc/length.bin` | runtime-data | 400 | — | 0 | No |
| `data/chroma/2890eceb-d9c5-44b7-9a9e-f2fb6031cccc/link_lists.bin` | runtime-data | 0 | — | 0 | No |
| `data/chroma/chroma.sqlite3` | runtime-data | 811,008 | — | 0 | No |
| `data/chroma_e2e/676a8889-e53e-4336-a11c-c3ee8f0c932c/data_level0.bin` | runtime-data | 167,600 | — | 0 | No |
| `data/chroma_e2e/676a8889-e53e-4336-a11c-c3ee8f0c932c/header.bin` | runtime-data | 100 | — | 0 | No |
| `data/chroma_e2e/676a8889-e53e-4336-a11c-c3ee8f0c932c/length.bin` | runtime-data | 400 | — | 0 | No |
| `data/chroma_e2e/676a8889-e53e-4336-a11c-c3ee8f0c932c/link_lists.bin` | runtime-data | 0 | — | 0 | No |
| `data/chroma_e2e/chroma.sqlite3` | runtime-data | 446,464 | — | 0 | No |
| `data/mediguard.db` | runtime-data | 806,912 | — | 0 | No |
| `data/mediguard_before_phase0_20260825_233206.db` | runtime-data | 253,952 | — | 0 | No |
| `data/policies/23a00ecd-9579-42e8-b78e-68a37f700c71_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/policies/6bfa9c58-1f92-4fc2-80ef-adcc44c0fe4a_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/policies/e6b7d864-5623-4ee8-9db3-f9a827fc6b24_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/policies/ed2d46b5-4dcb-459e-ad7e-074bf8e4bee8_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/06de216b-c40f-42a3-92e1-0d4b6371edb8/a5c4a91d-7555-49de-b61f-c086194fbe30_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/06de216b-c40f-42a3-92e1-0d4b6371edb8/f138aad2-1cce-46f8-8489-c806ca8da2a3_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/188f0a02-2ede-4651-8aeb-30979e8d1f7d/phase7-doc_synthetic.txt` | documentation/report | 23 | 1 | 0 | No |
| `data/uploads/18eb0c60-bd96-4064-adff-c00c23d76095/05b0a6a9-64cf-4659-8213-aa1beb64ab76_med_doc_bill_100002_noisy.jpg` | fixture/media | 263,777 | — | 0 | No |
| `data/uploads/18eb0c60-bd96-4064-adff-c00c23d76095/53173d5a-6300-4364-a3a2-de3c8d67010d_arogya-sanjeevani-policy---(health-insurance-product)--prospectus.pdf` | fixture/media | 339,000 | — | 0 | No |
| `data/uploads/19cbe20a-a72e-4425-9700-8a3177a9d3e8/aca62516-59e4-4435-ae06-ab91ba82ec67_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/19cbe20a-a72e-4425-9700-8a3177a9d3e8/d129a90b-9635-4004-94d0-960bb14830fd_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/3cc6d3b1-e56c-456e-a49c-30a6562a987a/9afb9c7f-834c-45f7-b07c-bdbbd77cd821_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/3cc6d3b1-e56c-456e-a49c-30a6562a987a/b8a78b43-e367-421f-9176-785f7ab9a78d_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/45932a17-4b26-40bb-b1d4-5b82f1d3f98c/01e1c0a0-83b9-417d-90a7-b243694cb11a_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/45932a17-4b26-40bb-b1d4-5b82f1d3f98c/d66b3336-3692-4aca-95ae-59c6a8132efb_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/51a14b55-15ef-4bcd-a4ae-a834e4a35d24/1a7ff298-a1ab-479b-84a2-151e8971ba26_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/51a14b55-15ef-4bcd-a4ae-a834e4a35d24/297d777a-21e2-4ef7-b42a-faaacb9cd9c1_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/51a14b55-15ef-4bcd-a4ae-a834e4a35d24/7d093a89-a427-465a-95ee-eb0c3615139c_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/51a14b55-15ef-4bcd-a4ae-a834e4a35d24/ffad9ddc-8b01-4f77-94a1-e0b217bead36_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/62554367-d446-4ba5-9721-8c218f89a333/9e039425-7bb1-4433-b3f0-22529032ca97_sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `data/uploads/62554367-d446-4ba5-9721-8c218f89a333/ce156c77-8f8f-4896-a978-3979cedb81ce_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/6abc17bb-57eb-4e2f-a629-f9e06b5a22e9/31aa5522-4372-4341-9b93-6db777d9fec2_med_doc_bill_100001_noisy.jpg` | fixture/media | 212,713 | — | 0 | No |
| `data/uploads/6abc17bb-57eb-4e2f-a629-f9e06b5a22e9/8c19fa09-6832-4ad9-a06c-5f24994528ee_policy_bill_matched_usd.pdf` | fixture/media | 4,339 | — | 0 | No |
| `data/uploads/71066948-12b0-44a0-ba29-0e5b7e19235e/04701971-4080-42b2-9b34-269eb796f061_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/71066948-12b0-44a0-ba29-0e5b7e19235e/7086bb33-a54f-43fa-b3db-39a2f6b88948_sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `data/uploads/759a1b3a-de5a-4a18-9cde-86d0b0920d52/5d1abb1b-770a-4d0d-98b6-d7a1d5bf4b63_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/759a1b3a-de5a-4a18-9cde-86d0b0920d52/e6b1676a-9b31-44f0-b0f7-03534f929a63_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/7872c572-897e-4200-a591-58749eca4b53/596bf6f9-1b45-4b7b-9c40-53a05579dc29_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/7872c572-897e-4200-a591-58749eca4b53/d0841d03-add3-4381-97a8-0a5db779f3bd_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/87b1a10f-0844-4df0-a9f9-6e88ac1f1bdb/0238f6b9-f245-4aa6-a9f8-198b9e4cbd3b_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/87b1a10f-0844-4df0-a9f9-6e88ac1f1bdb/0559ac0f-cc52-4b18-8f89-16d2caaf5c05_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/87b1a10f-0844-4df0-a9f9-6e88ac1f1bdb/2949f1d2-87e0-4154-b2ca-36e7e7471120_sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `data/uploads/87b1a10f-0844-4df0-a9f9-6e88ac1f1bdb/caf57574-190c-4cd1-bb10-c749cb1893ee_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/87b1a10f-0844-4df0-a9f9-6e88ac1f1bdb/de504bb8-eb46-40b2-a998-871cadfc2992_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/96eb03cd-73d8-42b0-92a2-0fa9f590834d/770ee3c0-67ad-4f41-96db-e5afdadec34e_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/96eb03cd-73d8-42b0-92a2-0fa9f590834d/e5d8c9e1-76da-42e5-8bc5-139c4db422d9_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/987acb2e-ddca-4513-b4fa-f43397fa242b/3dd00812-69cc-4a5a-b34f-c85f7748610d_policy_clean_mobile_demo.pdf` | fixture/media | 3,282 | — | 0 | No |
| `data/uploads/987acb2e-ddca-4513-b4fa-f43397fa242b/f7f77890-5bb7-48a3-8c0a-e7a17d0d16d6_bill_clean_mobile_demo_(1).png` | fixture/media | 164,558 | — | 0 | No |
| `data/uploads/9b6b2fb3-0c96-427c-a090-38af6ed6b97a/017852ea-da75-4c78-8184-cfd6800e7b17_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/9b6b2fb3-0c96-427c-a090-38af6ed6b97a/24b8bdd1-3034-4cff-b3ea-de819c044dc0_sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `data/uploads/9b6b2fb3-0c96-427c-a090-38af6ed6b97a/7b92c3ba-9b63-405e-9f4b-422f3faab5c7_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/9b6b2fb3-0c96-427c-a090-38af6ed6b97a/d15f2efa-0666-4de6-927b-4ed8f9440ba4_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/a16ee222-1d89-4527-829b-42c944162d18/1f760291-7c97-4717-806f-a5c39abc503b_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/a16ee222-1d89-4527-829b-42c944162d18/4f90d0dd-d056-47b1-b9cd-dda7f6a206a3_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/a16ee222-1d89-4527-829b-42c944162d18/6506483a-4ddd-4fcf-b551-fb6b49cb6267_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/a16ee222-1d89-4527-829b-42c944162d18/9af0e7b6-4f89-4001-879c-7acf481c3cdc_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/baac48b0-9739-4bcd-9793-74a9b84bf2d1/c2a6a648-d38a-478d-ae3f-9808de487939_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/baac48b0-9739-4bcd-9793-74a9b84bf2d1/e06d87c8-53ac-460c-9228-b8abaaf7b923_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/cba593d5-279b-4742-828f-158db126c246/94510d6d-202b-41b1-9854-d1fc911b8aa3_sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `data/uploads/cba593d5-279b-4742-828f-158db126c246/99024e04-043f-41b6-9d29-72dd29234c00_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/cba593d5-279b-4742-828f-158db126c246/c4451a65-ff29-4908-9db9-474df98477d2_sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `data/uploads/cba593d5-279b-4742-828f-158db126c246/fa408e76-4ab6-4022-bc11-332ca1fbc35f_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/e77fa998-597a-4c61-bf19-110b9456d8c1/71d79350-f2c1-4462-a22b-e7de3ce8cf80_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `data/uploads/e77fa998-597a-4c61-bf19-110b9456d8c1/7365cbf1-8861-4157-95c2-3d96f8a2832c_med_doc_bill_100001_noisy.jpg` | fixture/media | 212,713 | — | 0 | No |
| `data/uploads/e77fa998-597a-4c61-bf19-110b9456d8c1/a7122688-ba96-4196-8d5e-bf24249e7eb5_policy_bill_matched_usd.pdf` | fixture/media | 4,339 | — | 0 | No |
| `data/uploads/e77fa998-597a-4c61-bf19-110b9456d8c1/f6c4f844-5a79-4295-8cfe-9f6ac7d05516_med_doc_bill_100001_noisy.jpg` | fixture/media | 212,713 | — | 0 | No |
| `data/uploads/fb4d1bb4-c240-491e-aa17-544c50b0541c/38af450d-2618-4c48-a64e-45bb39b597df_sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `data/uploads/fb4d1bb4-c240-491e-aa17-544c50b0541c/b1ec124b-4a80-46c4-8bf1-23a25240ed04_sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `extraction.py` | source | 18,574 | 391 | 0 | No |
| `fixtures/phase4/bill_clean_mobile_demo.png` | fixture/media | 164,558 | — | 0 | No |
| `fixtures/phase4/bill_low_light.jpg` | fixture/media | 45,676 | — | 0 | No |
| `fixtures/phase4/bill_multi_page.pdf` | fixture/media | 2,234 | — | 0 | No |
| `fixtures/phase4/bill_phone_photo.png` | fixture/media | 105,460 | — | 0 | No |
| `fixtures/phase4/bill_scanned_image_only.pdf` | fixture/media | 104,739 | — | 0 | No |
| `fixtures/phase4/bill_selectable_text.pdf` | fixture/media | 1,732 | — | 0 | No |
| `fixtures/phase4/bill_skewed_compressed.jpg` | fixture/media | 44,549 | — | 0 | No |
| `fixtures/phase4/ground_truth.json` | other | 2,506 | 92 | 0 | No |
| `fixtures/phase4/phase5_quality_report.json` | other | 9,666 | 353 | 0 | No |
| `fixtures/phase4/policy_bill_matched_usd.pdf` | fixture/media | 4,339 | — | 0 | No |
| `fixtures/phase4/policy_clean_mobile_demo.pdf` | fixture/media | 3,282 | — | 0 | No |
| `fixtures/phase4/policy_standard.pdf` | fixture/media | 1,687 | — | 0 | No |
| `fixtures/phase4/policy_variant_wording.pdf` | fixture/media | 1,797 | — | 0 | No |
| `policy_compare.py` | source | 1,933 | 46 | 0 | No |
| `policy_index.py` | source | 4,381 | 86 | 0 | No |
| `policy_terms.py` | source | 8,304 | 145 | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Denial_Reasons/denial_reasons.xlsx` | other | 5,525 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Denial_Reasons/README_Denial_Reasons.docx` | other | 36,727 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Prompt_Templates/llm_prompt.txt` | documentation/report | 383 | 16 | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Exclusion_Clause.docx` | other | 37,095 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/General_Appeal.docx` | other | 37,085 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Medical_Necessity.docx` | other | 37,084 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Missing_Documents.docx` | other | 37,070 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Partial_Claim.docx` | other | 37,078 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Pre_Authorization.docx` | other | 37,091 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/README_Appeal_Templates.docx` | other | 36,727 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Room_Rent_Limit.docx` | other | 37,075 | — | 0 | No |
| `REFERNCE DATASETS/AppealLetters/Template/Waiting_Period.docx` | other | 37,093 | — | 0 | No |
| `REFERNCE DATASETS/Environment_Planning/GitHub_Repository.xlsx` | other | 5,050 | — | 0 | No |
| `REFERNCE DATASETS/Environment_Planning/Project_Folder_Structure.xlsx` | other | 5,057 | — | 0 | No |
| `REFERNCE DATASETS/Environment_Planning/Python_Environment.xlsx` | other | 5,130 | — | 0 | No |
| `REFERNCE DATASETS/Environment_Planning/README(3).md` | documentation/report | 375 | 11 | 0 | No |
| `REFERNCE DATASETS/Ethics/Ethics_Checklist.xlsx` | other | 5,171 | — | 0 | No |
| `REFERNCE DATASETS/Ethics/Privacy_Principles.xlsx` | other | 5,065 | — | 0 | No |
| `REFERNCE DATASETS/Ethics/README(4).md` | documentation/report | 314 | 10 | 0 | No |
| `REFERNCE DATASETS/Evaluation_Dataset/GroundTruth/Ground_Truth.json` | other | 2,200 | 82 | 0 | No |
| `REFERNCE DATASETS/Evaluation_Dataset/README(1).md` | documentation/report | 456 | 20 | 0 | No |
| `REFERNCE DATASETS/Evaluation_Dataset/TestCases/Test_Cases.xlsx` | other | 5,494 | — | 0 | No |
| `REFERNCE DATASETS/Final_Deliverables/README_Unit2.docx` | other | 36,671 | — | 0 | No |
| `REFERNCE DATASETS/Final_Deliverables/Unit2_Completion_Checklist.xlsx` | other | 5,194 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/Acko/Prospectus_Acko_Personal_Health_Policy_9d9062a456.pdf` | fixture/media | 666,776 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/BAJAJ ALLIANZ/bajaj-health-guard-brochure-print.pdf` | fixture/media | 1,010,543 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/BAJAJ ALLIANZ/health_guard_gold_brochure.pdf` | fixture/media | 648,848 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/arogya-sanjeevani-policy---(health-insurance-product)--prospectus.pdf` | fixture/media | 339,000 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-(health-insurance-product)---brochure.pdf` | fixture/media | 375,253 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-(health-insurance-product)--prospectus-cum-sales-literature.pdf` | fixture/media | 1,863,723 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-advantage-(health-insurance-product)---brochure.pdf` | fixture/media | 320,841 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-freedom-(health-insurance-product)---brochure.pdf` | fixture/media | 349,089 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-heart-(health-insurance-product)---brochure.pdf` | fixture/media | 364,698 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-plus-(health-insurance-product)---brochure.pdf` | fixture/media | 277,571 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/care-plus--(health-insurance-product)---prospectus-cum-sales-literature.pdf` | fixture/media | 444,131 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/CARE/corona-kavach-policy-chi--(health-insurance-product)-prospectus-cum-sales-literature.pdf` | fixture/media | 304,258 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/Go digit/Policy Wordings - Digit Health Insurance Policy.pdf` | fixture/media | 4,702,069 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/HDFC_ERGO/hdfc-group-health-insurance-prospectus.pdf` | fixture/media | 662,279 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/ICICI_Lombard/new-complete-health-insurance-brochure.pdf` | fixture/media | 1,136,389 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/Niva_Bupa/health-companion-policy-wording.pdf` | fixture/media | 355,005 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/Niva_Bupa/Niva_Health_Premia_Brochure.pdf` | fixture/media | 6,057,805 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/Reliance/20200602202935.pdf` | fixture/media | 486,896 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/SBI/947e0e11c7a34c2ea1fac50af90ef60f.pdf` | fixture/media | 730,103 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/SBI/a370272f732749999e7c19e82e38ad7c.pdf` | fixture/media | 438,003 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/Star_Health/Policy_Star_Health_Assure_Insurance_Policy_V_9_c53663e68a.pdf` | fixture/media | 756,987 | — | 0 | No |
| `REFERNCE DATASETS/Insurance_policies/TATA AGI/Medi_Care_Prospectus_0eeb366114.pdf` | fixture/media | 486,300 | — | 0 | No |
| `REFERNCE DATASETS/Laboratory/blood_count_dataset.csv` | other | 16,764 | — | 0 | No |
| `REFERNCE DATASETS/Laboratory/LOIC (1).exe` | other | 0 | — | 0 | No |
| `REFERNCE DATASETS/Master_Schema/Generative AI.txt` | documentation/report | 2,180 | 90 | 0 | No |
| `REFERNCE DATASETS/Master_Schema/Medical_Bill_Schema.json` | other | 1,771 | 99 | 0 | No |
| `REFERNCE DATASETS/Master_Schema/Medical_Bill_Schema.xlsx` | other | 6,565 | — | 0 | No |
| `REFERNCE DATASETS/Master_Schema/README.md.txt` | documentation/report | 595 | 22 | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100001_noisy.jpg` | fixture/media | 212,713 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100002_noisy.jpg` | fixture/media | 263,777 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100003_noisy.jpg` | fixture/media | 246,360 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100004_noisy.jpg` | fixture/media | 305,166 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100005_noisy.jpg` | fixture/media | 230,855 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100006_noisy.jpg` | fixture/media | 235,202 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100007_noisy.jpg` | fixture/media | 269,432 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100008_noisy.jpg` | fixture/media | 212,798 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100009_noisy.jpg` | fixture/media | 266,996 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100010_noisy.jpg` | fixture/media | 269,549 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100011_noisy.jpg` | fixture/media | 247,443 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100012_noisy.jpg` | fixture/media | 197,981 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100013_noisy.jpg` | fixture/media | 249,727 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100014_noisy.jpg` | fixture/media | 261,048 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100015_noisy.jpg` | fixture/media | 232,304 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100016_noisy.jpg` | fixture/media | 235,168 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100017_noisy.jpg` | fixture/media | 241,923 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100018_noisy.jpg` | fixture/media | 246,874 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100019_noisy.jpg` | fixture/media | 253,849 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100020_noisy.jpg` | fixture/media | 266,038 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100021_noisy.jpg` | fixture/media | 229,561 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100022_noisy.jpg` | fixture/media | 255,364 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100023_noisy.jpg` | fixture/media | 244,886 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100024_noisy.jpg` | fixture/media | 210,898 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100025_noisy.jpg` | fixture/media | 219,696 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100026_noisy.jpg` | fixture/media | 245,396 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100027_noisy.jpg` | fixture/media | 255,064 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100028_noisy.jpg` | fixture/media | 260,284 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100029_noisy.jpg` | fixture/media | 228,288 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100030_noisy.jpg` | fixture/media | 246,953 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100031_noisy.jpg` | fixture/media | 237,154 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100032_noisy.jpg` | fixture/media | 224,379 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100033_noisy.jpg` | fixture/media | 200,303 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100034_noisy.jpg` | fixture/media | 201,490 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100035_noisy.jpg` | fixture/media | 250,368 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100036_noisy.jpg` | fixture/media | 227,434 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100037_noisy.jpg` | fixture/media | 263,541 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100038_noisy.jpg` | fixture/media | 262,784 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100039_noisy.jpg` | fixture/media | 265,375 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100040_noisy.jpg` | fixture/media | 257,774 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100041_noisy.jpg` | fixture/media | 226,232 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100042_noisy.jpg` | fixture/media | 244,684 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100043_noisy.jpg` | fixture/media | 294,663 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100044_noisy.jpg` | fixture/media | 244,385 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100045_noisy.jpg` | fixture/media | 237,587 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100046_noisy.jpg` | fixture/media | 223,006 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100047_noisy.jpg` | fixture/media | 269,707 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100048_noisy.jpg` | fixture/media | 227,193 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100049_noisy.jpg` | fixture/media | 258,255 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100050_noisy.jpg` | fixture/media | 289,359 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100051_noisy.jpg` | fixture/media | 231,662 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100052_noisy.jpg` | fixture/media | 244,355 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100053_noisy.jpg` | fixture/media | 295,624 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100054_noisy.jpg` | fixture/media | 230,038 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100055_noisy.jpg` | fixture/media | 222,299 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100056_noisy.jpg` | fixture/media | 242,449 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100057_noisy.jpg` | fixture/media | 289,206 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100058_noisy.jpg` | fixture/media | 206,910 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100059_noisy.jpg` | fixture/media | 286,005 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100060_noisy.jpg` | fixture/media | 197,411 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100061_noisy.jpg` | fixture/media | 242,427 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100062_noisy.jpg` | fixture/media | 268,288 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100063_noisy.jpg` | fixture/media | 233,018 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100064_noisy.jpg` | fixture/media | 223,029 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100065_noisy.jpg` | fixture/media | 262,224 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100066_noisy.jpg` | fixture/media | 221,895 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100067_noisy.jpg` | fixture/media | 210,945 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100068_noisy.jpg` | fixture/media | 203,764 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100069_noisy.jpg` | fixture/media | 194,786 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100070_noisy.jpg` | fixture/media | 231,212 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100071_noisy.jpg` | fixture/media | 239,911 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100072_noisy.jpg` | fixture/media | 221,766 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100073_noisy.jpg` | fixture/media | 241,097 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100074_noisy.jpg` | fixture/media | 258,972 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100075_noisy.jpg` | fixture/media | 308,812 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100076_noisy.jpg` | fixture/media | 211,239 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100077_noisy.jpg` | fixture/media | 223,840 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100078_noisy.jpg` | fixture/media | 221,507 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100079_noisy.jpg` | fixture/media | 230,153 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100080_noisy.jpg` | fixture/media | 237,970 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100081_noisy.jpg` | fixture/media | 267,170 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100082_noisy.jpg` | fixture/media | 221,594 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100083_noisy.jpg` | fixture/media | 267,233 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100084_noisy.jpg` | fixture/media | 237,789 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100085_noisy.jpg` | fixture/media | 270,258 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100086_noisy.jpg` | fixture/media | 232,034 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100087_noisy.jpg` | fixture/media | 235,610 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100088_noisy.jpg` | fixture/media | 259,358 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100089_noisy.jpg` | fixture/media | 248,263 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100090_noisy.jpg` | fixture/media | 247,012 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100091_noisy.jpg` | fixture/media | 286,448 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100092_noisy.jpg` | fixture/media | 265,771 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100093_noisy.jpg` | fixture/media | 201,087 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100094_noisy.jpg` | fixture/media | 279,372 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100095_noisy.jpg` | fixture/media | 243,592 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100096_noisy.jpg` | fixture/media | 301,930 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100097_noisy.jpg` | fixture/media | 228,231 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100098_noisy.jpg` | fixture/media | 221,302 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100099_noisy.jpg` | fixture/media | 225,560 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100100_noisy.jpg` | fixture/media | 289,427 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100101_noisy.jpg` | fixture/media | 249,493 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100102_noisy.jpg` | fixture/media | 255,388 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100103_noisy.jpg` | fixture/media | 236,884 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100104_noisy.jpg` | fixture/media | 234,287 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100105_noisy.jpg` | fixture/media | 219,748 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100106_noisy.jpg` | fixture/media | 248,235 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100107_noisy.jpg` | fixture/media | 222,263 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100108_noisy.jpg` | fixture/media | 255,900 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100109_noisy.jpg` | fixture/media | 236,846 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100110_noisy.jpg` | fixture/media | 294,678 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100111_noisy.jpg` | fixture/media | 285,029 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100112_noisy.jpg` | fixture/media | 268,426 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100113_noisy.jpg` | fixture/media | 228,703 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100114_noisy.jpg` | fixture/media | 270,336 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100115_noisy.jpg` | fixture/media | 261,266 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100116_noisy.jpg` | fixture/media | 267,821 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100117_noisy.jpg` | fixture/media | 222,828 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100118_noisy.jpg` | fixture/media | 236,479 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100119_noisy.jpg` | fixture/media | 221,024 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100120_noisy.jpg` | fixture/media | 250,094 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100121_noisy.jpg` | fixture/media | 291,058 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100122_noisy.jpg` | fixture/media | 277,862 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100123_noisy.jpg` | fixture/media | 250,404 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100124_noisy.jpg` | fixture/media | 278,780 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100125_noisy.jpg` | fixture/media | 239,440 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100126_noisy.jpg` | fixture/media | 245,734 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100127_noisy.jpg` | fixture/media | 219,234 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100128_noisy.jpg` | fixture/media | 273,975 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100129_noisy.jpg` | fixture/media | 259,903 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100130_noisy.jpg` | fixture/media | 273,451 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100131_noisy.jpg` | fixture/media | 248,516 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100132_noisy.jpg` | fixture/media | 298,267 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100133_noisy.jpg` | fixture/media | 271,044 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100134_noisy.jpg` | fixture/media | 198,770 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100135_noisy.jpg` | fixture/media | 283,811 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100136_noisy.jpg` | fixture/media | 263,034 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100137_noisy.jpg` | fixture/media | 244,562 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100138_noisy.jpg` | fixture/media | 247,558 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100139_noisy.jpg` | fixture/media | 241,615 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100140_noisy.jpg` | fixture/media | 231,985 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100141_noisy.jpg` | fixture/media | 282,831 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100142_noisy.jpg` | fixture/media | 221,589 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100143_noisy.jpg` | fixture/media | 216,808 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100144_noisy.jpg` | fixture/media | 268,544 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100145_noisy.jpg` | fixture/media | 273,510 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100146_noisy.jpg` | fixture/media | 273,604 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100147_noisy.jpg` | fixture/media | 208,123 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100148_noisy.jpg` | fixture/media | 272,890 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100149_noisy.jpg` | fixture/media | 212,669 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100150_noisy.jpg` | fixture/media | 220,488 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100151_noisy.jpg` | fixture/media | 238,555 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100152_noisy.jpg` | fixture/media | 244,703 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100153_noisy.jpg` | fixture/media | 249,967 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100154_noisy.jpg` | fixture/media | 256,367 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100155_noisy.jpg` | fixture/media | 223,390 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100156_noisy.jpg` | fixture/media | 286,446 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100157_noisy.jpg` | fixture/media | 291,991 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100158_noisy.jpg` | fixture/media | 276,629 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100159_noisy.jpg` | fixture/media | 259,751 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100160_noisy.jpg` | fixture/media | 257,012 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100161_noisy.jpg` | fixture/media | 300,927 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100162_noisy.jpg` | fixture/media | 229,617 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100163_noisy.jpg` | fixture/media | 277,403 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100164_noisy.jpg` | fixture/media | 239,185 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100165_noisy.jpg` | fixture/media | 267,013 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100166_noisy.jpg` | fixture/media | 211,724 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100167_noisy.jpg` | fixture/media | 248,028 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100168_noisy.jpg` | fixture/media | 234,117 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100169_noisy.jpg` | fixture/media | 212,514 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100170_noisy.jpg` | fixture/media | 254,231 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100171_noisy.jpg` | fixture/media | 258,058 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100172_noisy.jpg` | fixture/media | 273,864 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100173_noisy.jpg` | fixture/media | 251,992 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100174_noisy.jpg` | fixture/media | 244,102 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100175_noisy.jpg` | fixture/media | 224,358 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100176_noisy.jpg` | fixture/media | 282,772 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100177_noisy.jpg` | fixture/media | 233,376 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100178_noisy.jpg` | fixture/media | 239,002 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100179_noisy.jpg` | fixture/media | 264,968 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100180_noisy.jpg` | fixture/media | 208,600 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100181_noisy.jpg` | fixture/media | 250,884 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100182_noisy.jpg` | fixture/media | 220,111 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100183_noisy.jpg` | fixture/media | 267,102 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100184_noisy.jpg` | fixture/media | 270,868 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100185_noisy.jpg` | fixture/media | 280,000 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100186_noisy.jpg` | fixture/media | 237,184 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100187_noisy.jpg` | fixture/media | 231,247 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100188_noisy.jpg` | fixture/media | 260,574 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100189_noisy.jpg` | fixture/media | 239,113 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100190_noisy.jpg` | fixture/media | 230,034 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100191_noisy.jpg` | fixture/media | 247,484 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100192_noisy.jpg` | fixture/media | 223,618 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100193_noisy.jpg` | fixture/media | 266,832 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100194_noisy.jpg` | fixture/media | 224,608 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100195_noisy.jpg` | fixture/media | 255,055 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100196_noisy.jpg` | fixture/media | 236,223 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100197_noisy.jpg` | fixture/media | 225,040 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100198_noisy.jpg` | fixture/media | 263,915 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100199_noisy.jpg` | fixture/media | 244,403 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100200_noisy.jpg` | fixture/media | 244,386 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100201_noisy.jpg` | fixture/media | 231,036 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100202_noisy.jpg` | fixture/media | 227,345 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100203_noisy.jpg` | fixture/media | 192,655 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100204_noisy.jpg` | fixture/media | 260,966 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100205_noisy.jpg` | fixture/media | 220,259 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100206_noisy.jpg` | fixture/media | 237,484 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100207_noisy.jpg` | fixture/media | 256,997 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100208_noisy.jpg` | fixture/media | 248,134 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100209_noisy.jpg` | fixture/media | 209,505 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100210_noisy.jpg` | fixture/media | 274,752 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100211_noisy.jpg` | fixture/media | 212,016 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100212_noisy.jpg` | fixture/media | 266,075 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100213_noisy.jpg` | fixture/media | 231,759 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100214_noisy.jpg` | fixture/media | 205,772 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100215_noisy.jpg` | fixture/media | 225,668 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100216_noisy.jpg` | fixture/media | 240,368 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100217_noisy.jpg` | fixture/media | 252,860 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100218_noisy.jpg` | fixture/media | 192,212 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100219_noisy.jpg` | fixture/media | 249,907 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100220_noisy.jpg` | fixture/media | 266,633 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100221_noisy.jpg` | fixture/media | 245,391 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100222_noisy.jpg` | fixture/media | 260,180 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100223_noisy.jpg` | fixture/media | 221,886 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100224_noisy.jpg` | fixture/media | 217,177 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100225_noisy.jpg` | fixture/media | 211,788 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100226_noisy.jpg` | fixture/media | 247,889 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100227_noisy.jpg` | fixture/media | 213,458 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100228_noisy.jpg` | fixture/media | 216,286 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100229_noisy.jpg` | fixture/media | 213,722 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100230_noisy.jpg` | fixture/media | 223,800 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100231_noisy.jpg` | fixture/media | 199,330 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100232_noisy.jpg` | fixture/media | 223,398 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100233_noisy.jpg` | fixture/media | 247,726 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100234_noisy.jpg` | fixture/media | 257,303 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100235_noisy.jpg` | fixture/media | 256,703 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100236_noisy.jpg` | fixture/media | 283,985 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100237_noisy.jpg` | fixture/media | 228,030 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100238_noisy.jpg` | fixture/media | 232,207 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100239_noisy.jpg` | fixture/media | 205,008 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100240_noisy.jpg` | fixture/media | 238,212 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100241_noisy.jpg` | fixture/media | 235,721 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100242_noisy.jpg` | fixture/media | 253,759 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100243_noisy.jpg` | fixture/media | 293,050 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100244_noisy.jpg` | fixture/media | 210,051 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100245_noisy.jpg` | fixture/media | 247,153 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100246_noisy.jpg` | fixture/media | 243,211 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100247_noisy.jpg` | fixture/media | 222,823 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100248_noisy.jpg` | fixture/media | 228,340 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100249_noisy.jpg` | fixture/media | 243,747 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100250_noisy.jpg` | fixture/media | 245,399 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100251_noisy.jpg` | fixture/media | 285,861 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100252_noisy.jpg` | fixture/media | 251,847 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100253_noisy.jpg` | fixture/media | 239,689 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100254_noisy.jpg` | fixture/media | 281,534 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100255_noisy.jpg` | fixture/media | 213,540 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100256_noisy.jpg` | fixture/media | 283,238 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100257_noisy.jpg` | fixture/media | 211,748 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100258_noisy.jpg` | fixture/media | 273,652 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100259_noisy.jpg` | fixture/media | 251,051 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100260_noisy.jpg` | fixture/media | 232,766 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100261_noisy.jpg` | fixture/media | 221,603 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100262_noisy.jpg` | fixture/media | 276,076 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100263_noisy.jpg` | fixture/media | 192,021 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100264_noisy.jpg` | fixture/media | 198,246 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100265_noisy.jpg` | fixture/media | 237,444 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100266_noisy.jpg` | fixture/media | 198,186 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100267_noisy.jpg` | fixture/media | 231,589 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100268_noisy.jpg` | fixture/media | 222,405 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100269_noisy.jpg` | fixture/media | 248,645 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100270_noisy.jpg` | fixture/media | 211,581 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100271_noisy.jpg` | fixture/media | 242,951 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100272_noisy.jpg` | fixture/media | 219,553 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100273_noisy.jpg` | fixture/media | 224,210 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100274_noisy.jpg` | fixture/media | 293,556 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100275_noisy.jpg` | fixture/media | 239,000 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100276_noisy.jpg` | fixture/media | 257,496 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100277_noisy.jpg` | fixture/media | 214,791 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100278_noisy.jpg` | fixture/media | 214,798 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100279_noisy.jpg` | fixture/media | 222,801 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100280_noisy.jpg` | fixture/media | 238,256 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100281_noisy.jpg` | fixture/media | 257,897 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100282_noisy.jpg` | fixture/media | 298,406 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100283_noisy.jpg` | fixture/media | 230,014 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100284_noisy.jpg` | fixture/media | 257,827 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100285_noisy.jpg` | fixture/media | 244,051 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100286_noisy.jpg` | fixture/media | 270,308 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100287_noisy.jpg` | fixture/media | 243,717 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100288_noisy.jpg` | fixture/media | 300,732 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100289_noisy.jpg` | fixture/media | 279,179 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100290_noisy.jpg` | fixture/media | 298,863 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100291_noisy.jpg` | fixture/media | 251,741 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100292_noisy.jpg` | fixture/media | 273,204 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100293_noisy.jpg` | fixture/media | 282,982 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100294_noisy.jpg` | fixture/media | 224,747 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100295_noisy.jpg` | fixture/media | 239,738 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100296_noisy.jpg` | fixture/media | 237,927 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100297_noisy.jpg` | fixture/media | 229,538 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100298_noisy.jpg` | fixture/media | 258,457 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100299_noisy.jpg` | fixture/media | 210,003 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100300_noisy.jpg` | fixture/media | 204,628 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100301_noisy.jpg` | fixture/media | 214,138 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100302_noisy.jpg` | fixture/media | 214,419 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100303_noisy.jpg` | fixture/media | 235,268 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100304_noisy.jpg` | fixture/media | 220,914 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100305_noisy.jpg` | fixture/media | 262,522 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100306_noisy.jpg` | fixture/media | 253,991 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100307_noisy.jpg` | fixture/media | 262,374 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100308_noisy.jpg` | fixture/media | 218,435 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100309_noisy.jpg` | fixture/media | 214,455 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100310_noisy.jpg` | fixture/media | 280,487 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100311_noisy.jpg` | fixture/media | 251,577 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100312_noisy.jpg` | fixture/media | 221,169 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100313_noisy.jpg` | fixture/media | 233,877 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100314_noisy.jpg` | fixture/media | 216,034 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100315_noisy.jpg` | fixture/media | 244,391 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100316_noisy.jpg` | fixture/media | 235,942 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100317_noisy.jpg` | fixture/media | 241,320 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100318_noisy.jpg` | fixture/media | 210,817 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100319_noisy.jpg` | fixture/media | 273,244 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100320_noisy.jpg` | fixture/media | 199,067 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100321_noisy.jpg` | fixture/media | 202,336 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100322_noisy.jpg` | fixture/media | 267,572 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100323_noisy.jpg` | fixture/media | 256,241 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100324_noisy.jpg` | fixture/media | 216,974 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100325_noisy.jpg` | fixture/media | 242,828 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100326_noisy.jpg` | fixture/media | 235,898 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100327_noisy.jpg` | fixture/media | 259,690 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100328_noisy.jpg` | fixture/media | 213,017 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100329_noisy.jpg` | fixture/media | 209,914 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100330_noisy.jpg` | fixture/media | 251,658 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100331_noisy.jpg` | fixture/media | 274,949 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100332_noisy.jpg` | fixture/media | 246,173 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100333_noisy.jpg` | fixture/media | 219,664 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100334_noisy.jpg` | fixture/media | 292,717 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100335_noisy.jpg` | fixture/media | 218,222 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100336_noisy.jpg` | fixture/media | 279,086 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100337_noisy.jpg` | fixture/media | 242,272 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100338_noisy.jpg` | fixture/media | 214,539 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100339_noisy.jpg` | fixture/media | 269,891 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100340_noisy.jpg` | fixture/media | 243,358 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100341_noisy.jpg` | fixture/media | 237,505 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100342_noisy.jpg` | fixture/media | 252,949 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100343_noisy.jpg` | fixture/media | 276,944 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100344_noisy.jpg` | fixture/media | 229,001 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100345_noisy.jpg` | fixture/media | 196,882 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100346_noisy.jpg` | fixture/media | 218,144 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100347_noisy.jpg` | fixture/media | 235,410 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100348_noisy.jpg` | fixture/media | 217,575 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100349_noisy.jpg` | fixture/media | 279,772 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100350_noisy.jpg` | fixture/media | 248,758 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100351_noisy.jpg` | fixture/media | 266,727 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100352_noisy.jpg` | fixture/media | 261,532 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100353_noisy.jpg` | fixture/media | 247,318 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100354_noisy.jpg` | fixture/media | 211,777 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100355_noisy.jpg` | fixture/media | 222,334 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100356_noisy.jpg` | fixture/media | 228,563 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100357_noisy.jpg` | fixture/media | 231,955 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100358_noisy.jpg` | fixture/media | 218,229 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100359_noisy.jpg` | fixture/media | 279,773 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100360_noisy.jpg` | fixture/media | 227,620 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100361_noisy.jpg` | fixture/media | 266,198 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100362_noisy.jpg` | fixture/media | 230,639 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100363_noisy.jpg` | fixture/media | 252,446 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100364_noisy.jpg` | fixture/media | 250,637 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100365_noisy.jpg` | fixture/media | 281,938 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100366_noisy.jpg` | fixture/media | 249,600 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100367_noisy.jpg` | fixture/media | 222,978 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100368_noisy.jpg` | fixture/media | 230,992 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100369_noisy.jpg` | fixture/media | 224,990 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100370_noisy.jpg` | fixture/media | 276,829 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100371_noisy.jpg` | fixture/media | 223,322 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100372_noisy.jpg` | fixture/media | 219,900 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100373_noisy.jpg` | fixture/media | 246,348 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100374_noisy.jpg` | fixture/media | 210,495 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100375_noisy.jpg` | fixture/media | 259,735 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100376_noisy.jpg` | fixture/media | 248,494 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100377_noisy.jpg` | fixture/media | 233,652 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100378_noisy.jpg` | fixture/media | 232,953 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100379_noisy.jpg` | fixture/media | 218,166 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100380_noisy.jpg` | fixture/media | 198,190 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100381_noisy.jpg` | fixture/media | 261,509 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100382_noisy.jpg` | fixture/media | 223,236 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100383_noisy.jpg` | fixture/media | 228,515 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100384_noisy.jpg` | fixture/media | 229,585 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100385_noisy.jpg` | fixture/media | 227,840 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100386_noisy.jpg` | fixture/media | 283,421 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100387_noisy.jpg` | fixture/media | 256,976 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100388_noisy.jpg` | fixture/media | 227,192 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100389_noisy.jpg` | fixture/media | 222,017 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100390_noisy.jpg` | fixture/media | 219,774 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100391_noisy.jpg` | fixture/media | 231,806 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100392_noisy.jpg` | fixture/media | 239,446 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100393_noisy.jpg` | fixture/media | 206,750 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100394_noisy.jpg` | fixture/media | 236,115 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100395_noisy.jpg` | fixture/media | 261,540 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100396_noisy.jpg` | fixture/media | 246,076 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100397_noisy.jpg` | fixture/media | 213,850 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100398_noisy.jpg` | fixture/media | 237,812 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100399_noisy.jpg` | fixture/media | 251,286 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100400_noisy.jpg` | fixture/media | 242,623 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100401_noisy.jpg` | fixture/media | 251,572 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100402_noisy.jpg` | fixture/media | 217,246 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100403_noisy.jpg` | fixture/media | 275,792 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100404_noisy.jpg` | fixture/media | 243,066 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100405_noisy.jpg` | fixture/media | 254,886 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100406_noisy.jpg` | fixture/media | 247,372 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100407_noisy.jpg` | fixture/media | 209,116 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100408_noisy.jpg` | fixture/media | 286,795 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100409_noisy.jpg` | fixture/media | 213,891 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100410_noisy.jpg` | fixture/media | 233,404 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100411_noisy.jpg` | fixture/media | 251,658 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100412_noisy.jpg` | fixture/media | 244,400 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100413_noisy.jpg` | fixture/media | 280,370 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100414_noisy.jpg` | fixture/media | 281,921 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100415_noisy.jpg` | fixture/media | 213,500 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100416_noisy.jpg` | fixture/media | 285,952 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100417_noisy.jpg` | fixture/media | 257,404 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100418_noisy.jpg` | fixture/media | 239,670 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100419_noisy.jpg` | fixture/media | 245,321 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100420_noisy.jpg` | fixture/media | 215,490 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100421_noisy.jpg` | fixture/media | 237,870 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100422_noisy.jpg` | fixture/media | 237,683 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100423_noisy.jpg` | fixture/media | 249,363 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100424_noisy.jpg` | fixture/media | 224,423 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100425_noisy.jpg` | fixture/media | 251,830 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100426_noisy.jpg` | fixture/media | 196,498 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100427_noisy.jpg` | fixture/media | 228,796 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100428_noisy.jpg` | fixture/media | 254,352 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100429_noisy.jpg` | fixture/media | 243,865 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100430_noisy.jpg` | fixture/media | 270,941 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100431_noisy.jpg` | fixture/media | 217,668 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100432_noisy.jpg` | fixture/media | 234,424 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100433_noisy.jpg` | fixture/media | 241,388 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100434_noisy.jpg` | fixture/media | 236,476 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100435_noisy.jpg` | fixture/media | 250,512 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100436_noisy.jpg` | fixture/media | 254,182 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100437_noisy.jpg` | fixture/media | 249,227 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100438_noisy.jpg` | fixture/media | 266,865 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100439_noisy.jpg` | fixture/media | 264,293 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100440_noisy.jpg` | fixture/media | 227,499 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100441_noisy.jpg` | fixture/media | 265,185 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100442_noisy.jpg` | fixture/media | 228,823 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100443_noisy.jpg` | fixture/media | 231,108 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100444_noisy.jpg` | fixture/media | 246,497 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100445_noisy.jpg` | fixture/media | 226,040 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100446_noisy.jpg` | fixture/media | 206,675 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100447_noisy.jpg` | fixture/media | 227,395 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100448_noisy.jpg` | fixture/media | 210,503 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100449_noisy.jpg` | fixture/media | 268,903 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100450_noisy.jpg` | fixture/media | 219,288 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100451_noisy.jpg` | fixture/media | 222,029 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100452_noisy.jpg` | fixture/media | 285,454 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100453_noisy.jpg` | fixture/media | 273,101 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100454_noisy.jpg` | fixture/media | 234,482 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100455_noisy.jpg` | fixture/media | 247,508 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100456_noisy.jpg` | fixture/media | 257,810 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100457_noisy.jpg` | fixture/media | 235,239 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100458_noisy.jpg` | fixture/media | 277,270 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100459_noisy.jpg` | fixture/media | 229,902 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100460_noisy.jpg` | fixture/media | 295,256 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100461_noisy.jpg` | fixture/media | 243,457 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100462_noisy.jpg` | fixture/media | 298,871 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100463_noisy.jpg` | fixture/media | 271,681 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100464_noisy.jpg` | fixture/media | 225,114 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100465_noisy.jpg` | fixture/media | 235,912 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100466_noisy.jpg` | fixture/media | 216,978 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100467_noisy.jpg` | fixture/media | 240,751 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100468_noisy.jpg` | fixture/media | 273,934 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100469_noisy.jpg` | fixture/media | 217,074 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100470_noisy.jpg` | fixture/media | 216,839 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100471_noisy.jpg` | fixture/media | 241,485 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100472_noisy.jpg` | fixture/media | 197,115 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100473_noisy.jpg` | fixture/media | 278,004 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100474_noisy.jpg` | fixture/media | 258,821 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100475_noisy.jpg` | fixture/media | 264,687 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100476_noisy.jpg` | fixture/media | 252,564 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100477_noisy.jpg` | fixture/media | 291,178 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100478_noisy.jpg` | fixture/media | 247,643 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100479_noisy.jpg` | fixture/media | 238,560 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100480_noisy.jpg` | fixture/media | 233,535 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100481_noisy.jpg` | fixture/media | 267,053 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100482_noisy.jpg` | fixture/media | 219,823 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100483_noisy.jpg` | fixture/media | 238,225 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100484_noisy.jpg` | fixture/media | 205,147 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100485_noisy.jpg` | fixture/media | 264,543 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100486_noisy.jpg` | fixture/media | 294,771 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100487_noisy.jpg` | fixture/media | 231,559 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100488_noisy.jpg` | fixture/media | 246,894 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100489_noisy.jpg` | fixture/media | 187,977 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100490_noisy.jpg` | fixture/media | 271,924 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100491_noisy.jpg` | fixture/media | 280,257 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100492_noisy.jpg` | fixture/media | 279,941 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100493_noisy.jpg` | fixture/media | 209,917 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100494_noisy.jpg` | fixture/media | 305,350 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100495_noisy.jpg` | fixture/media | 225,821 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100496_noisy.jpg` | fixture/media | 241,362 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100497_noisy.jpg` | fixture/media | 220,900 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100498_noisy.jpg` | fixture/media | 240,262 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100499_noisy.jpg` | fixture/media | 189,244 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/bills/med_doc_bill_100500_noisy.jpg` | fixture/media | 242,458 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200001_noisy.jpg` | fixture/media | 358,124 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200002_noisy.jpg` | fixture/media | 356,376 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200003_noisy.jpg` | fixture/media | 336,318 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200004_noisy.jpg` | fixture/media | 367,721 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200005_noisy.jpg` | fixture/media | 383,723 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200006_noisy.jpg` | fixture/media | 448,236 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200007_noisy.jpg` | fixture/media | 486,599 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200008_noisy.jpg` | fixture/media | 410,610 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200009_noisy.jpg` | fixture/media | 440,063 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200010_noisy.jpg` | fixture/media | 347,217 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200011_noisy.jpg` | fixture/media | 430,145 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200012_noisy.jpg` | fixture/media | 357,645 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200013_noisy.jpg` | fixture/media | 409,083 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200014_noisy.jpg` | fixture/media | 414,857 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200015_noisy.jpg` | fixture/media | 315,726 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200016_noisy.jpg` | fixture/media | 418,763 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200017_noisy.jpg` | fixture/media | 332,429 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200018_noisy.jpg` | fixture/media | 434,060 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200019_noisy.jpg` | fixture/media | 349,125 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200020_noisy.jpg` | fixture/media | 362,521 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200021_noisy.jpg` | fixture/media | 385,600 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200022_noisy.jpg` | fixture/media | 352,809 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200023_noisy.jpg` | fixture/media | 464,146 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200024_noisy.jpg` | fixture/media | 400,999 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200025_noisy.jpg` | fixture/media | 450,571 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200026_noisy.jpg` | fixture/media | 393,774 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200027_noisy.jpg` | fixture/media | 343,875 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200028_noisy.jpg` | fixture/media | 341,308 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200029_noisy.jpg` | fixture/media | 397,868 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200030_noisy.jpg` | fixture/media | 379,551 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200031_noisy.jpg` | fixture/media | 363,988 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200032_noisy.jpg` | fixture/media | 344,193 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200033_noisy.jpg` | fixture/media | 452,950 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200034_noisy.jpg` | fixture/media | 379,795 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200035_noisy.jpg` | fixture/media | 374,142 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200036_noisy.jpg` | fixture/media | 376,036 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200037_noisy.jpg` | fixture/media | 412,884 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200038_noisy.jpg` | fixture/media | 367,707 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200039_noisy.jpg` | fixture/media | 327,888 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200040_noisy.jpg` | fixture/media | 417,281 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200041_noisy.jpg` | fixture/media | 354,721 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200042_noisy.jpg` | fixture/media | 455,651 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200043_noisy.jpg` | fixture/media | 408,637 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200044_noisy.jpg` | fixture/media | 415,228 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200045_noisy.jpg` | fixture/media | 422,847 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200046_noisy.jpg` | fixture/media | 416,275 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200047_noisy.jpg` | fixture/media | 377,458 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200048_noisy.jpg` | fixture/media | 370,522 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200049_noisy.jpg` | fixture/media | 353,702 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200050_noisy.jpg` | fixture/media | 367,117 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200051_noisy.jpg` | fixture/media | 364,721 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200052_noisy.jpg` | fixture/media | 339,485 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200053_noisy.jpg` | fixture/media | 425,424 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200054_noisy.jpg` | fixture/media | 376,200 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200055_noisy.jpg` | fixture/media | 326,053 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200056_noisy.jpg` | fixture/media | 333,351 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200057_noisy.jpg` | fixture/media | 325,778 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200058_noisy.jpg` | fixture/media | 432,267 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200059_noisy.jpg` | fixture/media | 421,604 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200060_noisy.jpg` | fixture/media | 374,088 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200061_noisy.jpg` | fixture/media | 355,327 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200062_noisy.jpg` | fixture/media | 422,531 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200063_noisy.jpg` | fixture/media | 341,992 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200064_noisy.jpg` | fixture/media | 371,715 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200065_noisy.jpg` | fixture/media | 330,052 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200066_noisy.jpg` | fixture/media | 379,325 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200067_noisy.jpg` | fixture/media | 355,645 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200068_noisy.jpg` | fixture/media | 331,833 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200069_noisy.jpg` | fixture/media | 381,322 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200070_noisy.jpg` | fixture/media | 369,835 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200071_noisy.jpg` | fixture/media | 394,808 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200072_noisy.jpg` | fixture/media | 432,952 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200073_noisy.jpg` | fixture/media | 435,450 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200074_noisy.jpg` | fixture/media | 383,095 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200075_noisy.jpg` | fixture/media | 411,642 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200076_noisy.jpg` | fixture/media | 405,115 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200077_noisy.jpg` | fixture/media | 477,760 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200078_noisy.jpg` | fixture/media | 423,334 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200079_noisy.jpg` | fixture/media | 340,540 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200080_noisy.jpg` | fixture/media | 344,137 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200081_noisy.jpg` | fixture/media | 342,347 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200082_noisy.jpg` | fixture/media | 425,639 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200083_noisy.jpg` | fixture/media | 351,224 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200084_noisy.jpg` | fixture/media | 472,871 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200085_noisy.jpg` | fixture/media | 366,080 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200086_noisy.jpg` | fixture/media | 479,680 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200087_noisy.jpg` | fixture/media | 418,953 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200088_noisy.jpg` | fixture/media | 403,059 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200089_noisy.jpg` | fixture/media | 358,005 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200090_noisy.jpg` | fixture/media | 393,356 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200091_noisy.jpg` | fixture/media | 348,829 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200092_noisy.jpg` | fixture/media | 360,314 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200093_noisy.jpg` | fixture/media | 416,593 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200094_noisy.jpg` | fixture/media | 456,260 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200095_noisy.jpg` | fixture/media | 407,895 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200096_noisy.jpg` | fixture/media | 413,895 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200097_noisy.jpg` | fixture/media | 380,944 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200098_noisy.jpg` | fixture/media | 411,872 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200099_noisy.jpg` | fixture/media | 411,755 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200100_noisy.jpg` | fixture/media | 353,074 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200101_noisy.jpg` | fixture/media | 419,261 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200102_noisy.jpg` | fixture/media | 446,959 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200103_noisy.jpg` | fixture/media | 457,584 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200104_noisy.jpg` | fixture/media | 391,004 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200105_noisy.jpg` | fixture/media | 373,812 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200106_noisy.jpg` | fixture/media | 472,391 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200107_noisy.jpg` | fixture/media | 421,038 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200108_noisy.jpg` | fixture/media | 442,131 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200109_noisy.jpg` | fixture/media | 357,247 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200110_noisy.jpg` | fixture/media | 360,684 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200111_noisy.jpg` | fixture/media | 410,873 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200112_noisy.jpg` | fixture/media | 476,776 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200113_noisy.jpg` | fixture/media | 415,939 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200114_noisy.jpg` | fixture/media | 338,011 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200115_noisy.jpg` | fixture/media | 369,228 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200116_noisy.jpg` | fixture/media | 349,725 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200117_noisy.jpg` | fixture/media | 394,184 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200118_noisy.jpg` | fixture/media | 433,854 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200119_noisy.jpg` | fixture/media | 461,474 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200120_noisy.jpg` | fixture/media | 335,468 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200121_noisy.jpg` | fixture/media | 318,620 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200122_noisy.jpg` | fixture/media | 341,110 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200123_noisy.jpg` | fixture/media | 359,375 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200124_noisy.jpg` | fixture/media | 354,353 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200125_noisy.jpg` | fixture/media | 364,478 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200126_noisy.jpg` | fixture/media | 452,705 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200127_noisy.jpg` | fixture/media | 419,246 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200128_noisy.jpg` | fixture/media | 404,900 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200129_noisy.jpg` | fixture/media | 363,427 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200130_noisy.jpg` | fixture/media | 460,807 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200131_noisy.jpg` | fixture/media | 397,129 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200132_noisy.jpg` | fixture/media | 345,877 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200133_noisy.jpg` | fixture/media | 405,916 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200134_noisy.jpg` | fixture/media | 398,667 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200135_noisy.jpg` | fixture/media | 420,782 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200136_noisy.jpg` | fixture/media | 344,725 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200137_noisy.jpg` | fixture/media | 444,046 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200138_noisy.jpg` | fixture/media | 440,184 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200139_noisy.jpg` | fixture/media | 387,402 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200140_noisy.jpg` | fixture/media | 410,083 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200141_noisy.jpg` | fixture/media | 325,419 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200142_noisy.jpg` | fixture/media | 359,528 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200143_noisy.jpg` | fixture/media | 436,884 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200144_noisy.jpg` | fixture/media | 370,603 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200145_noisy.jpg` | fixture/media | 359,084 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200146_noisy.jpg` | fixture/media | 371,086 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200147_noisy.jpg` | fixture/media | 330,483 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200148_noisy.jpg` | fixture/media | 412,024 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200149_noisy.jpg` | fixture/media | 439,801 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200150_noisy.jpg` | fixture/media | 413,671 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200151_noisy.jpg` | fixture/media | 370,704 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200152_noisy.jpg` | fixture/media | 393,285 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200153_noisy.jpg` | fixture/media | 391,495 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200154_noisy.jpg` | fixture/media | 346,015 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200155_noisy.jpg` | fixture/media | 342,756 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200156_noisy.jpg` | fixture/media | 350,921 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200157_noisy.jpg` | fixture/media | 431,047 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200158_noisy.jpg` | fixture/media | 373,324 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200159_noisy.jpg` | fixture/media | 458,523 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200160_noisy.jpg` | fixture/media | 367,294 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200161_noisy.jpg` | fixture/media | 340,617 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200162_noisy.jpg` | fixture/media | 342,032 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200163_noisy.jpg` | fixture/media | 366,807 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200164_noisy.jpg` | fixture/media | 331,528 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200165_noisy.jpg` | fixture/media | 406,031 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200166_noisy.jpg` | fixture/media | 314,834 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200167_noisy.jpg` | fixture/media | 333,457 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200168_noisy.jpg` | fixture/media | 330,654 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200169_noisy.jpg` | fixture/media | 426,989 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200170_noisy.jpg` | fixture/media | 343,645 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200171_noisy.jpg` | fixture/media | 403,641 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200172_noisy.jpg` | fixture/media | 377,729 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200173_noisy.jpg` | fixture/media | 429,794 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200174_noisy.jpg` | fixture/media | 345,694 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200175_noisy.jpg` | fixture/media | 417,607 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200176_noisy.jpg` | fixture/media | 402,783 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200177_noisy.jpg` | fixture/media | 442,310 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200178_noisy.jpg` | fixture/media | 439,742 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200179_noisy.jpg` | fixture/media | 365,649 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200180_noisy.jpg` | fixture/media | 363,748 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200181_noisy.jpg` | fixture/media | 326,387 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200182_noisy.jpg` | fixture/media | 351,551 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200183_noisy.jpg` | fixture/media | 350,145 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200184_noisy.jpg` | fixture/media | 485,477 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200185_noisy.jpg` | fixture/media | 425,987 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200186_noisy.jpg` | fixture/media | 450,852 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200187_noisy.jpg` | fixture/media | 412,650 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200188_noisy.jpg` | fixture/media | 419,416 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200189_noisy.jpg` | fixture/media | 402,931 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200190_noisy.jpg` | fixture/media | 356,025 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200191_noisy.jpg` | fixture/media | 401,044 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200192_noisy.jpg` | fixture/media | 452,039 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200193_noisy.jpg` | fixture/media | 345,890 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200194_noisy.jpg` | fixture/media | 457,697 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200195_noisy.jpg` | fixture/media | 341,778 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200196_noisy.jpg` | fixture/media | 357,370 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200197_noisy.jpg` | fixture/media | 326,046 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200198_noisy.jpg` | fixture/media | 380,147 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200199_noisy.jpg` | fixture/media | 416,675 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200200_noisy.jpg` | fixture/media | 434,051 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200201_noisy.jpg` | fixture/media | 347,771 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200202_noisy.jpg` | fixture/media | 362,314 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200203_noisy.jpg` | fixture/media | 427,429 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200204_noisy.jpg` | fixture/media | 416,747 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200205_noisy.jpg` | fixture/media | 391,466 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200206_noisy.jpg` | fixture/media | 334,361 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200207_noisy.jpg` | fixture/media | 360,281 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200208_noisy.jpg` | fixture/media | 325,735 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200209_noisy.jpg` | fixture/media | 367,933 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200210_noisy.jpg` | fixture/media | 388,182 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200211_noisy.jpg` | fixture/media | 444,315 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200212_noisy.jpg` | fixture/media | 424,178 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200213_noisy.jpg` | fixture/media | 354,681 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200214_noisy.jpg` | fixture/media | 332,927 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200215_noisy.jpg` | fixture/media | 435,090 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200216_noisy.jpg` | fixture/media | 358,415 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200217_noisy.jpg` | fixture/media | 419,879 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200218_noisy.jpg` | fixture/media | 348,171 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200219_noisy.jpg` | fixture/media | 350,364 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200220_noisy.jpg` | fixture/media | 346,979 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200221_noisy.jpg` | fixture/media | 433,039 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200222_noisy.jpg` | fixture/media | 356,623 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200223_noisy.jpg` | fixture/media | 428,758 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200224_noisy.jpg` | fixture/media | 380,762 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200225_noisy.jpg` | fixture/media | 411,578 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200226_noisy.jpg` | fixture/media | 324,079 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200227_noisy.jpg` | fixture/media | 388,874 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200228_noisy.jpg` | fixture/media | 433,898 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200229_noisy.jpg` | fixture/media | 422,890 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200230_noisy.jpg` | fixture/media | 411,612 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200231_noisy.jpg` | fixture/media | 354,346 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200232_noisy.jpg` | fixture/media | 396,173 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200233_noisy.jpg` | fixture/media | 448,199 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200234_noisy.jpg` | fixture/media | 415,524 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200235_noisy.jpg` | fixture/media | 488,906 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200236_noisy.jpg` | fixture/media | 357,803 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200237_noisy.jpg` | fixture/media | 434,669 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200238_noisy.jpg` | fixture/media | 425,236 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200239_noisy.jpg` | fixture/media | 328,068 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200240_noisy.jpg` | fixture/media | 379,258 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200241_noisy.jpg` | fixture/media | 420,388 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200242_noisy.jpg` | fixture/media | 386,006 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200243_noisy.jpg` | fixture/media | 411,814 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200244_noisy.jpg` | fixture/media | 387,347 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200245_noisy.jpg` | fixture/media | 372,522 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200246_noisy.jpg` | fixture/media | 362,945 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200247_noisy.jpg` | fixture/media | 424,189 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200248_noisy.jpg` | fixture/media | 331,181 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200249_noisy.jpg` | fixture/media | 421,892 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200250_noisy.jpg` | fixture/media | 470,558 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200251_noisy.jpg` | fixture/media | 428,786 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200252_noisy.jpg` | fixture/media | 331,153 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200253_noisy.jpg` | fixture/media | 427,644 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200254_noisy.jpg` | fixture/media | 360,485 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200255_noisy.jpg` | fixture/media | 465,151 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200256_noisy.jpg` | fixture/media | 427,785 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200257_noisy.jpg` | fixture/media | 374,630 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200258_noisy.jpg` | fixture/media | 347,483 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200259_noisy.jpg` | fixture/media | 358,091 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200260_noisy.jpg` | fixture/media | 336,956 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200261_noisy.jpg` | fixture/media | 432,499 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200262_noisy.jpg` | fixture/media | 331,122 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200263_noisy.jpg` | fixture/media | 347,866 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200264_noisy.jpg` | fixture/media | 367,299 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200265_noisy.jpg` | fixture/media | 410,807 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200266_noisy.jpg` | fixture/media | 367,896 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200267_noisy.jpg` | fixture/media | 334,849 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200268_noisy.jpg` | fixture/media | 334,110 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200269_noisy.jpg` | fixture/media | 439,751 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200270_noisy.jpg` | fixture/media | 334,571 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200271_noisy.jpg` | fixture/media | 402,555 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200272_noisy.jpg` | fixture/media | 429,875 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200273_noisy.jpg` | fixture/media | 389,183 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200274_noisy.jpg` | fixture/media | 354,365 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200275_noisy.jpg` | fixture/media | 360,957 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200276_noisy.jpg` | fixture/media | 421,346 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200277_noisy.jpg` | fixture/media | 333,878 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200278_noisy.jpg` | fixture/media | 363,170 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200279_noisy.jpg` | fixture/media | 378,185 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200280_noisy.jpg` | fixture/media | 437,601 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200281_noisy.jpg` | fixture/media | 417,530 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200282_noisy.jpg` | fixture/media | 349,988 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200283_noisy.jpg` | fixture/media | 439,299 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200284_noisy.jpg` | fixture/media | 413,013 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200285_noisy.jpg` | fixture/media | 387,622 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200286_noisy.jpg` | fixture/media | 460,539 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200287_noisy.jpg` | fixture/media | 377,897 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200288_noisy.jpg` | fixture/media | 358,472 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200289_noisy.jpg` | fixture/media | 468,777 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200290_noisy.jpg` | fixture/media | 443,337 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200291_noisy.jpg` | fixture/media | 456,991 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200292_noisy.jpg` | fixture/media | 355,220 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200293_noisy.jpg` | fixture/media | 435,958 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200294_noisy.jpg` | fixture/media | 359,657 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200295_noisy.jpg` | fixture/media | 336,994 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200296_noisy.jpg` | fixture/media | 385,959 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200297_noisy.jpg` | fixture/media | 415,476 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200298_noisy.jpg` | fixture/media | 378,558 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200299_noisy.jpg` | fixture/media | 471,972 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200300_noisy.jpg` | fixture/media | 363,200 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200301_noisy.jpg` | fixture/media | 344,992 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200302_noisy.jpg` | fixture/media | 437,224 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200303_noisy.jpg` | fixture/media | 417,324 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200304_noisy.jpg` | fixture/media | 361,404 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200305_noisy.jpg` | fixture/media | 432,689 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200306_noisy.jpg` | fixture/media | 411,283 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200307_noisy.jpg` | fixture/media | 414,085 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200308_noisy.jpg` | fixture/media | 385,720 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200309_noisy.jpg` | fixture/media | 432,405 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200310_noisy.jpg` | fixture/media | 319,661 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200311_noisy.jpg` | fixture/media | 351,471 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200312_noisy.jpg` | fixture/media | 356,801 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200313_noisy.jpg` | fixture/media | 342,335 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200314_noisy.jpg` | fixture/media | 436,195 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200315_noisy.jpg` | fixture/media | 342,041 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200316_noisy.jpg` | fixture/media | 351,792 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200317_noisy.jpg` | fixture/media | 306,871 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200318_noisy.jpg` | fixture/media | 459,281 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200319_noisy.jpg` | fixture/media | 434,201 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200320_noisy.jpg` | fixture/media | 451,222 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200321_noisy.jpg` | fixture/media | 302,858 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200322_noisy.jpg` | fixture/media | 427,641 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200323_noisy.jpg` | fixture/media | 331,412 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200324_noisy.jpg` | fixture/media | 365,240 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200325_noisy.jpg` | fixture/media | 366,894 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200326_noisy.jpg` | fixture/media | 433,755 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200327_noisy.jpg` | fixture/media | 331,477 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200328_noisy.jpg` | fixture/media | 396,728 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200329_noisy.jpg` | fixture/media | 421,280 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200330_noisy.jpg` | fixture/media | 404,339 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200331_noisy.jpg` | fixture/media | 360,806 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200332_noisy.jpg` | fixture/media | 327,983 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200333_noisy.jpg` | fixture/media | 484,574 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200334_noisy.jpg` | fixture/media | 375,350 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200335_noisy.jpg` | fixture/media | 329,285 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200336_noisy.jpg` | fixture/media | 348,034 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200337_noisy.jpg` | fixture/media | 349,828 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200338_noisy.jpg` | fixture/media | 418,165 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200339_noisy.jpg` | fixture/media | 432,628 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200340_noisy.jpg` | fixture/media | 330,533 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200341_noisy.jpg` | fixture/media | 362,156 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200342_noisy.jpg` | fixture/media | 340,486 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200343_noisy.jpg` | fixture/media | 302,858 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200344_noisy.jpg` | fixture/media | 424,049 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200345_noisy.jpg` | fixture/media | 448,501 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200346_noisy.jpg` | fixture/media | 366,957 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200347_noisy.jpg` | fixture/media | 337,993 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200348_noisy.jpg` | fixture/media | 405,318 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200349_noisy.jpg` | fixture/media | 424,912 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200350_noisy.jpg` | fixture/media | 425,467 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200351_noisy.jpg` | fixture/media | 350,931 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200352_noisy.jpg` | fixture/media | 376,839 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200353_noisy.jpg` | fixture/media | 351,866 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200354_noisy.jpg` | fixture/media | 344,275 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200355_noisy.jpg` | fixture/media | 416,619 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200356_noisy.jpg` | fixture/media | 399,897 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200357_noisy.jpg` | fixture/media | 334,314 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200358_noisy.jpg` | fixture/media | 351,842 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200359_noisy.jpg` | fixture/media | 366,289 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200360_noisy.jpg` | fixture/media | 450,618 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200361_noisy.jpg` | fixture/media | 409,779 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200362_noisy.jpg` | fixture/media | 438,420 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200363_noisy.jpg` | fixture/media | 377,961 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200364_noisy.jpg` | fixture/media | 343,779 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200365_noisy.jpg` | fixture/media | 338,891 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200366_noisy.jpg` | fixture/media | 407,031 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200367_noisy.jpg` | fixture/media | 414,403 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200368_noisy.jpg` | fixture/media | 349,807 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200369_noisy.jpg` | fixture/media | 354,707 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200370_noisy.jpg` | fixture/media | 343,362 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200371_noisy.jpg` | fixture/media | 450,085 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200372_noisy.jpg` | fixture/media | 398,191 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200373_noisy.jpg` | fixture/media | 373,290 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200374_noisy.jpg` | fixture/media | 426,548 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200375_noisy.jpg` | fixture/media | 326,638 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200376_noisy.jpg` | fixture/media | 402,821 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200377_noisy.jpg` | fixture/media | 327,651 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200378_noisy.jpg` | fixture/media | 477,182 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200379_noisy.jpg` | fixture/media | 398,777 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200380_noisy.jpg` | fixture/media | 346,190 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200381_noisy.jpg` | fixture/media | 341,960 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200382_noisy.jpg` | fixture/media | 355,643 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200383_noisy.jpg` | fixture/media | 319,260 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200384_noisy.jpg` | fixture/media | 371,342 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200385_noisy.jpg` | fixture/media | 418,494 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200386_noisy.jpg` | fixture/media | 391,200 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200387_noisy.jpg` | fixture/media | 411,289 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200388_noisy.jpg` | fixture/media | 342,692 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200389_noisy.jpg` | fixture/media | 359,971 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200390_noisy.jpg` | fixture/media | 442,174 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200391_noisy.jpg` | fixture/media | 407,758 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200392_noisy.jpg` | fixture/media | 360,437 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200393_noisy.jpg` | fixture/media | 387,104 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200394_noisy.jpg` | fixture/media | 374,566 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200395_noisy.jpg` | fixture/media | 346,651 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200396_noisy.jpg` | fixture/media | 389,183 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200397_noisy.jpg` | fixture/media | 427,312 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200398_noisy.jpg` | fixture/media | 375,698 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200399_noisy.jpg` | fixture/media | 386,514 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200400_noisy.jpg` | fixture/media | 377,897 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200401_noisy.jpg` | fixture/media | 352,675 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200402_noisy.jpg` | fixture/media | 322,909 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200403_noisy.jpg` | fixture/media | 426,752 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200404_noisy.jpg` | fixture/media | 441,710 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200405_noisy.jpg` | fixture/media | 348,473 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200406_noisy.jpg` | fixture/media | 373,083 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200407_noisy.jpg` | fixture/media | 357,046 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200408_noisy.jpg` | fixture/media | 328,016 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200409_noisy.jpg` | fixture/media | 442,160 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200410_noisy.jpg` | fixture/media | 367,591 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200411_noisy.jpg` | fixture/media | 343,982 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200412_noisy.jpg` | fixture/media | 330,988 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200413_noisy.jpg` | fixture/media | 480,461 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200414_noisy.jpg` | fixture/media | 333,756 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200415_noisy.jpg` | fixture/media | 340,335 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200416_noisy.jpg` | fixture/media | 327,825 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200417_noisy.jpg` | fixture/media | 411,941 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200418_noisy.jpg` | fixture/media | 327,713 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200419_noisy.jpg` | fixture/media | 353,483 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200420_noisy.jpg` | fixture/media | 436,334 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200421_noisy.jpg` | fixture/media | 424,667 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200422_noisy.jpg` | fixture/media | 372,665 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200423_noisy.jpg` | fixture/media | 359,272 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200424_noisy.jpg` | fixture/media | 349,893 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200425_noisy.jpg` | fixture/media | 333,704 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200426_noisy.jpg` | fixture/media | 418,850 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200427_noisy.jpg` | fixture/media | 395,931 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200428_noisy.jpg` | fixture/media | 317,992 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200429_noisy.jpg` | fixture/media | 330,303 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200430_noisy.jpg` | fixture/media | 364,801 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200431_noisy.jpg` | fixture/media | 415,624 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200432_noisy.jpg` | fixture/media | 463,480 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200433_noisy.jpg` | fixture/media | 383,622 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200434_noisy.jpg` | fixture/media | 455,985 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200435_noisy.jpg` | fixture/media | 459,627 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200436_noisy.jpg` | fixture/media | 419,221 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200437_noisy.jpg` | fixture/media | 368,250 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200438_noisy.jpg` | fixture/media | 362,506 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200439_noisy.jpg` | fixture/media | 362,306 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200440_noisy.jpg` | fixture/media | 426,220 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200441_noisy.jpg` | fixture/media | 363,777 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200442_noisy.jpg` | fixture/media | 451,745 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200443_noisy.jpg` | fixture/media | 314,915 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200444_noisy.jpg` | fixture/media | 354,683 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200445_noisy.jpg` | fixture/media | 360,052 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200446_noisy.jpg` | fixture/media | 429,783 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200447_noisy.jpg` | fixture/media | 462,097 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200448_noisy.jpg` | fixture/media | 371,704 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200449_noisy.jpg` | fixture/media | 475,128 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200450_noisy.jpg` | fixture/media | 354,318 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200451_noisy.jpg` | fixture/media | 360,651 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200452_noisy.jpg` | fixture/media | 358,386 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200453_noisy.jpg` | fixture/media | 420,228 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200454_noisy.jpg` | fixture/media | 357,902 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200455_noisy.jpg` | fixture/media | 338,077 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200456_noisy.jpg` | fixture/media | 387,504 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200457_noisy.jpg` | fixture/media | 409,518 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200458_noisy.jpg` | fixture/media | 370,994 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200459_noisy.jpg` | fixture/media | 374,762 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200460_noisy.jpg` | fixture/media | 343,828 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200461_noisy.jpg` | fixture/media | 330,532 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200462_noisy.jpg` | fixture/media | 371,203 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200463_noisy.jpg` | fixture/media | 404,509 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200464_noisy.jpg` | fixture/media | 429,547 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200465_noisy.jpg` | fixture/media | 437,240 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200466_noisy.jpg` | fixture/media | 456,722 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200467_noisy.jpg` | fixture/media | 344,362 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200468_noisy.jpg` | fixture/media | 384,581 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200469_noisy.jpg` | fixture/media | 339,942 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200470_noisy.jpg` | fixture/media | 372,656 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200471_noisy.jpg` | fixture/media | 359,761 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200472_noisy.jpg` | fixture/media | 359,376 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200473_noisy.jpg` | fixture/media | 393,852 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200474_noisy.jpg` | fixture/media | 344,966 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200475_noisy.jpg` | fixture/media | 343,594 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200476_noisy.jpg` | fixture/media | 419,860 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200477_noisy.jpg` | fixture/media | 406,292 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200478_noisy.jpg` | fixture/media | 418,328 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200479_noisy.jpg` | fixture/media | 359,063 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200480_noisy.jpg` | fixture/media | 356,064 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200481_noisy.jpg` | fixture/media | 347,800 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200482_noisy.jpg` | fixture/media | 343,143 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200483_noisy.jpg` | fixture/media | 344,864 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200484_noisy.jpg` | fixture/media | 370,790 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200485_noisy.jpg` | fixture/media | 339,332 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200486_noisy.jpg` | fixture/media | 349,576 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200487_noisy.jpg` | fixture/media | 354,396 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200488_noisy.jpg` | fixture/media | 360,955 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200489_noisy.jpg` | fixture/media | 469,326 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200490_noisy.jpg` | fixture/media | 433,555 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200491_noisy.jpg` | fixture/media | 375,190 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200492_noisy.jpg` | fixture/media | 334,029 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200493_noisy.jpg` | fixture/media | 420,201 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200494_noisy.jpg` | fixture/media | 413,442 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200495_noisy.jpg` | fixture/media | 324,129 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200496_noisy.jpg` | fixture/media | 352,088 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200497_noisy.jpg` | fixture/media | 436,918 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200498_noisy.jpg` | fixture/media | 367,376 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200499_noisy.jpg` | fixture/media | 404,719 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries/med_doc_discharge_summary_200500_noisy.jpg` | fixture/media | 347,751 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/discharge_summaries_ground_truth.csv` | other | 671,733 | — | 0 | No |
| `REFERNCE DATASETS/Medical_Bills/public/Data/medical_bills_ground_truth.csv` | other | 652,147 | — | 0 | No |
| `REFERNCE DATASETS/Medicines/package.txt` | documentation/report | 29,880,022 | 216187 | 0 | No |
| `REFERNCE DATASETS/Medicines/product.txt` | documentation/report | 39,949,053 | 115070 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/HCPC2026_JUL_ANWEB_06172026.txt` | documentation/report | 3,193,427 | 16827 | 1 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/HCPC2026_JUL_ANWEB_06172026.xlsx` | other | 1,921,560 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/HCPC2026_JUL_ANWEB_Corrections.xlsx` | other | 18,612 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/HCPC2026_JUL_ANWEB_Transaction Report_06172026.xlsx` | other | 838,079 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/HCPC2026_recordlayout.txt` | documentation/report | 62,138 | 995 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/NOC codes_JUL2026.xlsx` | other | 20,368 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/HCPCS/proc_notes_JUL2026.txt` | documentation/report | 44,816 | 652 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/ICD-10-CM-October-1-2026-FY27-Guidelines.pdf` | fixture/media | 830,104 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-code-descriptions-2027/icd10cm-codes-2027.txt` | documentation/report | 6,425,201 | 74880 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-code-descriptions-2027/icd10cm-codes-addenda-2027.txt` | documentation/report | 18,561 | 236 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-code-descriptions-2027/icd10cm-order-2027.txt` | documentation/report | 14,724,229 | 98404 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-code-descriptions-2027/icd10cm-order-addenda-2027.txt` | documentation/report | 42,495 | 320 | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-code-descriptions-2027/icd10cmCodesFile.pdf` | fixture/media | 114,279 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-code-descriptions-2027/icd10OrderFiles.pdf` | fixture/media | 141,901 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-drug-2027.pdf` | fixture/media | 32,536,134 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-drug-2027.xml` | other | 2,123,972 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-drug-neoplasm.xsd` | other | 5,518 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-eindex-2027.pdf` | fixture/media | 4,154,359 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-eindex-2027.xml` | other | 1,051,110 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-index-2027.pdf` | fixture/media | 42,765,290 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-index-2027.xml` | other | 9,707,127 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-index.xsd` | other | 6,301 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-neoplasm-2027.pdf` | fixture/media | 4,704,516 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-neoplasm-2027.xml` | other | 583,387 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-tabular-2027.pdf` | fixture/media | 29,487,597 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-tabular.xsd` | other | 12,170 | — | 0 | No |
| `REFERNCE DATASETS/Procedure_codes/ICD10/icd10cm-table-and-index-2027/icd10cm-tabular_-2027.xml` | other | 9,779,494 | — | 0 | No |
| `REFERNCE DATASETS/Resource_Planning/Hardware_Requirements.xlsx` | other | 5,046 | — | 0 | No |
| `REFERNCE DATASETS/Resource_Planning/Libraries.xlsx` | other | 5,250 | — | 0 | No |
| `REFERNCE DATASETS/Resource_Planning/README(2).md` | documentation/report | 316 | 16 | 0 | No |
| `REFERNCE DATASETS/Resource_Planning/Software_Requirements.xlsx` | other | 5,112 | — | 0 | No |
| `REFERNCE DATASETS/ResourceMatrix/Final_Resource_Matrix.xlsx` | other | 5,493 | — | 0 | No |
| `REFERNCE DATASETS/ResourceMatrix/README(6).md` | documentation/report | 275 | 9 | 0 | No |
| `REFERNCE DATASETS/RiskAnalysis/Challenges_and_Solutions.xlsx` | other | 5,102 | — | 0 | No |
| `REFERNCE DATASETS/RiskAnalysis/README(5).md` | documentation/report | 234 | 8 | 0 | No |
| `REFERNCE DATASETS/RiskAnalysis/Risk_Matrix.xlsx` | other | 5,325 | — | 0 | No |
| `reports.py` | source | 3,988 | 50 | 0 | No |
| `requirements.txt` | documentation/report | 364 | 16 | 0 | No |
| `rules.py` | source | 11,414 | 174 | 0 | No |
| `run_complete_audit.py` | source | 10,879 | 84 | 4 | No |
| `run_full_audit_suite.py` | test/tool | 1,145 | 27 | 0 | No |
| `sample_documents/bill_clean_mobile_demo (1).png` | fixture/media | 164,558 | — | 0 | No |
| `sample_documents/med_doc_bill_100001_noisy.jpg` | fixture/media | 212,713 | — | 0 | No |
| `sample_documents/POL-DEMO-2026-001.pdf` | fixture/media | 3,282 | — | 0 | No |
| `sample_documents/policy_bill_matched_usd.pdf` | fixture/media | 4,339 | — | 0 | No |
| `sample_documents/sample_medical_bill.pdf` | fixture/media | 1,984 | — | 0 | No |
| `sample_documents/sample_medical_bill_image.png` | fixture/media | 78,232 | — | 0 | No |
| `sample_documents/sample_policy.pdf` | fixture/media | 2,117 | — | 0 | No |
| `streamlit_smoke.log` | other | 54 | — | 0 | No |
| `test_core_advancements.py` | test/tool | 917 | 19 | 0 | No |
| `test_end_to_end.py` | test/tool | 3,852 | 75 | 0 | No |
| `test_phase5_real_document_quality.py` | test/tool | 2,795 | 43 | 0 | No |
| `test_phase6_business_rules.py` | test/tool | 2,857 | 41 | 0 | No |
| `verify_clean_mobile_pair.py` | test/tool | 1,683 | 26 | 0 | No |

## Core-file assessment

| File | Responsibility | Audit assessment |
|---|---|---|
| `app.py` | Main Streamlit UI, SQLite access, auth helpers, claim orchestration, policy screens, result rendering. Large high-risk integration file; inspect import/runtime paths and keep auth disabled only for demo. | Review required before production use. |
| `agents.py` | Two-agent LangGraph/Ollama workflow. Must remain compact-evidence-only, strict JSON, bounded calls, and Manual Review fallback. | Review required before production use. |
| `extraction.py` | PyMuPDF/Tesseract extraction and normalization. Verify confidence/provenance and image/PDF parity. | Review required before production use. |
| `rules.py` | Deterministic financial rule engine. Authoritative calculation layer; protect with fixture matrix. | Review required before production use. |
| `policy_terms.py` | Policy term extraction and normalization. Must avoid demonstration defaults when live policy terms are absent. | Review required before production use. |
| `policy_index.py` | Persistent ChromaDB indexing/retrieval. Verify policy-number matching and persistence. | Review required before production use. |
| `policy_compare.py` | Policy-edition comparison utility. Optional to core flow but imported by app. | Review required before production use. |
| `reports.py` | Report/appeal generation. Optional/deferred feature but imported by app, so import failure can break startup. | Review required before production use. |
| `requirements.txt` | Dependency manifest. Tesseract is correctly used instead of PaddleOCR for Python 3.13 Windows; versions are minimums rather than fully locked pins. | Review required before production use. |

## Static verification

| Check | Result |
|---|---|
| Python parse: `agents.py` | PASS |
| Python parse: `app.py` | PASS |
| Python parse: `extraction.py` | PASS |
| Python parse: `policy_compare.py` | PASS |
| Python parse: `policy_index.py` | PASS |
| Python parse: `policy_terms.py` | PASS |
| Python parse: `reports.py` | PASS |
| Python parse: `rules.py` | PASS |
| Python parse: `run_complete_audit.py` | PASS |
| Python parse: `run_full_audit_suite.py` | PASS |
| Python parse: `test_core_advancements.py` | PASS |
| Python parse: `test_end_to_end.py` | PASS |
| Python parse: `test_phase5_real_document_quality.py` | PASS |
| Python parse: `test_phase6_business_rules.py` | PASS |
| Python parse: `verify_clean_mobile_pair.py` | PASS |
| Imported local modules missing from project root | None detected |
| `AGENTS.md` found | No |

## Database inventory

| Table | Rows | Columns |
|---|---:|---|
| `audit_events` | 591 | event_id, claim_id, actor, event_type, details, created_at |
| `claims` | 130 | claim_id, user_id, claim_number, patient_name, hospital_name, policy_number, incident_date, status, created_at, updated_at, assigned_reviewer_id, review_priority, adjudication_context_json |
| `documents` | 53 | document_id, claim_id, original_name, stored_path, document_type, size_bytes, sha256, page_count, processing_status, created_at, extracted_json, extraction_error |
| `evidence_confirmations` | 25 | confirmation_id, claim_id, reviewer_id, field_name, document_id, page_number, confirmed_at |
| `password_reset_tokens` | 21 | reset_id, user_id, token_hash, expires_at, used_at, created_at |
| `policy_versions` | 4 | version_id, policy_number, version_label, insurer_name, effective_date, status, source_name, stored_path, content_text, indexed_chunks, created_at, policy_terms_json |
| `reviewer_decisions` | 25 | review_id, claim_id, reviewer_id, automated_status, final_status, comments, created_at |
| `reviewer_field_edits` | 50 | edit_id, claim_id, reviewer_id, field_name, old_value, new_value, created_at |
| `reviewer_invitations` | 46 | invitation_id, user_id, token_hash, expires_at, used_at, created_by, created_at |
| `rule_evaluations` | 25 | evaluation_id, claim_id, rule_version, status, result_json, created_at |
| `users` | 175 | user_id, email, display_name, role, created_at, password_hash, is_active, password_set_at, disabled_at, mfa_enabled, mfa_secret_encrypted |

## Configuration review

```text
streamlit>=1.40.0
requests>=2.32.0
python-dotenv>=1.0.0
pymupdf>=1.24.0
pydantic>=2.8.0
# PaddlePaddle 2.6.1 is unavailable for this Python 3.13 Windows environment.
# Image OCR uses the stable Tesseract backend instead.
pytesseract>=0.3.13
Pillow>=10.0.0
langgraph>=0.2.0
langchain-ollama>=0.2.0
chromadb>=0.5.0
reportlab>=4.2.0
cryptography>=43.0.0
pyotp>=2.9.0
```

- `requirements.txt` deliberately excludes PaddleOCR/PaddlePaddle and uses Tesseract, matching the Windows Python 3.13 decision.
- Dependency versions use `>=` ranges, so reproducibility is weaker than a lock file or exact pins.
- `.env.example` is absent from the current root inventory and is shown as deleted by Git status; restore a safe template before handoff.
- `.gitignore` is absent from the current root inventory and is shown as deleted by Git status; this can expose SQLite, uploads, ChromaDB, logs, and environment files.

## Repository hygiene and risks

The Git status shows important tracked files deleted from the root, including `.env.example`, `.gitignore`, `README.md`, `SECURITY_OPERATIONS.md`, and several tests. Copies exist in `EXTRA`, but a backup folder is not a substitute for the live project structure. This should be repaired before any release or handoff.

The root contains runtime state such as `data/mediguard.db`, ChromaDB directories, uploads, logs, and generated reports. These should be deliberately classified as local demo artifacts and excluded from version control unless there is a documented reason to keep them.

The application contains authentication and MFA code, but `CORE_DEMO_MODE` defaults to `true`, meaning the core demo can bypass login. This is acceptable only for synthetic local testing and not for real patient documents.

The inspected `app.py` import section calls `base64.urlsafe_b64encode` and `base64.urlsafe_b64decode` in password/MFA functions without showing an import for `base64`. This must be fixed or verified immediately because it would fail when those paths execute.

## Prioritized action plan

| Priority | Action | Reason |
|---|---|---|
| P0 | Restore `.gitignore`, `.env.example`, README, and required tracked tests; remove accidental root deletions or formally document them. | Prevents broken handoff and accidental sensitive-data commits. |
| P0 | Add/verify `import base64` in `app.py`; run authentication/MFA tests if those paths remain in code. | Potential runtime defect in password/MFA functionality. |
| P0 | Confirm the patched dark UI app compiles and starts on Windows after the latest change. | Final live frontend verification was interrupted by the disconnected sidecar. |
| P1 | Lock dependencies using a tested Windows requirements lock or constraints file. | Prevents environment drift. |
| P1 | Run the complete test matrix, not only the reduced root test subset. | Current root is missing many tests that remain in `EXTRA`. |
| P1 | Add explicit tests for covered, excluded, deductible, copayment, and claimant responsibility reconciliation. | Protects the user-facing financial explanation. |
| P2 | Separate demo runtime data from source and define retention/deletion rules. | Medical-document data needs controlled handling. |
| P2 | Keep authentication, MFA, authorization, encryption, audit, and retention work before real-user deployment. | Core demo mode is not production security. |

## Git status evidence

```text
D .env.example
 D .gitignore
 D MEDI_GAURD_AI_MUST_CHECK_AUDIT.md
 D README.md
 D SECURITY_OPERATIONS.md
 M app.py
 M extraction.py
 D generate_phase4_fixtures.py
 M policy_terms.py
 D test_auth_lifecycle.py
 D test_dynamic_policy_terms.py
 D test_normalization_policy_isolation.py
 D test_ocr_fallback.py
 D test_ollama_warmup.py
 D test_phase1_decisions.py
 D test_phase2_agent_failures.py
 D test_phase2_failure_paths.py
 D test_phase2_real_fixtures.py
 D test_phase4_fixture_matrix.py
 D test_phase7_data_security.py
 D test_policy_and_rules.py
 D test_policy_controls_batch.py
 D test_reports.py
 D test_reviewer_controls.py
 D test_reviewer_invitation.py
 D test_reviewer_workflow.py
 D test_security_access.py
?? .agents/
?? CORE_MVP_SIMPLIFICATION.md
?? EXTRA/
?? "REFERNCE DATASETS/"
?? __pycache__/
?? backend_full_audit_test_results.txt
?? clean_mobile_bill_ocr.txt
?? data/
?? fixtures/phase4/bill_clean_mobile_demo.png
?? fixtures/phase4/policy_bill_matched_usd.pdf
?? fixtures/phase4/policy_clean_mobile_demo.pdf
?? run_complete_audit.py
?? run_full_audit_suite.py
?? sample_documents/
?? streamlit_smoke.log
?? test_core_advancements.py
?? verify_clean_mobile_pair.py
```

## Overall rating

**Core MVP functionality:** conditionally working. **Automated evidence:** partial but positive. **Repository readiness:** not ready for release or real medical data until P0 hygiene, security-runtime, and final Windows UI checks are closed.

