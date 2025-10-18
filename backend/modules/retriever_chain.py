# backend/modules/retriever_chain.py
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from backend.core.settings import settings
from backend.modules.utils import logger

def get_conversational_chain(vector_store, temperature: float = 0.0, k: int = 3):
    logger.info("Creating LLM and conversational chain using model %s", settings.LLM_MODEL)
    llm = ChatOpenAI(model=settings.LLM_MODEL, temperature=temperature)
    memory = ConversationBufferMemory(
        memory_key="chat_history", 
        return_messages=True,
        output_key="answer"  # Explicitly set output key for memory
    )
    retriever = vector_store.as_retriever(search_kwargs={"k": k})
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        return_source_documents=True,
        output_key="answer"  # Explicitly set output key for chain
    )
    return chain

# # Test block to verify the code runs (no real OpenAI calls)
# if __name__ == "__main__":
#     print(" Testing retriever_chain.py setup...")
#     try:
#         # Create a fake vector store with a dummy retriever method
#         class DummyRetriever:
#             def as_retriever(self, search_kwargs):
#                 return self
#         dummy_store = DummyRetriever()

#         # Try to create a chain (this will fail only if imports/config are wrong)
#         chain = get_conversational_chain(dummy_store)
#         print(" retriever_chain module structure is working fine (no API calls).")
#     except Exception as e:
#         print(" Skipped API call or encountered issue (likely missing API key).")
#         print("Error details:", e)