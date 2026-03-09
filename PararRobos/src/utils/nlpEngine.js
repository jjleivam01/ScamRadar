// c:\Tesis_IA\PararRobos\src\utils\nlpEngine.js
import { doc, getDoc } from 'firebase/firestore';
import { db } from '../config/firebase';

// Diccionarios Dinámicos
let URGENCY_KEYWORDS = [
    'urgente', 'inmediato', 'bloqueo', 'bloqueada', 'suspendida',
    'suspenderemos', 'cancela', 'cancelada', 'verificar ahora',
    'último aviso', 'evite multas', 'acción requerida', 'restricción',
    'inhabilitado', 'inhabilitada', 'robo', 'clonada', 'peligro', 'alerta',
    'phishing', 'fraude', 'cuenta bloqueada', 'verificar una transacción',
    'verificar transacción'
];

// Lista de entidades comúnmente suplantadas
let ENTITIES = [
    'banco', 'bancolombia', 'davivienda', 'bbva', 'nequi', 'daviplata',
    'netflix', 'amazon', 'mercado libre', 'mercadolibre', 'dian', 'policia',
    'scotiabank', 'colpatria', 'bogota', 'occidente', 'popular', 'caja social'
];

// Fuentes Oficiales Seguras (Whitelist)
let OFFICIAL_CHANNELS = [
    '891 333', '891333', // Mensajería oficial Bancolombia
    'validaciondeseguridad@notificacionesbancolombia.com'
];

// Palabras relacionadas a peticiones de datos
let DATA_REQUESTS = [
    'contraseña', 'clave', 'pin', 'código', 'codigo', 'actualizar datos',
    'verificar cuenta', 'ingrese aquí', 'su cuenta', 'validar identidad',
    'ingresa tu', 'digita', 'entrar a', 'entrar acá', 'enlace', 'link'
];

// Regex para detectar URLs
const URL_REGEX = /(https?:\/\/[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.[a-zA-Z]{2,}(\/[^\s]*)?)/g;

/**
 * Downloads and merges remote dictionary words from Firebase.
 * Silently fails and uses local hardcoded defaults if offline.
 */
export const syncFraudPatterns = async () => {
    try {
        const docRef = doc(db, 'system', 'fraud_patterns');
        const docSnap = await getDoc(docRef);

        if (docSnap.exists()) {
            const remoteData = docSnap.data();

            // Merge remote arrays into local state if they exist
            if (remoteData.URGENCY_KEYWORDS) {
                URGENCY_KEYWORDS = [...new Set([...URGENCY_KEYWORDS, ...remoteData.URGENCY_KEYWORDS])];
            }
            if (remoteData.ENTITIES) {
                ENTITIES = [...new Set([...ENTITIES, ...remoteData.ENTITIES])];
            }
            if (remoteData.OFFICIAL_CHANNELS) {
                OFFICIAL_CHANNELS = [...new Set([...OFFICIAL_CHANNELS, ...remoteData.OFFICIAL_CHANNELS])];
            }
            if (remoteData.DATA_REQUESTS) {
                DATA_REQUESTS = [...new Set([...DATA_REQUESTS, ...remoteData.DATA_REQUESTS])];
            }
            console.log('Firebase Fraud Patterns synced successfully (Edge Dictionary Updated).');
        }
    } catch (e) {
        console.error('Failed to sync fraud patterns from Firebase (Using local defaults):', e);
    }
};

export const analyzeText = (text) => {
    const textLower = text.toLowerCase();

    let score = 0;
    let matches = {
        urgency: [],
        entities: [],
        dataRequests: [],
        links: [],
    };

    // 1. Detectar Links (Muy sospechoso en SMS de entidades no solicitadas)
    const linksFound = text.match(URL_REGEX);
    if (linksFound) {
        matches.links = linksFound;
        score += linksFound.length * 50; // Aumentado drásticamente
    }

    // 2. Detectar Sentido de Urgencia
    URGENCY_KEYWORDS.forEach(keyword => {
        if (textLower.includes(keyword)) {
            matches.urgency.push(keyword);
            score += 35; // Aumentado
        }
    });

    // 3. Detectar Suplantación de Entidades
    let isBancolombia = false;
    ENTITIES.forEach(entity => {
        if (textLower.includes(entity)) {
            matches.entities.push(entity);
            score += 30; // Aumentado
            if (entity === 'bancolombia') isBancolombia = true;
        }
    });

    // REGLA ESTRICTA BANCOLOMBIA: "Nunca enviamos enlaces"
    if (isBancolombia && matches.links.length > 0) {
        // Fraude 100% garantizado según las reglas del banco
        score += 200;
        matches.urgency.push("Violación de Política de Bancolombia (Uso de Links)");
    }

    // 4. Detectar Petición de Datos
    DATA_REQUESTS.forEach(req => {
        if (textLower.includes(req)) {
            matches.dataRequests.push(req);
            score += 40; // Aumentado drásticamente
        }
    });

    // 5. Lista Blanca (Whitelist) - Reducir puntuación si viene de canal oficial
    let isOfficial = false;
    OFFICIAL_CHANNELS.forEach(channel => {
        if (textLower.includes(channel.toLowerCase())) {
            isOfficial = true;
        }
    });

    if (isOfficial) {
        score = 0; // Es seguro porque proviene del canal oficial
    }

    // Determinar nivel de riesgo
    let riskLevel = 'SAFE'; // SAFE, WARNING, DANGER
    let riskMessage = 'El mensaje no parece contener patrones de fraude conocidos.';

    // Niveles de peligro ajustados para ser más sensibles
    if (isOfficial) {
        riskLevel = 'SAFE';
        riskMessage = 'Mensaje Seguro: Proviene de un canal oficial verificado del banco.';
        score = 0;
    } else if (score >= 50) {
        riskLevel = 'DANGER';
        riskMessage = '¡ALTO RIESGO DE FRAUDE! Este mensaje intenta generar urgencia, suplanta una entidad o contiene enlaces engañosos solicitando datos. Recuerda: Los bancos nunca envian enlaces.';
    } else if (score >= 25) {
        riskLevel = 'WARNING';
        riskMessage = 'Precaución: El mensaje tiene elementos sospechosos (posibile entidad falsa o palabras de alarma). Verifica la fuente.';
    }

    return {
        score: Math.min(score, 100), // Cap at 100%
        riskLevel,
        riskMessage,
        details: matches
    };
};
