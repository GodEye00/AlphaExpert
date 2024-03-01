from typing import Any

from ..registry import ability


@ability(
    name="execute_query_code",
    description="Has the code having the query and how the query' response is to be handled",
    parameters=[
        {
            "name": "code",
            "description": "code with query to be run",
            "type": "string",
            "required": True,
        }
    ],
    output_type="Any",
)
async def list_files(agent, task_id: str, code: str) -> Any:
    """
    Execute sequel alchemy code and return response
    """
    return agent.workspace.list(task_id=task_id, code=code)