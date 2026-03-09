from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 1. Configuración del LLM local (LM Studio)
llm = ChatOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed",
    temperature=0.3 # Bajo para redacción académica técnica
)

# 2. Configuración de la Memoria (Para recordar sesiones)
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

# Nota: Para la investigación (RAG), necesitaremos inicializar el VectorStore
# con tus documentos. Por ahora, definiremos el cerebro del agente.

def procesar_consulta(query, vectorstore=None):
    # Si tenemos documentos cargados, usamos RAG. Si no, solo chat con memoria.
    if vectorstore:
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(),
            memory=memory
        )
        return chain.run(query)
    else:
        # Lógica de chat simple con memoria para redacción y código
        prompt = f"Como asistente de Tesis de IA, ayuda a John con: {query}"
        return llm.predict(prompt)