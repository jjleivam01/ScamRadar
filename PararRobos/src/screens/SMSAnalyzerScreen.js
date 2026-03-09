import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView, Alert } from 'react-native';
import { analyzeText } from '../utils/nlpEngine';

export default function SMSAnalyzerScreen() {
    const [smsText, setSmsText] = useState('');
    const [analysisResult, setAnalysisResult] = useState(null);

    const handleAnalyze = () => {
        if (!smsText.trim()) {
            Alert.alert('Aviso', 'Por favor pega un mensaje para analizar.');
            return;
        }
        const result = analyzeText(smsText);
        setAnalysisResult(result);
    };

    const renderDetails = (details) => {
        return (
            <View style={styles.detailsContainer}>
                {details.links.length > 0 && <Text style={styles.detailText}>🔗 Enlaces detectados: {details.links.length}</Text>}
                {details.urgency.length > 0 && <Text style={styles.detailText}>⚠️ Palabras de urgencia: {details.urgency.join(', ')}</Text>}
                {details.dataRequests.length > 0 && <Text style={styles.detailText}>🔐 Petición de datos: {details.dataRequests.join(', ')}</Text>}
                {details.entities.length > 0 && <Text style={styles.detailText}>🏦 Entidad mencionada: {details.entities.join(', ')}</Text>}
            </View>
        );
    };

    return (
        <ScrollView contentContainerStyle={styles.container}>
            <Text style={styles.title}>Analizador de SMS</Text>
            <Text style={styles.description}>Pega aquí el mensaje de texto sospechoso que recibiste:</Text>

            <TextInput
                style={styles.inputArea}
                multiline
                numberOfLines={6}
                placeholder="Ej: Estimado cliente de BANCO X, su cuenta será bloqueada. Ingrese a este link urgente..."
                value={smsText}
                onChangeText={setSmsText}
            />

            <TouchableOpacity style={styles.analyzeButton} onPress={handleAnalyze}>
                <Text style={styles.buttonText}>Analizar Mensaje</Text>
            </TouchableOpacity>

            {analysisResult && (
                <View style={[
                    styles.resultBox,
                    analysisResult.riskLevel === 'DANGER' ? styles.resultDanger :
                        analysisResult.riskLevel === 'WARNING' ? styles.resultWarning :
                            styles.resultSafe
                ]}>
                    <Text style={[styles.resultTitle, { color: analysisResult.riskLevel === 'DANGER' ? '#c0392b' : analysisResult.riskLevel === 'WARNING' ? '#d35400' : '#27ae60' }]}>
                        Nivel de Riesgo: {analysisResult.riskLevel} ({analysisResult.score}%)
                    </Text>
                    <Text style={styles.resultText}>{analysisResult.riskMessage}</Text>
                    {renderDetails(analysisResult.details)}
                </View>
            )}
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flexGrow: 1,
        padding: 20,
        backgroundColor: '#fff',
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        color: '#2c3e50',
        marginBottom: 10,
    },
    description: {
        fontSize: 16,
        color: '#34495e',
        marginBottom: 20,
    },
    inputArea: {
        borderWidth: 1,
        borderColor: '#bdc3c7',
        borderRadius: 8,
        padding: 15,
        fontSize: 16,
        textAlignVertical: 'top',
        marginBottom: 20,
        backgroundColor: '#f9f9f9',
    },
    analyzeButton: {
        backgroundColor: '#3498db',
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
        marginBottom: 20,
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
    },
    resultBox: {
        padding: 15,
        borderRadius: 8,
        marginTop: 10,
    },
    resultDanger: {
        backgroundColor: '#fadbd8',
        borderColor: '#e74c3c',
        borderWidth: 2,
    },
    resultWarning: {
        backgroundColor: '#fdebd0',
        borderColor: '#f39c12',
        borderWidth: 2,
    },
    resultSafe: {
        backgroundColor: '#d5f5e3',
        borderColor: '#2ecc71',
        borderWidth: 2,
    },
    resultTitle: {
        fontSize: 18,
        fontWeight: 'bold',
        marginBottom: 10,
    },
    resultText: {
        fontSize: 15,
        color: '#2c3e50',
        marginBottom: 15,
        lineHeight: 22,
    },
    detailsContainer: {
        marginTop: 10,
        borderTopWidth: 1,
        borderTopColor: 'rgba(0,0,0,0.1)',
        paddingTop: 10,
    },
    detailText: {
        fontSize: 14,
        color: '#34495e',
        marginBottom: 4,
    }
});
