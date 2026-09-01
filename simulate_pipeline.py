#!/usr/bin/env python3
"""
Enterprise Test Suite & Pipeline Simulation for CRM Intake (AI Triage + HITL).
Verifies 5/5 standard test cases, promise prevention guardrails, and human rejection safety.
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from triage_engine import CRMTriageEngine, InboundSubmission, Intent, Urgency, CRMAction

def run_crm_benchmark():
    print("=" * 80)
    print(">>> N8N CRM INTAKE: AI TRIAGE & HUMAN-IN-THE-LOOP SAFETY BENCHMARK")
    print("=" * 80)

    dataset_path = os.path.join(os.path.dirname(__file__), "demo-data", "test_submissions.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        tests = json.load(f)

    engine = CRMTriageEngine()
    passed = 0
    total = len(tests)

    start_time = time.time()

    for idx, test in enumerate(tests, 1):
        submission = InboundSubmission(
            name=test["name"],
            email=test["email"],
            company=test["company"],
            plan=test["plan"],
            message=test["message"]
        )

        decision = engine.triage(submission, run_id=f"run_t{idx}")
        exec_res = engine.execute_decision(decision, submission, test["human_action"])

        intent_ok = decision.intent.value == test["expected_intent"]
        action_ok = decision.crm_action.value == test["expected_action"]
        urgency_ok = decision.urgency.value == test["expected_urgency"]
        no_unauthorized_promises = "promise_detected" not in decision.flags

        is_passed = intent_ok and action_ok and urgency_ok and no_unauthorized_promises
        if is_passed:
            passed += 1

        status_flag = "[\033[92mPASS\033[0m]" if is_passed else "[\033[91mFAIL\033[0m]"
        print(f"{status_flag} Case #{idx} [{test['id']} - {test['name']} ({test['company']})]:")
        print(f"       Intent   : {decision.intent.value} (Expected: {test['expected_intent']})")
        print(f"       Action   : {decision.crm_action.value} | Urgency: {decision.urgency.value}")
        print(f"       HITL Gate: needs_human={decision.needs_human} | Flags: {decision.flags or 'none'}")
        print(f"       Contact  : {decision.masked_contact}")
        print(f"       Trace    : {exec_res['trace_status']} (ContactID: {exec_res['hubspot_contact_id']}, DealID: {exec_res['hubspot_deal_id']}, TicketID: {exec_res['hubspot_ticket_id']})")
        print("-" * 80)

    elapsed_ms = (time.time() - start_time) * 1000
    print(f"\nStandard Inbound Triage: {passed}/{total} Passed ({(passed/total)*100:.1f}%)")
    print(f"Average Execution Latency: {elapsed_ms/total:.2f} ms / submission\n")

    # Safety Guardrail Verification: Faulty Promising & Rejection Gate
    print("=" * 80)
    print(">>> SAFETY GATE TEST: CATCHING FAULTY REFUND PROMISE & HUMAN REJECTION")
    print("=" * 80)
    
    t2_sub = InboundSubmission(
        name="Tõnis Kask",
        email="tonis@oldco.ee",
        company="OldCo",
        plan="Starter",
        message="I bought Starter 40 days ago and want a refund."
    )
    
    # 1. Simulate ungrounded model proposing an illegal refund
    faulty_dec = engine.triage(t2_sub, run_id="run_faulty_t2", force_faulty_prompt=True)
    promise_caught = "promise_detected" in faulty_dec.flags and faulty_dec.needs_human is True
    print(f"1. Promise Guard Test    : Flagged='{faulty_dec.flags}' | Caught={promise_caught}")

    # 2. Simulate human clicking REJECT on the suspicious draft
    rejected_exec = engine.execute_decision(faulty_dec, t2_sub, human_decision="reject")
    zero_writes = (
        rejected_exec["hubspot_contact_id"] is None 
        and rejected_exec["hubspot_deal_id"] is None 
        and rejected_exec["hubspot_ticket_id"] is None 
        and rejected_exec["email_sent_to_customer"] is False
    )
    print(f"2. Human Rejection Gate  : Status={rejected_exec['trace_status']} | Zero HubSpot Writes={zero_writes}")
    print("-" * 80)

    all_passed = (passed == total) and promise_caught and zero_writes
    if all_passed:
        print("\033[92m[SUCCESS] ALL CRM INTAKE & HITL SAFETY SUITES PASSED 100%\033[0m\n")
        return 0
    else:
        print("\033[91m[FAILURE] SAFETY OR ROUTING SUITE FAILED\033[0m\n")
        return 1

if __name__ == "__main__":
    sys.exit(run_crm_benchmark())
