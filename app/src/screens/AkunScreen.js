import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import * as Api from '../ApiService';
import { useAuth } from '../AuthContext';
import { Banner, Body, Button, Card, Label, Screen, colors, tierLabel } from '../ui';

function Row({ label, value }) {
  return (
    <View style={styles.row}>
      <Body muted>{label}</Body>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

export default function AkunScreen() {
  const { user, logout, refreshUser } = useAuth();
  const [quota, setQuota] = useState(null);
  const [error, setError] = useState(null);
  const [leaving, setLeaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [q] = await Promise.all([Api.getSubscription(), refreshUser()]);
      setQuota(q);
    } catch (err) {
      setError(err);
    }
  }, [refreshUser]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const tier = tierLabel(quota?.tier || user?.tier);

  return (
    <Screen>
      {error ? <Banner onRetry={load}>{error.message}</Banner> : null}
      <Card>
        <Label>Akun</Label>
        <Row label="Email" value={user?.email || '-'} />
        <Row label="Paket" value={tier} />
      </Card>

      <Card>
        <Label>Kuota hari ini</Label>
        {quota ? (
          quota.limit == null ? (
            <Row label="Sesi" value="Tanpa batas harian" />
          ) : (
            <>
              <Row label="Terpakai" value={`${quota.used} dari ${quota.limit} sesi`} />
              <Row label="Sisa" value={`${quota.remaining} sesi`} />
            </>
          )
        ) : (
          <Body muted>Memuat kuota…</Body>
        )}
        <Body muted style={styles.note}>
          Free: 5 sesi per hari. Pro: tanpa batas harian dan bisa ekspor hasil. Pergantian paket tidak tersedia di aplikasi.
        </Body>
      </Card>

      <Button
        title="Keluar"
        variant="danger"
        loading={leaving}
        onPress={async () => {
          setLeaving(true);
          await logout();
        }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  value: { fontSize: 15, fontWeight: '600', color: colors.text, flexShrink: 1, textAlign: 'right' },
  note: { fontSize: 13 },
});
