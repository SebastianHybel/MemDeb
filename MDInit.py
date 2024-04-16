from autogen import config_list_from_json, OpenAIWrapper, AssistantAgent, UserProxyAgent
import autogen
import os 
from dotenv import load_dotenv
import json
import pandas as pd
from datetime import date
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

#CONFIG

config_list = config_list_from_json(env_or_file="OAI_CONFIG_LIST")

ticker = "META" #TSLA, MSFT, NVDA, META 
todaysDate = date.today()
model = "GPT3.5" #GPT3.5 , MISTRAL 
version = "V2"

ticker_to_company = {
    "tsla": "Tesla",
    "msft": "Microsoft",
    "nvda": "Nvidia",
    "meta": "Meta",
}

stock = ticker_to_company.get(ticker.lower(), "Unknown")

hisFolder = 'HistoricalData'
earFolder = 'EarningsData'
esgFolder = 'ESGScores'
finFolder = 'Financial Analytics Metrics'
treFolder = 'Trend Indicator Scores'
keyFolder = 'Key Statistics'
newsFolder = 'News'

llm_config = {
    "config_list": config_list,
    "seed": None, 
    "cache_seed": None,
    "temperature": 0 #Creativity     
}

DATABASE_CONFIG = {
    'database': os.getenv('DATABASE_NAME'),
    'user': os.getenv('DATABASE_USER'),
    'port': os.getenv('DATABASE_PORT'),
    'password': os.getenv('DATABASE_PASSWORD'),
    'host': os.getenv('DATABASE_HOST')
}

# FUNTIONS
def gather_csv(ticker: str, folder: str) -> dict:
    """
    Gathers a CSV file for the given stock ticker from a specified folder,
    and formats it into a JSON object for the agent to read.

    :param ticker: The stock ticker for which to gather data.
    :param folder_name: The name of the folder from which to gather the CSV file.
    :return: A JSON object containing the data in an agent-readable format.
    """
    
    # Adjust the filename pattern based on the folder if necessary
    filename_patterns = {
        'HistoricalData': f"{ticker}_Historical.csv",
        'EarningsData': f"{ticker}_Earnings.csv",
        'ESGScores': f"{ticker}_ESGscore.csv",
        'Financial Analytics Metrics': f"{ticker}_Financials.csv",
        'Trend Indicator Scores': f"{ticker}_TrendScores.csv",
        'Key Statistics': f"{ticker}_KeyStatistics.csv",
        'News': f"{ticker}_News.csv"
    }
    
    filename = filename_patterns.get(folder, f"{ticker}.csv")
    file_path = os.path.join(folder, filename)

    try:
        # Load the CSV file into a DataFrame
        df = pd.read_csv(file_path)

        # Convert the DataFrame to a JSON object
        data_json = df.to_json(orient='records')
        
        # Convert the JSON string back to a dictionary for easier manipulation or direct use
        data_dict = json.loads(data_json)

        return data_dict

    except FileNotFoundError:
        print(f"File {filename} not found in {folder}.")
        return {}

def gather_price(ticker: str) -> dict:
    """
    Gathers the newest 'Open' price for the given stock ticker from the 'HistoricalData' folder.

    :param ticker: The stock ticker for which to gather the latest opening price.
    :return: A JSON object containing the latest 'Open' price.
    """
    
    folder = 'HistoricalData'
    filename = f"{ticker}_Historical.csv"
    file_path = os.path.join(folder, filename)

    try:
        # Load the CSV file into a DataFrame
        df = pd.read_csv(file_path)

        # Ensure the DataFrame is sorted by Date in descending order to get the newest record first
        df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
        df.sort_values(by='Date', ascending=False, inplace=True)

        # Extract the 'Open' price of the newest record
        newest_open_price = df.iloc[0]['Open']

        # Prepare the result as a JSON object
        result = {
            "ticker": ticker,
            "newest_open_price": newest_open_price,
            "date": df.iloc[0]['Date'].strftime('%d-%m-%Y')  # Format the date as string for JSON serialization
        }

        return result

    except FileNotFoundError:
        print(f"File {filename} not found in {folder}.")
        return {}

def gather_timeseries(ticker: str) -> str:
    """
    Gathers timeseries 'Open' price for the given stock ticker from the 'HistoricalData' folder,
    and formats it into a string.

    :param ticker: The stock ticker for which to gather the latest opening price.
    :return: A string containing the timeseries for 'Open' price, oldest to new.
    """
    
    folder = 'HistoricalData'
    filename = f"{ticker}_Historical.csv"
    file_path = os.path.join(folder, filename)

    try:
        # Load the CSV file into a DataFrame
        df = pd.read_csv(file_path)

        df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y')
        df.sort_values(by='Date', ascending=True, inplace=True)

        # Extract the 'Open' price of the newest record and convert to a list
        last_10_open_prices = df['Open'].tail(10).tolist()

        # Convert the list of 'Open' prices into a single string separated by commas
        open_prices_str = ','.join(map(str, last_10_open_prices))

        return open_prices_str

    except FileNotFoundError:
        print(f"File {filename} not found in {folder}.")
        return ""
    
