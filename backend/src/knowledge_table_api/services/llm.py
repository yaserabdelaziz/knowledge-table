"""The functions for generating responses from the language model."""

import logging
from typing import Any, Literal

import instructor
from openai import OpenAI

from knowledge_table_api.models.graph import Table
from knowledge_table_api.models.llm_response import (
    BoolResponseModel,
    IntArrayResponseModel,
    IntResponseModel,
    StrArrayResponseModel,
    StrResponseModel,
    KeywordsResponseModel,
    SubQueriesResponseModel,
    SchemaResponseModel,
)
from knowledge_table_api.models.query import Rule
from knowledge_table_api.services.prompts import *
from knowledge_table_api.config import settings

# Initialize OpenAI client with the API key
openai_client = OpenAI(api_key=settings.openai_api_key)

# Patch the OpenAI client with instructor
client = instructor.from_openai(openai_client)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def generate_response(
    query: str,
    chunks: str,
    rules: list[Rule],
    format: Literal["int", "str", "bool", "int_array", "str_array"],
) -> dict[str, Any]:
    """Generate a response from the language model."""
    logger.info(f"Generating response for query: {query} in format: {format}")

    str_rule = next((rule for rule in rules if rule.type in ["must_return", "may_return"]), None)
    int_rule = next((rule for rule in rules if rule.type == "max_length"), None)

    format_specific_instructions = ""
    if format == "bool":
        format_specific_instructions = BOOL_INSTRUCTIONS
        output_model = BoolResponseModel
    elif format in ["str_array", "str"]:
        str_rule_line = _get_str_rule_line(str_rule, query)
        int_rule_line = _get_int_rule_line(int_rule)
        format_specific_instructions = STR_ARRAY_INSTRUCTIONS.substitute(
            str_rule_line=str_rule_line,
            int_rule_line=int_rule_line
        )
        output_model = StrArrayResponseModel if format == "str_array" else StrResponseModel
    elif format in ["int", "int_array"]:
        int_rule_line = _get_int_rule_line(int_rule)
        format_specific_instructions = INT_ARRAY_INSTRUCTIONS.substitute(int_rule_line=int_rule_line)
        output_model = IntArrayResponseModel if format == "int_array" else IntResponseModel

    prompt = BASE_PROMPT.substitute(
        query=query,
        chunks=chunks,
        format_specific_instructions=format_specific_instructions,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_model=output_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.model_dump()
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        return {"answer": None}

async def get_keywords(query: str) -> dict[str, list[str]]:
    """Extract keywords from a query using the language model."""
    prompt = KEYWORD_PROMPT.substitute(query=query)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_model=KeywordsResponseModel,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"keywords": response.keywords}
    except Exception as e:
        logger.error(f"Error extracting keywords: {e}")
        return {"keywords": []}

async def get_similar_keywords(chunks: str, rule: list[str]) -> dict[str, Any]:
    """Retrieve keywords similar to the provided keywords from the text chunks."""
    logger.info(f"Retrieving keywords which are similar to the provided keywords: {rule}")

    prompt = SIMILAR_KEYWORDS_PROMPT.substitute(
        rule=rule,
        chunks=chunks,
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_model=KeywordsResponseModel,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"keywords": response.keywords}
    except Exception as e:
        logger.error(f"Error getting similar keywords: {e}")
        return {"keywords": []}

async def decompose_query(query: str) -> dict[str, Any]:
    """Decompose a query into multiple sub-queries."""
    logger.info("Decomposing query into multiple sub-queries.")

    prompt = DECOMPOSE_QUERY_PROMPT.substitute(query=query)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_model=SubQueriesResponseModel,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"sub-queries": response.sub_queries}
    except Exception as e:
        logger.error(f"Error decomposing query: {e}")
        return {"sub-queries": []}

async def generate_schema(data: Table) -> dict[str, Any]:
    """Generate a schema for the table based on column information and questions."""
    logger.info("Generating schema.")

    prepared_data = {
        "documents": list(set(row.document.name for row in data.rows)),
        "columns": [
            {
                "id": column.id,
                "entity_type": column.prompt.entityType,
                "type": column.prompt.type,
                "question": column.prompt.query,
            }
            for column in data.columns
        ],
    }

    entity_types = [column["entity_type"] for column in prepared_data["columns"]]

    prompt = SCHEMA_PROMPT.substitute(
        documents=', '.join(prepared_data['documents']),
        columns=json.dumps(prepared_data['columns'], indent=2),
        entity_types=', '.join(entity_types),
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_model=SchemaResponseModel,
            messages=[{"role": "user", "content": prompt}],
        )
        return {"schema": response.model_dump()}
    except Exception as e:
        logger.error(f"Error generating schema: {e}")
        return {"schema": {"relationships": []}}

def _get_str_rule_line(str_rule: Rule | None, query: str) -> str:
    if str_rule:
        if str_rule.type == "must_return" and str_rule.options:
            options_str = ", ".join(f'"{option}"' for option in str_rule.options)
            return f'You should only consider these possible values when answering the question: {options_str}. If these values do not exist in the raw text chunks, or if they do not correctly answer the question, respond with "not found".'
        elif str_rule.type == "may_return" and str_rule.options:
            options_str = ", ".join(str_rule.options)
            return f'For example: Query: {query} Response: {options_str}, etc... If you cannot find a related, correct answer in the raw text chunks, respond with "not found".'
    return ""

def _get_int_rule_line(int_rule: Rule | None) -> str:
    if int_rule and int_rule.length is not None:
        return f"Your answer should only return up to {int_rule.length} items. If you have to choose between multiple, return those that answer the question the best."
