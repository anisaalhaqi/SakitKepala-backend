import { useCallback, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import * as Api from '../ApiService';
import { validateSessionForm, LIMITS } from '../validation';
import { Banner, Body, Button, Card, Field, Screen, Title } from '../ui';

function quotaText(q) {
  if (!q) return null;
  if (q.limit == null) return `Paket ${q.tier}: sesi tanpa batas harian.`;
  return `Paket ${q.tier}: sisa ${q.remaining} dari ${q.limit} sesi hari ini.`;
}

export default function BelajarScreen({ navigation }) {
  const [topic, setTopic] = useState('');
  const [question, setQuestion] = useState('');
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [quota, setQuota] = useState(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      Api.getSubscription()
        .then((q) => alive && setQuota(q))
        .catch(() => {}); // info kuota bersifat tambahan; form tetap bisa dipakai
      return () => {
        alive = false;
      };
    }, []),
  );

  const quotaEmpty = quota && quota.limit != null && quota.remaining === 0;

  const submit = async () => {
    const found = validateSessionForm({ topic, question });
    setErrors(found);
    setError(null);
    if (Object.keys(found).length) return;

    setLoading(true);
    try {
      const session = await Api.createSession(topic.trim(), question.trim());
      if (session.quota) setQuota(session.quota);
      setTopic('');
      setQuestion('');
      navigation.navigate('DetailSesi', { sessionId: session.session_id, initial: session });
    } catch (err) {
      if (err.code === 'QUOTA_EXCEEDED') {
        setQuota((q) => (q ? { ...q, remaining: 0 } : q));
      }
      if (err.status === 422) setErrors(err.fields);
      setError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <Title>Mau paham apa hari ini?</Title>
      <Body muted>
        Penjelasan langsung tampil. Hasil akhir dibuka setelah kamu menulis ulang intisarinya.
      </Body>

      {quotaEmpty || error?.code === 'QUOTA_EXCEEDED' ? (
        <Banner tone="warning">
          {error?.code === 'QUOTA_EXCEEDED'
            ? error.message
            : 'Kuota harian paket Free (5 sesi) habis. Coba lagi besok.'}
        </Banner>
      ) : quota ? (
        <Banner tone="info">{quotaText(quota)}</Banner>
      ) : null}

      {error && error.code !== 'QUOTA_EXCEEDED' ? (
        <Banner onRetry={error.code === 'TIMEOUT' || error.code === 'NETWORK' ? submit : undefined}>
          {error.message}
        </Banner>
      ) : null}

      <Card>
        <Field
          label="Topik"
          value={topic}
          onChangeText={setTopic}
          error={errors.topic}
          max={LIMITS.topic.max}
          placeholder="mis. rekursi"
          autoCapitalize="none"
        />
        <Field
          label="Pertanyaan"
          value={question}
          onChangeText={setQuestion}
          error={errors.question}
          max={LIMITS.question.max}
          multiline
          placeholder="mis. Tolong buatkan fungsi faktorial rekursif"
        />
        <Button title="Buat sesi belajar" onPress={submit} loading={loading} disabled={quotaEmpty} />
        {loading ? <Body muted>AI sedang menyusun penjelasan. Ini bisa memakan waktu hingga 30 detik.</Body> : null}
      </Card>
    </Screen>
  );
}
