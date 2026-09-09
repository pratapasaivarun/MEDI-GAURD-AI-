from __future__ import annotations
import app

app.init_db()

# Reconciliation must fail closed when payable does not match the breakdown.
invalid = app._reconcile_result({"status": "approved", "covered_amount": 1000.0, "deductible": 100.0, "copayment": 100.0, "payable_amount": 900.0, "warnings": []}, 1000.0)
assert invalid["status"] == "manual_review"
assert "calculation_reconciliation_failed" in invalid["warnings"]

# A valid breakdown must remain approved and expose claimant-safe amounts.
valid = app._reconcile_result({"status": "approved", "covered_amount": 1000.0, "deductible": 100.0, "copayment": 90.0, "payable_amount": 810.0, "warnings": []}, 1000.0)
assert valid["status"] == "approved"
assert valid["claimant_result"]["amount_billed"] == 1000.0
assert valid["claimant_result"]["amount_covered"] == 810.0
assert valid["claimant_result"]["amount_claimant_pays"] == 190.0

print("CORE_ADVANCEMENTS_OK")
