finetuned_prompt = """\n
NOTE: Here is some extra info that you need to keep in mind:
1. The queries you generate should be in accordance with the Calcite SQL parser and use the MySQL ANSI Dialect, as they are going to run on Apache Pinot.
2. Always try to use the tools available to you:
    - `sql_db_list_tables` -  to get all the table names.
    - `sql_db_schema` - to get the column schema for all tables in the list of tables.
    - `sql_db_query_checker` -  to double check your generated query before executing it.
    - `sql_db_query` - to finally execute the query and return the result.
3. Description of tables:
    a. "clickstream_events" - this contains transactional info about user events (view, click, save, purchase), when they were performed and the duration. The timestamp is stored as milliseconds from epoch.
    b. "purchase_info" - this contains transactional info about purchases performed by users (buyers).
    c. "NewProducts" - this is the Products dimensional table - contains info about the items and their descriptions.
    d. "Users" - this is the Users dimensional table.
4. Your SQL query responses are required to answer questions in the context of Clickstream analysis, i.e. the purpose of the questions is to answer questions such as the following
    - Q. What is the overall funnel conversion rate?
        - This means how many people have completed the funnel. "Overall" signifies that the entry point could be anywhere, but the count of users that completed the final action (i.e. purchase) should be considered.
    - Q. What is the biggest drop-off in the funnel?
        - This means at which step did the most number of users drop off. 
        - For example, say:
                - 7 users entered the funnel (i.e. viewed the product).
                - Out of the 7, only 4 clicked on the product.
                - From these 4, only 2 saved the product.
                - From these 2, only 1 purchased the product.
            - Here the biggest drop-off would be 3, and it occurs after event_type = view.
    - Q. Who are the top 3 users in terms of time spent? 
        - This means that which users (i.e. return the Names of the users) spent the most amount of time across all event types (view, click, save, purchase).
    - Q. What other products can we recommend to these top users?
        - This means that which products are similar to the products that the top users have spent the most amount of time on.
        - For example, say users 1, 2 and 3 are the top 3 users.
            - Get the sum of durations grouped by product for user1, and get the top result - top 1 product that this user currently has spent time on.
            - Get the embeddings of this top product. This would look like a list [0.001, 0.002, 0.003 ...] (384 dimensions)
            - Then, do a vector similarity search using the embeddings column to get 3 similar products (i.e. with similar descriptions).
            - Example Query:
                SELECT Name, Description,
                    cosine_distance(embedding, ARRAY[0.001, 0.002, 0.003 ...]) AS cosine
                    from NewProducts
                    where 
                    VECTOR_SIMILARITY(embedding, ARRAY[0.001, 0.002, 0.003 ...], 3)
                order by cosine asc
                    limit 3;
            - Make sure to replace the values in "ARRAY[0.001, 0.002, 0.003 ...]" with the actual embeddings for the top product to get similar products for it.
            - Repeat for the other 2 top users.
    - Q. What are the top 5 electronic items sold?
6. DO NOT use joins and subqueries in the generated SQL queries as they are not supported. Instead, use Pinot's lookup function to get dimensional info.
    - This is how the lookup function would look like:
        LOOKUP('ws_2opqcdizwoh9.dimTableName', 'dimColToLookUp', 'dimJoinKey1', factJoinKeyVal1, 'dimJoinKey2', factJoinKeyVal2 ... )
        Where:
        - dimTableName - Name of the dimension table to perform the lookup on.
        - dimColToLookUp - The column name of the dimension table to be retrieved to decorate our result.
        - dimJoinKey - The column name on which we want to perform the lookup, i.e., the join column name for the dimension table.
        - factJoinKeyVal - The value of the dimension table join column will retrieve the dimColToLookUp for the scope and invocation.
    - The return type of the function will be that of the dimColToLookUp column type. There can also be multiple primary keys and corresponding values.
    - Also note the inclusion of "ws_2opqcdizwoh9." before the dimTableName. This is the database name and is mandatory for Pinot to be able to find the dimension table. Without it you will get a QueryExecutionError.
    - Example query with lookups for both dimension tables and also filtering on a lookup column:
        SELECT 
            duration, event_timestamp, event_type, 
            product_id, lookup('ws_2opqcdizwoh9.NewProducts','Name','ID', product_id) as product_name, 
            user_id, lookup('ws_2opqcdizwoh9.Users','Name','ID', user_id) as user_name 
        FROM clickstream_events
        WHERE lookup('ws_2opqcdizwoh9.Users','Name','ID', user_id) = 'Brett Castillo';
7. If you get an error like "Unsupported function: lookup", that could be because you cannot combine lookup function usage with GROUP BY statements currently. In this case do not use the lookup, just use group by normally with the fact columns, no need to provide the lookup columns.
8. Do not use column aliases in the WHERE, ORDER BY or GROUP BY clauses, as it will give cryptic errors. Always use the actual column mapping.
9. Do not lie, hallucinate or assume column or table names which are not present in the schema. Only return a response if the query worked.
10. Always prefer to use Pinot's Funnel analysis functions, such as FUNNEL_COUNT whenever the question asks how many users reached a certain step in the funnel, or similar questions.
    1. FUNNEL_COUNT:
        - It is a Funnel analytics aggregation function.
        - Syntax: FUNNEL_COUNT ( STEPS ( predicate1, predicate2 ... ), CORRELATE_BY ( correlation_column ), SETTINGS ( setting1, setting2 ... ) )
        - Returns: array of distinct correlated counts for each funnel step.
        - One example:
            Say we want to analyse the following checkout funnel:
                /cart/add
                /checkout/start
                /checkout/confirmation
                
            Count:
            
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
        - Note that the "url" column was just part of the above example. In our case it should be replaced by "event_type" as that is the name of the funnel events column. Also, the values should look exactly how they appear in the event_type column.
"""

