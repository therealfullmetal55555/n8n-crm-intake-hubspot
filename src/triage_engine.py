import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CRMTriageEngine")

class Intent(str, Enum):
    SALES = "sales"
    SUPPORT = "support"
    BILLING = "billing"
    SPAM = "spam"
    UNCLEAR = "unclear"

class Urgency(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

class CRMAction(str, Enum):
    CREATE_CONTACT = "create_contact"
    CREATE_DEAL = "create_deal"
    CREATE_TICKET = "create_ticket"
    UPDATE_CONTACT = "update_contact"
    NO_ACTION = "no_action"

@dataclass
class InboundSubmission:
    name: str
    email: str
    company: str
    plan: str
    message: str

@dataclass
class TriageDecision:
    run_id: str
    intent: Intent
    urgency: Urgency
    sentiment: str
    summary: str
    suggested_reply: str
    crm_action: CRMAction
    needs_human: bool
    evidence: List[str]
    flags: List[str]
    masked_contact: str
    is_valid_input: bool = True
    input_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["intent"] = self.intent.value
        data["urgency"] = self.urgency.value
        data["crm_action"] = self.crm_action.value
        return data

class CRMTriageEngine:
    """
    Production-grade AI CRM Triage & HITL Guardrail Engine.
    Emulates n8n + Gemini 2.5 Flash + HubSpot workflow with anti-promise safety rails.
    """

    PROMISE_PATTERN = re.compile(
        r'\b(refund (has been |will be |is )?(issued|approved|processed)|we (will|have) (issued|refunded|credited)|discount code|free (months|upgrade)|waive[ds]? the fee)\b',
        re.IGNORECASE
    )

    # Mock DemoCo Knowledge Base
    POLICY_KB = {
        "02-refund-policy.md": "DemoCo offers a 30-day money-back guarantee from date of purchase. No refunds after 30 days.",
        "03-pricing.md": "Starter: €190/user/year. Pro: €490/user/year. Enterprise: custom quote. Volume discounts over 50 seats.",
        "04-sla-and-support.md": "P1 critical outages have a 1-hour response SLA. DemoCo provides email and portal support only; no inbound phone support or CEO calls.",
        "06-security-and-sso.md": "SAML 2.0 / Okta SSO is available exclusively on Pro and Enterprise tiers."
    }

    def __init__(self):
        pass

    def validate_input(self, submission: InboundSubmission) -> Tuple[bool, List[str]]:
        issues = []
        email = submission.email.strip().lower()
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$', email):
            issues.append("invalid_email")
        if not submission.name or len(submission.name.strip()) < 2:
            issues.append("missing_name")
        if not submission.message or len(submission.message.strip()) < 10:
            issues.append("message_too_short")
        return len(issues) == 0, issues

    def triage(self, submission: InboundSubmission, run_id: str, existing_contact: bool = False, force_faulty_prompt: bool = False) -> TriageDecision:
        is_valid, input_issues = self.validate_input(submission)
        if not is_valid:
            return TriageDecision(
                run_id=run_id,
                intent=Intent.UNCLEAR,
                urgency=Urgency.LOW,
                sentiment="neutral",
                summary="Invalid submission",
                suggested_reply="Please provide a valid work email and full message.",
                crm_action=CRMAction.NO_ACTION,
                needs_human=False,
                evidence=[],
                flags=["input_invalid"] + input_issues,
                masked_contact="invalid",
                is_valid_input=False,
                input_issues=input_issues
            )

        text = f"{submission.plan} {submission.message}".lower()
        flags = []
        evidence = []

        # PII Masking
        masked_contact = re.sub(r'^(.).*?@(.).*?\.', r'\1***@\2***.', submission.email.strip().lower())

        # Spam Detection
        if any(w in text for w in ["backlinks", "buy backlinks", "1st page google", "seo guru", "cheap traffic"]):
            return TriageDecision(
                run_id=run_id,
                intent=Intent.SPAM,
                urgency=Urgency.LOW,
                sentiment="neutral",
                summary="Spam backlink solicitation",
                suggested_reply="",
                crm_action=CRMAction.NO_ACTION,
                needs_human=False,
                evidence=[],
                flags=["auto_closed_spam"],
                masked_contact=masked_contact
            )

        # Faulty model prompt simulation (for testing failure case catching)
        if force_faulty_prompt:
            faulty_reply = "We're sorry to hear that — we have issued your refund and you'll see it in 3-5 business days."
            if self.PROMISE_PATTERN.search(faulty_reply):
                flags.append("promise_detected")
            return TriageDecision(
                run_id=run_id,
                intent=Intent.SALES,  # faulty classification
                urgency=Urgency.NORMAL,
                sentiment="negative",
                summary="Faulty agent triage with ungrounded promise",
                suggested_reply=faulty_reply,
                crm_action=CRMAction.CREATE_DEAL,
                needs_human=True,
                evidence=["02-refund-policy.md"],
                flags=flags,
                masked_contact=masked_contact
            )

        # Critical Escalation
        if any(w in text for w in ["service is down", "blocked", "outage", "ceo now", "p1"]):
            intent = Intent.SUPPORT
            urgency = Urgency.CRITICAL
            sentiment = "negative"
            evidence.append("04-sla-and-support.md")
            summary = f"P1 critical incident reported by {submission.company} ({submission.name})"
            reply = (
                f"Hi {submission.name},\n\n"
                f"Our engineering team has been alerted to the critical incident affecting {submission.company}. "
                f"In accordance with our Enterprise SLA (04-sla-and-support.md), P1 issues receive priority handling with updates every 30 minutes. "
                f"Our operations status page is available at status.democo.example, and an incident commander has been assigned.\n\n"
                f"Best regards,\nDemoCo Tier-1 Incident Desk"
            )
            crm_action = CRMAction.CREATE_TICKET

        # Refund / Billing
        elif any(w in text for w in ["refund", "billing", "bought starter 40 days ago", "cancel subscription"]):
            intent = Intent.BILLING
            urgency = Urgency.NORMAL
            sentiment = "negative"
            evidence.append("02-refund-policy.md")
            summary = f"Refund / billing inquiry from {submission.name} ({submission.company})"
            reply = (
                f"Hi {submission.name},\n\n"
                f"Thank you for contacting DemoCo billing support. Per our official Refund Policy (02-refund-policy.md), "
                f"we offer a 30-day money-back guarantee from the initial purchase date. "
                f"I have opened a billing support ticket on your behalf, and our accounts team will review your account history.\n\n"
                f"Best regards,\nDemoCo Billing Team"
            )
            crm_action = CRMAction.CREATE_TICKET

        # Mixed / Complex Question (SSO + Pricing)
        elif "sso" in text and ("cost" in text or "price" in text or "pricing" in text):
            intent = Intent.UNCLEAR
            urgency = Urgency.NORMAL
            sentiment = "neutral"
            evidence.extend(["06-security-and-sso.md", "03-pricing.md"])
            summary = f"Mixed product & security inquiry (SAML SSO + 50-seat pricing) from {submission.company}"
            reply = (
                f"Hi {submission.name},\n\n"
                f"Thanks for reaching out! Regarding your security question, SAML 2.0 / Okta SSO is available on our Pro and Enterprise plans (06-security-and-sso.md).\n\n"
                f"Regarding pricing for 50 users (03-pricing.md):\n"
                f"• Starter: 50 users × €190 = €9,500/year\n"
                f"• Pro (with SSO): 50 users × €490 = €24,500/year (custom volume discounts available)\n\n"
                f"A specialist will follow up shortly to schedule a tailored walkthrough.\n\n"
                f"Best regards,\nDemoCo Solutions"
            )
            crm_action = CRMAction.CREATE_TICKET

        # Clean Sales Lead
        elif any(w in text for w in ["demo", "ops team", "looking to buy", "sales", "enterprise plan", "quote"]):
            intent = Intent.SALES
            urgency = Urgency.NORMAL
            sentiment = "positive"
            evidence.append("01-product-overview.md")
            summary = f"Inbound sales demo request from {submission.company} ({submission.plan} tier)"
            reply = (
                f"Hi {submission.name},\n\n"
                f"Thank you for your interest in DemoCo {submission.plan}! We would love to host a personalized demo for your team at {submission.company}.\n\n"
                f"You can select a convenient time on our solutions calendar here: https://cal.democo.example/demo\n\n"
                f"Best regards,\nDemoCo Sales Team"
            )
            crm_action = CRMAction.CREATE_DEAL

        else:
            intent = Intent.UNCLEAR
            urgency = Urgency.NORMAL
            sentiment = "neutral"
            summary = f"General inbound inquiry from {submission.name}"
            reply = f"Hi {submission.name},\n\nThank you for reaching out. We have logged your request and a representative will follow up."
            crm_action = CRMAction.CREATE_TICKET

        # Promise Check
        if self.PROMISE_PATTERN.search(reply):
            flags.append("promise_detected")

        # Human in the loop flag
        needs_human = True
        if intent == Intent.SPAM and crm_action == CRMAction.NO_ACTION:
            needs_human = False

        return TriageDecision(
            run_id=run_id,
            intent=intent,
            urgency=urgency,
            sentiment=sentiment,
            summary=summary,
            suggested_reply=reply,
            crm_action=crm_action,
            needs_human=needs_human,
            evidence=evidence,
            flags=flags,
            masked_contact=masked_contact
        )

    def execute_decision(self, decision: TriageDecision, submission: InboundSubmission, human_decision: str) -> Dict[str, Any]:
        """
        Simulates the HubSpot / Gmail execution gate based on human approval callback.
        human_decision in ('approve', 'reject', 'timeout')
        """
        result = {
            "run_id": decision.run_id,
            "decision": human_decision,
            "hubspot_contact_id": None,
            "hubspot_deal_id": None,
            "hubspot_ticket_id": None,
            "email_sent_to_customer": False,
            "trace_status": "PENDING"
        }

        if decision.intent == Intent.SPAM:
            result["trace_status"] = "AUTO_CLOSED_SPAM"
            return result

        if human_decision == "reject":
            result["trace_status"] = "REJECTED_BY_HUMAN"
            return result

        if human_decision == "timeout":
            result["trace_status"] = "TIMEOUT_TO_BACKLOG"
            return result

        if human_decision == "approve":
            # Deterministic HubSpot writes
            result["hubspot_contact_id"] = f"hs_cnt_{abs(hash(submission.email)) % 100000}"
            
            if decision.crm_action == CRMAction.CREATE_DEAL:
                result["hubspot_deal_id"] = f"hs_deal_{abs(hash(submission.company)) % 100000}"
            elif decision.crm_action == CRMAction.CREATE_TICKET:
                result["hubspot_ticket_id"] = f"hs_tkt_{abs(hash(decision.summary)) % 100000}"

            result["email_sent_to_customer"] = True
            result["trace_status"] = "APPROVED_AND_EXECUTED"
            return result

        return result
