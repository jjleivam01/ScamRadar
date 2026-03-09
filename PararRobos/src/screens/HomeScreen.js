import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';

export default function HomeScreen({ navigation }) {
    return (
        <View style={styles.container}>
            <Text style={styles.title}>ScamRadar IA</Text>
            <Text style={styles.subtitle}>Protección contra fraude e ingeniería social</Text>

            <View style={styles.buttonContainer}>
                <TouchableOpacity
                    style={styles.buttonPrimary}
                    onPress={() => navigation.navigate('SMSAnalyzer')}>
                    <Text style={styles.buttonText}>Analizar mensaje de texto</Text>
                </TouchableOpacity>

                <TouchableOpacity
                    style={styles.buttonSecondary}
                    onPress={() => navigation.navigate('CallAnalyzer')}>
                    <Text style={styles.buttonText}>Analizar llamada</Text>
                </TouchableOpacity>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#f5f7fa',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
    },
    title: {
        fontSize: 32,
        fontWeight: 'bold',
        color: '#2c3e50',
        marginBottom: 10,
    },
    subtitle: {
        fontSize: 16,
        color: '#7f8c8d',
        marginBottom: 50,
        textAlign: 'center',
    },
    buttonContainer: {
        width: '100%',
        paddingHorizontal: 20,
    },
    buttonPrimary: {
        backgroundColor: '#3498db',
        padding: 15,
        borderRadius: 10,
        marginBottom: 15,
        alignItems: 'center',
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 2,
    },
    buttonSecondary: {
        backgroundColor: '#e74c3c',
        padding: 15,
        borderRadius: 10,
        alignItems: 'center',
        elevation: 2,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 2,
    },
    buttonText: {
        color: '#fff',
        fontSize: 18,
        fontWeight: 'bold',
    }
});
