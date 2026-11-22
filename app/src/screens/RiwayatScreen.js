import { useCallback, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import * as Api from '../ApiService';
import { Banner, Body, Card, EmptyState, Label, Loading, Pill, Screen, colors, formatDate } from '../ui';

export default function RiwayatScreen({ navigation }) {
  const [sessions, setSessions] = useState(null);
  const [proofs, setProofs] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [s, p] = await Promise.all([Api.listSessions(), Api.getProofOfLearning()]);
      setSessions(s);
      setProofs(p);
    } catch (err) {
      setError(err);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const refresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const open = (sessionId) => navigation.navigate('DetailSesi', { sessionId });

  if (!sessions && !error) return <Loading label="Memuat riwayat…" />;

  return (
    <Screen refreshing={refreshing} onRefresh={refresh}>
      {error ? <Banner onRetry={load}>{error.message}</Banner> : null}

      {sessions ? (
        <Card>
          <Label>Sesi belajar</Label>
          {sessions.length === 0 ? (
            <EmptyState title="Belum ada sesi">Buat sesi pertamamu di tab Belajar.</EmptyState>
          ) : (
            sessions.map((s) => (
              <Pressable
                key={s.session_id}
                onPress={() => open(s.session_id)}
                accessibilityRole="button"
                accessibilityLabel={`Buka sesi ${s.topic}`}
                style={({ pressed }) => [styles.row, pressed && styles.pressed]}
              >
                <View style={styles.rowMain}>
                  <Text style={styles.rowTitle}>{s.topic}</Text>
                  <Body muted style={styles.small}>
                    {formatDate(s.created_at)}
                    {s.status === 'LOCKED' ? ` · sisa ${s.attempts_left}/3 percobaan` : ''}
                  </Body>
                </View>
                <Pill status={s.status} />
              </Pressable>
            ))
          )}
        </Card>
      ) : null}

      {proofs ? (
        <Card>
          <Label>Bukti belajar</Label>
          {proofs.length === 0 ? (
            <EmptyState title="Belum ada bukti belajar">
              Bukti tercatat setiap kali kamu lolos logic checkpoint.
            </EmptyState>
          ) : (
            proofs.map((p) => (
              <Pressable
                key={p.session_id}
                onPress={() => open(p.session_id)}
                accessibilityRole="button"
                style={({ pressed }) => [styles.row, pressed && styles.pressed]}
              >
                <View style={styles.rowMain}>
                  <Text style={styles.rowTitle}>{p.topic}</Text>
                  <Body muted style={styles.small}>
                    Lolos pada percobaan ke-{p.attempt_no} · {formatDate(p.passed_at)}
                  </Body>
                </View>
              </Pressable>
            ))
          )}
        </Card>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.line,
  },
  pressed: { opacity: 0.6 },
  rowMain: { flex: 1, gap: 2 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: colors.text },
  small: { fontSize: 13 },
});
