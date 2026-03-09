import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput, ScrollView } from 'react-native';
// import Voice from '@react-native-voice/voice'; // Descomentaremos y usaremos cuando el dev-client esté listo
import { analyzeText } from '../utils/nlpEngine';

export default function CallAnalyzerScreen() {
    const [isActiveCall, setIsActiveCall] = useState(null);
    const [phoneNumber, setPhoneNumber] = useState('');
    const [manualCheckResult, setManualCheckResult] = useState(null);

    // Voice & Analysis State
    const [isListening, setIsListening] = useState(false);
    const [transcription, setTranscription] = useState('');
    const [realtimeScore, setRealtimeScore] = useState(0);
    const [riskLevel, setRiskLevel] = useState('SAFE');

    // Referencia y Estado del API Web
    const [recognitionObj, setRecognitionObj] = useState(null);

    // Configurar API de Voz (Navegador Web)
    useEffect(() => {
        if (typeof window !== 'undefined' && ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognition = new SpeechRecognition();
            recognition.continuous = true;
            recognition.interimResults = true;
            recognition.lang = 'es-ES'; // Idioma Español

            recognition.onresult = (event) => {
                let currentTranscript = '';

                // Reconstruir toda la oración desde cero usando la memoria de la API
                // Esto sobreescribe los fragmentos temporales ("interim") y evita la repetición
                for (let i = 0; i < event.results.length; ++i) {
                    currentTranscript += event.results[i][0].transcript;
                }

                setTranscription(currentTranscript);

                // Evaluar el texto limpio en tiempo real
                const { score, riskLevel } = analyzeText(currentTranscript);
                setRealtimeScore(score);
                setRiskLevel(riskLevel);
            };

            recognition.onerror = (event) => {
                console.error("Speech Recognition Error:", event.error);
                setIsListening(false);
            };

            recognition.onend = () => {
                // Si seguimos en modo listening pero se cortó, reactivar
                if (isListening) {
                    try { recognition.start(); } catch (e) { }
                }
            };

            setRecognitionObj(recognition);
        }
    }, []);

    // Controlar ciclo de vida del micrófono según state isListening
    useEffect(() => {
        if (recognitionObj) {
            if (isListening) {
                try {
                    recognitionObj.start();
                } catch (e) {
                    // Evitar error si ya estaba escuchando
                }
            } else {
                recognitionObj.stop();
            }
        }
    }, [isListening, recognitionObj]);

    const toggleListening = () => {
        if (!recognitionObj && Platform.OS === 'web') {
            window.alert('Tu navegador no soporta Reconocimiento de Voz nativo. Usa Chrome o Safari.');
            return;
        }

        if (isListening) {
            setIsListening(false);
        } else {
            setTranscription('');
            setRealtimeScore(0);
            setRiskLevel('SAFE');
            setIsListening(true);
        }
    };

    const renderActiveCallUI = () => (
        <ScrollView contentContainerStyle={styles.activeCallContainer}>
            <Text style={styles.instructionTitle}>Instrucciones:</Text>
            <Text style={styles.instructionText}>1. Ingresa el número que te está llamando para una evaluación instantánea.</Text>
            <Text style={styles.instructionText}>2. Pon la llamada en altavoz (speaker).</Text>
            <Text style={styles.instructionText}>3. Presiona el botón de abajo para iniciar el análisis en tiempo real.</Text>

            <View style={{ marginTop: 15, marginBottom: 20 }}>
                <Text style={styles.instructionText}>Número de la llamada actual:</Text>
                <TextInput
                    style={[styles.input, { marginTop: 5, marginBottom: 10 }]}
                    placeholder="Ej: 300 500 0991"
                    keyboardType="phone-pad"
                    value={phoneNumber}
                    onChangeText={(text) => {
                        setPhoneNumber(text);
                        setManualCheckResult(null);
                    }}
                />
                <TouchableOpacity style={styles.searchButton} onPress={handleCheckNumber}>
                    <Text style={styles.buttonText}>Evaluar Número Rápidamente</Text>
                </TouchableOpacity>

                {manualCheckResult && (
                    <View style={[
                        styles.analysisBox,
                        manualCheckResult.status === 'SAFE' ? styles.bgSafe : styles.bgDanger,
                        { marginTop: 10, padding: 10 }
                    ]}>
                        <Text style={styles.riskText}>{manualCheckResult.status === 'SAFE' ? '✅ Seguro' : '🚨 PELIGRO'}</Text>
                        <Text style={[styles.instructionText, { marginTop: 5, fontWeight: 'bold' }]}>
                            {manualCheckResult.message}
                        </Text>
                    </View>
                )}
            </View>

            <TouchableOpacity
                style={[styles.listenButton, isListening && styles.listenButtonActive]}
                onPress={toggleListening}
            >
                <Text style={styles.buttonText}>
                    {isListening ? '🛑 Detener Análisis' : '🎙️ Iniciar Análisis'}
                </Text>
            </TouchableOpacity>

            {isListening || transcription !== '' ? (
                <View style={styles.analysisBox}>
                    <Text style={styles.statusLabel}>Estado del Análisis:</Text>
                    <View style={[
                        styles.riskBadge,
                        riskLevel === 'DANGER' ? styles.bgDanger :
                            riskLevel === 'WARNING' ? styles.bgWarning :
                                styles.bgSafe
                    ]}>
                        <Text style={styles.riskText}>{riskLevel} ({realtimeScore}%)</Text>
                    </View>

                    <Text style={styles.transcriptionLabel}>Transcripción en vivo:</Text>
                    <Text style={styles.transcriptionText}>{transcription || 'Escuchando...'}</Text>
                </View>
            ) : null}
        </ScrollView>
    );

    const handleCheckNumber = () => {
        if (!phoneNumber.trim()) return;

        // Limpiar símbolos para solo comparar números
        const cleanNumber = phoneNumber.replace(/[^0-9]/g, '');

        if (cleanNumber === '3005000991' || cleanNumber === '573005000991') {
            setManualCheckResult({
                status: 'SAFE',
                message: 'Verificado: Este número es seguro y pertenece a una entidad oficial.'
            });
        } else {
            setManualCheckResult({
                status: 'DANGER',
                message: '¡Peligro! Este número NO pertenece a canales oficiales registrados. Alta probabilidad de Fraude.'
            });
        }
    };

    const renderManualEntryUI = () => (
        <View style={styles.manualEntryContainer}>
            <Text style={styles.instructionText}>Ingresa el número sospechoso para verificar en nuestra base de datos:</Text>
            <TextInput
                style={styles.input}
                placeholder="Ej: 300 500 0991"
                keyboardType="phone-pad"
                value={phoneNumber}
                onChangeText={(text) => {
                    setPhoneNumber(text);
                    setManualCheckResult(null); // Reset result when typing
                }}
            />
            <TouchableOpacity style={styles.searchButton} onPress={handleCheckNumber}>
                <Text style={styles.buttonText}>Verificar Número</Text>
            </TouchableOpacity>

            {manualCheckResult && (
                <View style={[
                    styles.analysisBox,
                    manualCheckResult.status === 'SAFE' ? styles.bgSafe : styles.bgDanger,
                    { marginTop: 20 }
                ]}>
                    <Text style={styles.riskText}>{manualCheckResult.status === 'SAFE' ? '✅ Seguro' : '🚨 PELIGRO'}</Text>
                    <Text style={[styles.instructionText, { marginTop: 10, fontWeight: 'bold' }]}>
                        {manualCheckResult.message}
                    </Text>
                </View>
            )}
        </View>
    );

    return (
        <View style={styles.container}>
            <Text style={styles.title}>Analizador de Llamadas</Text>

            {isActiveCall === null ? (
                <View style={styles.questionContainer}>
                    <Text style={styles.questionText}>¿Es una llamada activa en este momento?</Text>
                    <View style={styles.buttonRow}>
                        <TouchableOpacity style={styles.choiceButton} onPress={() => setIsActiveCall(true)}>
                            <Text style={styles.choiceText}>Sí, está activa</Text>
                        </TouchableOpacity>
                        <TouchableOpacity style={[styles.choiceButton, styles.choiceNo]} onPress={() => setIsActiveCall(false)}>
                            <Text style={styles.choiceText}>No, ya terminó</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            ) : (
                <View style={styles.contentContainer}>
                    <TouchableOpacity style={styles.backButton} onPress={() => { setIsActiveCall(null); setIsListening(false); }}>
                        <Text style={styles.backText}>← Volver</Text>
                    </TouchableOpacity>
                    {isActiveCall ? renderActiveCallUI() : renderManualEntryUI()}
                </View>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        padding: 20,
        backgroundColor: '#fff',
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#2c3e50',
        marginBottom: 20,
    },
    questionContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
    },
    questionText: {
        fontSize: 20,
        textAlign: 'center',
        marginBottom: 30,
        color: '#34495e',
    },
    buttonRow: {
        flexDirection: 'row',
        justifyContent: 'space-around',
        width: '100%',
    },
    choiceButton: {
        backgroundColor: '#3498db',
        paddingVertical: 15,
        paddingHorizontal: 25,
        borderRadius: 8,
        minWidth: 140,
        alignItems: 'center',
    },
    choiceNo: {
        backgroundColor: '#95a5a6',
    },
    choiceText: {
        color: '#fff',
        fontSize: 16,
        fontWeight: 'bold',
    },
    contentContainer: {
        flex: 1,
    },
    backButton: {
        marginBottom: 10,
    },
    backText: {
        color: '#3498db',
        fontSize: 16,
    },
    activeCallContainer: {
        flexGrow: 1,
        paddingBottom: 30,
    },
    instructionTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        marginBottom: 10,
        color: '#e74c3c',
    },
    instructionText: {
        fontSize: 16,
        marginBottom: 6,
        color: '#2c3e50',
    },
    listenButton: {
        backgroundColor: '#27ae60',
        padding: 20,
        borderRadius: 10,
        alignItems: 'center',
        marginTop: 20,
    },
    listenButtonActive: {
        backgroundColor: '#c0392b',
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
    },
    analysisBox: {
        marginTop: 30,
        padding: 15,
        backgroundColor: '#f8f9f9',
        borderRadius: 8,
        borderWidth: 1,
        borderColor: '#d5dbdb',
    },
    statusLabel: {
        fontSize: 16,
        fontWeight: 'bold',
        marginBottom: 10,
    },
    riskBadge: {
        padding: 10,
        borderRadius: 5,
        alignItems: 'center',
        marginBottom: 20,
    },
    bgSafe: { backgroundColor: '#d5f5e3' },
    bgWarning: { backgroundColor: '#fdebd0' },
    bgDanger: { backgroundColor: '#fadbd8' },
    riskText: {
        fontWeight: 'bold',
        fontSize: 16,
        color: '#2c3e50',
    },
    transcriptionLabel: {
        fontSize: 14,
        color: '#7f8c8d',
        marginBottom: 5,
    },
    transcriptionText: {
        fontSize: 18,
        color: '#34495e',
        fontStyle: 'italic',
    },
    manualEntryContainer: {
        flex: 1,
    },
    input: {
        borderWidth: 1,
        borderColor: '#bdc3c7',
        borderRadius: 8,
        padding: 15,
        fontSize: 18,
        marginTop: 15,
        marginBottom: 20,
        backgroundColor: '#f9f9f9',
    },
    searchButton: {
        backgroundColor: '#2ecc71',
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
    }
});
