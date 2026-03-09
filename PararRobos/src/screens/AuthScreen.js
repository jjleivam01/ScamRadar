import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, Alert, Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { scheduleBankEmulationTest } from '../utils/emulationEngine';
import { signInAnonymously } from 'firebase/auth';
import { doc, setDoc, getDoc } from 'firebase/firestore';
import { auth, db } from '../config/firebase';

export default function AuthScreen({ navigation }) {
    const [name, setName] = useState('');
    const [phone, setPhone] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        checkExistingSession();
    }, []);

    const checkExistingSession = async () => {
        try {
            const storedUID = await AsyncStorage.getItem('@user_uid');
            if (storedUID) {
                // Check if user actually exists in Firestore
                const userDoc = await getDoc(doc(db, "users", storedUID));
                if (userDoc.exists()) {
                    navigation.replace('Home');
                }
            }
        } catch (e) {
            console.error('Error reading session data', e);
        }
    };

    const handleRegister = async () => {
        if (!name.trim() || !phone.trim()) {
            if (Platform.OS === 'web') {
                window.alert('Por favor llena todos los campos.');
            } else {
                Alert.alert('Error', 'Por favor llena todos los campos.');
            }
            return;
        }

        setIsLoading(true);

        try {
            // Sign in anonymously mapping device to unique Firebase user
            const userCredential = await signInAnonymously(auth);
            const user = userCredential.user;

            const userData = {
                uid: user.uid,
                name,
                phone,
                registrationDate: new Date().toISOString(),
                hasTrial: true,
            };

            // Save permanent profile to Firestore Database
            await setDoc(doc(db, "users", user.uid), userData);

            // Keep local persistence to skip login screen
            await AsyncStorage.setItem('@user_uid', user.uid);

            // TEMP: Inicializar Fraud Patterns en V2 para demostración si no existen
            try {
                const initialFraudPatterns = {
                    URGENCY_KEYWORDS: ['congelar', 'multa inminente', 'cierre de cuenta', 'oficina virtual', 'embargo', 'suplantado'],
                    ENTITIES: ['banco de occidente', 'bancoomeva', 'nu', 'nubank', 'movii', 'tuya'],
                    DATA_REQUESTS: ['número de tarjeta', 'fecha de vencimiento', 'cvv', 'ingresa al link', 'código de confirmación', 'token'],
                    OFFICIAL_CHANNELS: ['85000', '89000', 'alertas@bancolombia.com']
                };
                await setDoc(doc(db, "system", "fraud_patterns"), initialFraudPatterns, { merge: true });
                console.log("Firestore (fraud_patterns) Inicializado.");
            } catch (initErr) {
                console.warn("No se pudo autoiniciar fraud_patterns:", initErr);
            }

            if (Platform.OS === 'web') {
                window.alert('¡Bienvenido! Tu mes de prueba gratuito ha comenzado. Disfruta la protección de ScamRadar IA.');
                scheduleBankEmulationTest();
                navigation.replace('Home');
            } else {
                Alert.alert(
                    '¡Bienvenido!',
                    'Tu mes de prueba gratuito ha comenzado. Disfruta la protección de ScamRadar IA.',
                    [{
                        text: 'Comenzar', onPress: () => {
                            scheduleBankEmulationTest();
                            navigation.replace('Home');
                        }
                    }]
                );
            }
        } catch (e) {
            console.error('Registration failed', e);
            if (Platform.OS === 'web') {
                window.alert('Hubo un problema registrando al usuario. Intenta de nuevo.');
            } else {
                Alert.alert('Error', 'Hubo un problema registrando al usuario. Intenta de nuevo.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <View style={styles.container}>
            <Text style={styles.title}>ScamRadar IA</Text>
            <Text style={styles.subtitle}>Registro de Usuario</Text>

            <Text style={styles.label}>Nombre completo:</Text>
            <TextInput
                style={styles.input}
                placeholder="Ej: Juan Pérez"
                value={name}
                onChangeText={setName}
            />

            <Text style={styles.label}>Número Telefónico:</Text>
            <TextInput
                style={styles.input}
                placeholder="Ej: +57 300 000 0000"
                keyboardType="phone-pad"
                value={phone}
                onChangeText={setPhone}
            />

            <View style={styles.infoBox}>
                <Text style={styles.infoText}>
                    Al registrarte obtendrás 1 mes de prueba **totalmente gratis**.
                    Finalizado el mes, se solicitará un pago único de 10.000 COP para acceder de por vida a la Versión 2.
                </Text>
            </View>

            <TouchableOpacity
                style={[styles.button, isLoading && styles.buttonDisabled]}
                onPress={handleRegister}
                disabled={isLoading}
            >
                <Text style={styles.buttonText}>
                    {isLoading ? 'Registrando...' : 'Comenzar Mes de Prueba'}
                </Text>
            </TouchableOpacity>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        padding: 20,
        backgroundColor: '#fff',
        justifyContent: 'center',
    },
    title: {
        fontSize: 36,
        fontWeight: 'bold',
        color: '#2ecc71',
        textAlign: 'center',
        marginBottom: 5,
    },
    subtitle: {
        fontSize: 18,
        color: '#7f8c8d',
        textAlign: 'center',
        marginBottom: 40,
    },
    label: {
        fontSize: 16,
        color: '#2c3e50',
        marginBottom: 8,
        fontWeight: 'bold',
    },
    input: {
        borderWidth: 1,
        borderColor: '#bdc3c7',
        borderRadius: 8,
        padding: 15,
        fontSize: 16,
        marginBottom: 20,
        backgroundColor: '#f9f9f9',
    },
    infoBox: {
        backgroundColor: '#fff3cd',
        padding: 15,
        borderRadius: 8,
        marginBottom: 30,
        borderLeftWidth: 4,
        borderLeftColor: '#f1c40f',
    },
    infoText: {
        color: '#856404',
        fontSize: 14,
        lineHeight: 20,
    },
    button: {
        backgroundColor: '#27ae60',
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
    },
    buttonDisabled: {
        backgroundColor: '#95a5a6',
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
    }
});
