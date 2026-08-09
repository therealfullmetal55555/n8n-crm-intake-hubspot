const t = $input.first().json;
const base = $('Normalize & Validate').first().json;

const INTENTS = ['sales','support','billing','spam','unclear'];
const ACTIONS = ['create_contact','create_deal','create_ticket','update_contact','no_action'];
const flags = [];
if (!INTENTS.includes(t.intent)) { t.intent = 'unclear'; flags.push('intent_repaired'); }
if (!ACTIONS.includes(t.crm_action)) { t.crm_action = 'create_ticket'; flags.push('action_repaired'); }

// Promise detection: the reply must never promise outcomes (lesson from the failure case)
const PROMISES = /\b(refund (has been |will be |is )?(issued|approved|processed)|we (will|have) (issued|refunded|credited)|discount code|free (months|upgrade)|waive[ds]? the fee)\b/i;
const promises = PROMISES.test(t.suggested_reply ?? '');
if (promises) flags.push('promise_detected');

// Spam never reaches the gate; everything else needs a human when in doubt
let needsHuman = t.needs_human !== false;
if (t.intent === 'spam' && t.crm_action === 'no_action') needsHuman = false;
if (promises || t.intent === 'unclear' || t.urgency === 'critical') needsHuman = true;

// PII masking for logs
const masked = base.email.replace(/^(.).*?@(.).*?\./, '$1***@$2***.');

return [{ json: {
  ...t, needs_human: needsHuman, flags,
  masked_contact: masked,
  run_id: $('Init Run').first().json.run_id,
  started_at: $('Init Run').first().json.started_at,
  name: base.name, email: base.email, company: base.company, message: base.message, plan: base.plan,
}}];
