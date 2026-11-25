"""Direct-mode tests for AcceptanceJudge.

Run:  pytest tests/direct/ -v
The LLM is mocked: the same mocked answer serves leader and validators, so
consensus on the verdict vector is reached deterministically.
"""
import json

CONTRACT = "contracts/acceptance_judge.py"

CRITERIA = [
    "The report is published as a public web page",
    "The page states the total number of entries reviewed",
    "The page names the three winning entries",
]

ALL_MET = json.dumps({
    "criteria": [
        {"met": True, "reason": "Page is public and reachable"},
        {"met": True, "reason": "States 128 entries reviewed"},
        {"met": True, "reason": "Names three winning entries"},
    ],
    "summary": "All criteria demonstrated",
})

ONE_UNMET = json.dumps({
    "criteria": [
        {"met": True, "reason": "Page is public and reachable"},
        {"met": True, "reason": "States 128 entries reviewed"},
        {"met": False, "reason": "Winning entries are not named"},
    ],
    "summary": "Winners not named",
})


def _open_case(contract, direct_vm, client, worker):
    direct_vm.sender = client
    return contract.open_case("Weekly contest report", CRITERIA, worker)


def test_open_case_validation(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT)
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("BAD_CRITERIA_COUNT"):
        contract.open_case("Empty", [], direct_bob)
    with direct_vm.expect_revert("BAD_CRITERIA_COUNT"):
        contract.open_case("Too many", ["c"] * 9, direct_bob)
    case_id = _open_case(contract, direct_vm, direct_alice, direct_bob)
    case = contract.get_case(case_id)
    assert case["status"] == "OPEN"
    assert case["criteria"] == CRITERIA


def test_full_flow_accepted(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy(CONTRACT)
    case_id = _open_case(contract, direct_vm, direct_alice, direct_bob)

    # Evidence can only come from the worker.
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("NOT_WORKER"):
        contract.submit_evidence(case_id, "", "client trying to submit")

    # Evaluation requires submitted evidence first.
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("NOT_SUBMITTED"):
        contract.evaluate(case_id)

    contract.submit_evidence(
        case_id, "", "Report at the linked page: 128 entries, winners named."
    )
    direct_vm.mock_llm(r".*acceptance evaluator.*", ALL_MET)
    contract.evaluate(case_id)

    case = contract.get_case(case_id)
    assert case["status"] == "DECIDED"
    assert case["verdict"] == "ACCEPTED"
    assert case["met"] == [True, True, True]


def test_rejected_when_any_criterion_unmet(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT)
    case_id = _open_case(contract, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_evidence(case_id, "", "Partial report page")
    direct_vm.mock_llm(r".*acceptance evaluator.*", ONE_UNMET)
    contract.evaluate(case_id)

    case = contract.get_case(case_id)
    assert case["verdict"] == "REJECTED"
    assert case["met"] == [True, True, False]
    assert case["reasons"][2] == "Winning entries are not named"


def test_appeal_once_then_exhausted(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy(CONTRACT)
    case_id = _open_case(contract, direct_vm, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_evidence(case_id, "", "Partial report page")
    direct_vm.mock_llm(r".*acceptance evaluator.*", ONE_UNMET)
    contract.evaluate(case_id)
    assert contract.get_case(case_id)["verdict"] == "REJECTED"

    # Client appeals; worker resubmits fixed evidence; verdict flips.
    direct_vm.sender = direct_alice
    contract.appeal(case_id)
    assert contract.get_case(case_id)["status"] == "OPEN"
    direct_vm.sender = direct_bob
    contract.submit_evidence(case_id, "", "Fixed report: winners now named")
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r".*acceptance evaluator.*", ALL_MET)
    contract.evaluate(case_id)
    assert contract.get_case(case_id)["verdict"] == "ACCEPTED"

    # Only one appeal is available.
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("APPEAL_EXHAUSTED"):
        contract.appeal(case_id)
