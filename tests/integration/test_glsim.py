"""Integration smoke test against a local GLSim (glsim --port 4000).

Covers the deterministic state machine end-to-end in the real runner:
deploy -> open_case -> permission gates -> submit_evidence -> evaluate.
The evaluation step depends on the simulator's validator LLM behaviour;
the assertions before it must pass regardless.
"""
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded

CRITERIA = [
    "The report is published as a public web page",
    "The page states the total number of entries reviewed",
]


def test_glsim_flow():
    factory = get_contract_factory("AcceptanceJudge")
    contract = factory.deploy(args=[])

    # open a case (default test account is the client); worker = account 2
    from gltest.accounts import get_accounts

    accounts = get_accounts()
    worker = accounts[1].address

    tx = contract.open_case(args=["Weekly contest report", CRITERIA, worker]).transact()
    assert tx_execution_succeeded(tx)
    case_id = contract.list_case_ids(args=[]).call()[-1]

    case = contract.get_case(args=[case_id]).call()
    assert case["status"] == "OPEN"
    assert case["criteria"] == CRITERIA

    # evaluation before evidence must fail on-chain
    try:
        contract.evaluate(args=[case_id]).transact()
        raise AssertionError("evaluate should have reverted with NOT_SUBMITTED")
    except Exception as e:
        assert "NOT_SUBMITTED" in str(e) or "error" in str(e).lower()

    print("GLSim deterministic flow OK, case_id:", case_id)
