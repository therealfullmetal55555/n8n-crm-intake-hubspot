const j = $input.first().json;
const issues = [];
const email = String(j.email ?? '').trim().toLowerCase();
if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) issues.push('invalid_email');
if (!j.name || String(j.name).trim().length < 2) issues.push('missing_name');
if (!j.message || String(j.message).trim().length < 10) issues.push('message_too_short');
return [{ json: { ...j, email, valid: issues.length === 0, issues } }];
