# Local imports
from finetuned_prompt import finetuned_prompt
from langchain import hub
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

# from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pinotdb.sqlalchemy import PinotDialect, PinotHTTPDialect, PinotHTTPSDialect
from rich.markdown import Markdown
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from sqlalchemy.dialects import registry
from dotenv import load_dotenv
import os

# Initialize Agent and Prompt

load_dotenv(".env")
registry.register("pinot", "pinotdb.sqlalchemy", "PinotDialect")
PinotDialect.supports_statement_cache = False
PinotHTTPSDialect.supports_statement_cache = False

db = SQLDatabase.from_uri(os.environ["PINOT_SQLALCHEMY_URI"])

llm = ChatOpenAI(
    api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o-mini", temperature=0
)

toolkit = SQLDatabaseToolkit(db=db, llm=llm)
# print(toolkit.get_tools())

# Pull prompt
prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")

system_message = (
    prompt_template.format(dialect="Apache Pinot MYSQL_ANSI dialect", top_k=3)
    + finetuned_prompt
)
# print(system_message)


# Initialize a Rich Console for pretty console outputs
console = Console()

# print prompt
console.print(
    Panel(
        system_message,
        width=console.width,
        style="bold cyan",
    ),
    style="bold cyan",
)

# Create agent
agent_executor = create_react_agent(
    llm, toolkit.get_tools(), state_modifier=system_message
)


# Ask Questions to the Agent


def print_results(events):
    # stream output
    for event in events:
        last_message = event["messages"][-1]
        last_message: BaseMessage

        if last_message.type == "human":
            last_message: HumanMessage
            continue

        elif last_message.type == "ai":
            last_message: AIMessage
            if (
                last_message.tool_calls
                and last_message.tool_calls[-1]["name"] == "sql_db_query"
            ):
                query = last_message.tool_calls[-1]["args"]["query"]
                to_print = Markdown(
                    f"""Generated Query:

```sql
{query}
```""",
                    inline_code_lexer="sql",
                )
                # Display the generated SQL query
                console.print(to_print, markup=True, highlight=True)
                continue

        elif last_message.type == "tool":
            last_message: ToolMessage
            if last_message.name in [
                "sql_db_schema",
                "sql_db_list_tables",
                "sql_db_query_checker",
            ]:
                continue
            elif last_message.name == "sql_db_query":
                to_print = Text(
                    f"Query Result:\n{last_message.content}", style="bold green"
                )
                # Display the SQL Query Result
                console.print(to_print)
                continue
        else:
            print("Unknown Message Type, just printing out as it is.")

        to_print = (
            Markdown(f"Agent: {last_message.content}")
            if last_message.content != ""
            else Text(last_message.pretty_repr(), style="bold green")
        )

        # Display the agent's response
        console.print(to_print, markup=True, highlight=True)


def invoke_model(user_input: str):
    print("You:", user_input)

    # invoke model
    events = agent_executor.stream(
        {"messages": [("user", user_input)]},
        stream_mode="values",
    )

    print_results(events)


input_prompts = [
    "What is the overall funnel conversion rate?",
    "What is the biggest drop-off in the funnel?",
    "Who are the top 3 users in terms of time spent?",
    "What other products can we recommend to these top users? For context, also show the names and descriptions of the top products of the users, and also of the recommended products.",
    "What are the top 5 electronic items sold?",
]

for i, user_input in enumerate(input_prompts, 1):
    print(f"Question #{i}:", user_input)
    result = invoke_model(user_input)
    print(result)
