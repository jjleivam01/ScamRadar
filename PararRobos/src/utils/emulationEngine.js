import { Alert } from 'react-native';

/**
 * Mocking a local background job / simulator that sends "Bank Emulation" SMS
 * to train the user on identifying frauds.
 */
export const scheduleBankEmulationTest = () => {
    // In a real device, we'd schedule a local push notification
    // using expo-notifications. 
    // For now we simulate an alert that pops up after a few seconds of registering

    setTimeout(() => {
        Alert.alert(
            '¡Mensaje de Prueba!',
            'Acabas de recibir un SMS simulado: "Su cuenta será bloqueada, ingrese aquí". ¿Qué deberías hacer?\n\n¡Ignorarlo y analizarlo en ScamRadar IA! Así es como protegemos tu información.',
            [{ text: 'Entendido' }]
        );
    }, 15000); // 15 seconds after app starts or user registers
};
