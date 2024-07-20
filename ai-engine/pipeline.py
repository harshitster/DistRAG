from llama_index.core import SQLDatabase, VectorStoreIndex
from llama_index.core.retrievers import SQLRetriever
from llama_index.core.query_pipeline import FnComponent, QueryPipeline
from llama_index.core.prompts.default_prompts import DEFAULT_TEXT_TO_SQL_PROMPT
from llama_index.core import PromptTemplate
from llama_index.core.llms import ChatResponse
from llama_index.core.query_pipeline import InputComponent

def _build_query_pipeline(engine, vector_store, llm):
    sql_database = SQLDatabase(engine)
    sql_retriever = SQLRetriever(sql_database)

    index = VectorStoreIndex.from_vector_store(vector_store)
    obj_retriever = index.as_retriever(similarity_top_k=3)

    def get_table_context_str(table_schema_objs):
        context_strs = []
        for table_schema_obj in table_schema_objs:
            table_info = sql_database.get_single_table_info(
                table_schema_obj.metadata['table_name']
            )
            if table_schema_obj.text:
                table_opt_context = " The table description is: "
                table_opt_context += table_schema_obj.text.split("Table Summary: ")[1]
                table_info += table_opt_context
            context_strs.append(table_info)
        return "\n\n".join(context_strs)
    
    table_parser_component = FnComponent(fn=get_table_context_str)

    def parse_response_to_sql(response: ChatResponse) -> str:
        response = response.message.content
        sql_query_start = response.find("SQLQuery:")
        if sql_query_start != -1:
            response = response[sql_query_start:]
            response = response.removeprefix("SQLQuery:")
            sql_result_start = response.find("SQLResult:")
            if (sql_result_start != -1):
                response = response[:sql_result_start]
        return response.strip().strip("```").strip()
    
    sql_parser_component = FnComponent(fn=parse_response_to_sql)

    text2sql_prompt = DEFAULT_TEXT_TO_SQL_PROMPT.partial_format(
        dialect=engine.dialect.name
    )

    response_synthesis_prompt_str = (
        "Given an input question, synthesize a response from the query results.\n"
        "Query: {query_str}\n"
        "SQL: {sql_query}\n"
        "SQL Response: {context_str}\n"
        "Response: "
    )
    response_synthesis_prompt = PromptTemplate(
        response_synthesis_prompt_str,
    )

    qp = QueryPipeline(
        modules={
            "input": InputComponent(),
            "table_retriever": obj_retriever,
            "table_output_parser": table_parser_component,
            "text2sql_prompt": text2sql_prompt,
            "text2sql_llm": llm,
            "sql_output_parser": sql_parser_component,
            "sql_retriever": sql_retriever,
            "response_synthesis_prompt": response_synthesis_prompt,
            "response_synthesis_llm": llm,
        },
        verbose=False,
    )

    qp.add_chain(["input", "table_retriever", "table_output_parser"])
    qp.add_link("input", "text2sql_prompt", dest_key="query_str")
    qp.add_link("table_output_parser", "text2sql_prompt", dest_key="schema")
    qp.add_chain(
        ["text2sql_prompt", "text2sql_llm", "sql_output_parser", "sql_retriever"]
    )
    qp.add_link(
        "sql_output_parser", "response_synthesis_prompt", dest_key="sql_query"
    )
    qp.add_link(
        "sql_retriever", "response_synthesis_prompt", dest_key="context_str"
    )
    qp.add_link("input", "response_synthesis_prompt", dest_key="query_str")
    qp.add_link("response_synthesis_prompt", "response_synthesis_llm")

    return qp