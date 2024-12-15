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
from rich import markdown
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from sqlalchemy.dialects import registry
from dotenv import load_dotenv
import os

load_dotenv(".env")
registry.register("pinot", "pinotdb.sqlalchemy", "PinotDialect")
PinotDialect.supports_statement_cache = False
PinotHTTPSDialect.supports_statement_cache = False

db = SQLDatabase.from_uri(
    "pinot+https://K8q36Z0d9lLQXFIM:uIFdTZBdNJiw8cV3V2kczKBVt7cHlSvg@broker.pinot.celpxu.cp.s7e.startree.cloud/query/sql?controller=https%3A%2F%2Fpinot.celpxu.cp.s7e.startree.cloud&verify_ssl=true&database=ws_2opqcdizwoh9"
)
# print(db.dialect)
# print(db.get_usable_table_names())
# db.run("SELECT * FROM Users LIMIT 10;")

# llm = ChatOllama(model="llama3.1:8b", temperature=0.1)

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

# Query agent

while True:
    try:
        # Prompt the user for input with a styled prompt
        user_input = console.input("[bold blue]You:[/bold blue] ")
        # Check if the user wants to exit the chat
        if user_input.lower() in ["/exit", "/quit"]:
            console.print("Exiting chat...")
            break
    except KeyboardInterrupt:
        break  # only catch the exception if Ctrl+C is pressed during input time.

    events = agent_executor.stream(
        {"messages": [("user", user_input)]},
        stream_mode="values",
    )

    # events = track(
    #     agent_executor.invoke(
    #         {"messages": [("user", user_input)]},
    #         stream_mode="values",
    #     )
    # )
    # for event in events:
    #     # if event["messages"][-1].type != "human":
    #     event["messages"][-1].pretty_print()

    for event in events:
        last_message = event["messages"][-1]
        last_message: BaseMessage

        to_print = last_message.pretty_repr()

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
                to_print = markdown.Markdown(
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
            if last_message.name == "sql_db_schema":
                continue
            elif last_message.name == "sql_db_query":
                to_print = Text(f"Query Result:\n{last_message.content}")
                continue
        else:
            print("Unknown Message Type, just printing out as it is.")

        # Display the agent's response
        console.print(Text(f"Agent: {to_print}", style="bold green"))
