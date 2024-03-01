"""Commands to retrieve matching passages of user input from elasticsearch"""

COMMAND_CATEGORY = "content_retrieval_operations"
COMMAND_CATEGORY_TITLE = "Content Retrieval Operations"

from elasticsearch import Elasticsearch
import pandas as pd
import os
import logging
import openai

from pathlib import Path

from git.repo import Repo

from autogpt.agents.agent import Agent
from autogpt.agents.utils.exceptions import CommandExecutionError
from autogpt.command_decorator import command
from autogpt.core.utils.json_schema import JSONSchema
from autogpt.url_utils.validators import validate_url


@command(
    "retrieve_from_elasticsearch",
    "Used for retrieving items from elasticsearch",
    {
        "user_input": JSONSchema(
            type=JSONSchema.Type.STRING,
            description="The input from user which is supposed to be matched and retrieved from elasticsearch",
            required=True,
        ),
        "size": JSONSchema(
            type=JSONSchema.Type.NUMBER,
            description="The of information to retrieve from elasticsearch. The greater the number, the more the information. Default is 3",
            required=False,
        ),
    },
    lambda config: bool(config.elasticsearch_cloud_id and config.elasticsearch_api_key),
    "Configure elasticsearch_cloud_id and elasticsearch_api_key.",
)
def retrieve_from_elasticsearch(user_input: str, agent: Agent, size: int=3 ) -> str:
    """Retrieves matching entities, intents and sentiments of user's query.

    Args:
        user_input (str): The input from the user's that is supposed to be used to retrieve the matching entities
        size (int): The size of the information extracted from elasticsearch.

    Returns:
        str: The result of the retrieval
    """


    # Connecting to Elasticsearch
    es = Elasticsearch(
        cloud_id=agent.legacy_config.elasticsearch_cloud_id,
        api_key=os.environ.agent.legacy_config.elasticsearch_api_key,
        request_timeout=30,
    )

    def get_embedding(text, model=agent.legacy_config.embedding_model):
        text = text.replace("\n", " ")
        return openai.embeddings.create(input = [text], model=model).data[0].embedding

    logging.info(f"About to retrieve passages for queries: {user_input}")
    results = []
    try:

        # Generating the embeddings for every query in the user_queries
        query_embedding = get_embedding(user_input)

        # Searching elasticsearch for the matched passages
        body = {
            "query": {
                "script_score": {
                    "query": {"match_all": {}},
                    "script": {
                        "source": "cosineSimilarity(params.queryVector, 'Embedding') + 1.0",
                        "params": {"queryVector": query_embedding}
                    }
                }
            }
        }
        response = es.search(index=agent.legacy_config.elasticsearch_index, body=body)

        # Getting the needed passages and metadata from the search response
        needed_passages = []
        for hit in response['hits']['hits']:
            passage = hit['_source']['Passage']
            score = hit['_score']
            needed_passages.append((passage, score))

        # sorting the needed passages by their score
        needed_passages.sort(key=lambda x: x[1], reverse=True)

        # extracting the top {size} passages
        top_passages = needed_passages[:size]

        # current_app.logger.info("Passages are: ",needed_passages)

        # extracting the necessary information for csv output
        passage_texts, score = zip(*top_passages)
        passage_texts = list(passage_texts)
        score = list(score)

        results = ""
        chunks = []
        for i, passage in enumerate(passage_texts):
            chunks.append({
                "Question": user_input,
                "Passage 1": passage_texts[i],
                "Relevance Score 1": score[i]
            })
            results += f" Passage {i+1}: "+ passage_texts[i]+ f" Passage {i+1} Score: "+str(score[i])+"."

        return chunks, results
    except Exception as e:
        logging.exception(f"An error occurred while retrieving passages from elasticsearch. Error: {e}")
        raise Exception


@command(
    "retrieve_relationships",
    "Used for retrieving the relationships that exists between the various entities obtained from elasticsearch",
    {
        "user_input": JSONSchema(
            type=JSONSchema.Type.STRING,
            description="The input from user which is supposed to be matched and retrieved from elasticsearch",
            required=True,
        ),
        "size": JSONSchema(
            type=JSONSchema.Type.NUMBER,
            description="The of information to retrieve from elasticsearch. The greater the number, the more the information. Default is 3",
            required=False,
        ),
    },
    lambda config: bool(config.elasticsearch_cloud_id and config.elasticsearch_api_key),
    "Configure elasticsearch_cloud_id and elasticsearch_api_key.",
)
def retrieve_relationships(user_input: str, agent: Agent, size: int=3 ) -> str:
    """Retrieves matching entities, intents and sentiments of user's query.

    Args:
        user_input (str): The input from the user's that is supposed to be used to retrieve the matching entities
        size (int): The size of the information extracted from elasticsearch.

    Returns:
        str: The result of the retrieval
    """
