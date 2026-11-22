// Semua komunikasi HTTP aplikasi lewat berkas ini.
// - Microservice sendiri: EXPO_PUBLIC_API_URL (sudah termasuk /api).
// - Data kelompok mitra (Sistem Siaran Belajar & Sistem Materi Belajar): lewat layanan integrasi
//   (Anti-Corruption Layer) di EXPO_PUBLIC_INTEGRATION_URL; default = URL microservice.
// Setiap kegagalan diubah menjadi ApiError { status, code, message, fields } yang siap ditampilkan.

const trimSlash = (url) => String(url || '').replace(/\/+$/, '');

export const API_URL = trimSlash(process.env.EXPO_PUBLIC_API_URL || 'https://sakitkepala.stei.site/api');
export const INTEGRATION_URL = trimSlash(process.env.EXPO_PUBLIC_INTEGRATION_URL || API_URL);

// Backend memberi API AI waktu 30 detik; klien menunggu sedikit lebih lama agar tidak memotong
// respons yang sebenarnya hampir selesai.
export const TIMEOUT_DEFAULT_MS = 15000;
export const TIMEOUT_AI_MS = 45000;

export class ApiError extends Error {
  constructor(message, { status = 0, code = null, fields = {} } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

let authToken = null;
let unauthorizedHandler = null;

export function setToken(token) {
  authToken = token || null;
}

// Dipanggil saat request bertoken mendapat 401 (token kedaluwarsa/tidak sah).
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = typeof fn === 'function' ? fn : null;
}

const STATUS_MESSAGES = {
  400: 'Permintaan tidak dapat diproses.',
  401: 'Sesi berakhir, silakan masuk lagi.',
  403: 'Kamu tidak punya akses ke fitur ini.',
  404: 'Data tidak ditemukan.',
  409: 'Data sudah berubah. Memuat ulang…',
  422: 'Data yang dikirim belum sesuai. Periksa kembali isian.',
  429: 'Terlalu banyak permintaan. Coba lagi nanti.',
  500: 'Terjadi kesalahan di server. Coba lagi nanti.',
  502: 'Server sedang tidak dapat dihubungi. Coba lagi nanti.',
  503: 'Layanan sedang tidak tersedia. Coba lagi sebentar lagi.',
};

function parseJson(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

// 502/504 dan 520–530 berasal dari gateway/Cloudflare, bukan dari backend kita: isinya teks teknis
// (mis. "The origin web server returned an invalid ... response to Cloudflare"), jadi tidak ditampilkan.
const isUpstreamFailure = (status) => status === 502 || status === 504 || (status >= 520 && status <= 530);

// FastAPI mengirim `detail` sebagai string, objek {code, message}, atau daftar error validasi (422).
export function errorFromResponse(status, body) {
  if (isUpstreamFailure(status)) {
    return new ApiError(`Server SakitKepala sedang tidak dapat dihubungi (HTTP ${status}). Coba lagi beberapa saat lagi.`, {
      status,
      code: 'SERVER_DOWN',
    });
  }
  const detail = body && typeof body === 'object' ? body.detail : undefined;
  const fallback = STATUS_MESSAGES[status] || `Permintaan gagal (HTTP ${status}).`;

  if (Array.isArray(detail)) {
    const fields = {};
    for (const item of detail) {
      const loc = Array.isArray(item?.loc) ? item.loc : [];
      const name = loc[loc.length - 1];
      if (typeof name === 'string' && !fields[name]) fields[name] = 'Isian ini belum sesuai aturan.';
    }
    return new ApiError(STATUS_MESSAGES[422], { status, code: 'VALIDATION', fields });
  }
  if (detail && typeof detail === 'object') {
    return new ApiError(detail.message || fallback, { status, code: detail.code || null });
  }
  if (typeof detail === 'string' && detail.trim()) {
    return new ApiError(detail, { status });
  }
  return new ApiError(fallback, { status });
}

export async function request(path, { method = 'GET', body, auth = true, timeout = TIMEOUT_DEFAULT_MS, baseUrl = API_URL } = {}) {
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth && authToken) headers.Authorization = `Bearer ${authToken}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  let response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new ApiError('Server terlalu lama merespons, coba lagi.', { code: 'TIMEOUT' });
    }
    throw new ApiError('Tidak dapat terhubung ke server. Periksa koneksi internet.', { code: 'NETWORK' });
  } finally {
    clearTimeout(timer);
  }

  const data = parseJson(await response.text().catch(() => ''));
  if (response.ok) return data;

  const error = errorFromResponse(response.status, data);
  if (response.status === 401 && auth && authToken && unauthorizedHandler) {
    unauthorizedHandler(error);
  }
  throw error;
}

// ------------------------------------------------------------------ autentikasi (generic)

export const register = (email, password) =>
  request('/auth/register', { method: 'POST', body: { email, password }, auth: false });

export const login = (email, password) =>
  request('/auth/login', { method: 'POST', body: { email, password }, auth: false });

export const getMe = () => request('/auth/me');

// ------------------------------------------------------------------ validasi pemahaman (core)

export const createSession = (topic, question) =>
  request('/sessions', { method: 'POST', body: { topic, question }, timeout: TIMEOUT_AI_MS });

export const listSessions = () => request('/sessions');

export const getSession = (id) => request(`/sessions/${encodeURIComponent(id)}`);

export const submitCheckpoint = (id, summary) =>
  request(`/sessions/${encodeURIComponent(id)}/checkpoint`, {
    method: 'POST',
    body: { summary },
    timeout: TIMEOUT_AI_MS,
  });

export const getExport = (id) => request(`/sessions/${encodeURIComponent(id)}/export`);

export const getProofOfLearning = () => request('/proof-of-learning');

// ------------------------------------------------------------------ kuota & langganan (supporting)

export const getSubscription = () => request('/subscription');

// ------------------------------------------------------------------ kelompok mitra (lewat ACL)

const PARTNER_STATUSES = ['ok', 'stale', 'empty', 'unavailable', 'disabled'];

function normalizeBlock(block) {
  const status = PARTNER_STATUSES.includes(block?.status) ? block.status : 'unavailable';
  const items = Array.isArray(block?.items) ? block.items : [];
  return { status, items };
}

// Sesi siaran (Sistem Siaran Belajar) dan materi (Sistem Materi Belajar) dengan topic yang sama.
// Tidak pernah melempar error: mitra yang mati tidak boleh menghentikan alur belajar.
export async function getReferences(id) {
  try {
    const data = await request(`/sessions/${encodeURIComponent(id)}/references`, { baseUrl: INTEGRATION_URL });
    return {
      topic: data?.topic || '',
      liveSessions: normalizeBlock(data?.live_sessions),
      materials: normalizeBlock(data?.materials),
    };
  } catch {
    const down = { status: 'unavailable', items: [] };
    return { topic: '', liveSessions: down, materials: { ...down } };
  }
}