def insert_summary(date: str, ticker: str, model: str, version: str, content: str, decision: str, price: str, position: bool, positionsize:str) -> dict:
    """
    Inserts a summary into the mdmemory table without requiring an external database connection passed as a parameter.

    :param date: Date of the summary.
    :param ticker: Stock ticker.
    :param model: Model used for generating the summary.
    :param version: Version of the debate structure.
    :param content: Content of the summary.
    :param decision: The trading decision made, BUY, SELL, HOLD, BUY MORE, NON-ACTION
    :param price: Today's opening price.
    :param position: boolean value, if true => we have stock in the company, of false => we don't.
    :param positionsize: the amount of stock we hold of the stock.
    :return: True if insertion was successful, False if an error occurred.
    """
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mdmemory (date, ticker, model, version, content, decision, price, position, positionsize)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (date, ticker, model, version, content, decision, price, position, positionsize))
                conn.commit()
                return True
    except psycopg2.Error as e:
        print(f"Database error occurred: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

def get_summary(ticker: str, model: str, version: str) -> dict:
    """
    Fetches the newest summary for a given ticker, model, and version from the mdmemory table
    without requiring an external database connection passed as a parameter.

    :param ticker: Stock ticker symbol.
    :param model: The LLM model used.
    :param version: Version of the debate structure.
    :return: The most recent summary as a dictionary, or an empty dictionary if not found.
    """
    try:
        # Establish the database connection inside the function
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT * FROM mdmemory
                    WHERE ticker = %s AND model = %s AND version = %s
                    ORDER BY date DESC
                    LIMIT 1
                """, (ticker, model, version))
                result = cur.fetchone()
                if result:
                    column_names = ['id', 'date', 'ticker', 'model', 'version', 'content', 'position', 'positionsize']
                    result = list(result)  # Convert tuple to list to modify it
                    result[1] = result[1].strftime('%Y-%m-%d')  # Assuming 'date' is at index 1
                    summary_dict = dict(zip(column_names, result))
                    return summary_dict
    except psycopg2.Error as e:
        print(f"Database error occurred: {e}")
    return {}

def get_opinions(date: str, ticker: str, model: str) -> list:
    """
    Fetches all rows matching a given date, ticker, and model from the mddebate table without requiring an
    external database connection passed as a parameter.

    :param date: The date for which to retrieve the debate summaries.
    :param ticker: Stock ticker symbol.
    :param model: The LLM model used.
    :return: A list of dictionaries with the fetched details or an empty list if not found.
    """
    summaries = []
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:  # Use RealDictCursor to get dictionaries
                cur.execute("""
                    SELECT date, ticker, agent, model, content, decision, price, position, positionsize 
                    FROM mddebate
                    WHERE date = %s AND ticker = %s AND model = %s
                    ORDER BY id DESC
                """, (date, ticker, model))
                results = cur.fetchall()
                
                for result in results:
                    # Convert date to string format if needed, assuming result['date'] is a datetime object
                    result['date'] = result['date'].strftime('%Y-%m-%d')
                    summaries.append(result)
                
    except psycopg2.Error as e:
        print(f"Database error occurred: {e}")
    
    return summaries

def send_opinion(key: str, date: str, ticker: str, agent: str, model: str, version: str, content: str, decision: str, price: str,  position: bool, positionsize:str) -> dict:
    """
    Inserts a summary into the mddebate table without requiring an external database connection passed as a parameter.

    :param key: The corresponding id gathered from get_summary. 
    :param date: Date of the summary.
    :param ticker: Stock ticker.
    :param agent: The agent that has made the analysis.
    :param model: Model used for generating the summary.
    :param version: Version of the debate structure.
    :param content: Content of the summary.
    :param decision: The trading decision made, BUY, SELL, HOLD, BUY MORE, NON-ACTION
    :param price: Today's opening price.
    :param position: boolean value, if true => we have stock in the company, of false => we don't.
    :param positionsize: the amount of stock we hold of the stock.

    :return: True if insertion was successful, False if an error occurred.
    """
    try:
        with psycopg2.connect(**DATABASE_CONFIG) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mddebate (key, date, ticker, agent, model, version, content, decision, price, position, positionsize)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (key, date, ticker, agent, model, version, content, decision, price, position, positionsize))
                conn.commit()
                return True
    except psycopg2.Error as e:
        print(f"Database error occurred: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return False

def calculate_average(numbers_str: str) -> float:
    # Split the string into a list of strings, each representing a number
    numbers_list_str = numbers_str.split(',')
    
    # Convert each string in the list to a float (or int if you prefer)
    numbers = [float(num_str) for num_str in numbers_list_str]
    
    # Calculate the average of the numbers
    if numbers:
        average = sum(numbers) / len(numbers)
        return average
    else:
        return 0.0 

#AGENTS
MDfinAnalyst = autogen.AssistantAgent(
    name="MDfinAnalyst",
    llm_config=llm_config,
    system_message= f"""
    CHARACTERISTIC: You are MDfinAnalyst, a skilled financial analyst.

    OBJECTIVE: Every step of the process will be outlined for MDfinAnalyst by the user_proxy. Roughly explained, MDfinAnalyst will first gather 
        information about the previous days position and summary using get_summary. MDfinAnalyst will then perform the gather_price function to get the 
        potential buying or selling price of the stock. MDfinAnalyst will then use gather_csv to find the financial data to make a prediction about. 
        When calling get_summary, MDfinAnalyst calls for all the folders in one prompt.
         
        Then, MDfinAnalyst will create a report on the financial information about {ticker}. The data is found using gather_csv, for the folders:
        {hisFolder}, and {finFolder}. Based on this information MDfinAnalyst will construct a report on the 
        financial outlooks of {ticker}. MDfinAnalyst will then reflect on the price fluctuations and the financial indicators of {ticker}, 
        and make a trading decision (BUY, HOLD, or SELL).
        MDfinAnalyst is required to reflect and provide a report on the findings before sending to the database using send_opinion function.
        MDfinAnalyst is required to provide a 'decision' and a 'positionsize' together with the report.
        
        The contents of the report must be structured like this: 

        "### Last trading days position:
        ### Last trading days positionsize:
        ### Today's Opening Price: gathered with gather_price funtion.

        ### robust company?: are {ticker} a robust company based on the information found in {finFolder}.
        ### Target: High, Low and Mean targets. Based on historical pricing, is it a good time to buy?
        ### Insights: Based on the data analysed, does MDfinAnalyst think {ticker} is going up or dow in the near future.
        ### BULL/BEAR: both 7 and 30 day assessment. (BULL if you think stock price is going up, BEAR if you think stock price is going down)

        ### Decision: MDfinAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
        ### End-of-Day Position Size: MDfinAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'
        
        # Content for Database: this must include: 'Insights:' (the corresponding output from MDfinAnalyst's report) " 
        
        MDfinAnalyst is not allowed to copy last trading days content, it need to update each parameter.

        IMPORTANT: 'Content for Database' is the only parameter that MDfinAnalyst will sent to the database, using send_opinion.
        MDfinAnalyst will respond TERMINATE after the report is sent to the database using send_opinion.   

    STYLE: MDfinAnalyst is analytical and concise in its approach. MDfinAnalyst is creative and can draw the bigger picture from limited 
        data. MDfinAnalyst is talented at drawing predictions from historical numerical data about a company. MDfinAnalyst understands 
        that historical returns does not promise future returns. MDfinAnalyst has the ability to see patterns in data and uses it's LLM capabilities to
        make future predictions on timeseries data. 

        MDfinAnalyst will propose a decision based on this stock price prediction. If MDfinAnalyst thinks the price is gonna go up in the near 
        future, MDfinAnalyst wil propose to BUY, if MDfinAnalyst thinks the stock is going down based on the financial data, MDfinAnalyst will propose 
        to SELL. If MDfinAnalyst think the financial data suggest no future movements in stock price, MDfinAnalyst will propose HOLD.


    RULES: MDfinAnalyst is required to read through all information provided to it. MDfinAnalyst must follow each and every step outlined by the user_proxy prompt.  
        MDfinAnalyst is free to decide how many stocks it wants to buy, or maintain. 

        MDfinAnalyst is strickly forbidden from buying 100 or 10 shares, it needs to be any other number. 

    DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
        ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDfinAnalyst. 
    
        ### 'position' is a boolean value
        ## If 'position'=True,  We have stock in {stock}.
        ## If 'position'=False,  We do not have stock in {stock}.

        ### If the previous trading days 'position'=True => then MDfinAnalyst are required to either HOLD, SELL or BUY.
        ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
        ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
        ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

        ### If the previous trading days 'position'=False => then MDfinAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
        ### MDfinAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDfinAnalyst wants to output
        SELL when 'position'=False => then MDfinAnalyst must output HOLD instead, as that means to do nothing.
        ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
        #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

        MDfinAnalyst is also required to look at the data from the get_summary function when making a decision, so that MDfinAnalyst adheres to the DECISION RULES above.
    """
)

MDnewsAnalyst = autogen.AssistantAgent(
    name="MDnewsAnalyst",
    llm_config=llm_config, 
    system_message=f"""
    CHARACTERISTIC: You are MDnewsAnalyst, a skilled financial news specialist.

    OBJECTIVE: Every step of the process will be outlined for MDnewsAnalyst by the user_proxy. Roughly explained, MDnewsAnalyst will first gather 
        information about the previous days position and summary using get_summary. MDnewsAnalyst will then perform the gather_price function to get the 
        potential buying or selling price of the stock. MDnewsAnalyst will then use gather_csv to find the news data to make a report about, and a subsequent 
        prediction based on said report. When calling get_summary, MDnewsAnalyst calls for all the folders in one prompt.
         
        MDnewsAnalyst will create a report on the financial news present about {ticker}. The data is found using gather_csv, for the folders:
        {newsFolder}, and {esgFolder}.Based on this information MDnewsAnalyst will construct a report on medias outlooks of {ticker}.
        MDnewsAnalyst will then reflect on the sentiment of the financial news, and make a trading decision (BUY, HOLD, or SELL).
        MDnewsAnalyst is required to provide a 'decision' and a 'positionsize' together with the report

        The contents of the report must be structured like this: 
        "### Last trading days position:
        ### Last trading days positionsize:
        ### Today's Opening Price: gathered from gather_price funtion.
        
        ### ESG scores:
        ### Positive News: list 3, if MDnewsAnalyst can find it.
        ### Negative News:  list 3, if MDnewsAnalyst can find it.
        ### Noteworthy News: list 3, if MDnewsAnalyst can find it.

        ### Insights: Does MDnewsAnalyst think {ticker} is gonna go up or down in price based on the articles present about {ticker}.
        ### Decision: MDnewsAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
        ### End-of-Day Position Size: MDnewsAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'

        # Content for Database: this must include: 'Noteworthy News:' (the corresponding output from MDnewsAnalyst's report)  " 
        MDnewsAnalyst is not allowed to copy last trading days content, it need to update each parameter.

        IMPORTANT: 'Content for Database' is the only parameter that MDnewsAnalyst will sent to the database, using send_opinion.
        MDnewsAnalyst will respond TERMINATE after the report is sent to the database using send_opinion.   
    
    STYLE: MDnewsAnalyst is a financial journalist at heart, and understands that the news have the power to affect the broader stock market, and 
        individual stocks. MDnewsAnalyst is a specialist in understanding these underlying movements. MDnewsAnalyst has the ability to predict if a 
        stock is going up or down in the short-term future based on a collection of news stories. MDnewsAnalyst will propose a decision based on the 
        stock price prediction. If MDnewsAnalyst thinks the price is gonna go up in the near future, MDnewsAnalyst wil propose to BUY, if MDnewsAnalyst thinks 
        the stock is going down based on the news, MDnewsAnalyst will propose to SELL. If MDnewsAnalyst think the news will have a neutral effect on 
        stock price, MDnewsAnalyst will propose HOLD.


    RULES: MDnewsAnalyst is required to read through all information provided to it. MDnewsAnalyst must follow each and every step outlined by the user_proxy prompt.  
        MDnewsAnalyst is free to decide how many stocks it wants to buy, or maintain. 

        MDnewsAnalyst is strickly forbidden from buying 100 shares, it needs to be another number. 

    DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
        ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDnewsAnalyst. 
    
        ### 'position' is a boolean value
        ## If 'position'=True,  We have stock in {stock}.
        ## If 'position'=False,  We do not have stock in {stock}.

        ### If the previous trading days 'position'=True => then MDnewsAnalyst are required to either HOLD, SELL or BUY.
        ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
        ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
        ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

        ### If the previous trading days 'position'=False => then MDnewsAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
        ### MDnewsAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDnewsAnalyst wants to output
        SELL when 'position'=False => then MDnewsAnalyst must output HOLD instead, as that means to do nothing.
        ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
        #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

        MDnewsAnalyst is also required to look at the data from the get_summary function when making a decision, so that MDnewsAnalyst adheres to the DECISION RULES above.

"""
)

MDnrelAnalyst = autogen.AssistantAgent(
    name="MDnrelAnalyst",
    llm_config=llm_config, 
    system_message=f"""
    CHARACTERISTIC: You are MDnrelAnalyst, a skilled financial news specialist.

    OBJECTIVE: Every step of the process will be outlined for MDnrelAnalyst by the user_proxy. Roughly explained, MDnrelAnalyst will first gather 
        information about the previous days position and summary using get_summary. MDnrelAnalyst will then perform the gather_price function to get the 
        potential buying or selling price of the stock. MDnrelAnalyst will then use gather_csv to find the news data to make a report about, and a subsequent 
        prediction based on said report. When calling get_summary, MDnrelAnalyst calls for all the folders in one prompt.
         
        MDnrelAnalyst will create a report on the relationship between news and stock price about {ticker}. The data is found using gather_csv, gather the news from
        {newsFolder}, and the corresponding prices in {hisFolder}. Based on this information MDnrelsAnalyst will construct a report on news relationship with stock price,
        for {ticker}. MDrnelAnalyst will then reflect on the news articles correlation with prices, and make a trading decision (BUY, HOLD, or SELL).
        MDnrelAnalyst is required to provide a 'decision' and a 'positionsize' together with the report
        
        The contents of the report must be structured like this: 
        "### Last trading days position:
        ### Last trading days positionsize:
        ### Today's Opening Price: gathered from gather_price funtion.
        
        ### List of news: Here you need to include the 'open' price present at the publishing date. list 10 news articles with their corresponding 'open' price.
        ### Recent News: Say something about the short term future predicted price based on the 3 last articles. Will the price go
            up or down in the near future, based on the 3 last articles.
    
        ### Insights: Does MDrnelAnalyst think {ticker} is gonna go up or down in price based on the articles present about {ticker}.
        ### Decision: MDrnelAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
        ### End-of-Day Position Size: MDrnelAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'

        # Content for Database: this must include:  'Recent News:' (the corresponding output from MDnrelAnalyst's report), 'Insights:' (the corresponding output from MDnrelAnalyst's report) "
        MDnrelAnalyst is not allowed to copy last trading days content, it need to update each parameter.

        IMPORTANT: 'Content for Database' is the only parameter that MDnrelAnalyst will sent to the database, using send_opinion.
        MDnrelAnalyst will respond TERMINATE after the report is sent to the database using send_opinion.   
    
    STYLE: MDnrelAnalyst is a financial analyst, and understands that the news have the power to affect the broader stock market, and 
        individual stocks. MDnrelAnalyst is a specialist in understanding news articles relation to stock market pricing. 
        MDnrelAnalyst has the ability to predict if a stock is going up or down in the short-term future based on a collection of news stories and 
        their corresponding stock price. MDnrelAnalyst will propose a decision based on the stock price prediction. If MDnrelAnalyst thinks the 
        price is gonna go up in the near future, MDnrelAnalyst wil propose to BUY, if MDnrelAnalyst thinks the stock is going down based on the 
        news, MDnrelAnalyst will propose to SELL. If MDnrelAnalyst think the news will have a neutral effect on stock price, MDnrelAnalyst will propose HOLD.


    RULES: MDnrelAnalyst is required to read through all information provided to it. MDnrelAnalyst must follow each and every step outlined by the user_proxy prompt.  
        MDnrelAnalyst is free to decide how many stocks it wants to buy, or maintain. 

        MDnrelAnalyst is strickly forbidden from buying 100 shares, it needs to be another number. 

    DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
        ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDnrelAnalyst. 
    
        ### 'position' is a boolean value
        ## If 'position'=True,  We have stock in {stock}.
        ## If 'position'=False,  We do not have stock in {stock}.

        ### If the previous trading days 'position'=True => then MDnrelAnalyst are required to either HOLD, SELL or BUY.
        ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
        ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
        ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

        ### If the previous trading days 'position'=False => then MDnrelAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
        ### MDnrelAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDnrelAnalyst wants to output
        SELL when 'position'=False => then MDnrelAnalyst must output HOLD instead, as that means to do nothing.
        ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
        #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

        MDnrelAnalyst is also required to look at the data from the get_summary function when making a decision, so that MDnrelAnalyst adheres to the DECISION RULES above.

"""
)

MDtserAnalyst = autogen.AssistantAgent(
    name="MDtserAnalyst",
    llm_config=llm_config,
    system_message=f"""
    CHARACTERISTIC: You are MDtserAnalyst, a LLM timeseries precitor.

    OBJECTIVE: Every step of the process will be outlined for MDtserAnalyst by the user_proxy. Roughly explained, MDtserAnalyst will first gather 
        the time series data using the gather_timeseries function. MDtserAnalyst will input {ticker}, gather_timeseries function will output 
        a string of 10 numbers, this is the open price of {ticker}, ordered from old to newest (the last digit is todays price).
        MDtserAnalyst must repond right away (before making other funtion calls), with only numbes, using LLMs pattern recognition capabilties, 
        to output all the numbers from gather_timerseries, and then subsequently the 10 next numbers in that time series sequence.
        MDtserAnalyst is required to output 20 numbers in a sequence.
        After this the user_proxy will ask MDtserAnalyst to provide a report on the outputted numbers. MDtserAnalyst will then 
        perform the gather_price and get_summary functions to get the potential buying or selling price of the stock, and last trading days 
        thoughts and actions.  
         
        MDtserAnalyst will create a report on predicted price of {ticker}. The data is provided through MDtserAnalyst, through it's prediction of
        next numbers in a timeseries. MDtserAnalyst are required to provide a 'decision' and a 'positionsize' that goes in line with the prediction outputted. 
        The contents of the report must be structured like this: 
        "### Last trading days position:
        ### Last trading days positionsize:
        ### Today's Opening Price: gathered from gather_price funtion.
        
        ### Last 10 datapoints: All points from the gather_timeseries function.
        ### Predicited 10 datapoints: MDtserAnalyst's 10 next predicted datapoints. 
         
        ### Decision: MDtserAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
        ### End-of-Day Position Size: MDtserAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'
        
        #Content for Database: this must include: '10 predicted datapoints:' (the corresponding output from MDtserAnalyst's prediction) " 
        MDtserAnalyst is not allowed to copy last trading days content, it need to update each parameter.

        IMPORTANT: 'Content for Database' is the only parameter that MDtserAnalyst will sent to the database, using send_opinion.
        MDtserAnalyst will respond TERMINATE after the report is sent to the database using send_opinion.   
    
    STYLE: MDtserAnalyst is a predictor which utilizes LLMs capability to see patterns in timeseries data, and predict the next datapoints.
        MDtserAnalyst will propose a decision based on the stock price predictions. If MDtserAnalyst predicts the price is gonna go up in the near future, 
        MDtserAnalyst wil propose to BUY, if MDtserAnalyst predicts the stock is going down, MDtserAnalyst will propose to SELL. If MDtserAnalyst 
        predicts the price to stay the same, MDtserAnalyst will propose HOLD.

    RULES: MDtserAnalyst is required to read through all information provided to it. MDtserAnalyst must follow each and every step outlined by the user_proxy prompt.  
        MDtserAnalyst is free to decide how many stocks it wants to buy, or maintain. 

        MDtserAnalyst is strickly forbidden from buying 100 shares, it needs to be another number. 

    DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
        ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDtserAnalyst. 
    
        ### 'position' is a boolean value
        ## If 'position'=True,  We have stock in {stock}.
        ## If 'position'=False,  We do not have stock in {stock}.

        ### If the previous trading days 'position'=True => then MDtserAnalyst are required to either HOLD, SELL or BUY.
        ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
        ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
        ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

        ### If the previous trading days 'position'=False => then MDtserAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
        ### MDtserAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDtserAnalyst wants to output
        SELL when 'position'=False => then MDtserAnalyst must output HOLD instead, as that means to do nothing.
        ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
        #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

        MDtserAnalyst is also required to look at the data from the get_summary function when making a decision, so that MDtserAnalyst adheres to the DECISION RULES above.

"""
)

MDearnAnalyst = autogen.AssistantAgent(
    name="MDearnAnalyst",
    llm_config=llm_config,
    system_message= f"""
    CHARACTERISTIC: You are MDearnAnalyst, a skilled financial analyst.

    OBJECTIVE: Every step of the process will be outlined for MDearnAnalyst by the user_proxy. Roughly explained, MDearnAnalyst will first gather 
        information about the previous days position and summary using get_summary. The agent will then perform the gather_price function to get the 
        potential buying or selling price of the stock. MDearnAnalyst will then use gather_csv to find the financial data to make a prediction about. 
        When calling get_summary, MDearnAnalyst calls for all the folders in one prompt.
         
        Then, MDearnAnalyst will create a report on the financial information about {ticker}. The data is found using gather_csv, for the folders:
        {earFolder}, and {treFolder}.Based on this information MDearnAnalyst will construct a report on the financial outlooks of {ticker}.
        MDearnAnalyst will then reflect on the earnings and trend indicators, and make a trading decision (BUY, HOLD, or SELL).  
        MDearnAnalyst are required to provide a 'decision' and a 'positionsize' at the same time as the report.
        
        The contents of the report must be structured like this: 
        "### Last trading days position:
        ### Last trading days positionsize:
        ### Today's Opening Price: gathered from gather_price funtion.

        ### Earnings: Have the earnings gone up or down in recent quarters and/or years. Based on the estimated in {treFolder}, are {ticker} in a good place financially?
        ### Insights: Does MDearnAnalyst think {ticker} is gonna go up or down in price based on the financial data present about {ticker}.

        ### Decision: MDearnAnalyst must provide a 'decision' that adheres to the 'DECISION RULES' (IMPORTANT).
        ### End-of-Day Position Size: MDearnAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES' (IMPORTANT).
        
        # Content for Database: this must include: 'Earnings:' (the corresponding output from MDearnAnalyst's report), 'Insights:' (the corresponding output from MDearnAnalyst's report) " 
        MDearnAnalyst is not allowed to copy last trading days content, it need to update each parameter.

        IMPORTANT: 'Content for Database' is the only parameter that MDearnAnalyst will sent to the database, using send_opinion.

        MDearnAnalyst will respond TERMINATE after the report is sent to the database using send_opinion.   

    STYLE: MDearnAnalyst is analytical and concise in its approach. MDearnAnalyst is creative and can draw the bigger picture from limited 
        data. MDearnAnalyst is talented at drawing predictions from historical numerical data about a company. MDearnAnalyst understands 
        that historical returns does not promise future returns. MDearnAnalyst has the ability to see patterns in data and uses it's LLM capabilities to
        make future predictions on timeseries data. 

        MDearnAnalyst will propose a decision based on this stock price prediction. If MDearnAnalyst thinks the price is gonna go up in the near 
        future, MDearnAnalyst wil propose to BUY, if MDearnAnalyst thinks the stock is going down based on the financial data, MDearnAnalyst will propose 
        to SELL. If MDearnAnalyst think the financial data suggest no future movements in stock price, MDearnAnalyst will propose HOLD.


    RULES: MDearnAnalyst is required to read through all information provided to it. MDearnAnalyst must follow each and every step outlined by the user_proxy prompt.  
        MDearnAnalyst is free to decide how many stocks it wants to buy, or maintain. 

        MDearnAnalyst is strickly forbidden from buying 100 shares, it needs to be another number. 

    DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
        ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDearnAnalyst. 
    
        ### 'position' is a boolean value
        ## If 'position'=True,  We have stock in {stock}.
        ## If 'position'=False,  We do not have stock in {stock}.

        ### If the previous trading days 'position'=True => then MDearnAnalyst are required to either HOLD, SELL or BUY.
        ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
        ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
        ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

        ### If the previous trading days 'position'=False => then MDearnAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
        
        ### MDearnAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDearnAnalyst wants to output
        SELL when 'position'=False => then MDearnAnalyst must output HOLD instead, as that means to do nothing.

        ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
        #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

        MDearnAnalyst is also required to look at the data from the get_summary function when making a decision, so that MDearnAnalyst adheres to the DECISION RULES above.
    """
)

MDkeyAnalyst = autogen.AssistantAgent(
    name="MDkeyAnalyst",
    llm_config=llm_config,
    system_message=f"""
    CHARACTERISTIC: You are MDkeyAnalyst, a skilled financial analyst.

    OBJECTIVE: Every step of the process will be outlined for MDkeyAnalyst by the user_proxy. Roughly explained, MDkeyAnalyst will first gather 
        information about the previous days position and summary using get_summary. The agent will then perform the gather_price function to get the 
        potential buying or selling price of the stock. MDkeyAnalyst will then use gather_csv to find the financial data to make a prediction about. 
        When calling get_summary, MDkeyAnalyst calls for all the folders in one prompt. 
         
        Then, MDkeyAnalyst will create a report on the financial information about {ticker}. The data is found using gather_csv, for the folders:
        {keyFolder}, and {finFolder}.Based on this information MDkeyAnalyst will construct a report on the financial outlooks of {ticker}. 
        MDkeyAnalyst will then reflect on the key statistics and financial analystic indicators, and make a trading decision (BUY, HOLD, or SELL).
        MDkeyAnalyst is required to provide a 'decision' and a 'positionsize' together with the report
        
        The contents of the report must be structured like this: 
        
        "### Last trading days position:
        ### Last trading days positionsize:
        ### Today's Opening Price: gathered from gather_price funtion.

        ### PriceInfo: from {keyFolder} find information about 'twoHundredDayAverage',  'fiftyDayAverage', and 'priceToBook'. 
        ### Finance: from {finFolder}, look at the total 'totalDebt', 'totalCash', 'totalRevenue', 'revenuePerShare', 'operatingCashflow' and 'earningsGrowth'
        ### Insights: Does MDkeyAnalyst think {ticker} is gonna go up or down in price based on the financial data present about {ticker}.

        ### Decision: MDkeyAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
        ### End-of-Day Position Size: MDkeyAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'
        
        # Content for Database: this must include: 'PriceInfo:': (the corresponding output from MDkeyAnalyst's report), 
        'Finance:' (the corresponding output from MDkeyAnalyst's report) 'Insights:' (the corresponding output from MDkeyAnalyst's report) "
        MDkeyAnalyst is not allowed to copy last trading days content, it need to update each parameter.
        
        IMPORTANT: 'Content for Database' is the only parameter that MDkeyAnalyst will sent to the database, using send_opinion.
        
        MDkeyAnalyst will respond TERMINATE after the report is sent to the database using send_opinion.   

    STYLE: MDkeyAnalyst is analytical and concise in its approach. MDkeyAnalyst is creative and can draw the bigger picture from limited 
        data. MDkeyAnalyst is talented at drawing predictions from historical numerical data about a company. MDkeyAnalyst understands 
        that historical returns does not promise future returns. MDkeyAnalyst has the ability to see patterns in data and uses it's LLM capabilities to
        make future predictions on timeseries data. 

        MDkeyAnalyst will propose a decision based on this stock price prediction. If MDkeyAnalyst thinks the price is gonna go up in the near 
        future, MDkeyAnalyst wil propose to BUY, if MDkeyAnalyst thinks the stock is going down based on the financial data, MDkeyAnalyst will propose 
        to SELL. If MDkeyAnalyst think the financial data suggest no future movements in stock price, MDkeyAnalyst will propose HOLD.


    RULES: MDkeyAnalyst is required to read through all information provided to it. MDkeyAnalyst must follow each and every step outlined by the user_proxy prompt.  
        MDkeyAnalyst is free to decide how many stocks it wants to buy, or maintain. 

        MDkeyAnalyst is strickly forbidden from buying 100 shares, it needs to be another number. 

    DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
        ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDkeyAnalyst. 
    
        ### 'position' is a boolean value
        ## If 'position'=True,  We have stock in {stock}.
        ## If 'position'=False,  We do not have stock in {stock}.

        ### If the previous trading days 'position'=True => then MDkeyAnalyst are required to either HOLD, SELL or BUY.
        ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
        ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
        ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

        ### If the previous trading days 'position'=False => then MDkeyAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
        ### MDkeyAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDkeyAnalyst wants to output
        SELL when 'position'=False => then MDkeyAnalyst must output HOLD instead, as that means to do nothing.
        ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
        #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

        MDkeyAnalyst is also required to look at the data from the get_summary function when making a decision, so that MDkeyAnalyst adheres to the DECISION RULES above.
"""
)

MDmanager = autogen.AssistantAgent(
    name="MDmanager",
    llm_config=llm_config,
    system_message=f"""
    CHARACTERISTIC: You are MDmanager, a professional data gatherer and summarizer.

    OBJECTIVE: The complete tasklist will be outlined by the user_proxy prompt. Roughly explained, MDmanager will first gather all the 6 agents 
    opinions. MDmanager will use the get_opinions function, inputting {todaysDate}, {ticker}, and {model}.
    The function will output: 'date', 'ticker', 'agent', 'model', 'content', 'decision', 'price', 'position', and 'positionsize' for all 6 agents. 
    MDmanager only calls get_opinions function 1 time, 1 function call is enough and will output the data necessary from all the agents. 
    MDmanager will then construct a report, consisting of:

    "###  MDfinAnalyst decision:
    ### MDfinAnalyst positionsize:
    ### MDfinAnalyst content:

    ### MDnewsAnalyst decision:
    ### MDnewsAnalyst positionsize:
    ### MDnewsAnalyst content:

    ### MDnrelAnalyst decision:
    ### MDnrelAnalyst positionsize:
    ### MDnrelAnalyst content:

    ### MDtserAnalyst decision:
    ### MDtserAnalyst positionsize:
    ### MDtserAnalyst content:

    ### MDearnAnalyst decision:
    ### MDearnAnalyst positionsize:
    ### MDearnAnalyst content:

    ### MDkeyAnalyst decision
    ### MDkeyAnalyst positionsize:
    ### MDkeyAnalyst content:

    ### Todays Decision: (todays decision will be the 'decision' that most agent picked (MAX COUNT OF THE 'DECISONS'). If there if a draw then the decision = HOLD)
    ## Agents With Todays Decision: Output the agents that picked the same 'decision that ended up being the final decision, list their 'positionsize'

    IMPORTANT: MDmanager must complete the report before continuing with the next steps.

    Only AFTER constructing the report, will MDmanager move on to the next stage. Which is:
    After the report is created, the user_proxy will prompt MDmanager to CONTINUE. MDmanager will then use calculate_average function to get the average 
    position of those that picked the winning and final decision. MDmanager will input the different 'positionsize' of exlusively the agents in '## Agents With Todays Decision' (from the report) as a string of numbers.
    If the final 'decision' is HOLD, then MDmanager is required to input all the 'positionsize' from the HOLD agents, this will output the same number as previous day 'positionsize'. 
    This will output a float, this outputted number will be the 'positionsize' that MDmanager sends to the database later
    

    After crafting the report and finding the average 'positionsize', then MDmanager will send the information, using the insert_summary, to the database. Information MDmanager needs: {todaysDate}, 
    {ticker}, {model}, {version}, 'content' (which will be each agents (MDfinAnalyst, MDnewsAnalyst, etc.) respective 'content' output (derived from the report), formatted like 'MDfinAnalyst:', 'MDnewsAnalyst:', 'MDnrelAnalyst:', etc. ), 
    'decision', 'price', 'position', and 'positionsize' (from calculate_average). 

    After MDmanager has sent the information to the database, using insert_summary, MDmanager will reply TERMINATE.
    MDmanager can only send todays decision 1 time using insert_summary, more than 1 calls is highly forbidden

    STYLE: MDmanager is a conscientious worker, always doing what is told. MDmanager will only input the agents opinions, and based on 
    pre-defined rules ('DECISION RULES'), collect and calculate the final outcomes, which will be sent to the database. MDmanager will move 
    data from one place, transforming the collective thoughts of 6 agents into 1 decision and 1 positionsize. The transformed data will then be sent 
    to the database. 


    RULES: MDmanager is required to read through all information provided to it. MDmanager must follow each and every step outlined by the user_proxy prompt.

    DECISION RULES: MDmanager will gather the opinions from all 6 agents, they will output wither BUY, SELL or HOLD.
    the majority will decide, if a decision gets 3 votes, while another gets 2 vote, and another gets 1 vote, the decision with 3 votes will win.
    They same applies if a decision gets 4 or 5 votes. 
    IF the decision ends in a tie, either 2x2x2 votes, or 3x3x0 votes => The decision will be HOLD (we do nothing).

    When picking 'positionsize', MDanalyst will gather all the positionsize from the agents that picked the final decision. 
    If the vote ends at a 3x2x1 split, MDanalyst will gather the 'positionsize' from the 3 agents picking the final decision.
    If outputted 'decision' = HOLD, then 'positionsize' is unchanged from previous trading day. IF we have initial positionsize=0 => then outputted positionsize=0.
    MDanalyst will then take the average from those 'positionsize's and input it into the database, using insert_summary.
     
     
"""    
)

user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=20,
    code_execution_config={},
    llm_config=llm_config,
    system_message= """You are the human admin that execute the function, and exclusively that. 
    Reply TERMINATE if the task has been solved at full satisfaction.
    Otherwise, Reply CONTINUE, or the reason why the task is not solved yet."""
)


#TASKS
finTask = f"""Perform the following task list, to arrive at a decision and end-of-day 'positionsize':

(1) Firstly, the agent will retieve the latest report from the SQL database. To get the report, use get_summary function, 
    insert {ticker}, {model}, {version}. This will output 'id', 'date', 'ticker', 'model', 'version', 'content', 'decision', 'position', and 'positionsize'. 
    'id', 'content', 'decision' 'position' and 'positionsize' is especially important for the further tasks. 
    MDfinAnalyst will then perform the gather_price function to get the potential buying/selling price of the stock, here only input the ticker: {ticker}.
    The position will be a boolean value, either we have a position in the stock or not (True if we have position, False if we have none).
    The decision from get_summary is the trading action the agents took yesterday.

    RULE: The 'position' will be a boolean value, if we have stock in the company 'position'=True, then 'positionsize' > 0 (above 0). 
        The 'positionsize' is the amount of stock we hold. If we dont have stock in the company 'position'=False, and 'positionsize' = 0. 

(2) Secondly, the agent will retrieve the financial and news data using the gather_csv function, insert {ticker} along with the accompanying
    folders: {hisFolder}, and {finFolder}. The agent will call all the folders in one prompt.
    Based on this information the agent will construct a report on the financial outlooks of {ticker}. 
    MDfinAnalyst will then reflect on the price fluctuations and the financial indicators of {ticker}, and make a trading decision (BUY, HOLD, or SELL). 
    MDfinAnalyst is required to reflect and provide a report on the findings before sending to the database using send_opinion function.
    MDfinAnalyst is required to provide a 'decision' and a 'positionsize' together with the report 

    "### Last trading days position:
    ### Last trading days positionsize:
    ### Today's Opening Price: gathered with gather_price funtion.

    ### robust company?: are {ticker} a robust company based on the information found in {finFolder}.
    ### Target: High, Low and Mean targets. Based on historical pricing, is it a good time to buy?
    ### Insights: Based on the data analysed, does MDfinAnalyst think {ticker} is going up or dow in the near future.
    ### BULL/BEAR: both 7 and 30 day assessment. (BULL if you think stock price is going up, BEAR if you think stock price is going down)

    ### Decision: MDfinAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
    ### End-of-Day Position Size: MDfinAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'
    
    # Content for Database: this must include: 'Insights:' (the corresponding output from MDfinAnalyst's report) "  
    
    MDfinAnalyst is not allowed to copy last trading days content, it need to update each parameter.

    IMPORTANT: 'Content for Database' is the only parameter that MDfinAnalyst will sent to the database, using send_opinion.

(3) Lastly, the agreed decision and 'positionsize' are required to be sent to the  database by the agent using the send_opinion function.
    the agent will use the send_opinion function to insert the content into the mddebate database (the agent is required to exlusively use 
    send_opinion fuction to send to the db). Information needed for send_opinion:  'key' which is 
    the same number as the id gathered from the get_summary function in step 1, {todaysDate}, {ticker}, 'agent' (MDfinAnalyst), {model}, {version},
    'content' which the agent gather from ### Content for Database, 'decision', 'price' (from gather_price), 'position', and 'positionsize'. 


    RULE: The agent is not allowed to copy last trading days content, it need to update each parameter.

(4) After the information is sent to the mddebate database, using send_opinion, reply with 'TERMINATE'

GENERAL RULES: the agent are required to follow the task list exactly how it is laid out above. 

DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
    ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDfinAnalyst. 

    ### 'position' is a boolean value
    ## If 'position'=True,  We have stock in {stock}.
    ## If 'position'=False,  We do not have stock in {stock}.

    ### If the previous trading days 'position'=True => then MDfinAnalyst are required to either HOLD, SELL or BUY.
    ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
    ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
    ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

    ### If the previous trading days 'position'=False => then MDfinAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
    ### MDfinAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDfinAnalyst wants to output
    SELL when 'position'=False => then MDfinAnalyst must output HOLD instead, as that means to do nothing.
    ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
    #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

    The agent is required to look at the data from the get_summary function when making a decision, so that the agent adheres to the DECISION RULES above.
"""

newsTask = f"""Perform the following task list, to arrive at a decision and end-of-day 'positionsize':

(1) Firstly, the agent will retieve the latest report from the SQL database. To get the report, use get_summary function, 
    insert {ticker}, {model}, {version}. This will output 'id', 'date', 'ticker', 'model', 'version', 'content', 'decision', 'position', and 'positionsize'. 
    'id', 'content', 'decision' 'position' and 'positionsize' is especially important for the further tasks. 
    The agent will then perform the gather_price function to get the potential buying/selling price of the stock, here only input the ticker: {ticker}.
    The position will be a boolean value, either we have a position in the stock or not (True if we have position, False if we have none).
    The 'decision' is the trading action we took yesterday.

    RULE: The 'position' will be a boolean value, if we have stock in the company 'position'=True, then 'positionsize' > 0 (above 0). 
        The 'positionsize' is the amount of stock we hold. If we dont have stock in the company 'position'=False, and 'positionsize' = 0. 

(2) Secondly, the agent will retrieve financial news data using the gather_csv function, insert {ticker} along with the accompanying
    folders: {newsFolder}, {treFolder},  and {esgFolder}. The agent will call all the folders in one prompt.
    Based on this information the agent will construct a report on the financial outlooks of {ticker}. 
    MDnewsAnalyst will then reflect on the sentiment of the financial news, and make a trading decision (BUY, HOLD, or SELL). 
    MDnewsAnalyst is required to provide a 'decision' and a 'positionsize' together with the report.

    RULE: The contents of the report must be structured like this: 
    "### Last trading days position:
    ### Last trading days positionsize:
    ### Today's Opening Price: gathered from gather_price funtion.
    
    ### ESG scores:
    ### Positive News: list 3, if MDnewsAnalyst can find it.
    ### Negative News:  list 3, if MDnewsAnalyst can find it.
    ### Noteworthy News: list 3, if MDnewsAnalyst can find it.

    ### Insights: Does MDnewsAnalyst think {ticker} is gonna go up or down in price based on the articles present about {ticker}.
    ### Decision: MDnewsAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
    ### End-of-Day Position Size: MDnewsAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'

    # Content for Database: this must include: 'Noteworthy News:' (the corresponding output from MDnewsAnalyst's report)  " 
    MDnewsAnalyst is not allowed to copy last trading days content, it need to update each parameter.

    IMPORTANT: 'Content for Database' is the only parameter that MDnewsAnalyst will sent to the database, using send_opinion.

(3) Lastly, the agreed decision and 'positionsize' are required to be sent to the  database by the agent using the send_opinion function.
    the agent will use the send_opinion function to insert the content into the mddebate database (the agent is required to exlusively use 
    send_opinion fuction to send to the db). Information needed for send_opinion:  'key' which is 
    the same number as the id gathered from the get_summary function in step 1, {todaysDate}, {ticker}, 'agent' (MDnewsAnalyst), {model}, {version},
    'content' which the agent gather from ### Content for Database, 'decision', 'price' (from gather_price), 'position', and 'positionsize'. 


    RULE: The agent is not allowed to copy last trading days content, it need to update each parameter.

(4) After the information is sent to the mddebate database, using send_opinion, reply with 'TERMINATE'

GENERAL RULES: the agent are required to follow the task list exactly how it is laid out above. 

DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
    ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDnewsAnalyst. 

    ### 'position' is a boolean value
    ## If 'position'=True,  We have stock in {stock}.
    ## If 'position'=False,  We do not have stock in {stock}.

    ### If the previous trading days 'position'=True => then MDnewsAnalyst are required to either HOLD, SELL or BUY.
    ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
    ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
    ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

    ### If the previous trading days 'position'=False => then MDnewsAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
    ### MDnewsAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDnewsAnalyst wants to output
    SELL when 'position'=False => then MDnewsAnalyst must output HOLD instead, as that means to do nothing.
    ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
    #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

    The agent is required to look at the data from the get_summary function when making a decision, so that the agent adheres to the DECISION RULES above.
"""

nrelTask = f"""Perform the following task list, to arrive at a decision and end-of-day 'positionsize':

(1) Firstly, the agent will retieve the latest report from the SQL database. To get the report, use get_summary function, 
    insert {ticker}, {model}, {version}. This will output 'id', 'date', 'ticker', 'model', 'version', 'content', 'decision', 'position', and 'positionsize'. 
    'id', 'content', 'decision' 'position' and 'positionsize' is especially important for the further tasks. 
    The agent will then perform the gather_price function to get the potential buying/selling price of the stock, here only input the ticker: {ticker}.
    The position will be a boolean value, either we have a position in the stock or not (True if we have position, False if we have none).
    The 'decision' is the trading action we took yesterday.

    RULE: The 'position' will be a boolean value, if we have stock in the company 'position'=True, then 'positionsize' > 0 (above 0). 
        The 'positionsize' is the amount of stock we hold. If we dont have stock in the company 'position'=False, and 'positionsize' = 0. 

(2) Secondly, the agent will retrieve news data and historical price data using the gather_csv function, insert {ticker} along with the accompanying
    folders: gather the news from {newsFolder}, and the corresponding prices in {hisFolder}. The agent will call all the folders in one prompt.
    Based on this information the agent will construct a report sentiment analysis for news in relationship to prices, for {ticker}.
    MDrnelAnalyst will then reflect on the news relationship with prices, and make a trading decision (BUY, HOLD, or SELL). 
    MDrnelAnalyst must conduct the analysis and provide a decision before sending to the database.
    MDnrelAnalyst is required to provide a 'decision' and a 'positionsize' together with the report.

    RULE: The contents of the report must be structured like this: 
    "### Last trading days position:
    ### Last trading days positionsize:
    ### Today's Opening Price: gathered from gather_price funtion.
    
    ### List of news: Here you need to include the 'open' price present at the publishing date. list 10 news articles with their corresponding 'open' price.
    ### Recent News: Say something about the short term future predicted price based on the 3 last articles. Will the price go
        up or down in the near future, based on the 3 last articles.

    ### Insights: Does MDrnelAnalyst think {ticker} is gonna go up or down in price based on the articles present about {ticker}.
    ### Decision: MDrnelAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
    ### End-of-Day Position Size: MDrnelAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'

    # Content for Database: this must include:  'Recent News:' (the corresponding output from MDnrelAnalyst's report), 'Insights:' (the corresponding output from MDnrelAnalyst's report) "
    MDnrelAnalyst is not allowed to copy last trading days content, it need to update each parameter.

    IMPORTANT: 'Content for Database' is the only parameter that MDnrelAnalyst will sent to the database, using send_opinion.

(3) Lastly, the agreed decision and 'positionsize' are required to be sent to the database by the agent using the send_opinion function.
    the agent will use the send_opinion function to insert the content into the mddebate database (the agent is required to exlusively use 
    send_opinion fuction to send to the db). Information needed for send_opinion:  'key' which is 
    the same number as the id gathered from the get_summary function in step 1, {todaysDate}, {ticker}, 'agent' (MDnrelAnalyst), {model}, {version},
    'content' which the agent gather from ### Content for Database, 'decision', 'price' (from gather_price), 'position', and 'positionsize'. 

    RULE: The agent is not allowed to copy last trading days content, it need to update each parameter.

(4) After the information is sent to the mddebate database, using send_opinion, reply with 'TERMINATE'

GENERAL RULES: the agent are required to follow the task list exactly how it is laid out above. 

DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
    ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDnrelAnalyst. 

    ### 'position' is a boolean value
    ## If 'position'=True,  We have stock in {stock}.
    ## If 'position'=False,  We do not have stock in {stock}.

    ### If the previous trading days 'position'=True => then MDnrelAnalyst are required to either HOLD, SELL or BUY.
    ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
    ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
    ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

    ### If the previous trading days 'position'=False => then MDnrelAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
    ### MDnrelAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDnrelAnalyst wants to output
    SELL when 'position'=False => then MDnrelAnalyst must output HOLD instead, as that means to do nothing.
    ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
    #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

    The agent is required to look at the data from the get_summary function when making a decision, so that the agent adheres to the DECISION RULES above.
"""

tserTask = f"""Perform the following task list, to arrive at a decision and end-of-day 'positionsize':

(1) MDtserAnalyst will first gather the time series data using the gather_timeseries function. MDtserAnalyst will input {ticker} into 
    gather_timeseries function, which will output a string of 10 numbers. Before doing any other funtion calls, 
    MDtserAnalyst are required to first write out the 10 numbers as a string of numbers, MDtserAnalyst will continue the sequence the 10 next numbers. 
    MDtserAnalyst is required to output 20 numbers in total, this is achieved by using the LLMs capabilties of pattern recognition.

(2) After this the user_proxy will ask MDtserAnalyst to provide an analysis on the already outputted numbers. MDtserAnalyst will then perform the 
    gather_price and get_summary functions to get the potential buying or selling price of the stock, and last trading days thoughts and actions.  
      
    MDtserAnalyst will create a report on predicted price of {ticker}. The data is provided through MDtserAnalyst, through it's prediction of
    next numbers in a timeseries. MDtserAnalyst are required to provide a 'decision' and a 'positionsize' that goes in line with the prediction outputted. 
    The contents of the report must be structured like this: 
    "### Last trading days position:
    ### Last trading days positionsize:
    ### Today's Opening Price: gathered from gather_price funtion.
    
    ### Last 10 datapoints: All points from the gather_timeseries function.
    ### Predicited 10 datapoints: MDtserAnalyst's 10 next predicted datapoints. 
        
    ### Decision: MDtserAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
    ### End-of-Day Position Size: MDtserAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'
    
    #Content for Database: this must include: '10 predicted datapoints:' (the corresponding output from MDtserAnalyst's prediction) " 
    
    MDtserAnalyst is not allowed to copy last trading days content, it need to update each parameter.

    IMPORTANT: 'Content for Database' is the only parameter that MDtserAnalyst will sent to the database, using send_opinion.

(3) Lastly, the agreed decision and 'positionsize' are required to be sent to the database by the agent using the send_opinion function.
    the agent will use the send_opinion function to insert the content into the mddebate database (the agent is required to exlusively use 
    send_opinion fuction to send to the db). Information needed for send_opinion:  'key' which is 
    the same number as the id gathered from the get_summary function in step 1, {todaysDate}, {ticker}, 'agent' (MDtserAnalyst), {model}, {version},
    'content' which the agent gather from ### Content for Database, 'decision', 'price' (from gather_price), 'position', and 'positionsize'. 

    RULE: The agent is not allowed to copy last trading days content, it need to update each parameter.

(4) After the information is sent to the mddebate database, using send_opinion, reply with 'TERMINATE'

GENERAL RULES: the agent are required to follow the task list exactly how it is laid out above. 

DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
    ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDtserAnalyst. 

    ### 'position' is a boolean value
    ## If 'position'=True,  We have stock in {stock}.
    ## If 'position'=False,  We do not have stock in {stock}.

    ### If the previous trading days 'position'=True => then MDtserAnalyst are required to either HOLD, SELL or BUY.
    ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
    ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
    ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

    ### If the previous trading days 'position'=False => then MDtserAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
    ### MDtserAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDtserAnalyst wants to output
    SELL when 'position'=False => then MDtserAnalyst must output HOLD instead, as that means to do nothing.
    ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
    #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

    The agent is required to look at the data from the get_summary function when making a decision, so that the agent adheres to the DECISION RULES above.

"""

earnTask = f"""Perform the following task list, to arrive at a decision and end-of-day 'positionsize':

(1) Firstly, the agent will retieve the latest report from the SQL database. To get the report, use get_summary function, 
    insert {ticker}, {model}, {version}. This will output 'id', 'date', 'ticker', 'model', 'version', 'content', 'decision', 'position', and 'positionsize'. 
    'id', 'content', 'decision' 'position' and 'positionsize' is especially important for the further tasks. 
    The agent will then perform the gather_price function to get the potential buying/selling price of the stock, here only input the ticker: {ticker}.
    The position will be a boolean value, either we have a position in the stock or not (True if we have position, False if we have none).
    The 'decision' is the trading action we took yesterday.

    RULE: The 'position' will be a boolean value, if we have stock in the company 'position'=True, then 'positionsize' > 0 (above 0). 
        The 'positionsize' is the amount of stock we hold. If we dont have stock in the company 'position'=False, and 'positionsize' = 0. 

(2) Secondly, the agent will retrieve the financial and news data using the gather_csv function, insert {ticker} along with the accompanying
    folders: {treFolder}, and {earFolder}. The agent will call all the folders in one prompt.
    Based on this information the agent will construct a report on the financial outlooks of {ticker}. 
    MDearnAnalyst will then reflect on the earnings and trend indicators, and make a trading decision (BUY, HOLD, or SELL). 
    MDearnAnalyst are required to provide a 'decision' and a 'positionsize' at the same time as the report.

    RULE: The contents of the report must be structured like this: 
    "### Last trading days position:
    ### Last trading days positionsize:
    ### Today's Opening Price: gathered from gather_price funtion.

    ### Earnings: Have the earnings gone up or down in recent quarters and/or years. Based on the estimated in {treFolder}, are {ticker} in a good place financially?
    ### Insights: Does MDearnAnalyst think {ticker} is gonna go up or down in price based on the financial data present about {ticker}.

    ### Decision: MDearnAnalyst must provide a 'decision' that adheres to the 'DECISION RULES' (IMPORTANT).
    ### End-of-Day Position Size: MDearnAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES' (IMPORTANT).
    
    # Content for Database: this must include: 'Earnings:' (the corresponding output from MDearnAnalyst's report), 'Insights:' (the corresponding output from MDearnAnalyst's report)  ""  
    
    MDearnAnalyst is not allowed to copy last trading days content, it need to update each parameter.

   IMPORTANT: 'Content for Database' is the only parameter that MDearnAnalyst will sent to the database, using send_opinion.

(3) Lastly, the agreed decision and 'positionsize' are required to be sent to the  database by the agent using the send_opinion function.
    the agent will use the send_opinion function to insert the content into the mddebate database (the agent is required to exlusively use 
    send_opinion fuction to send to the db). Information needed for send_opinion:  'key' which is 
    the same number as the id gathered from the get_summary function in step 1, {todaysDate}, {ticker}, 'agent' (MDearnAnalyst), {model}, {version},
    'content' which the agent gather from ### Content for Database, 'decision', 'price' (from gather_price), 'position', and 'positionsize'. 


    RULE: The agent is not allowed to copy last trading days content, it need to update each parameter.

(4) After the information is sent to the mddebate database, using send_opinion, reply with 'TERMINATE'

GENERAL RULES: the agent are required to follow the task list exactly how it is laid out above. 

DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
    ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDearnAnalyst. 

    ### 'position' is a boolean value
    ## If 'position'=True,  We have stock in {stock}.
    ## If 'position'=False,  We do not have stock in {stock}.

    ### If the previous trading days 'position'=True => then MDearnAnalyst are required to either HOLD, SELL or BUY.
    ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
    ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
    ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

    ### If the previous trading days 'position'=False => then MDearnAnalyst are required to either BUY or HOLD (HOLD means to do nothing).

    ### MDearnAnalyst are restricted from outputting SELL when 'position'=False (when we have no stock). If MDearnAnalyst wants to output
    SELL when 'position'=False => then MDearnAnalyst must output HOLD instead, as that means to do nothing.

    ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
    #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

    The agent is required to look at the data from the get_summary function when making a decision, so that the agent adheres to the DECISION RULES above.

"""

keyTask = f"""Perform the following task list, to arrive at a decision and end-of-day 'positionsize':

(1) Firstly, the agent will retieve the latest report from the SQL database. To get the report, use get_summary function, 
    insert {ticker}, {model}, {version}. This will output 'id', 'date', 'ticker', 'model', 'version', 'content', 'decision', 'position', and 'positionsize'. 
    'id', 'content', 'decision' 'position' and 'positionsize' is especially important for the further tasks. 
    The agent will then perform the gather_price function to get the potential buying/selling price of the stock, here only input the ticker: {ticker}.
    The position will be a boolean value, either we have a position in the stock or not (True if we have position, False if we have none).
    The 'decision' is the trading action we took yesterday.

    RULE: The 'position' will be a boolean value, if we have stock in the company 'position'=True, then 'positionsize' > 0 (above 0). 
        The 'positionsize' is the amount of stock we hold. If we dont have stock in the company 'position'=False, and 'positionsize' = 0. 

(2) Secondly, the agent will retrieve the financial and news data using the gather_csv function, insert {ticker} along with the accompanying
    folders: {keyFolder}, and {finFolder}. The agent will call all the folders in one prompt.
    Based on this information the agent will construct a report on the financial outlooks of {ticker}. 
    MDkeyAnalyst will then reflect on the key statistics and financial analystic indicators, and make a trading decision (BUY, HOLD, or SELL). 
    MDkeyAnalyst is required to provide a 'decision' and a 'positionsize' together with the report.

    RULE: The contents of the report must be structured like this: 
    "### Last trading days position:
    ### Last trading days positionsize:
    ### Today's Opening Price: gathered from gather_price funtion.

    ### PriceInfo: from {keyFolder} find information about 'twoHundredDayAverage',  'fiftyDayAverage', and 'priceToBook'. 
    ### Finance: from {finFolder}, look at the total 'totalDebt', 'totalCash', 'totalRevenue', 'revenuePerShare', 'operatingCashflow' and 'earningsGrowth'
    ### Insights: Does MDkeyAnalyst think {ticker} is gonna go up or down in price based on the financial data present about {ticker}.

    ### Decision: MDkeyAnalyst must provide a 'decision' that adheres to the 'DECISION RULES'
    ### End-of-Day Position Size: MDkeyAnalyst must provide a 'positionsize' that adheres to the 'DECISION RULES'
    
    # Content for Database: this must include: 'PriceInfo:': (the corresponding output from MDkeyAnalyst's report), 
    'Finance:' (the corresponding output from MDkeyAnalyst's report) 'Insights:' (the corresponding output from MDkeyAnalyst's report) "
    
    MDkeyAnalyst is not allowed to copy last trading days content, it need to update each parameter.

   IMPORTANT: 'Content for Database' is the only parameter that MDkeyAnalyst will sent to the database, using send_opinion.

(3) Lastly, the agreed decision and 'positionsize' are required to be sent to the  database by the agent using the send_opinion function.
    the agent will use the send_opinion function to insert the content into the mddebate database (the agent is required to exlusively use 
    send_opinion fuction to send to the db). Information needed for send_opinion:  'key' which is 
    the same number as the id gathered from the get_summary function in step 1, {todaysDate}, {ticker}, 'agent' (MDkeyAnalyst), {model}, {version},
    'content' which the agent gather from ### Content for Database, 'decision', 'price' (from gather_price), 'position', and 'positionsize'. 


    RULE: The agent is not allowed to copy last trading days content, it need to update each parameter.

(4) After the information is sent to the mddebate database, using send_opinion, reply with 'TERMINATE'

GENERAL RULES: the agent are required to follow the task list exactly how it is laid out above. 

DECISION RULES: ### 'positionsize' is the amount of stock we hold at the end of the day.
    ## outputted 'positionsize' will be the previous days 'positionsize' minus/plus the bought or sold amount by MDkeyAnalyst. 

    ### 'position' is a boolean value
    ## If 'position'=True,  We have stock in {stock}.
    ## If 'position'=False,  We do not have stock in {stock}.

    ### If the previous trading days 'position'=True => then MDkeyAnalyst are required to either HOLD, SELL or BUY.
    ## If 'decision' is BUY while 'position'=True => then previous trading days 'positionsize' + bought (BUY) shares amount = new 'positionsize'.
    ## If 'decision' is SELL while 'position'=True => then previous trading days 'positionsize' - sold (SELL) shares amount = new 'positionsize'.
    ## If 'decision' is HOLD while 'position'=True => then keep 'positionsize' and 'position' unchanged.

    ### If the previous trading days 'position'=False => then MDkeyAnalyst are required to either BUY or HOLD (HOLD means to do nothing).
    ### MDkeyAnalyst are highly restricted from outputting SELL when 'position'=False (when we have no stock). If MDkeyAnalyst wants to output
    SELL when 'position'=False => then MDkeyAnalyst must output HOLD instead, as that means to do nothing. 
    ##If 'decision' is BUY while 'position'=False => then todays 'position'=True & 'positionsize'>0 (send_opinion).
    #If 'decision' is HOLD while 'position'=False => then todays 'position'=False & 'positionsize'= 0 (send_opinion).

    The agent is required to look at the data from the get_summary function when making a decision, so that the agent adheres to the DECISION RULES above.

"""

sumTask = f"""Perform the following task list:

(1) MDmanager will first use the get_opinions function to get todays agents opinions. MDmanager will input {todaysDate}, {ticker}, and {model},
the funtion will output 6 observations of data, 1 for each agent that takes part in the debate. The function will output: 'date', 'ticker', 'agent', 'model',
'content', 'decision', 'price', 'position', and 'positionsize'. MDmanager only calls get_opinions function 1 time, 1 function call
is enough and will output the data necessary from all the agents.

MDmanager will then use this information to form today's decison. MDmanager will create a report on the opinions of the agents. The report must 
be structured like this:

"###  MDfinAnalyst decision:
### MDfinAnalyst positionsize:
### MDfinAnalyst content:

### MDnewsAnalyst decision:
### MDnewsAnalyst positionsize:
### MDnewsAnalyst content:

### MDnrelAnalyst decision:
### MDnrelAnalyst positionsize:
### MDnrelAnalyst content:

### MDtserAnalyst decision:
### MDtserAnalyst positionsize:
### MDtserAnalyst content:

### MDearnAnalyst decision:
### MDearnAnalyst positionsize:
### MDearnAnalyst content:

### MDkeyAnalyst decision
### MDkeyAnalyst positionsize:
### MDkeyAnalyst content:

### Todays Decision: (todays decision will be the 'decision' that most agent picked (MAX COUNT OF THE 'DECISONS'). If there if a draw then the decision = HOLD)
## Agents With Todays Decision: Output the agents that picked the same 'decision that ended up being the final decision, list their 'positionsize'

IMPORTANT: complete the report before continuing to step (2).


(2) Only AFTER constructing the report, will MDmanager move on to the next stage. Which is:
    After the report is created, the user_proxy will prompt MDmanager to CONTINUE. MDmanager will then use calculate_average function to get the average 
    position of those that picked the winning and final decision. MDmanager will input the different 'positionsize' of exlusively the agents in '## Agents With Todays Decision' (from the report) as a string of numbers.
    If the final 'decision' is HOLD, then MDmanager is required to input all the 'positionsize' from the HOLD agents, this will output the same number as previous day 'positionsize'. 
    This will output a float, this outputted number will be the 'positionsize' that MDmanager sends to the database later
    

(3) After crafting the report and finding the average 'positionsize', then MDmanager will send the information, using the insert_summary, to the database. Information MDmanager needs: {todaysDate}, 
{ticker}, {model}, {version}, 'content' (which will be each agents (MDfinAnalyst, MDnewsAnalyst, etc.) respective 'content' output (derived from the report), formatted like 'MDfinAnalyst:', 'MDnewsAnalyst:', 'MDnrelAnalyst:', etc. ), 
'decision', 'price', 'position', and 'positionsize' (from calculate_average). 

After MDmanager has sent the information to the database, using insert_summary, MDmanager will reply TERMINATE.
MDmanager can only send todays decision 1 time using insert_summary, more than 1 calls is highly forbidden


DECISION RULES: MDmanager will gather the opinions from all 6 agents, they will output wither BUY, SELL or HOLD.
    the majority will decide, if a decision gets 3 votes, while another gets 2 vote, and another gets 1 vote, the decision with 3 votes will win.
    They same applies if a decision gets 4 or 5 votes. 
    IF the decision ends in a tie, either 2x2x2 votes, or 3x3x0 votes => The decision will be HOLD (we do nothing).

    When picking 'positionsize', MDanalyst will gather all the positionsize from the agents that picked the final decision. 
    If the vote ends at a 3x2x1 split, MDanalyst will gather the 'positionsize' from the 3 agents picking the final decision.
    If outputted 'decision' = HOLD, then 'positionsize' is unchanged from previous trading day. IF we have initial positionsize=0 => then outputted positionsize=0.
    MDanalyst will then take the average from those 'positionsize's and input it into the database, using insert_summary.
"""


#FUNTION MAP

#-----------------------------------------------------------------------
#gather_csv
autogen.agentchat.register_function(
    gather_csv,
    caller=MDfinAnalyst,
    executor=user_proxy,
    description= f"Gathers data from the different folders, the folders are {hisFolder}, {earFolder}, {esgFolder}, {finFolder}, {treFolder}, {keyFolder}, {newsFolder}",
)

autogen.agentchat.register_function(
    gather_csv,
    caller=MDnewsAnalyst,
    executor=user_proxy,
    description= f"Gathers data from the different folders, the folders are {hisFolder}, {earFolder}, {esgFolder}, {finFolder}, {treFolder}, {keyFolder}, {newsFolder}",
)

autogen.agentchat.register_function(
    gather_csv,
    caller=MDnrelAnalyst,
    executor=user_proxy,
    description= f"Gathers data from the different folders, the folders are {hisFolder}, {earFolder}, {esgFolder}, {finFolder}, {treFolder}, {keyFolder}, {newsFolder}",
)

autogen.agentchat.register_function(
    gather_csv,
    caller=MDearnAnalyst,
    executor=user_proxy,
    description= f"Gathers data from the different folders, the folders are {hisFolder}, {earFolder}, {esgFolder}, {finFolder}, {treFolder}, {keyFolder}, {newsFolder}",
)

autogen.agentchat.register_function(
    gather_csv,
    caller=MDkeyAnalyst,
    executor=user_proxy,
    description= f"Gathers data from the different folders, the folders are {hisFolder}, {earFolder}, {esgFolder}, {finFolder}, {treFolder}, {keyFolder}, {newsFolder}",
)


#-----------------------------------------------------------------------
#gather_price
autogen.agentchat.register_function(
    gather_price,
    caller=MDfinAnalyst,
    executor=user_proxy,
    description= f"Gathers the latest price for {ticker}",
)

autogen.agentchat.register_function(
    gather_price,
    caller=MDnewsAnalyst,
    executor=user_proxy,
    description= f"Gathers the latest price for {ticker}",
)

autogen.agentchat.register_function(
    gather_price,
    caller=MDnrelAnalyst,
    executor=user_proxy,
    description= f"Gathers the latest price for {ticker}",
)

autogen.agentchat.register_function(
    gather_price,
    caller=MDtserAnalyst,
    executor=user_proxy,
    description= f"Gathers the latest price for {ticker}",
)

autogen.agentchat.register_function(
    gather_price,
    caller=MDearnAnalyst,
    executor=user_proxy,
    description= f"Gathers the latest price for {ticker}",
)

autogen.agentchat.register_function(
    gather_price,
    caller=MDkeyAnalyst,
    executor=user_proxy,
    description= f"Gathers the latest price for {ticker}",
)


#-----------------------------------------------------------------------
#get_summary
autogen.agentchat.register_function(
    get_summary,
    caller=MDfinAnalyst,
    executor=user_proxy,
    description= f"Use this funtion to get the latest report from the database, input {ticker}, {model} and {version}. This will return a dictonary, with id, date, ticker, model, version, content, position, and positionSize",
)

autogen.agentchat.register_function(
    get_summary,
    caller=MDnewsAnalyst,
    executor=user_proxy,
    description= f"Use this funtion to get the latest report from the database, input {ticker}, {model} and {version}. This will return a dictonary, with id, date, ticker, model, version, content, position, and positionSize",
)

autogen.agentchat.register_function(
    get_summary,
    caller=MDnrelAnalyst,
    executor=user_proxy,
    description= f"Use this funtion to get the latest report from the database, input {ticker}, {model} and {version}. This will return a dictonary, with id, date, ticker, model, version, content, position, and positionSize",
)

autogen.agentchat.register_function(
    get_summary,
    caller=MDtserAnalyst,
    executor=user_proxy,
    description= f"Use this funtion to get the latest report from the database, input {ticker}, {model} and {version}. This will return a dictonary, with id, date, ticker, model, version, content, position, and positionSize",
)

autogen.agentchat.register_function(
    get_summary,
    caller=MDearnAnalyst,
    executor=user_proxy,
    description= f"Use this funtion to get the latest report from the database, input {ticker}, {model} and {version}. This will return a dictonary, with id, date, ticker, model, version, content, position, and positionSize",
)

autogen.agentchat.register_function(
    get_summary,
    caller=MDkeyAnalyst,
    executor=user_proxy,
    description= f"Use this funtion to get the latest report from the database, input {ticker}, {model} and {version}. This will return a dictonary, with id, date, ticker, model, version, content, position, and positionSize",
)


#-----------------------------------------------------------------------
#send_opinion
autogen.agentchat.register_function(
    send_opinion,
    caller=MDfinAnalyst,
    executor=user_proxy,
    description= f"Use this fuction to send your opinion to the mddebate postgres database ",
)

autogen.agentchat.register_function(
    send_opinion,
    caller=MDnewsAnalyst,
    executor=user_proxy,
    description= f"Use this fuction to send your opinion to the mddebate postgres database ",
)

autogen.agentchat.register_function(
    send_opinion,
    caller=MDnrelAnalyst,
    executor=user_proxy,
    description= f"Use this fuction to send your opinion to the mddebate postgres database ",
)

autogen.agentchat.register_function(
    send_opinion,
    caller=MDtserAnalyst,
    executor=user_proxy,
    description= f"Use this fuction to send your opinion to the mddebate postgres database ",
)

autogen.agentchat.register_function(
    send_opinion,
    caller=MDearnAnalyst,
    executor=user_proxy,
    description= f"Use this fuction to send your opinion to the mddebate postgres database ",
)

autogen.agentchat.register_function(
    send_opinion,
    caller=MDkeyAnalyst,
    executor=user_proxy,
    description= f"Use this fuction to send your opinion to the mddebate postgres database ",
)


#---------------------------------------------------------------------
#gather_timeseries
autogen.agentchat.register_function(
    gather_timeseries,
    caller=MDtserAnalyst,
    executor=user_proxy,
    description= f"Gather the openining price for {ticker} as timer series data.",
)


#---------------------------------------------------------------------
#get_opinions
autogen.agentchat.register_function(
    get_opinions,
    caller=MDmanager,
    executor=user_proxy,
    description= f"Gather the opinions about {ticker} for all 6 agents",
)

#---------------------------------------------------------------------
#insert_summary
autogen.agentchat.register_function(
    insert_summary,
    caller=MDmanager,
    executor=user_proxy,
    description= f"Use this fuction to send your report to the postgres database",
)


#---------------------------------------------------------------------
#calculate_average
autogen.agentchat.register_function(
    calculate_average,
    caller=MDmanager,
    executor=user_proxy,
    description= f"Use this fuction to input numbers and recieve the average number",
)



#INITIALIZE SEQUENCE OF CHATS
chat_results = user_proxy.initiate_chats(  
    [
        {   
            "chat_id": 1,
            "recipient": MDfinAnalyst,
            "message": finTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        {   
            "chat_id": 2,
            "recipient": MDnewsAnalyst,
            "message": newsTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        {   
            "chat_id": 3,
            "recipient": MDnrelAnalyst,
            "message": nrelTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        {   
            "chat_id": 4,
            "recipient": MDtserAnalyst,
            "message": tserTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        {   
            "chat_id": 5,
            "recipient": MDearnAnalyst,
            "message": earnTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        {   
            "chat_id": 6,
            "recipient": MDkeyAnalyst,
            "message": keyTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        {   
            "chat_id": 7,
            "recipient": MDmanager,
            "message": sumTask,
            "clear_history": True,
            "summary_method": "last_msg"
        },
        
    ]
)

# Define the directory for chat history
chat_history_dir = "Chat History"
if not os.path.exists(chat_history_dir):
    os.makedirs(chat_history_dir)

# Construct the filename
filename = f"{todaysDate}_{ticker}_{model}_{version}.txt"
filepath = os.path.join(chat_history_dir, filename)

# Write the chat history to the file
with open(filepath, 'w') as f:
    for i, chat_res in enumerate(chat_results):
        f.write(f"*****{i}th chat*******:\n")
        f.write(str(chat_res.chat_history) + "\n")
        f.write("Conversation cost: " + str(chat_res.cost) + "\n\n")