extra_vector_similarity_prompt = """
    - Q. What other products can we recommend to these top users?
        - This means that which products are similar to the products that the top users have spent the most amount of time on.
        - For example, say users 1, 2 and 3 are the top 3 users.
            - Get the sum of durations grouped by product for user1, and get the top result - top 1 product that this user currently has spent time on.
            - Then, do a vector similarity search using the embeddings column to get similar products (i.e. with similar descriptions).
            - Example Query:
                WITH top_product_embedding as (select embedding from ...)
                SELECT Name, Description,
                    cosine_distance(embedding, top_product_embedding) AS cosine
                    from NewProducts
                    where 
                    VECTOR_SIMILARITY(embedding, top_product_embedding, 3)
                order by cosine asc
                    limit 3;
"""

extra_pinot_functions_prompt = """

    2. FunnelCompleteCount
        - The FunnelCompleteCount function in Pinot is designed to track user progress through a predefined series of steps or stages in a funnel, such as user interactions on a website from page views to purchases. This function is particularly useful for analyzing how many times users progress through the whole conversion processes within a specified time window.
        - Syntax:
            FunnelCompleteCount(
                timestampExpression, 
                windowSize, 
                numberSteps, stepExpression
                [, stepExpression[, stepExpression, ...]]
                [, mode [, mode, ... ]]
            )
        - Returns:
            This function returns how many times the funnel has been went through.
        - Arguments:
            timestampExpression:
                Type: Expression in TIMESTAMP or LONG
                Description: This is an expression that evaluates to the timestamp of each event. It's used to determine the order of events for a particular user or session. The timestamp is crucial for evaluating whether subsequent actions fall within the specified window.
            windowSize:
                Type: LONG
                Description: Specifies the size of the time window in which the sequence of funnel steps must occur. The window is defined in milliseconds. This parameter sets the maximum allowed time between the first and the last step in the funnel for them to be considered as part of the same user journey.
            numberSteps:
                Type: Integer
                Description: Defines the total number of distinct steps in the funnel. This count should match the number of stepExpression parameters provided.
            stepExpression:
                Type: Boolean Expression
                Description: These are expressions that define each step in the funnel. Typically, these are conditions that evaluate whether a specific event type or action has occurred. Multiple step expressions are separated by commas, with each expression corresponding to a step in the funnel sequence.
            mode (optional):
                Type: String
                Description: Defines additional modes or options that alter how the funnel analysis is calculated. Common modes might include settings to handle overlapping events, reset the window upon each step, or other custom behaviors specific to the needs of the funnel analysis. If unspecified, the default behavior as defined by Pinot is used.

    3. FunnelMaxStep
         - The FunnelMaxStep function in Pinot is designed to track user progress through a predefined series of steps or stages in a funnel, such as user interactions on a website from page views to purchases. This function is particularly useful for analyzing how far users progress through a conversion process within a specified time window.
        - Syntax:
            FunnelMaxStep(
                timestampExpression, 
                windowSize, 
                numberSteps, stepExpression
                [, stepExpression[, stepExpression, ...]]
                [, mode [, mode, ... ]]
            )
        - Returns: This function returns the Integer value of the max steps that window funnel could proceed forward.
        - Arguments:
            timestampExpression:
                Type: Expression in TIMESTAMP or LONG
                Description: This is an expression that evaluates to the timestamp of each event. It's used to determine the order of events for a particular user or session. The timestamp is crucial for evaluating whether subsequent actions fall within the specified window.
            windowSize:
                Type: LONG
                Description: Specifies the size of the time window in which the sequence of funnel steps must occur. The window is defined in milliseconds. This parameter sets the maximum allowed time between the first and the last step in the funnel for them to be considered as part of the same user journey.
            numberSteps
                Type: Integer
                Description: Defines the total number of distinct steps in the funnel. This count should match the number of stepExpression parameters provided.
            stepExpression
                Type: Boolean Expression
                Description: These are expressions that define each step in the funnel. Typically, these are conditions that evaluate whether a specific event type or action has occurred. Multiple step expressions are separated by commas, with each expression corresponding to a step in the funnel sequence.
            mode (optional):
                Type: String
                Description: Defines additional modes or options that alter how the funnel analysis is calculated. Common modes might include settings to handle overlapping events, reset the window upon each step, or other custom behaviors specific to the needs of the funnel analysis. If unspecified, the default behavior as defined by Pinot is used.

    4. FunnelMatchStep
        - The FunnelMatchStep function in Pinot is designed to track user progress through a predefined series of steps or stages in a funnel, such as user interactions on a website from page views to purchases. This function is particularly useful for analyzing how far users progress through a conversion process within a specified time window.
        - Syntax:
            FunnelMatchStep(
                timestampExpression, 
                windowSize, 
                numberSteps, stepExpression
                [, stepExpression[, stepExpression, ...]]
                [, mode [, mode, ... ]]
            )
        - Returns:
            This function is similar to the function FunnelMaxStep, instead of returning the number of max step, it returns an array of the size 'number of steps', and marked the matched steps as 1, non-matching as 0. 
            Example:
                numberSteps = 3, maxStep = 0 -> [0, 0, 0]
                numberSteps = 4, maxStep = 2 -> [1, 1, 0, 0]
        - Arguments:
            timestampExpression:
                Type: Expression in TIMESTAMP or LONG
                Description: This is an expression that evaluates to the timestamp of each event. It's used to determine the order of events for a particular user or session. The timestamp is crucial for evaluating whether subsequent actions fall within the specified window.
            windowSize:
                Type: LONG
                Description: Specifies the size of the time window in which the sequence of funnel steps must occur. The window is defined in milliseconds. This parameter sets the maximum allowed time between the first and the last step in the funnel for them to be considered as part of the same user journey.
            numberSteps:
                Type: Integer
                Description: Defines the total number of distinct steps in the funnel. This count should match the number of stepExpression parameters provided.
            stepExpression:
                Type: Boolean Expression
                Description: These are expressions that define each step in the funnel. Typically, these are conditions that evaluate whether a specific event type or action has occurred. Multiple step expressions are separated by commas, with each expression corresponding to a step in the funnel sequence.
            mode (optional):
                Type: String
                Description: Defines additional modes or options that alter how the funnel analysis is calculated. Common modes might include settings to handle overlapping events, reset the window upon each step, or other custom behaviors specific to the needs of the funnel analysis. If unspecified, the default behavior as defined by Pinot is used."""
