import * as Api from '../src/ApiService';

const jsonResponse = (status, body) => ({
  ok: status >= 200 && status < 300,
  status,
  text: () => Promise.resolve(body === undefined ? '' : JSON.stringify(body)),
});

beforeEach(() => {
  global.fetch = jest.fn();
  Api.setToken(null);
  Api.setUnauthorizedHandler(null);
});

test('login mengirim JSON tanpa header Authorization', async () => {
  fetch.mockResolvedValue(jsonResponse(200, { access_token: 'jwt', token_type: 'bearer', expires_in: 3600 }));
  const res = await Api.login('a@b.co', 'rahasia123');
  expect(res.access_token).toBe('jwt');
  const [url, init] = fetch.mock.calls[0];
  expect(url).toBe(`${Api.API_URL}/auth/login`);
  expect(init.method).toBe('POST');
  expect(JSON.parse(init.body)).toEqual({ email: 'a@b.co', password: 'rahasia123' });
  expect(init.headers.Authorization).toBeUndefined();
});

test('request privat menyertakan Bearer token', async () => {
  Api.setToken('abc');
  fetch.mockResolvedValue(jsonResponse(200, []));
  await Api.listSessions();
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer abc');
});

test('kuota habis dipetakan ke QUOTA_EXCEEDED dengan pesan server', async () => {
  Api.setToken('abc');
  fetch.mockResolvedValue(
    jsonResponse(429, { detail: { code: 'QUOTA_EXCEEDED', message: 'Kuota harian paket Free (5 sesi) habis.', limit: 5 } }),
  );
  await expect(Api.createSession('rekursi', 'faktorial?')).rejects.toMatchObject({
    status: 429,
    code: 'QUOTA_EXCEEDED',
    message: 'Kuota harian paket Free (5 sesi) habis.',
  });
});

test('422 mengembalikan nama field yang salah', async () => {
  Api.setToken('abc');
  fetch.mockResolvedValue(
    jsonResponse(422, { detail: [{ loc: ['body', 'summary'], msg: 'String should have at least 30 characters' }] }),
  );
  const err = await Api.submitCheckpoint('s1', 'pendek').catch((e) => e);
  expect(err.code).toBe('VALIDATION');
  expect(Object.keys(err.fields)).toEqual(['summary']);
});

test('401 pada request bertoken memanggil handler sesi berakhir', async () => {
  const handler = jest.fn();
  Api.setToken('kedaluwarsa');
  Api.setUnauthorizedHandler(handler);
  fetch.mockResolvedValue(jsonResponse(401, { detail: 'Token tidak valid atau kedaluwarsa' }));
  await expect(Api.getMe()).rejects.toMatchObject({ status: 401 });
  expect(handler).toHaveBeenCalledTimes(1);
});

test('401 saat login (kata sandi salah) tidak memicu handler', async () => {
  const handler = jest.fn();
  Api.setUnauthorizedHandler(handler);
  fetch.mockResolvedValue(jsonResponse(401, { detail: 'Email atau password salah' }));
  await expect(Api.login('a@b.co', 'salahsalah')).rejects.toMatchObject({ message: 'Email atau password salah' });
  expect(handler).not.toHaveBeenCalled();
});

test('error Cloudflare (502/520) tidak menampilkan teks teknisnya', async () => {
  fetch.mockResolvedValue(
    jsonResponse(520, { detail: 'The origin web server returned an invalid or incomplete response to Cloudflare.' }),
  );
  const err = await Api.login('a@b.co', 'rahasia123').catch((e) => e);
  expect(err.code).toBe('SERVER_DOWN');
  expect(err.message).not.toMatch(/Cloudflare/);
});

test('jaringan putus menjadi pesan yang jelas', async () => {
  fetch.mockRejectedValue(new TypeError('Network request failed'));
  await expect(Api.getMe()).rejects.toMatchObject({ code: 'NETWORK' });
});

test('request yang terlalu lama dibatalkan dengan TIMEOUT', async () => {
  fetch.mockImplementation(
    (_url, { signal }) =>
      new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => reject(new Error('aborted')));
      }),
  );
  await expect(Api.request('/sessions', { timeout: 20 })).rejects.toMatchObject({ code: 'TIMEOUT' });
});

test('getReferences menerjemahkan blok mitra', async () => {
  Api.setToken('abc');
  fetch.mockResolvedValue(
    jsonResponse(200, {
      topic: 'rekursi',
      live_sessions: { status: 'ok', items: [{ title: 'Live rekursi', description: '', tags: [] }] },
      materials: { status: 'stale', items: [{ title: 'Modul rekursi', url: 'https://x.y', summary: '' }] },
    }),
  );
  const refs = await Api.getReferences('s1');
  expect(fetch.mock.calls[0][0]).toBe(`${Api.INTEGRATION_URL}/sessions/s1/references`);
  expect(refs.liveSessions.status).toBe('ok');
  expect(refs.materials.status).toBe('stale');
  expect(refs.materials.items).toHaveLength(1);
});

test('getReferences tidak melempar error bila layanan integrasi mati', async () => {
  fetch.mockRejectedValue(new TypeError('Network request failed'));
  const refs = await Api.getReferences('s1');
  expect(refs.liveSessions).toEqual({ status: 'unavailable', items: [] });
  expect(refs.materials).toEqual({ status: 'unavailable', items: [] });
});
