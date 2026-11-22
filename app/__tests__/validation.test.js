import { validateCredentials, validateSessionForm, validateSummary } from '../src/validation';

test('kredensial valid tidak punya error', () => {
  expect(validateCredentials({ email: 'demo@sakitkepala.test', password: '12345678' })).toEqual({});
});

test('email tidak valid dan kata sandi pendek ditolak', () => {
  const e = validateCredentials({ email: 'bukan-email', password: '123' });
  expect(e.email).toBeTruthy();
  expect(e.password).toMatch(/minimal 8/);
});

test('batas topik 2–80 dan pertanyaan 5–1000 karakter', () => {
  expect(validateSessionForm({ topic: 'a', question: 'halo' })).toEqual({
    topic: 'Topik minimal 2 karakter.',
    question: 'Pertanyaan minimal 5 karakter.',
  });
  expect(validateSessionForm({ topic: 'x'.repeat(81), question: 'apa itu rekursi?' }).topic).toMatch(/maksimal 80/);
  expect(validateSessionForm({ topic: 'rekursi', question: 'apa itu rekursi?' })).toEqual({});
});

test('intisari dihitung setelah spasi di tepi dibuang', () => {
  expect(validateSummary('   terlalu pendek   ').summary).toMatch(/minimal 30/);
  expect(validateSummary('x'.repeat(30))).toEqual({});
  expect(validateSummary('x'.repeat(2001)).summary).toMatch(/maksimal 2000/);
});
