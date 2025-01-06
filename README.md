# funnel_analysis_agent

## About

Funnel Analysis Agent that converts natural language prompts to SQL queries and provides insights on data coming from StarTree cloud (Apache Pinot). 

Created as part of my submission for [StarTree's Mission: Impossible Data Reckoning Challenge](https://startree.ai/startree-mission-impossible).

It is fine-tuned to perform clickstream analysis, to answer key business questions such as:

  - What is the overall funnel conversion rate? (e.g., how many users viewed a product, clicked on it, saved it, and eventually purchased it)
  - What is the biggest drop-off in the funnel? (e.g., identifying the step where most users abandoned the purchase)
  - Who are the top 3 users in terms of time spent?
  - What other products can we recommend to these top users?
