const w = $('Wait for Approval').first().json;
const body = w.body ?? {};
const query = w.query ?? {};
const action = String(body.action ?? query.action ?? '').toLowerCase();
const decision = ['approve','reject'].includes(action) ? action : 'timeout';
const t = $('Validate Triage').first().json;
return [{ json: { ...t, decision, decided_at: new Date().toISOString() } }];
