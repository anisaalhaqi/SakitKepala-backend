// Dipakai untuk dua rute: "Masuk" dan "Daftar".
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Api from '../ApiService';
import { useAuth } from '../AuthContext';
import { validateCredentials, LIMITS } from '../validation';
import { Banner, Body, Button, Card, Field, Screen, Title, colors } from '../ui';

export default function LoginScreen({ navigation, route }) {
  const isRegister = route.name === 'Daftar';
  const { login, notice, clearNotice } = useAuth();
  const [email, setEmail] = useState(route.params?.email || '');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const info = !isRegister ? route.params?.message : null;

  const submit = async () => {
    const found = validateCredentials({ email, password });
    setErrors(found);
    setServerError(null);
    if (Object.keys(found).length) return;

    setLoading(true);
    try {
      if (isRegister) {
        await Api.register(email.trim(), password);
        navigation.navigate('Masuk', { email: email.trim(), message: 'Akun berhasil dibuat. Silakan masuk.' });
      } else {
        clearNotice();
        await login(email, password); // berhasil -> navigator berpindah ke tab Belajar
      }
    } catch (err) {
      if (err.status === 409) setErrors({ email: 'Email sudah terdaftar.' });
      else if (err.status === 422) setErrors(Object.keys(err.fields).length ? err.fields : {});
      setServerError(err.status === 409 ? null : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Screen>
      <View style={styles.hero}>
        <Title>Uji Paham Belajar</Title>
        <Body muted>
          {isRegister
            ? 'Buat akun untuk mulai belajar. Paket Free memberi 5 sesi per hari.'
            : 'Baca penjelasan, tulis ulang intisarinya, lalu buka hasil akhirnya.'}
        </Body>
      </View>

      {notice && !isRegister ? <Banner tone="warning">{notice}</Banner> : null}
      {info ? <Banner tone="success">{info}</Banner> : null}
      {serverError ? <Banner>{serverError}</Banner> : null}

      <Card>
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          error={errors.email}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          placeholder="nama@contoh.com"
          textContentType="emailAddress"
        />
        <Field
          label="Kata sandi"
          value={password}
          onChangeText={setPassword}
          error={errors.password}
          secureTextEntry
          autoComplete={isRegister ? 'new-password' : 'current-password'}
          placeholder={`${LIMITS.password.min}–${LIMITS.password.max} karakter`}
          onSubmitEditing={submit}
        />
        <Button title={isRegister ? 'Daftar' : 'Masuk'} onPress={submit} loading={loading} />
      </Card>

      <Pressable
        onPress={() => navigation.navigate(isRegister ? 'Masuk' : 'Daftar')}
        accessibilityRole="link"
        style={styles.switch}
      >
        <Text style={styles.switchText}>
          {isRegister ? 'Sudah punya akun? Masuk' : 'Belum punya akun? Daftar'}
        </Text>
      </Pressable>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { gap: 6, paddingTop: 8 },
  switch: { alignSelf: 'center', padding: 8 },
  switchText: { color: colors.primary, fontSize: 15, fontWeight: '600' },
});
