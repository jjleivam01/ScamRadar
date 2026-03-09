import React, { useEffect } from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import ErrorBoundary from 'react-native-error-boundary';
import { View, Text, StyleSheet } from 'react-native';
import AuthScreen from './src/screens/AuthScreen';
import HomeScreen from './src/screens/HomeScreen';
import SMSAnalyzerScreen from './src/screens/SMSAnalyzerScreen';
import CallAnalyzerScreen from './src/screens/CallAnalyzerScreen';
import { syncFraudPatterns } from './src/utils/nlpEngine';

const Stack = createNativeStackNavigator();

const ErrorFallback = ({ error }) => (
  <View style={styles.errorContainer}>
    <Text style={styles.errorTitle}>💥 La app se detuvo</Text>
    <Text style={styles.errorText}>Por favor toma un pantallazo de esto y envíaselo a John:</Text>
    <Text style={styles.errorTextDetail}>{error.name}: {error.message}</Text>
    <Text style={styles.errorStack} selectable>{error.stack}</Text>
  </View>
);

export default function App() {
  useEffect(() => {
    // Sincronizar diccionario de IA desde la Nube al iniciar App
    syncFraudPatterns();
  }, []);

  return (
    <ErrorBoundary FallbackComponent={ErrorFallback}>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="Auth">
          <Stack.Screen
            name="Auth"
            component={AuthScreen}
            options={{ headerShown: false }}
          />
          <Stack.Screen
            name="Home"
            component={HomeScreen}
            options={{ title: 'ScamRadar IA', headerBackVisible: false }}
          />
          <Stack.Screen
            name="SMSAnalyzer"
            component={SMSAnalyzerScreen}
            options={{ title: 'Análisis de SMS' }}
          />
          <Stack.Screen
            name="CallAnalyzer"
            component={CallAnalyzerScreen}
            options={{ title: 'Análisis de Llamada' }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </ErrorBoundary>
  );
}

const styles = StyleSheet.create({
  errorContainer: { flex: 1, padding: 20, justifyContent: 'center', backgroundColor: '#fedebb' },
  errorTitle: { fontSize: 24, fontWeight: 'bold', marginBottom: 10, color: '#c0392b' },
  errorText: { fontSize: 16, marginBottom: 10, color: '#333' },
  errorTextDetail: { fontSize: 14, fontWeight: 'bold', color: '#000', marginBottom: 5 },
  errorStack: { fontSize: 10, color: '#555' }
});
