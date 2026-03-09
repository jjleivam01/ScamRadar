// c:\Tesis_IA\PararRobos\src\utils\initFirestore.js
import { doc, setDoc } from 'firebase/firestore';
import { db } from '../config/firebase.js';

const initialFraudPatterns = {
    URGENCY_KEYWORDS: [
        'congelar', 'multa inminente', 'cierre de cuenta', 'oficina virtual',
        'embargo', 'suplantado'
    ],
    ENTITIES: [
        'banco de occidente', 'bancoomeva', 'nu', 'nubank', 'movii', 'tuya'
    ],
    DATA_REQUESTS: [
        'número de tarjeta', 'fecha de vencimiento', 'cvv', 'ingresa al link',
        'código de confirmación', 'token'
    ],
    OFFICIAL_CHANNELS: [
        '85000', '89000', // Otros códigos cortos ficticios/ejemplos
        'alertas@bancolombia.com'
    ]
};

const initDB = async () => {
    try {
        console.log("Subiendo patrones iniciales a la Nube (Firestore)...");
        await setDoc(doc(db, "system", "fraud_patterns"), initialFraudPatterns);
        console.log("¡Carga exitosa! La Nube ahora tiene los diccionarios base.");
        process.exit(0);
    } catch (error) {
        console.error("Error inicializando BD: ", error);
        process.exit(1);
    }
};

initDB();
