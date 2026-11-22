// Aturan form sama dengan batas di backend, jadi error 422 jarang muncul.

export const LIMITS = {
  password: { min: 8, max: 128 },
  topic: { min: 2, max: 80 },
  question: { min: 5, max: 1000 },
  summary: { min: 30, max: 2000 },
};

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const lengthError = (value, { min, max }, label) => {
  const n = value.length;
  if (n < min) return `${label} minimal ${min} karakter.`;
  if (n > max) return `${label} maksimal ${max} karakter.`;
  return null;
};

const clean = (errors) => Object.fromEntries(Object.entries(errors).filter(([, v]) => v));

export function validateCredentials({ email = '', password = '' }) {
  const e = email.trim();
  return clean({
    email: !e ? 'Email wajib diisi.' : EMAIL_RE.test(e) && e.length <= 254 ? null : 'Format email tidak valid.',
    password: lengthError(password, LIMITS.password, 'Kata sandi'),
  });
}

export function validateSessionForm({ topic = '', question = '' }) {
  return clean({
    topic: lengthError(topic.trim(), LIMITS.topic, 'Topik'),
    question: lengthError(question.trim(), LIMITS.question, 'Pertanyaan'),
  });
}

export function validateSummary(summary = '') {
  return clean({ summary: lengthError(summary.trim(), LIMITS.summary, 'Intisari') });
}
