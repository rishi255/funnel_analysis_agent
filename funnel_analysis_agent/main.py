from langchain import hub
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from sqlalchemy.dialects import registry
from typing_extensions import Annotated, TypedDict
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

registry.register("pinot", "pinotdb.sqlalchemy", "PinotDialect")


db = SQLDatabase.from_uri(
    "pinot+https://K8q36Z0d9lLQXFIM:uIFdTZBdNJiw8cV3V2kczKBVt7cHlSvg@broker.pinot.celpxu.cp.s7e.startree.cloud/query/sql?controller=https%3A%2F%2Fpinot.celpxu.cp.s7e.startree.cloud&verify_ssl=true&database=ws_2opqcdizwoh9"
)
# print(db.dialect)
# print(db.get_usable_table_names())
# db.run("SELECT * FROM Users LIMIT 10;")

llm = ChatOllama(model="llama3.1:8b", temperature=0)

toolkit = SQLDatabaseToolkit(db=db, llm=llm)
# print(toolkit.get_tools())

# Pull prompt
prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")

system_message = (
    prompt_template.format(dialect="MYSQL_ANSI dialect", top_k=5)
    + """\n
NOTE: Here is some extra info that you need to keep in mind:
1. The queries you generate should be in accordance with the Calcite SQL parser and use the MySQL ANSI Dialect, as they are going to run on Apache Pinot.
2. You are required to answer questions in the context of Clickstream analysis, i.e. the purpose of the questions is to answer questions such as the following:
    - What is the overall funnel conversion rate?
    - What is the biggest drop-off in the funnel?
    - Who are the top 3 users in terms of time spent? 
        - What other products can we recommend to these users?
    - What are the top 5 electronic items sold?  
3. Description of tables:
    a. "clickstream_info" - this contains transactional info about user events (view, click, save, purchase), when they were performed and the duration. The timestamp is stored as milliseconds from epoch.
    b. "purchase_info" - this contains transactional info about purchases performed by users (buyers).
    c. "NewProducts" - this is the Products dimensional table - contains info about the items and their descriptions.
    d. "Users" - this is the Users dimensional table.
4. Pinot does not support JOINs, so you are not allowed to use joins in the returned queries. Make use of lookups instead to get dimensional info.
    - This is how the lookup function would look like:
        lookUp('dimTableName', 'dimColToLookUp', 'dimJoinKey1', factJoinKeyVal1, 'dimJoinKey2', factJoinKeyVal2 ... )
        Where:
        - dimTableName - Name of the dimension table to perform the lookup on.
        - dimColToLookUp - The column name of the dimension table to be retrieved to decorate our result.
        - dimJoinKey - The column name on which we want to perform the lookup, i.e., the join column name for the dimension table.
        - factJoinKeyVal - The value of the dimension table join column will retrieve the dimColToLookUp for the scope and invocation.
    - The return type of the function will be that of the dimColToLookUp column type. There can also be multiple primary keys and corresponding values.
5. Something that could come in handy for Funnel analysis is Pinot's FUNNELCOUNT function, some info below:
    - It is a Funnel analytics aggregation function.
    - Returns array of distinct correlated counts for each funnel step.
    - Signature: FUNNEL_COUNT ( STEPS ( predicate1, predicate2 ... ), CORRELATE_BY ( correlation_column ), SETTINGS ( setting1, setting2 ... ) )
    - One example:

        We want to analyse the following checkout funnel:
            /cart/add
            /checkout/start
            /checkout/confirmation

        Counts:

        Let's say we want to answer the following questions about the above funnel:
            - How many users entered the top of the funnel?
            - How many of these users proceeded to the second step?
            - How many users reached the bottom of the funnel after completing all steps?

        Query that can answer the above questions:

        select 
        FUNNEL_COUNT(
            STEPS(
            url = '/cart/add', 
            url = '/checkout/start', 
            url = '/checkout/confirmation'),
            CORRELATE_BY(user_id)
        ) AS counts
        from user_log 
    - Note that the "url" column was just part of the above example. In our case it should be replaced by "event_type" as that is the name of the funnel events column. Also, the values should look exa
ctly how they appear in the event_type column.
"""
)
print(system_message)


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

    for event in events:
        print(type(event["messages"][-1].content))

        # Display the agent's response
        agent_message = Text(event["messages"][-1].content, style="bold green")
        console.print(Text("Agent:", style="bold green"), end=" ")
        console.print(agent_message)

        # event["messages"][-1].pretty_print()
