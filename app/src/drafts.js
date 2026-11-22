// Draft intisari per sesi, disimpan di memori selama aplikasi terbuka.
// Bila token kedaluwarsa saat pengguna menulis, draft tetap ada dan dipulihkan setelah login ulang.
// Logout manual menghapus semua draft.

const drafts = new Map();

export const getDraft = (sessionId) => drafts.get(sessionId) || '';

export function setDraft(sessionId, text) {
  if (text) drafts.set(sessionId, text);
  else drafts.delete(sessionId);
}

export const clearDrafts = () => drafts.clear();
