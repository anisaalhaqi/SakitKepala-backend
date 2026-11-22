import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import { AuthProvider, useAuth } from './src/AuthContext';
import { Loading, colors } from './src/ui';
import LoginScreen from './src/screens/LoginScreen';
import BelajarScreen from './src/screens/BelajarScreen';
import DetailSesiScreen from './src/screens/DetailSesiScreen';
import RiwayatScreen from './src/screens/RiwayatScreen';
import AkunScreen from './src/screens/AkunScreen';

const Stack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const tabIcon = ({ color, focused }) => (
  <View style={{ width: focused ? 18 : 8, height: 8, borderRadius: 4, backgroundColor: color }} />
);

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        tabBarIcon: tabIcon,
        headerTitleStyle: { fontWeight: '700' },
      }}
    >
      <Tab.Screen name="Belajar" component={BelajarScreen} options={{ title: 'Belajar' }} />
      <Tab.Screen name="Riwayat" component={RiwayatScreen} />
      <Tab.Screen name="Akun" component={AkunScreen} />
    </Tab.Navigator>
  );
}

function RootNavigator() {
  const { status } = useAuth();

  if (status === 'restoring') {
    return (
      <Stack.Navigator>
        <Stack.Screen name="Pemulihan" options={{ headerShown: false }}>
          {() => <Loading label="Memeriksa sesi…" />}
        </Stack.Screen>
      </Stack.Navigator>
    );
  }

  return (
    <Stack.Navigator>
      {status === 'signedIn' ? (
        <>
          <Stack.Screen name="Utama" component={MainTabs} options={{ headerShown: false }} />
          <Stack.Screen name="DetailSesi" component={DetailSesiScreen} options={{ title: 'Detail Sesi' }} />
        </>
      ) : (
        <>
          <Stack.Screen name="Masuk" component={LoginScreen} options={{ title: 'Masuk' }} />
          <Stack.Screen name="Daftar" component={LoginScreen} options={{ title: 'Daftar' }} />
        </>
      )}
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <NavigationContainer>
          <RootNavigator />
          <StatusBar style="dark" />
        </NavigationContainer>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
