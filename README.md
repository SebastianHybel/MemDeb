# MemDeb README

MemDeb is a LLM agent architecture built on the AutoGen framework (https://github.com/microsoft/autogen). MemDeb is an innovative platform designed to utilize the capabilities of LLMs for predictive analysis in financial markets. This project harnesses the power of artificial intelligence to provide insightful, data-driven forecasts and trading signals based on an extensive array of financial data sources. 

## Project Overview

The MemDeb project integrates various LLM agent, each tailored to specialize in different aspects of financial data analysis. These agents collaborate in a democratic decision-making system where trading signals are determined based on a majority vote from specialized agents. Each agent processes its own unique dataset, including historical prices, financial metrics, news sentiment, and more, to generate informed predictions about stock movements.

## Key features

**Modular Agent Design**: The architecture features multiple specialized agents such as MDfinAnalyst, MDnewsAnalyst, MDtserAnalyst, and others, each focusing on a specific type of financial data.

**Democratic Decision Making**: Combines outputs from all agents to reach a decision through a voting mechanism, enhancing the robustness and accuracy of predictions.

**Daily Data Snapshots**: Each agent receives a daily updated snapshot of the financial landscape, ensuring that all decisions are based on the most current information available.

**Structured Data Integration**: Agents are fed data through structured CSV files and SQL databases, maintaining a consistent and organized data flow.

## Installation

To set up the MemDeb project on your local environment, follow these steps:

1. Clone the repository:

`git clone https://github.com/your-repo/memdeb.git`

2. Setup .env configuration for both AutoGen, the Postgres database and the API callings

3. Initialize the SQL database with `postgresSetup.py`

4. Initalize the folder structure and import data with `initMemory.py`

5. Run `MDinit.py` to get outputs from each agent, stored in the mddebate table within our SQL db, and 1 final output, derived from the majority of the agent's output for that stock that day.

6. The chatlog will be stored in the Chat History folder, use `displayHistory.py` to clean the text output unto a readable report.
