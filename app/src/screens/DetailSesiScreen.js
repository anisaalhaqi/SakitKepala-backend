import { useCallback, useEffect, useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, Text, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import * as Api from '../ApiService';
import { getDraft, setDraft } from '../drafts';
import { validateSummary, LIMITS } from '../validation';
import { Banner, Body, Button, Card, EmptyState, Field, Label, Loading, Pill, Screen, Title, colors, formatDate } from '../ui';

function exportText(data) {
  return [
    `Topik: ${data.topic}`,
    `Pertanyaan: ${data.question}`,
    '',
    'Penjelasan:',
    data.explanation,
    '',
    'Hasil akhir:',
    data.final_result,
    '',
    'Catatan pemahamanku:',
    data.understanding_notes,
    '',
    `Bukti belajar: lolos pada percobaan ke-${data.proof_of_learning.attempt_no}, ${formatDate(data.proof_of_learning.passed_at)}`,
  ].join('\n');
}

function PartnerBlock({ title, block, render }) {
  if (block.status === 'ok' || block.status === 'stale') {
    return (
      <View style={styles.partner}>
        <Label>{title}</Label>
        {block.status === 'stale' ? <Body muted>Data dari cache, mungkin tidak terbaru.</Body> : null}
        {block.items.map((item, i) => (
          <View key={`${item.title}-${i}`} style={styles.partnerItem}>
            {render(item)}
          </View>
        ))}
      </View>
    );
  }
  return null; // empty / unavailable / disabled: disembunyikan, belajar tetap jalan
}

function References({ refs }) {
  if (!refs) return null;
  const { liveSessions, materials } = refs;
  const visible = [liveSessions, materials].some((b) => (b.status === 'ok' || b.status === 'stale') && b.items.length);
  if (!visible) return null;
  return (
    <Card>
      <Title>Belajar lebih lanjut</Title>
      <PartnerBlock
        title="Sesi siaran terkait · Sistem Siaran Belajar"
        block={liveSessions}
        render={(item) => (
          <>
            <Text style={styles.partnerTitle}>{item.title}</Text>
            {item.description ? <Body muted>{item.description}</Body> : null}
            {item.tags?.length ? <Body muted>#{item.tags.join(' #')}</Body> : null}
          </>
        )}
      />
      <PartnerBlock
        title="Materi terkait · Sistem Materi Belajar"
        block={materials}
        render={(item) => (
          <>
            <Text style={styles.partnerTitle}>{item.title}</Text>
            {item.summary ? <Body muted>{item.summary}</Body> : null}
            {item.url ? (
              <Pressable onPress={() => Linking.openURL(item.url).catch(() => {})} accessibilityRole="link">
                <Text style={styles.link}>Buka materi</Text>
              </Pressable>
            ) : null}
          </>
        )}
      />
    </Card>
  );
}

export default function DetailSesiScreen({ navigation, route }) {
  const { sessionId, initial } = route.params;
  const [session, setSession] = useState(initial || null);
  const [loading, setLoading] = useState(!initial);
  const [loadError, setLoadError] = useState(null);
  const [refs, setRefs] = useState(null);

  const [summary, setSummary] = useState(() => getDraft(sessionId));
  const [fieldError, setFieldError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [submitError, setSubmitError] = useState(null);

  const [copyNote, setCopyNote] = useState(null);
  const [exporting, setExporting] = useState(false);
  const alive = useRef(true);

  useEffect(() => () => {
    alive.current = false;
  }, []);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const data = await Api.getSession(sessionId);
      if (alive.current) setSession(data);
    } catch (err) {
      if (alive.current) setLoadError(err);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    load();
    Api.getReferences(sessionId).then((r) => alive.current && setRefs(r));
  }, [load, sessionId]);

  const changeSummary = (text) => {
    setSummary(text);
    setDraft(sessionId, text);
  };

  const submit = async () => {
    const found = validateSummary(summary);
    setFieldError(found.summary || null);
    setSubmitError(null);
    if (found.summary) return;

    setSubmitting(true);
    try {
      const res = await Api.submitCheckpoint(sessionId, summary.trim());
      setResult(res);
      if (res.passed) {
        setDraft(sessionId, '');
        setSummary('');
      }
      await load(); // ambil status, copy_enabled, dan export_enabled terbaru
    } catch (err) {
      if (err.status === 409) await load();
      if (err.status === 422) setFieldError(err.fields.summary || err.message);
      else setSubmitError(err);
    } finally {
      if (alive.current) setSubmitting(false);
    }
  };

  const copyResult = async () => {
    try {
      await Clipboard.setStringAsync(session.final_result || '');
      setCopyNote('Hasil akhir disalin.');
    } catch {
      setCopyNote('Gagal menyalin. Coba lagi.');
    }
  };

  const exportResult = async () => {
    setExporting(true);
    try {
      const data = await Api.getExport(sessionId);
      await Clipboard.setStringAsync(exportText(data));
      setCopyNote('Ekspor (hasil akhir + catatan pemahaman) disalin.');
    } catch (err) {
      setCopyNote(err.message || 'Ekspor gagal.');
    } finally {
      setExporting(false);
    }
  };

  if (loading) return <Loading label="Memuat sesi…" />;

  if (!session) {
    const notFound = loadError?.status === 404;
    return (
      <Screen>
        <EmptyState title={notFound ? 'Sesi tidak ditemukan' : 'Sesi gagal dimuat'}>
          {notFound ? 'Sesi ini tidak ada atau bukan milik akunmu.' : loadError?.message}
        </EmptyState>
        {notFound ? (
          <Button title="Kembali" variant="secondary" onPress={() => navigation.goBack()} />
        ) : (
          <Button title="Coba lagi" onPress={() => { setLoading(true); load(); }} />
        )}
      </Screen>
    );
  }

  const unlocked = session.status === 'UNLOCKED';
  const lockedFinal = !unlocked && (session.attempts_left === 0 || result?.locked_final);

  return (
    <Screen refreshing={false} onRefresh={load}>
      <View style={styles.head}>
        <Pill status={session.status} />
        <Title>{session.topic}</Title>
        <Body muted>{session.question}</Body>
      </View>

      {loadError ? <Banner onRetry={load}>{loadError.message}</Banner> : null}

      <Card>
        <Label>Penjelasan</Label>
        <Body selectable>{session.explanation}</Body>
      </Card>

      {unlocked ? (
        <Card style={styles.unlocked}>
          <Label>Hasil akhir</Label>
          <Body selectable={session.copy_enabled}>{session.final_result}</Body>
          {copyNote ? <Banner tone="info">{copyNote}</Banner> : null}
          <Button title="Salin hasil akhir" onPress={copyResult} disabled={!session.copy_enabled} />
          <Button
            title={session.export_enabled ? 'Ekspor dengan catatan pemahaman' : 'Ekspor · Khusus Pro'}
            variant="secondary"
            onPress={exportResult}
            loading={exporting}
            disabled={!session.export_enabled}
            accessibilityHint="Menyalin hasil akhir dan catatan pemahaman ke clipboard"
          />
        </Card>
      ) : lockedFinal ? (
        <Card>
          <Banner tone="error">
            Percobaan 3/3 sudah habis. Hasil akhir tetap terkunci, tetapi penjelasan di atas tetap bisa kamu baca.
          </Banner>
          {result?.feedback ? <Body muted>{result.feedback}</Body> : null}
        </Card>
      ) : (
        <Card>
          <Label>Logic checkpoint</Label>
          <Body muted>
            Tulis ulang intisari penjelasan dengan kata-katamu sendiri. Sisa percobaan: {session.attempts_left} dari 3.
          </Body>
          {result && !result.passed ? <Banner tone="warning">{result.feedback}</Banner> : null}
          {submitError ? (
            <Banner onRetry={submitError.code === 'TIMEOUT' || submitError.code === 'NETWORK' || submitError.status === 503 ? submit : undefined}>
              {submitError.message}
            </Banner>
          ) : null}
          <Field
            label="Intisari pemahaman"
            value={summary}
            onChangeText={changeSummary}
            error={fieldError}
            max={LIMITS.summary.max}
            multiline
            placeholder={`Minimal ${LIMITS.summary.min} karakter`}
          />
          <Button title="Kirim intisari" onPress={submit} loading={submitting} />
        </Card>
      )}

      {unlocked && result?.passed ? <Banner tone="success">{result.feedback}</Banner> : null}

      <References refs={refs} />

      <Body muted style={styles.meta}>Dibuat {formatDate(session.created_at)}</Body>
    </Screen>
  );
}

const styles = StyleSheet.create({
  head: { gap: 8 },
  unlocked: { borderColor: colors.good },
  partner: { gap: 8 },
  partnerItem: { gap: 4, paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.line },
  partnerTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  link: { color: colors.primary, fontWeight: '600', fontSize: 14 },
  meta: { fontSize: 13, textAlign: 'center' },
});
