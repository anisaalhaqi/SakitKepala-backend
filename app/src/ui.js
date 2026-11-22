import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

export const colors = {
  bg: '#F5F6F8',
  surface: '#FFFFFF',
  text: '#1B2230',
  muted: '#5B6577',
  line: '#DDE1E8',
  primary: '#2A5BD7',
  primarySoft: '#E6EDFC',
  locked: '#8A5A00',
  lockedSoft: '#FBF0D9',
  good: '#2F7D4F',
  goodSoft: '#E3F3E9',
  bad: '#A33A3A',
  badSoft: '#F8E3E3',
};

export function Screen({ children, refreshing, onRefresh }) {
  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.screenContent}
        keyboardShouldPersistTaps="handled"
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} /> : undefined}
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function Title({ children }) {
  return <Text style={styles.title}>{children}</Text>;
}

export function Label({ children }) {
  return <Text style={styles.label}>{children}</Text>;
}

export function Body({ children, muted, style }) {
  return <Text style={[styles.body, muted && styles.muted, style]}>{children}</Text>;
}

export function Card({ children, style }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Button({ title, onPress, loading, disabled, variant = 'primary', accessibilityHint }) {
  const off = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={off}
      accessibilityRole="button"
      accessibilityState={{ disabled: off, busy: !!loading }}
      accessibilityHint={accessibilityHint}
      style={({ pressed }) => [
        styles.button,
        variant === 'secondary' && styles.buttonSecondary,
        variant === 'danger' && styles.buttonDanger,
        off && styles.buttonDisabled,
        pressed && !off && styles.buttonPressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'secondary' ? colors.primary : '#FFFFFF'} />
      ) : (
        <Text style={[styles.buttonText, variant === 'secondary' && styles.buttonTextSecondary]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Field({ label, value, onChangeText, error, max, multiline, ...rest }) {
  return (
    <View style={styles.field}>
      <View style={styles.fieldHead}>
        <Label>{label}</Label>
        {max ? (
          <Text style={[styles.counter, value.length > max && styles.counterOver]}>
            {value.length}/{max}
          </Text>
        ) : null}
      </View>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        multiline={multiline}
        placeholderTextColor={colors.muted}
        style={[styles.input, multiline && styles.inputMultiline, error && styles.inputError]}
        accessibilityLabel={label}
        {...rest}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

const BANNER_TONES = {
  error: { bg: colors.badSoft, fg: colors.bad },
  info: { bg: colors.primarySoft, fg: colors.primary },
  success: { bg: colors.goodSoft, fg: colors.good },
  warning: { bg: colors.lockedSoft, fg: colors.locked },
};

export function Banner({ tone = 'error', children, onRetry }) {
  const t = BANNER_TONES[tone];
  return (
    <View style={[styles.banner, { backgroundColor: t.bg }]} accessibilityRole="alert">
      <Text style={[styles.bannerText, { color: t.fg }]}>{children}</Text>
      {onRetry ? (
        <Pressable onPress={onRetry} accessibilityRole="button" hitSlop={8}>
          <Text style={[styles.bannerAction, { color: t.fg }]}>Coba lagi</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function Pill({ status }) {
  const unlocked = status === 'UNLOCKED';
  return (
    <View style={[styles.pill, { backgroundColor: unlocked ? colors.goodSoft : colors.lockedSoft }]}>
      <Text style={[styles.pillText, { color: unlocked ? colors.good : colors.locked }]}>
        {unlocked ? 'TERBUKA' : 'TERKUNCI'}
      </Text>
    </View>
  );
}

export function Loading({ label = 'Memuat…' }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={colors.primary} size="large" />
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}

export function EmptyState({ title, children }) {
  return (
    <View style={styles.empty}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {children ? <Text style={[styles.body, styles.muted, styles.textCenter]}>{children}</Text> : null}
    </View>
  );
}

export function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}, ${pad(d.getHours())}.${pad(d.getMinutes())}`;
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  screen: { flex: 1, backgroundColor: colors.bg },
  screenContent: { padding: 16, gap: 16, paddingBottom: 40 },
  title: { fontSize: 22, fontWeight: '700', color: colors.text },
  label: { fontSize: 13, fontWeight: '600', color: colors.text },
  body: { fontSize: 15, lineHeight: 22, color: colors.text },
  muted: { color: colors.muted },
  textCenter: { textAlign: 'center' },
  card: { backgroundColor: colors.surface, borderRadius: 12, borderWidth: 1, borderColor: colors.line, padding: 16, gap: 10 },
  button: { minHeight: 48, borderRadius: 10, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 16 },
  buttonSecondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.primary },
  buttonDanger: { backgroundColor: colors.bad },
  buttonDisabled: { opacity: 0.45 },
  buttonPressed: { opacity: 0.85 },
  buttonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '600' },
  buttonTextSecondary: { color: colors.primary },
  field: { gap: 6 },
  fieldHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  counter: { fontSize: 12, color: colors.muted, fontVariant: ['tabular-nums'] },
  counterOver: { color: colors.bad },
  input: { borderWidth: 1, borderColor: colors.line, borderRadius: 10, backgroundColor: colors.surface, paddingHorizontal: 12, paddingVertical: 10, fontSize: 15, color: colors.text },
  inputMultiline: { minHeight: 120, textAlignVertical: 'top' },
  inputError: { borderColor: colors.bad },
  fieldError: { fontSize: 13, color: colors.bad },
  banner: { borderRadius: 10, padding: 12, gap: 6 },
  bannerText: { fontSize: 14, lineHeight: 20 },
  bannerAction: { fontSize: 14, fontWeight: '700' },
  pill: { alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 3 },
  pillText: { fontSize: 12, fontWeight: '700', letterSpacing: 0.5 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, backgroundColor: colors.bg },
  empty: { alignItems: 'center', gap: 6, paddingVertical: 24 },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: colors.text },
});
