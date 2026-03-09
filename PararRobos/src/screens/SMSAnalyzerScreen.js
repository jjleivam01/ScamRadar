import React, { useState } from 'react';
import { View, Text, TextInput, StyleSheet, TouchableOpacity, ScrollView, Alert, PermissionsAndroid, Modal, FlatList } from 'react-native';
import SmsAndroid from 'react-native-get-sms-android';
import { analyzeText } from '../utils/nlpEngine';

export default function SMSAnalyzerScreen() {
    const [smsText, setSmsText] = useState('');
    const [analysisResult, setAnalysisResult] = useState(null);
    const [smsList, setSmsList] = useState([]);
    const [isModalVisible, setIsModalVisible] = useState(false);

    const requestSmsPermission = async () => {
        try {
            const granted = await PermissionsAndroid.request(
                PermissionsAndroid.PERMISSIONS.READ_SMS,
                {
                    title: "Permiso para leer SMS",
                    message: "ScamRadar IA necesita acceso a tus SMS para analizarlos rápidamente.",
                    buttonNeutral: "Preguntar Luego",
                    buttonNegative: "Cancelar",
                    buttonPositive: "Aceptar"
                }
            );
            if (granted === PermissionsAndroid.RESULTS.GRANTED) {
                fetchSmsList();
            } else {
                Alert.alert("Permiso Denegado", "No se pueden leer los SMS sin este permiso.");
            }
        } catch (err) {
            console.warn(err);
        }
    };

    const fetchSmsList = () => {
        const filter = {
            box: 'inbox',
            maxCount: 30,
        };

        SmsAndroid.list(
            JSON.stringify(filter),
            (fail) => {
                Alert.alert('Error', 'No se pudieron obtener los mensajes.');
                console.log('Failed with this error: ' + fail);
            },
            (count, smsListString) => {
                const arr = JSON.parse(smsListString);
                setSmsList(arr);
                setIsModalVisible(true);
            }
        );
    };

    const handleSelectSms = (sms) => {
        setIsModalVisible(false);
        setSmsText(`Remitente: ${sms.address}\n\nMensaje: ${sms.body}`);
    };

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

            <TouchableOpacity style={styles.smsButton} onPress={requestSmsPermission}>
                <Text style={styles.buttonText}>📤 Elegir de mi bandeja de SMS</Text>
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

            <Modal visible={isModalVisible} animationType="slide" onRequestClose={() => setIsModalVisible(false)}>
                <View style={styles.modalContainer}>
                    <Text style={styles.modalTitle}>Últimos Mensajes de Texto</Text>
                    <FlatList
                        data={smsList}
                        keyExtractor={(item) => item._id.toString()}
                        renderItem={({ item }) => (
                            <TouchableOpacity style={styles.smsItem} onPress={() => handleSelectSms(item)}>
                                <Text style={styles.smsAddress}>{item.address}</Text>
                                <Text style={styles.smsBody} numberOfLines={2}>{item.body}</Text>
                                <Text style={styles.smsDate}>{new Date(item.date).toLocaleString()}</Text>
                            </TouchableOpacity>
                        )}
                    />
                    <TouchableOpacity style={styles.closeModalButton} onPress={() => setIsModalVisible(false)}>
                        <Text style={styles.buttonText}>Cerrar</Text>
                    </TouchableOpacity>
                </View>
            </Modal>
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
        marginBottom: 10,
    },
    smsButton: {
        backgroundColor: '#8e44ad',
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
    },
    modalContainer: {
        flex: 1,
        padding: 20,
        backgroundColor: '#f5f6fa',
    },
    modalTitle: {
        fontSize: 22,
        fontWeight: 'bold',
        marginBottom: 15,
        color: '#2c3e50',
    },
    smsItem: {
        padding: 15,
        backgroundColor: '#fff',
        borderRadius: 8,
        marginBottom: 10,
        shadowColor: '#000',
        shadowOpacity: 0.1,
        shadowRadius: 4,
        elevation: 2,
    },
    smsAddress: {
        fontWeight: 'bold',
        fontSize: 16,
        color: '#2980b9',
    },
    smsBody: {
        fontSize: 14,
        color: '#7f8c8d',
        marginTop: 5,
    },
    smsDate: {
        fontSize: 12,
        color: '#bdc3c7',
        marginTop: 5,
    },
    closeModalButton: {
        backgroundColor: '#e74c3c',
        padding: 15,
        borderRadius: 8,
        alignItems: 'center',
        marginTop: 10,
    }
});
