import os

import yaml
from dotenv import load_dotenv
from fastapi import APIRouter
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores.pgvector import PGVector
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)

from app.api.deps import CurrentUser
from app.core.ai_clients import create_chat_model, create_embedding_model
from app.core.config import logger, settings
from app.schemas.chat_schema import ChatBody

load_dotenv()
router = APIRouter()

config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config/chat.yml")
with open(config_path) as config_file:
    config = yaml.load(config_file, Loader=yaml.FullLoader)

chat_config = config.get("CHAT_CONFIG", None)

logger.info(f"Chat config: {chat_config}")

chat_history = [AIMessage(content="Hello, I am a bot. How can I help you?")]


def get_context_retriever_chain(vector_store):
    logger.info("Creating context retriever chain")
    llm = create_chat_model(model=settings.RESEARCH_MODEL)

    retriever = vector_store.as_retriever()

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            (
                "user",
                "Given the above conversation, generate a search query to look up "
                "in order to get information relevant to the conversation",
            ),
        ]
    )

    retriever_chain = create_history_aware_retriever(llm, retriever, prompt)

    return retriever_chain


def get_conversational_rag_chain(retriever_chain):

    llm = create_chat_model(model=settings.RESEARCH_MODEL)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Answer the user's questions based on the below context:\n\n{context}",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
        ]
    )

    stuff_documents_chain = create_stuff_documents_chain(llm, prompt)

    return create_retrieval_chain(retriever_chain, stuff_documents_chain)


@router.post("/chat")
async def chat_action(
    request: ChatBody,
    current_user: CurrentUser,
):
    global chat_history

    embeddings = create_embedding_model()

    store = PGVector(
        collection_name="docs",
        connection_string=settings.SYNC_DATABASE_URI,
        embedding_function=embeddings,
    )

    # retriever = store.as_retriever()

    user_message = HumanMessage(content=request.message)

    retriever_chain = get_context_retriever_chain(store)
    conversation_rag_chain = get_conversational_rag_chain(retriever_chain)

    logger.info(f"User message: {user_message.content}")
    logger.info(f"Chat history: {chat_history}")
    response = conversation_rag_chain.invoke(
        {"chat_history": chat_history, "input": user_message}
    )

    chat_history.append(user_message)

    ai_message = AIMessage(content=response["answer"])
    chat_history.append(ai_message)

    return {"data": response["answer"]}

    # # Load prompts from configuration
    # _template_condense = chat_config["PROMPTS"]["CONDENSE_QUESTION"]
    # _template_answer = chat_config["PROMPTS"]["ANSWER_QUESTION"]
    # _template_default_document = chat_config["PROMPTS"]["DEFAULT_DOCUMENT"]

    # # Your existing logic here, replace hardcoded prompt templates with loaded ones
    # # Example of using loaded prompts:
    # CONDENSE_QUESTION_PROMPT = PromptTemplate.from_template(_template_condense)

    # ANSWER_PROMPT = ChatPromptTemplate.from_template(_template_answer)
    # DEFAULT_DOCUMENT_PROMPT = PromptTemplate.from_template(_template_default_document)
    # logger.info(f"CONDENSE_QUESTION_PROMPT: {CONDENSE_QUESTION_PROMPT}")
    # logger.info(f"ANSWER_PROMPT: {ANSWER_PROMPT}")
    # logger.info(f"DEFAULT_DOCUMENT_PROMPT: {DEFAULT_DOCUMENT_PROMPT}")

    # def _combine_documents(
    #     docs, document_prompt=DEFAULT_DOCUMENT_PROMPT, document_separator="\n\n"
    # ):
    #     doc_strings = [format_document(doc, document_prompt) for doc in docs]

    #     return document_separator.join(doc_strings)

    # memory = ConversationBufferMemory(
    #     return_messages=True, output_key="answer", input_key="question"
    # )

    # # First we add a step to load memory
    # # This adds a "memory" key to the input object
    # loaded_memory = RunnablePassthrough.assign(
    #     chat_history=RunnableLambda(memory.load_memory_variables)
    #     | itemgetter("history"),
    # )
    # # Now we calculate the standalone question
    # standalone_question = {
    #     "standalone_question": {
    #         "question": lambda x: x["question"],
    #         "chat_history": lambda x: get_buffer_string(x["chat_history"]),
    #     }
    #     | CONDENSE_QUESTION_PROMPT
    #     | ChatOpenAI(temperature=0.7, model="gpt-4-turbo-preview")
    #     | StrOutputParser(),
    # }
    # # Now we retrieve the documents
    # retrieved_documents = {
    #     "docs": itemgetter("standalone_question") | retriever,
    #     "question": lambda x: x["standalone_question"],
    # }
    # # Now we construct the inputs for the final prompt
    # final_inputs = {
    #     "context": lambda x: _combine_documents(x["docs"]),
    #     "question": itemgetter("question"),
    # }

    # test = final_inputs["context"]

    # logger.info(f"Final inputs: {test}")
    # # And finally, we do the part that returns the answers
    # answer = {
    #     "answer": final_inputs | ANSWER_PROMPT | ChatOpenAI(),
    #     "docs": itemgetter("docs"),
    # }

    # final_chain = loaded_memory | standalone_question | retrieved_documents | answer

    # inputs = {"question": request.message}
    # logger.info(f"Inputs: {inputs}")
    # result = final_chain.invoke(inputs)

    # test2 = result["answer"]

    # logger.info(f"Result: {test2}")

    # test3 = result["answer"].content

    # logger.info(f"Result: {test3}")

    # return {"data": result["answer"].content}
